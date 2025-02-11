import time
from pathlib import Path

import arize.public_pb2 as pb2
import numpy as np
import pandas as pd
import pytest
import os
from arize import __version__ as arize_version
from arize.api import Client, Embedding
from arize.pandas.validation.errors import InvalidAdditionalHeaders
from arize.utils.constants import (
    MAX_FUTURE_YEARS_FROM_CURRENT_TIME,
    MAX_PAST_YEARS_FROM_CURRENT_TIME,
    MAX_PREDICTION_ID_LEN,
    MAX_TAG_LENGTH,
    MIN_PREDICTION_ID_LEN,
    SPACE_KEY_ENVVAR_NAME,
    API_KEY_ENVVAR_NAME,
)
from arize.utils.types import (
    Environments,
    ModelTypes,
    ObjectDetectionLabel,
    RankingActualLabel,
    RankingPredictionLabel,
)
from arize.utils.utils import get_python_version
from google.protobuf.wrappers_pb2 import BoolValue, DoubleValue, StringValue

BOOL_VAL = True
STR_VAL = "arize"
INT_VAL = 5
FLOAT_VAL = 20.20
NP_FLOAT = float(1.2)
file_to_open = Path(__file__).parent / "fixtures/mpg.csv"

inputs = {
    "model_id": "model_v0",
    "model_version": "v1.2.3.4",
    "batch_id": "batch_id",
    "batch": "batch1234",
    "api_key": "API_KEY",
    "prediction_id": "prediction_0",
    "label_bool": BOOL_VAL,
    "label_str": STR_VAL,
    "label_int": INT_VAL,
    "label_float": FLOAT_VAL,
    "label_tuple": (STR_VAL, FLOAT_VAL),
    "object_detection_bounding_boxes": [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]],
    "object_detection_categories": ["dog", "cat"],
    "object_detection_scores": [0.8, 0.4],
    "ranking_group_id": "a",
    "ranking_rank": 1,
    "ranking_prediction_score": 1.0,
    "ranking_label": "click",
    "ranking_relevance_labels": ["click", "save"],
    "ranking_relevance_score": 0.5,
    "space_key": "test_space",
    "features": {
        "feature_str": STR_VAL,
        "feature_double": FLOAT_VAL,
        "feature_int": INT_VAL,
        "feature_bool": BOOL_VAL,
        "feature_None": None,
    },
    "object_detection_embedding_feature": {
        "image_embedding": Embedding(
            vector=np.array([1.0, 2, 3]),
            link_to_data="https://my-bucket.s3.us-west-2.amazonaws.com/puppy.png",
        ),
    },
    "embedding_features": {
        "image_embedding": Embedding(
            vector=np.array([1.0, 2, 3]),
            link_to_data="https://my-bucket.s3.us-west-2.amazonaws.com/puppy.png",
        ),
        "nlp_embedding_sentence": Embedding(
            vector=pd.Series([4.0, 5.0, 6.0, 7.0]),
            data="This is a test sentence",
        ),
        "nlp_embedding_tokens": Embedding(
            vector=pd.Series([4.0, 5.0, 6.0, 7.0]),
            data=["This", "is", "a", "test", "sentence"],
        ),
    },
    "tags": {
        "tag_str": STR_VAL,
        "tag_double": FLOAT_VAL,
        "tag_int": INT_VAL,
        "tag_bool": BOOL_VAL,
        "tag_None": None,
    },
    "feature_importances": {
        "feature_str": FLOAT_VAL,
        "feature_double": FLOAT_VAL,
        "feature_int": INT_VAL,
        "feature_bool": BOOL_VAL,
        "feature_numpy_float": NP_FLOAT,
    },
    "prompt": Embedding(
        vector=pd.Series([4.0, 5.0, 6.0, 7.0]),
        data="This is a test prompt",
    ),
    "response": Embedding(
        vector=pd.Series([4.0, 5.0, 6.0, 7.0]),
        data="This is a test response",
    ),
}


def _build_expected_record(
    ep: pb2.Record.EnvironmentParams = None,
    p: pb2.PredictionLabel = None,
    a: pb2.ActualLabel = None,
    fi: pb2.FeatureImportances = None,
    is_generative_llm_record: BoolValue = BoolValue(value=False),
) -> pb2.Record:
    return pb2.Record(
        space_key=inputs["space_key"],
        model_id=inputs["model_id"],
        prediction_id=str(inputs["prediction_id"]),
        prediction=p,
        actual=a,
        feature_importances=fi,
        environment_params=ep,
        is_generative_llm_record=is_generative_llm_record,
    )


def _get_proto_environment_params(
    env: Environments,
) -> pb2.Record.EnvironmentParams:
    env_params = None
    if env == Environments.TRAINING:
        env_params = pb2.Record.EnvironmentParams(training=pb2.Record.EnvironmentParams.Training())
    elif env == Environments.VALIDATION:
        env_params = pb2.Record.EnvironmentParams(
            validation=pb2.Record.EnvironmentParams.Validation(batch_id=inputs["batch_id"])
        )
    elif env == Environments.PRODUCTION:
        env_params = pb2.Record.EnvironmentParams(
            production=pb2.Record.EnvironmentParams.Production()
        )
    return env_params


