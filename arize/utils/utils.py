# type: ignore[pb2]
import base64
import json
import math
import sys
from typing import Any, Optional, Union

import pandas as pd
from arize.utils.constants import (
    MAX_FUTURE_YEARS_FROM_CURRENT_TIME,
    MAX_PAST_YEARS_FROM_CURRENT_TIME,
)
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.wrappers_pb2 import StringValue

from .. import public_pb2 as pb2
from .constants import MAX_BYTES_PER_BULK_RECORD
from .types import Embedding, Schema


def num_chunks(records):
    total_bytes = sum(r.ByteSize() for r in records)
    num_of_bulk = math.ceil(total_bytes / MAX_BYTES_PER_BULK_RECORD)
    return math.ceil(len(records) / num_of_bulk)


def bundle_records(records) -> {}:
    recs_per_msg = num_chunks(records)
    recs = {
        (i, i + recs_per_msg): records[i : i + recs_per_msg]
        for i in range(0, len(records), recs_per_msg)
    }
    return recs


def get_bulk_records(space_key: str, model_id: str, model_version: Optional[str], records):
    for k, r in records.items():
        records[k] = pb2.BulkRecord(
            records=r,
            space_key=space_key,
            model_id=model_id,
            model_version=model_version,
        )
    return records


def convert_element(value):
    """converts scalar or array to python native"""
    val = getattr(value, "tolist", lambda: value)()
    # Check if it's a list since elements from pd indices are converted to a scalar
    # whereas pd series/dataframe elements are converted to list of 1 with the native value
    if isinstance(val, list):
        val = val[0] if val else None
    if pd.isna(val):
        return None
    return val


def convert_dictionary(d):
    # Takes a dictionary and
    # - casts the keys as strings
    # - turns the values of the dictionary to our proto values pb2.Value()
    converted_dict = {}
    for k, v in d.items():
        val = get_value_object(value=v, name=k)
        if val is not None:
            converted_dict[str(k)] = val
    return converted_dict


def get_value_object(name: Union[str, int, float], value):
    if isinstance(value, pb2.Value):
        return value
    # The following `convert_element` done in single log validation
    # of features & tags. It is not done in bulk_log
    val = convert_element(value)
    if val is None:
        return None
    if isinstance(val, (str, bool)):
        return pb2.Value(string=str(val))
    if isinstance(val, int):
        return pb2.Value(int=val)
    if isinstance(val, float):
        return pb2.Value(double=val)
    if isinstance(val, Embedding):
        return pb2.Value(embedding=get_value_embedding(val))
    else:
        raise TypeError(
            f'dimension "{name}" = {value} is type {type(value)}, but must be one of: bool, str, '
            f"float, int, embedding"
        )


def get_value_embedding(val: Embedding) -> pb2.Embedding:
    if Embedding._is_valid_iterable(val.data):
        return pb2.Embedding(
            vector=val.vector,
            raw_data=pb2.Embedding.RawData(tokenArray=pb2.Embedding.TokenArray(tokens=val.data)),
            link_to_data=StringValue(value=val.link_to_data),
        )
    elif isinstance(val.data, str):
        return pb2.Embedding(
            vector=val.vector,
            raw_data=pb2.Embedding.RawData(
                tokenArray=pb2.Embedding.TokenArray(tokens=[val.data])
                # Convert to list of 1 string
            ),
            link_to_data=StringValue(value=val.link_to_data),
        )
    elif val.data is None:
        return pb2.Embedding(
            vector=val.vector,
            link_to_data=StringValue(value=val.link_to_data),
        )

    return None


def get_timestamp(time_overwrite):
    if time_overwrite is None:
        return None
    time = convert_element(time_overwrite)
    if not isinstance(time_overwrite, int):
        raise TypeError(
            f"time_overwrite {time_overwrite} is type {type(time_overwrite)}, but expects int. ("
            f"Unix epoch "
            f"time in seconds) "
        )
    ts = Timestamp()
    ts.FromSeconds(time)
    return ts


def is_timestamp_in_range(now: int, ts: int):
    max_time = now + (MAX_FUTURE_YEARS_FROM_CURRENT_TIME * 365 * 24 * 60 * 60)
    min_time = now - (MAX_PAST_YEARS_FROM_CURRENT_TIME * 365 * 24 * 60 * 60)
    return min_time <= ts <= max_time


def reconstruct_url(response: Any):
    returnedUrl = json.loads(response.content.decode())["realTimeIngestionUri"]
    parts = returnedUrl.split("/")
    encodedOrg = base64.b64encode(f"AccountOrganization:{parts[4]}".encode()).decode()
    encodedSpace = base64.b64encode(f"Space:{parts[6]}".encode()).decode()
    reconstructed = (
        f"https://{parts[2]}/organizations/{encodedOrg}/spaces/"
        f"{encodedSpace}/models/modelName/{parts[-1]}"
    )
    return reconstructed


def get_python_version():
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def overwrite_schema_fields(schema1: Schema, schema2: Schema) -> Schema:
    """This function overwrites a base Schema `schema1` with the fields of `schema2`
    that are not None

    Arguments:
    ----------
        schema1 (Schema): Base Schema with fields to be overwritten
        schema2 (Schema): New Schema used to overwrite schema1

    Returns:
    --------
        Schema: The resulting schema
    """
    schema_dict_fields = (
        "embedding_feature_column_names",
        "shap_values_column_names",
        "prompt_column_names",
        "response_column_names",
    )
    changes = {
        k: v for k, v in schema2.asdict().items() if v is not None and k not in schema_dict_fields
    }
    schema = schema1.replace(**changes)

    # Embedding column names need to be treated separately for being in a dictionary
    if schema2.embedding_feature_column_names is not None:
        emb_feat_col_names = schema1.embedding_feature_column_names
        if emb_feat_col_names is None:
            emb_feat_col_names = {}
        for k, v in schema2.embedding_feature_column_names.items():
            emb_feat_col_names[k] = v
        # replace embedding column names in schema
        schema = schema.replace(embedding_feature_column_names=emb_feat_col_names)

    # Prompt and response need to be treated separately
    if schema2.prompt_column_names is not None:
        schema = schema.replace(prompt_column_names=schema2.prompt_column_names)
    if schema2.response_column_names is not None:
        schema = schema.replace(response_column_names=schema2.response_column_names)

    # Shap values column names need to be treated separately for being in a dictionary
    if schema2.shap_values_column_names is not None:
        shap_val_col_names = schema1.shap_values_column_names
        if shap_val_col_names is None:
            shap_val_col_names = {}
        for k, v in schema2.shap_values_column_names.items():
            shap_val_col_names[k] = v
        # replace embedding column names in schema
        schema = schema.replace(shap_values_column_names=shap_val_col_names)

    return schema


def is_delayed_schema(schema: Schema) -> bool:
    """
    This function checks if the given schema, according to the columns provided by the user,
    has inherently latent information
    Args:
        schema (Schema): The schema to analyze

    Returns:
        bool: True if the schema is "delayed", i.e., does not possess prediction columns and has actual or
        feature importance columns.
    """
    return (
        schema.has_actual_columns() or schema.has_feature_importance_columns()
    ) and not schema.has_prediction_columns()