def _build_basic_prediction(type: str) -> pb2.Prediction:
    if type == "numeric_int":
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(numeric=inputs["label_int"]),
            model_version=inputs["model_version"],
        )
    elif type == "numeric_float":
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(numeric=inputs["label_float"]),
            model_version=inputs["model_version"],
        )
    elif type == "score_categorical_bool" or type == "generative_bool":
        sc = pb2.ScoreCategorical()
        sc.category.category = str(inputs["label_bool"])
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(score_categorical=sc),
            model_version=inputs["model_version"],
        )
    elif type == "score_categorical_str" or type == "generative_str":
        sc = pb2.ScoreCategorical()
        sc.category.category = inputs["label_str"]
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(score_categorical=sc),
            model_version=inputs["model_version"],
        )
    elif type == "score_categorical_int" or type == "generative_int":
        sc = pb2.ScoreCategorical()
        sc.score_value.value = inputs["label_int"]
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(score_categorical=sc),
            model_version=inputs["model_version"],
        )
    elif type == "score_categorical_float" or type == "generative_float":
        sc = pb2.ScoreCategorical()
        sc.score_value.value = inputs["label_float"]
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(score_categorical=sc),
            model_version=inputs["model_version"],
        )
    elif type == "score_categorical_tuple":
        sc = pb2.ScoreCategorical()
        sc.score_category.category = inputs["label_str"]
        sc.score_category.score = inputs["label_float"]
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(score_categorical=sc),
            model_version=inputs["model_version"],
        )
    elif type == "object_detection":
        od = pb2.ObjectDetection()
        bounding_boxes = []
        for i in range(len(inputs["object_detection_bounding_boxes"])):
            coordinates = inputs["object_detection_bounding_boxes"][i]
            category = inputs["object_detection_categories"][i]
            score = inputs["object_detection_scores"][i]
            bounding_boxes.append(
                pb2.ObjectDetection.BoundingBox(
                    coordinates=coordinates, category=category, score=DoubleValue(value=score)
                )
            )
        od.bounding_boxes.extend(bounding_boxes)
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(object_detection=od),
            model_version=inputs["model_version"],
        )
    elif type == "ranking":
        rp = pb2.RankingPrediction()
        rp.rank = inputs["ranking_rank"]
        rp.prediction_group_id = inputs["ranking_group_id"]
        rp.prediction_score.value = inputs["ranking_prediction_score"]
        rp.label = inputs["ranking_label"]
        return pb2.Prediction(
            prediction_label=pb2.PredictionLabel(ranking=rp),
            model_version=inputs["model_version"],
        )
    else:
        return pb2.Prediction()


def _build_basic_actual(type: str) -> pb2.Actual:
    if type == "numeric_int":
        return pb2.Actual(
            actual_label=pb2.ActualLabel(numeric=inputs["label_int"]),
        )
    elif type == "numeric_float":
        return pb2.Actual(
            actual_label=pb2.ActualLabel(numeric=inputs["label_float"]),
        )
    elif type == "score_categorical_bool" or type == "generative_bool":
        sc = pb2.ScoreCategorical()
        sc.category.category = str(inputs["label_bool"])
        return pb2.Actual(
            actual_label=pb2.ActualLabel(score_categorical=sc),
        )
    elif type == "score_categorical_str" or type == "generative_str":
        sc = pb2.ScoreCategorical()
        sc.category.category = inputs["label_str"]
        return pb2.Actual(
            actual_label=pb2.ActualLabel(score_categorical=sc),
        )
    elif type == "score_categorical_int" or type == "generative_int":
        sc = pb2.ScoreCategorical()
        sc.score_value.value = inputs["label_int"]
        return pb2.Actual(
            actual_label=pb2.ActualLabel(score_categorical=sc),
        )
    elif type == "score_categorical_float" or type == "generative_float":
        sc = pb2.ScoreCategorical()
        sc.score_value.value = inputs["label_float"]
        return pb2.Actual(
            actual_label=pb2.ActualLabel(score_categorical=sc),
        )
    elif type == "score_categorical_tuple":
        sc = pb2.ScoreCategorical()
        sc.score_category.category = inputs["label_str"]
        sc.score_category.score = inputs["label_float"]
        return pb2.Actual(
            actual_label=pb2.ActualLabel(score_categorical=sc),
        )
    elif type == "object_detection":
        od = pb2.ObjectDetection()
        bounding_boxes = []
        for i in range(len(inputs["object_detection_bounding_boxes"])):
            coordinates = inputs["object_detection_bounding_boxes"][i]
            category = inputs["object_detection_categories"][i]
            bounding_boxes.append(
                pb2.ObjectDetection.BoundingBox(coordinates=coordinates, category=category)
            )
        od.bounding_boxes.extend(bounding_boxes)
        return pb2.Actual(
            actual_label=pb2.ActualLabel(object_detection=od),
        )
    elif type == "ranking":
        ra = pb2.RankingActual()
        ra.category.values.extend(inputs["ranking_relevance_labels"])
        ra.relevance_score.value = inputs["ranking_relevance_score"]
        return pb2.Actual(
            actual_label=pb2.ActualLabel(ranking=ra),
        )
    else:
        return pb2.Actual()


def _attach_features_to_prediction() -> pb2.Prediction:
    features = {
        "feature_str": pb2.Value(string=STR_VAL),
        "feature_double": pb2.Value(double=FLOAT_VAL),
        "feature_int": pb2.Value(int=INT_VAL),
        "feature_bool": pb2.Value(string=str(BOOL_VAL)),
    }
    return pb2.Prediction(features=features)


def _attach_image_embedding_feature_to_prediction() -> pb2.Prediction:
    input_embeddings = inputs["embedding_features"]
    embedding_features = {
        "image_embedding": pb2.Value(
            embedding=pb2.Embedding(
                vector=input_embeddings["image_embedding"].vector,
                link_to_data=StringValue(value=input_embeddings["image_embedding"].link_to_data),
            )
        ),
    }
    return pb2.Prediction(features=embedding_features)


def _attach_embedding_features_to_prediction() -> pb2.Prediction:
    input_embeddings = inputs["embedding_features"]
    embedding_features = {
        "image_embedding": pb2.Value(
            embedding=pb2.Embedding(
                vector=input_embeddings["image_embedding"].vector,
                link_to_data=StringValue(value=input_embeddings["image_embedding"].link_to_data),
            )
        ),
        "nlp_embedding_sentence": pb2.Value(
            embedding=pb2.Embedding(
                vector=input_embeddings["nlp_embedding_sentence"].vector,
                raw_data=pb2.Embedding.RawData(
                    tokenArray=pb2.Embedding.TokenArray(
                        tokens=[
                            input_embeddings["nlp_embedding_sentence"].data
                        ],  # List of a single string
                    )
                ),
                link_to_data=StringValue(
                    value=input_embeddings["nlp_embedding_sentence"].link_to_data
                ),
            )
        ),
        "nlp_embedding_tokens": pb2.Value(
            embedding=pb2.Embedding(
                vector=input_embeddings["nlp_embedding_tokens"].vector,
                raw_data=pb2.Embedding.RawData(
                    tokenArray=pb2.Embedding.TokenArray(
                        tokens=input_embeddings["nlp_embedding_tokens"].data
                    )
                ),
                link_to_data=StringValue(
                    value=input_embeddings["nlp_embedding_tokens"].link_to_data
                ),
            )
        ),
    }
    return pb2.Prediction(features=embedding_features)


def _attach_prompt_and_response_to_prediction() -> pb2.Prediction:
    input_prompt = inputs["prompt"]
    input_response = inputs["response"]
    embedding_features = {
        "prompt": pb2.Value(
            embedding=pb2.Embedding(
                vector=input_prompt.vector,
                raw_data=pb2.Embedding.RawData(
                    tokenArray=pb2.Embedding.TokenArray(
                        tokens=[input_prompt.data],  # List of a single string
                    )
                ),
                link_to_data=StringValue(value=input_prompt.link_to_data),
            )
        ),
        "response": pb2.Value(
            embedding=pb2.Embedding(
                vector=input_response.vector,
                raw_data=pb2.Embedding.RawData(
                    tokenArray=pb2.Embedding.TokenArray(
                        tokens=[input_response.data],  # List of a single string
                    )
                ),
                link_to_data=StringValue(value=input_response.link_to_data),
            )
        ),
    }
    return pb2.Prediction(features=embedding_features)


def _attach_tags_to_prediction() -> pb2.Prediction:
    tags = {
        "tag_str": pb2.Value(string=STR_VAL),
        "tag_double": pb2.Value(double=FLOAT_VAL),
        "tag_int": pb2.Value(int=INT_VAL),
        "tag_bool": pb2.Value(string=str(BOOL_VAL)),
    }
    return pb2.Prediction(tags=tags)


def _attach_tags_to_actual() -> pb2.Actual:
    tags = {
        "tag_str": pb2.Value(string=STR_VAL),
        "tag_double": pb2.Value(double=FLOAT_VAL),
        "tag_int": pb2.Value(int=INT_VAL),
        "tag_bool": pb2.Value(string=str(BOOL_VAL)),
    }
    return pb2.Actual(tags=tags)


def get_stubbed_client(additional_headers=None):
    c = Client(
        space_key=inputs["space_key"],
        api_key=inputs["api_key"],
        uri="https://localhost:443",
        additional_headers=additional_headers,
    )

    def _post(record, uri, indexes):
        return record

    c._post = _post
    return c


# TODO for each existing test that has been modified to call Client.log, add a call
# to the pre-existing method that should map to the identical call to Client.log to
# assert that they are equivalent


def test_build_pred_and_actual_label_bool():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.SCORE_CATEGORICAL,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_bool"],
        actual_label=inputs["label_bool"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("score_categorical_bool")
    a = _build_basic_actual("score_categorical_bool")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_embedding_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to prediction according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, a=a, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_build_pred_and_actual_label_str():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.SCORE_CATEGORICAL,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_str"],
        actual_label=inputs["label_str"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("score_categorical_str")
    a = _build_basic_actual("score_categorical_str")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_embedding_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to prediction according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, a=a, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_build_pred_and_actual_label_int():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_int"],
        actual_label=inputs["label_int"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    record_new_model_type = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.REGRESSION,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_int"],
        actual_label=inputs["label_int"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_int")
    a = _build_basic_actual("numeric_int")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_embedding_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to prediction according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, a=a, ep=ep)
    #   Check result is as expected
    assert record == record_new_model_type == expected_record


def test_build_pred_and_actual_label_float():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
        actual_label=inputs["label_float"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    record_new_model_type = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.REGRESSION,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
        actual_label=inputs["label_float"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_float")
    a = _build_basic_actual("numeric_float")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_embedding_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to prediction according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, a=a, ep=ep)
    #   Check result is as expected
    assert record == record_new_model_type == expected_record


def test_build_pred_and_actual_label_tuple():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.SCORE_CATEGORICAL,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_tuple"],
        actual_label=inputs["label_tuple"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    record_new_model_type = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.BINARY_CLASSIFICATION,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_tuple"],
        actual_label=inputs["label_tuple"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("score_categorical_tuple")
    a = _build_basic_actual("score_categorical_tuple")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_embedding_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to prediction according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, a=a, ep=ep)
    #   Check result is as expected
    assert record == record_new_model_type == expected_record


def test_build_pred_and_actual_label_ranking():
    pred_label = RankingPredictionLabel(
        group_id=inputs["ranking_group_id"],
        rank=inputs["ranking_rank"],
        score=inputs["ranking_prediction_score"],
        label=inputs["ranking_label"],
    )
    act_label = RankingActualLabel(
        relevance_labels=inputs["ranking_relevance_labels"],
        relevance_score=inputs["ranking_relevance_score"],
    )
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.RANKING,
        prediction_id=inputs["prediction_id"],
        prediction_label=pred_label,
        actual_label=act_label,
        features=inputs["features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("ranking")
    a = _build_basic_actual("ranking")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to prediction according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, a=a, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_build_wrong_timestamp():
    c = get_stubbed_client()
    wrong_min_time = int(time.time()) - (MAX_PAST_YEARS_FROM_CURRENT_TIME * 365 * 24 * 60 * 60 + 1)
    wrong_max_time = int(time.time()) + (
        MAX_FUTURE_YEARS_FROM_CURRENT_TIME * 365 * 24 * 60 * 60 + 1
    )

    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            prediction_timestamp=wrong_min_time,
            model_type=ModelTypes.NUMERIC,
            prediction_id=inputs["prediction_id"],
            prediction_label=inputs["label_float"],
            features=inputs["features"],
            tags=inputs["tags"],
        )
    assert f"prediction_timestamp: {wrong_min_time} is out of range." in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            prediction_timestamp=wrong_max_time,
            model_type=ModelTypes.NUMERIC,
            prediction_id=inputs["prediction_id"],
            prediction_label=inputs["label_float"],
            features=inputs["features"],
            tags=inputs["tags"],
        )
    assert f"prediction_timestamp: {wrong_max_time} is out of range." in str(excinfo.value)


def test_ranking_label_missing_group_id_rank():
    with pytest.raises(TypeError) as excinfo:
        _ = RankingPredictionLabel(
            group_id=inputs["ranking_group_id"],
            score=inputs["ranking_prediction_score"],
            label=inputs["ranking_label"],
        )
    assert "missing 1 required positional argument: 'rank'" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        _ = RankingPredictionLabel(
            rank=inputs["ranking_rank"],
            score=inputs["ranking_prediction_score"],
            label=inputs["ranking_label"],
        )
    assert "missing 1 required positional argument: 'group_id'" in str(excinfo.value)


def test_build_wrong_ranking_rank():
    c = get_stubbed_client()
    pred_label = RankingPredictionLabel(
        group_id=inputs["ranking_group_id"],
        rank=101,
        score=inputs["ranking_prediction_score"],
        label=inputs["ranking_label"],
    )
    act_label = RankingActualLabel(
        relevance_labels=inputs["ranking_relevance_labels"],
        relevance_score=inputs["ranking_relevance_score"],
    )

    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.RANKING,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            actual_label=act_label,
            features=inputs["features"],
            tags=inputs["tags"],
        )
    assert "Rank must be between 1 and 100, inclusive. Found 101" in str(excinfo.value)


def test_ranking_group_id():
    c = get_stubbed_client()
    pred_label = RankingPredictionLabel(
        group_id=1,
        rank=inputs["ranking_rank"],
        score=inputs["ranking_prediction_score"],
        label=inputs["ranking_label"],
    )
    act_label = RankingActualLabel(
        relevance_labels=inputs["ranking_relevance_labels"],
        relevance_score=inputs["ranking_relevance_score"],
    )

    with pytest.raises(TypeError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.RANKING,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            actual_label=act_label,
            features=inputs["features"],
            tags=inputs["tags"],
        )
    assert "Prediction Group ID must be a string" in str(excinfo.value)

    pred_label = RankingPredictionLabel(
        group_id="aaabbbcccdddeeefffggghhhiiijjjkkklllmmmnnn",
        rank=inputs["ranking_rank"],
        score=inputs["ranking_prediction_score"],
        label=inputs["ranking_label"],
    )

    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.RANKING,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            actual_label=act_label,
            features=inputs["features"],
            tags=inputs["tags"],
        )
    assert "Prediction Group ID must have length between 1 and 36. Found 42" in str(excinfo.value)


def test_build_wrong_ranking_relevance_labels():
    c = get_stubbed_client()
    pred_label = RankingPredictionLabel(
        group_id=inputs["ranking_group_id"],
        rank=inputs["ranking_rank"],
        score=inputs["ranking_prediction_score"],
        label=inputs["ranking_label"],
    )
    act_label = RankingActualLabel(
        relevance_labels=["click", ""], relevance_score=inputs["ranking_relevance_score"]
    )

    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.RANKING,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            actual_label=act_label,
            features=inputs["features"],
            tags=inputs["tags"],
        )
    assert "Relevance Labels must be not contain empty strings" in str(excinfo.value)


def test_build_wrong_ranking_relevance_scores():
    c = get_stubbed_client()
    pred_label = RankingPredictionLabel(
        group_id=inputs["ranking_group_id"],
        rank=inputs["ranking_rank"],
        score=inputs["ranking_prediction_score"],
        label=inputs["ranking_label"],
    )
    act_label = RankingActualLabel(
        relevance_labels=inputs["ranking_relevance_labels"], relevance_score="click"
    )

    with pytest.raises(TypeError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.RANKING,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            actual_label=act_label,
            features=inputs["features"],
            tags=inputs["tags"],
        )
    assert "Relevance score must be a float or an int" in str(excinfo.value)


def test_build_pred_and_actual_label_object_detection():
    pred_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=inputs["object_detection_bounding_boxes"],
        categories=inputs["object_detection_categories"],
        scores=inputs["object_detection_scores"],
    )
    act_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=inputs["object_detection_bounding_boxes"],
        categories=inputs["object_detection_categories"],
    )
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.OBJECT_DETECTION,
        prediction_id=inputs["prediction_id"],
        prediction_label=pred_label,
        actual_label=act_label,
        features=inputs["features"],
        embedding_features=inputs["object_detection_embedding_feature"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("object_detection")
    a = _build_basic_actual("object_detection")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_image_embedding_feature_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to prediction according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, a=a, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_build_prediction_no_embedding_features():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
        features=inputs["features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_float")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, ep=ep)
    #   Check result is as expected
    assert record == expected_record


# Structured features refer to any feature that is not an embedding
def test_build_prediction_no_structured_features():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_float")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_embedding_features_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_build_prediction_no_features():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
        tags=inputs["tags"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_float")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_tags_to_prediction())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_build_prediction_no_tags():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_float")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_embedding_features_to_prediction())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_build_prediction_no_tags_no_features():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_float")
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_missing_model_type():
    c = get_stubbed_client()
    with pytest.raises(TypeError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=inputs["label_str"],
            actual_label=inputs["label_str"],
            features=inputs["features"],
            embedding_features=inputs["embedding_features"],
            tags=inputs["tags"],
        )
    assert "log() missing 1 required positional argument: 'model_type'" in str(excinfo.value)


def test_model_version_optional():
    c = get_stubbed_client()
    record = c.log(
        model_id=inputs["model_id"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.NUMERIC,
        prediction_id=inputs["prediction_id"],
        prediction_label=inputs["label_float"],
    )

    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    p = _build_basic_prediction("numeric_float")
    p.model_version = ""
    #   Build expected record using built prediction
    expected_record = _build_expected_record(p=p, ep=ep)
    #   Check result is as expected
    assert record == expected_record


def test_missing_environment():
    c = get_stubbed_client()
    with pytest.raises(TypeError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            model_type=ModelTypes.NUMERIC,
            prediction_id=inputs["prediction_id"],
            prediction_label=inputs["label_str"],
            actual_label=inputs["label_str"],
            features=inputs["features"],
            embedding_features=inputs["embedding_features"],
            tags=inputs["tags"],
        )
    assert "log() missing 1 required positional argument: 'environment'" in str(excinfo.value)


def test_object_detection_item_count_match():
    c = get_stubbed_client()
    extra = [0.11, 0.12, 0.13, 0.14]

    pred_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=inputs["object_detection_bounding_boxes"] + [extra],
        categories=inputs["object_detection_categories"],
        scores=inputs["object_detection_scores"],
    )
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.OBJECT_DETECTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            features=inputs["features"],
            embedding_features=inputs["object_detection_embedding_feature"],
            tags=inputs["tags"],
        )
    assert (
        "Object Detection Labels must contain the same number of bounding boxes and "
        "categories. Found 3 bounding boxes and 2 categories." in str(excinfo.value)
    )


def test_object_detection_wrong_coordinates_format():
    c = get_stubbed_client()

    pred_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7]],
        categories=inputs["object_detection_categories"],
        scores=inputs["object_detection_scores"],
    )
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.OBJECT_DETECTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            features=inputs["features"],
            embedding_features=inputs["object_detection_embedding_feature"],
            tags=inputs["tags"],
        )
    assert "Each bounding box's coordinates must be a collection of 4 floats." in str(excinfo.value)

    pred_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=[[-0.1, 0.2, 0.3, 0.4], [1.5, 0.6, 0.7, 0.8]],
        categories=inputs["object_detection_categories"],
        scores=inputs["object_detection_scores"],
    )
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.OBJECT_DETECTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            features=inputs["features"],
            embedding_features=inputs["object_detection_embedding_feature"],
            tags=inputs["tags"],
        )
    assert "Bounding box's coordinates cannot be negative. Found [-0.1, 0.2, 0.3, 0.4]" in str(
        excinfo.value
    )


def test_valid_prediction_id_embeddings():
    c = get_stubbed_client()

    # test case - too long prediction_id
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_type=ModelTypes.BINARY_CLASSIFICATION,
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            prediction_id="A" * 129,
            prediction_label=inputs["label_str"],
            actual_label=inputs["label_str"],
            features=inputs["features"],
            embedding_features=inputs["embedding_features"],
            tags=inputs["tags"],
        )
    assert "The string length of prediction_id" in str(excinfo.value)


def test_prediction_id():
    c = get_stubbed_client()

    correct_cases = [
        {
            # test case - None prediction_id, Training
            "prediction_id": None,
            "environment": Environments.TRAINING,
            "prediction_label": inputs["label_str"],
        },
        {
            # test case - None prediction_id, Production, not a delayed record
            "prediction_id": None,
            "environment": Environments.PRODUCTION,
            "prediction_label": inputs["label_str"],
        },
    ]
    for case in correct_cases:
        try:
            _ = c.log(
                model_id=inputs["model_id"],
                model_type=ModelTypes.BINARY_CLASSIFICATION,
                model_version=inputs["model_version"],
                environment=case["environment"],
                prediction_id=case["prediction_id"],
                prediction_label=case["prediction_label"],
                actual_label=inputs["label_str"],
                features=inputs["features"],
                embedding_features=inputs["embedding_features"],
                tags=inputs["tags"],
            )
        except Exception as e:
            msg = (
                f"Logging data without prediction_id raised an exception {e}. "
                + f"prediction_id={case['prediction_id']}, environment={case['environment']}, "
                + f"prediction_label={case['prediction_label']}."
            )
            assert False, msg

    short_prediction_id = "x" * (MIN_PREDICTION_ID_LEN - 1)
    long_prediction_id = "x" * (MAX_PREDICTION_ID_LEN + 1)
    incorrect_cases = [
        {
            # test case - None prediction_id, Production, delayed record
            "prediction_id": None,
            "environment": Environments.PRODUCTION,
            "prediction_label": None,
            "err_msg": "prediction_id value cannot be None for delayed records",
        },
        {
            # test case - Wrong length prediction_id, Training
            "prediction_id": short_prediction_id,
            "environment": Environments.TRAINING,
            "prediction_label": inputs["label_str"],
            "err_msg": f"The string length of prediction_id {short_prediction_id} must be between",
        },
        {
            # test case - Wrong length prediction_id, Production, delayed record
            "prediction_id": short_prediction_id,
            "environment": Environments.PRODUCTION,
            "prediction_label": None,
            "err_msg": f"The string length of prediction_id {short_prediction_id} must be between",
        },
        {
            # test case - Wrong length prediction_id, Production, not a delayed record
            "prediction_id": long_prediction_id,
            "environment": Environments.PRODUCTION,
            "prediction_label": inputs["label_str"],
            "err_msg": f"The string length of prediction_id {long_prediction_id} must be between",
        },
    ]
    for case in incorrect_cases:
        with pytest.raises(ValueError) as exc_info:
            _ = c.log(
                model_id=inputs["model_id"],
                model_type=ModelTypes.BINARY_CLASSIFICATION,
                model_version=inputs["model_version"],
                environment=case["environment"],
                prediction_id=case["prediction_id"],
                prediction_label=case["prediction_label"],
                actual_label=inputs["label_str"],
                features=inputs["features"],
                embedding_features=inputs["embedding_features"],
                tags=inputs["tags"],
            )
        assert case["err_msg"] in str(exc_info.value)


def test_object_detection_wrong_categories():
    c = get_stubbed_client()

    pred_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=inputs["object_detection_bounding_boxes"],
        categories=["dog", None],
        scores=inputs["object_detection_scores"],
    )
    with pytest.raises(TypeError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.OBJECT_DETECTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            features=inputs["features"],
            embedding_features=inputs["object_detection_embedding_feature"],
            tags=inputs["tags"],
        )
    assert "Object Detection Label categories must be a list of strings" in str(excinfo.value)


def test_object_detection_wrong_scores():
    c = get_stubbed_client()

    pred_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=inputs["object_detection_bounding_boxes"],
        categories=inputs["object_detection_categories"],
        scores=[-0.4],
    )
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.OBJECT_DETECTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            features=inputs["features"],
            embedding_features=inputs["object_detection_embedding_feature"],
            tags=inputs["tags"],
        )
    assert "Bounding box confidence scores must be between 0 and 1, inclusive" in str(excinfo.value)

    pred_label = ObjectDetectionLabel(
        bounding_boxes_coordinates=inputs["object_detection_bounding_boxes"],
        categories=inputs["object_detection_categories"],
        scores=[1.2],
    )
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.OBJECT_DETECTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=pred_label,
            features=inputs["features"],
            embedding_features=inputs["object_detection_embedding_feature"],
            tags=inputs["tags"],
        )
    assert "Bounding box confidence scores must be between 0 and 1, inclusive" in str(excinfo.value)


def test_valid_label_type_generative_model():
    c = get_stubbed_client()
    # Test allowed label types
    for label_type in ["str", "bool", "int", "float"]:
        prediction_label = inputs[f"label_{label_type}"]
        actual_label = prediction_label
        record = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.GENERATIVE_LLM,
            prediction_id=inputs["prediction_id"],
            prediction_label=prediction_label,
            actual_label=actual_label,
            features=inputs["features"],
            embedding_features=inputs["embedding_features"],
            tags=inputs["tags"],
            prompt=inputs["prompt"],
            response=inputs["response"],
        )
        #   Get environment in proto format
        ep = _get_proto_environment_params(Environments.PRODUCTION)
        #   Start constructing expected result by building the prediction
        p = _build_basic_prediction(f"generative_{label_type}")
        a = _build_basic_actual(f"generative_{label_type}")
        #   Add props to prediction according to this test
        p.MergeFrom(_attach_features_to_prediction())
        p.MergeFrom(_attach_embedding_features_to_prediction())
        p.MergeFrom(_attach_prompt_and_response_to_prediction())
        p.MergeFrom(_attach_tags_to_prediction())
        #   Add props to actual according to this test
        a.MergeFrom(_attach_tags_to_actual())
        #   Build expected record using built prediction
        expected_record = _build_expected_record(
            p=p, a=a, ep=ep, is_generative_llm_record=BoolValue(value=True)
        )
        #   Check result is as expected
        assert record == expected_record


def test_default_prediction_label_generative_model():
    c = get_stubbed_client()
    # Test allowed label types
    record = c.log(
        model_id=inputs["model_id"],
        model_version=inputs["model_version"],
        environment=Environments.PRODUCTION,
        model_type=ModelTypes.GENERATIVE_LLM,
        prediction_id=inputs["prediction_id"],
        actual_label=inputs["label_int"],
        features=inputs["features"],
        embedding_features=inputs["embedding_features"],
        tags=inputs["tags"],
        prompt=inputs["prompt"],
        response=inputs["response"],
    )
    #   Get environment in proto format
    ep = _get_proto_environment_params(Environments.PRODUCTION)
    #   Start constructing expected result by building the prediction
    # This prediction was not passed to the log call, but should be
    # created by default for GENERATIVE models
    sc = pb2.ScoreCategorical()
    sc.score_value.value = 1
    p = pb2.Prediction(
        prediction_label=pb2.PredictionLabel(score_categorical=sc),
        model_version=inputs["model_version"],
    )
    a = _build_basic_actual("generative_int")
    #   Add props to prediction according to this test
    p.MergeFrom(_attach_features_to_prediction())
    p.MergeFrom(_attach_embedding_features_to_prediction())
    p.MergeFrom(_attach_prompt_and_response_to_prediction())
    p.MergeFrom(_attach_tags_to_prediction())
    #   Add props to actual according to this test
    a.MergeFrom(_attach_tags_to_actual())
    #   Build expected record using built prediction
    expected_record = _build_expected_record(
        p=p, a=a, ep=ep, is_generative_llm_record=BoolValue(value=True)
    )
    #   Check result is as expected
    assert record == expected_record


def test_invalid_generative_model():
    c = get_stubbed_client()

    # Test that GENERATIVE_LLM models must contain prompt and response. Missing prompt
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.GENERATIVE_LLM,
            prediction_id=inputs["prediction_id"],
            prediction_label=1,
            features=inputs["features"],
            tags=inputs["tags"],
            prompt=inputs["prompt"],
        )
    assert "The following fields cannot be None for GENERATIVE_LLM models: prompt, response" in str(
        excinfo.value
    )
    # Test that GENERATIVE_LLM models must contain prompt and response. Missing response
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.GENERATIVE_LLM,
            prediction_id=inputs["prediction_id"],
            prediction_label=1,
            features=inputs["features"],
            tags=inputs["tags"],
            response=inputs["response"],
        )
    assert "The following fields cannot be None for GENERATIVE_LLM models: prompt, response" in str(
        excinfo.value
    )
    # Test that GENERATIVE_LLM models cannot contain embedding named prompt or response
    with pytest.raises(KeyError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.GENERATIVE_LLM,
            prediction_id=inputs["prediction_id"],
            prediction_label=1,
            features=inputs["features"],
            tags=inputs["tags"],
            embedding_features={"prompt": inputs["prompt"]},
            prompt=inputs["prompt"],
            response=inputs["response"],
        )
    assert (
        "embedding features cannot use the reserved feature names ('prompt', 'response') "
        "for GENERATIVE_LLM models" in str(excinfo.value)
    )
    # Test that prompt and repsonse must be Embedding type for GENERATIVE_LLM models
    with pytest.raises(TypeError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.GENERATIVE_LLM,
            prediction_id=inputs["prediction_id"],
            prediction_label=1,
            features=inputs["features"],
            tags=inputs["tags"],
            prompt=2,
            response=inputs["response"],
        )
    assert "Both prompt and response objects must be of type Embedding" in str(excinfo.value)


def test_invalid_prompt_response_for_model_type():
    c = get_stubbed_client()

    # Test that 'prompt' must be None for models other than GENERATIVE_LLM
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.SCORE_CATEGORICAL,
            prediction_id=inputs["prediction_id"],
            prediction_label=1,
            features=inputs["features"],
            tags=inputs["tags"],
            prompt=inputs["prompt"],
        )
    assert (
        "The fields 'prompt' and 'response' must be None for model types other than GENERATIVE_LLM"
        in str(excinfo.value)
    )
    # Test that 'response' must be None for models other than GENERATIVE_LLM
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            model_type=ModelTypes.SCORE_CATEGORICAL,
            prediction_id=inputs["prediction_id"],
            prediction_label=1,
            features=inputs["features"],
            tags=inputs["tags"],
            response=inputs["response"],
        )
    assert (
        "The fields 'prompt' and 'response' must be None for model types other than GENERATIVE_LLM"
        in str(excinfo.value)
    )


def test_invalid_tags():
    c = get_stubbed_client()
    wrong_tags = {
        "tag_str_incorrect": "a" * (MAX_TAG_LENGTH + 1),
    }

    # test case - too long tag value
    with pytest.raises(ValueError) as excinfo:
        _ = c.log(
            model_id=inputs["model_id"],
            model_type=ModelTypes.BINARY_CLASSIFICATION,
            model_version=inputs["model_version"],
            environment=Environments.PRODUCTION,
            prediction_id=inputs["prediction_id"],
            prediction_label=inputs["label_str"],
            actual_label=inputs["label_str"],
            features=inputs["features"],
            tags=wrong_tags,
        )
    assert (
        f"The number of characters for each tag must be less than or equal to {MAX_TAG_LENGTH}."
        in str(excinfo.value)
    )


def test_instantiating_client_duplicated_header():
    with pytest.raises(InvalidAdditionalHeaders) as excinfo:
        _ = get_stubbed_client({"authorization": "FAKE_VALUE"})
    assert (
        "Found invalid additional header, cannot use reserved headers named: authorization."
        in str(excinfo.value)
    )


def test_instantiating_client_additional_header():
    c = get_stubbed_client({"JWT": "FAKE_VALUE"})

    expected = {
        "authorization": inputs["api_key"],
        "Grpc-Metadata-space": inputs["space_key"],
        "Grpc-Metadata-sdk-language": "python",
        "Grpc-Metadata-language-version": get_python_version(),
        "Grpc-Metadata-sdk-version": arize_version,
        "JWT": "FAKE_VALUE",
    }
    assert c._headers == expected

def test_client_throws_if_missing_auth():
    with pytest.raises(ValueError, match="space_key must be supplied"):
        c = Client()
    with pytest.raises(ValueError, match="api_key must be supplied"):
        c = Client(space_key=inputs["space_key"])
    with pytest.raises(ValueError, match="space_key must be supplied"):
        c = Client(api_key=inputs["api_key"])
    
    # acceptable input
    c = Client(space_key=inputs["space_key"], api_key=inputs["api_key"])

@pytest.fixture(autouse=False)
def set_auth_envvars():
    originalEnviron = os.environ
    os.environ[SPACE_KEY_ENVVAR_NAME] = inputs["space_key"]
    os.environ[API_KEY_ENVVAR_NAME] = inputs["api_key"]
    yield
    os.environ[SPACE_KEY_ENVVAR_NAME] = originalEnviron.get(SPACE_KEY_ENVVAR_NAME)
    os.environ[API_KEY_ENVVAR_NAME] = originalEnviron.get(API_KEY_ENVVAR_NAME)

def test_client_uses_envvars(set_auth_envvars):    
    c = Client()
    assert c._space_key == inputs["space_key"]
    assert c._api_key == inputs["api_key"]

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
