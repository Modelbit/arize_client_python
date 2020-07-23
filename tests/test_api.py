import pandas as pd
import numpy as np
import uuid
from pathlib import Path

import arize.api as api
import arize.public_pb2 as public__pb2

from google.protobuf.timestamp_pb2 import Timestamp

NUM_VAL = 20.20
STR_VAL = 'arize'
BOOL_VAL = True
INT_VAL = 0
file_to_open = Path(__file__).parent / "fixtures/mpg.csv"

expected = {
    'model': 'model_v0',
    'model_version': 'v1.2.3.4',
    'api_key': 'API_KEY',
    'prediction_id': 'prediction_0',
    'value_binary': BOOL_VAL,
    'value_categorical': STR_VAL,
    'value_numeric': NUM_VAL,
    'organization_key': 'test_org',
    'features': {
        'feature_str': STR_VAL,
        'feature_double': NUM_VAL,
        'feature_int': INT_VAL,
        'feature_bool': BOOL_VAL
    }
}


def test_api_initialization():
    try:
        api.Client()
    except Exception as e:
        assert isinstance(e, TypeError)

    try:
        api.Client(api_key='test')
    except Exception as client_id_exception:
        assert isinstance(client_id_exception, TypeError)

    try:
        api.Client(organization_key='test')
    except Exception as organization_key_exception:
        assert isinstance(organization_key_exception, TypeError)


def setup_client():
    return api.Client(organization_key=expected['organization_key'],
                      api_key=expected['api_key'],
                      model_id=expected['model'],
                      model_version=expected['model_version'])


def mock_dataframes(file):
    features = pd.read_csv(file)
    labels = pd.DataFrame(
        np.random.randint(1, 100, size=(features.shape[0], 1)))
    ids = pd.DataFrame([str(uuid.uuid4()) for _ in range(len(labels.index))])
    return features, labels, ids


def mock_series(file):
    features = pd.read_csv(file)
    labels = pd.Series(np.random.randint(1, 100, size=features.shape[0]))
    ids = pd.Series([str(uuid.uuid4()) for _ in range(len(labels.index))])
    return features, labels, ids


def test_build_prediction_record_features():
    client = setup_client()
    record = client._build_record(model_id=expected['model'],
                                  model_version=expected['model_version'],
                                  prediction_id=expected['prediction_id'],
                                  prediction_label=expected['value_binary'],
                                  features=expected['features'],
                                  actual_label=None,
                                  time_overwrite=None)

    assert isinstance(record, public__pb2.Record)
    assert isinstance(record.prediction, public__pb2.Prediction)
    assert isinstance(record.prediction.label, public__pb2.Label)
    for feature in record.prediction.features:
        assert isinstance(record.prediction.features[feature],
                          public__pb2.Value)
    assert record.organization_key == expected['organization_key']
    assert record.model_id == expected['model']
    assert record.prediction_id == expected['prediction_id']
    assert record.prediction.model_version == expected['model_version']
    assert record.prediction.label.binary == expected['value_binary']
    assert record.prediction.features['feature_str'].WhichOneof(
        'data') == 'string'
    assert record.prediction.features['feature_double'].WhichOneof(
        'data') == 'double'
    assert record.prediction.features['feature_int'].WhichOneof(
        'data') == 'int'
    assert record.prediction.features['feature_bool'].WhichOneof(
        'data') == 'string'


def test_build_record_binary_prediction():
    client = setup_client()
    record = client._build_record(model_id=expected['model'],
                                  model_version=expected['model_version'],
                                  prediction_id=expected['prediction_id'],
                                  prediction_label=expected['value_binary'],
                                  features=expected['features'],
                                  actual_label=None,
                                  time_overwrite=None)
    assert isinstance(record, public__pb2.Record)
    assert isinstance(record.prediction, public__pb2.Prediction)
    assert isinstance(record.prediction.label, public__pb2.Label)
    assert record.organization_key == expected['organization_key']
    assert record.model_id == expected['model']
    assert record.prediction_id == expected['prediction_id']
    assert record.prediction.model_version == expected['model_version']
    assert bool(record.prediction.features)
    assert record.prediction.label.binary == expected['value_binary']


def test_build_record_categorical_prediction():
    client = setup_client()
    record = client._build_record(
        model_id=expected['model'],
        model_version=expected['model_version'],
        prediction_id=expected['prediction_id'],
        prediction_label=expected['value_categorical'],
        features=expected['features'],
        actual_label=None,
        time_overwrite=None)

    assert isinstance(record, public__pb2.Record)
    assert isinstance(record.prediction, public__pb2.Prediction)
    assert isinstance(record.prediction.label, public__pb2.Label)
    assert record.organization_key == expected['organization_key']
    assert record.model_id == expected['model']
    assert record.prediction_id == expected['prediction_id']
    assert record.prediction.model_version == expected['model_version']
    assert bool(record.prediction.features)
    assert record.prediction.label.categorical == expected['value_categorical']


def test_build_record_numeric_prediction():
    client = setup_client()
    record = client._build_record(model_id=expected['model'],
                                  model_version=expected['model_version'],
                                  prediction_id=expected['prediction_id'],
                                  prediction_label=expected['value_numeric'],
                                  features=expected['features'],
                                  actual_label=None,
                                  time_overwrite=None)

    assert isinstance(record, public__pb2.Record)
    assert isinstance(record.prediction, public__pb2.Prediction)
    assert isinstance(record.prediction.label, public__pb2.Label)

    assert record.organization_key == expected['organization_key']
    assert record.model_id == expected['model']
    assert record.prediction_id == expected['prediction_id']
    assert record.prediction.model_version == expected['model_version']
    assert bool(record.prediction.features)
    assert record.prediction.label.numeric == expected['value_numeric']


def test_build_record_numeric_actual():
    client = setup_client()
    record = client._build_record(model_id=expected['model'],
                                  model_version=None,
                                  prediction_id=expected['prediction_id'],
                                  prediction_label=None,
                                  features=None,
                                  actual_label=expected['value_numeric'],
                                  time_overwrite=None)
    assert isinstance(record, public__pb2.Record)
    assert isinstance(record.actual, public__pb2.Actual)
    assert isinstance(record.actual.label, public__pb2.Label)
    assert record.organization_key == expected['organization_key']
    assert record.model_id == expected['model']
    assert record.prediction_id == expected['prediction_id']
    assert record.actual.label.numeric == expected['value_numeric']


def test_build_record_categorical_actual():
    client = setup_client()
    record = client._build_record(model_id=expected['model'],
                                  model_version=None,
                                  prediction_id=expected['prediction_id'],
                                  prediction_label=None,
                                  features=None,
                                  actual_label=expected['value_categorical'],
                                  time_overwrite=None)
    assert isinstance(record, public__pb2.Record)
    assert isinstance(record.actual, public__pb2.Actual)
    assert isinstance(record.actual.label, public__pb2.Label)
    assert record.organization_key == expected['organization_key']
    assert record.model_id == expected['model']
    assert record.prediction_id == expected['prediction_id']
    assert record.actual.label.categorical == expected['value_categorical']


def test_build_record_binary_actual():
    client = setup_client()
    record = client._build_record(model_id=expected['model'],
                                  model_version=None,
                                  prediction_id=expected['prediction_id'],
                                  prediction_label=None,
                                  features=None,
                                  actual_label=expected['value_binary'],
                                  time_overwrite=None)
    assert isinstance(record, public__pb2.Record)
    assert isinstance(record.actual, public__pb2.Actual)
    assert isinstance(record.actual.label, public__pb2.Label)
    assert record.organization_key == expected['organization_key']
    assert record.model_id == expected['model']
    assert record.prediction_id == expected['prediction_id']
    assert record.actual.label.binary == expected['value_binary']


def test_build_bulk_records_predictions():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    bulk_records = client._build_bulk_record(
        model_id=expected['model'],
        model_version=expected['model_version'],
        prediction_ids=ids,
        prediction_labels=labels,
        actual_labels=None,
        features=features,
        features_name_overwrite=None,
        time_overwrite=None)
    record_count = 0
    for bulk in bulk_records:
        assert bulk.organization_key == expected['organization_key']
        assert bulk.model_id == expected['model']
        assert bulk.model_version == expected['model_version']
        assert isinstance(bulk.timestamp, Timestamp)
        for i in range(len(bulk.records)):
            record = bulk.records[i]
            assert isinstance(record, public__pb2.Record)
            assert isinstance(record.prediction.label, public__pb2.Label)
            assert len(record.prediction.features) == features.shape[1]
            assert record.prediction.label.WhichOneof('data') == 'numeric'
            record_count += 1
    assert record_count == len(ids)


def test_build_bulk_records_actuals():
    client = setup_client()
    _, labels, ids = mock_dataframes(file_to_open)
    bulk_records = client._build_bulk_record(
        model_id=expected['model'],
        model_version=expected['model_version'],
        prediction_ids=ids,
        prediction_labels=None,
        actual_labels=labels,
        features=None,
        features_name_overwrite=None,
        time_overwrite=None)
    record_count = 0
    for bulk in bulk_records:
        assert bulk.organization_key == expected['organization_key']
        assert bulk.model_id == expected['model']
        assert isinstance(bulk.timestamp, Timestamp)
        for i in range(len(bulk.records)):
            record = bulk.records[i]
            assert isinstance(record, public__pb2.Record)
            assert isinstance(record.actual.label, public__pb2.Label)
            assert record.prediction_id == ids[0][record_count]
            assert record.actual.label.WhichOneof('data') == 'numeric'
            record_count += 1
    assert record_count == len(ids)


def test_handle_log_single_actual():
    client = setup_client()
    record, uri = client._handle_log(model_id=expected['model'],
                                     model_version=None,
                                     prediction_ids=expected['prediction_id'],
                                     prediction_labels=None,
                                     features=None,
                                     actual_labels=expected['value_binary'],
                                     features_name_overwrite=None,
                                     time_overwrite=None)
    assert len(record) == 1
    assert isinstance(record[0].actual, public__pb2.Actual)
    assert uri == 'https://api.arize.com/v1/log'


def test_handle_log_single_prediction_with_features():
    client = setup_client()
    record, uri = client._handle_log(
        model_id=expected['model'],
        model_version=None,
        prediction_ids=expected['prediction_id'],
        prediction_labels=expected['value_binary'],
        features=expected['features'],
        actual_labels=None,
        features_name_overwrite=None,
        time_overwrite=None)
    assert len(record) == 1
    assert isinstance(record[0].prediction, public__pb2.Prediction)
    assert bool(record[0].prediction.features)
    assert uri == 'https://api.arize.com/v1/log'


def test_handle_log_single_prediction_no_features():
    client = setup_client()
    record, uri = client._handle_log(
        model_id=expected['model'],
        model_version=None,
        prediction_ids=expected['prediction_id'],
        prediction_labels=expected['value_binary'],
        features=None,
        actual_labels=None,
        features_name_overwrite=None,
        time_overwrite=None)
    assert len(record) == 1
    assert isinstance(record[0].prediction, public__pb2.Prediction)
    assert not bool(record[0].prediction.features)
    assert uri == 'https://api.arize.com/v1/log'


def test_handle_log_batch_prediction_with_features():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    records, uri = client._handle_log(model_id=expected['model'],
                                      model_version=None,
                                      prediction_ids=ids,
                                      prediction_labels=labels,
                                      features=features,
                                      actual_labels=None,
                                      features_name_overwrite=None,
                                      time_overwrite=None)
    assert len(records) > 0
    for bulk in records:
        assert isinstance(bulk, public__pb2.BulkRecord)
        for r in bulk.records:
            assert isinstance(r, public__pb2.Record)
            assert not bool(r.organization_key)
            assert not bool(r.model_id)
            assert bool(r.prediction.features)
    assert uri == 'https://api.arize.com/v1/bulk'


def test_handle_log_batch_prediction_with_no_features():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    records, uri = client._handle_log(model_id=expected['model'],
                                      model_version=None,
                                      prediction_ids=ids,
                                      prediction_labels=labels,
                                      features=None,
                                      actual_labels=None,
                                      features_name_overwrite=None,
                                      time_overwrite=None)
    assert len(records) > 0
    for bulk in records:
        assert isinstance(bulk, public__pb2.BulkRecord)
        for r in bulk.records:
            assert isinstance(r, public__pb2.Record)
            assert not bool(r.organization_key)
            assert not bool(r.model_id)
            assert not bool(r.prediction.features)
    assert uri == 'https://api.arize.com/v1/bulk'


def test_handle_log_batch_actuals_only():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    records, uri = client._handle_log(model_id=expected['model'],
                                      model_version=None,
                                      prediction_ids=ids,
                                      prediction_labels=None,
                                      features=None,
                                      actual_labels=labels,
                                      features_name_overwrite=None,
                                      time_overwrite=None)
    assert len(records) > 0
    for bulk in records:
        assert isinstance(bulk, public__pb2.BulkRecord)
        for r in bulk.records:
            assert isinstance(r, public__pb2.Record)
            assert not bool(r.organization_key)
            assert not bool(r.model_id)
            assert bool(r.actual.label)
    assert uri == 'https://api.arize.com/v1/bulk'


def test_handle_log_batch_actuals_and_predictions():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    records, uri = client._handle_log(model_id=expected['model'],
                                      model_version=None,
                                      prediction_ids=ids,
                                      prediction_labels=labels,
                                      features=features,
                                      actual_labels=labels,
                                      features_name_overwrite=None,
                                      time_overwrite=None)
    assert len(records) > 0
    actuals = 0
    predictions = 0
    for bulk in records:
        assert isinstance(bulk, public__pb2.BulkRecord)
        for r in bulk.records:
            assert isinstance(r, public__pb2.Record)
            assert not bool(r.organization_key)
            assert not bool(r.model_id)
            assert isinstance(
                getattr(r, r.WhichOneof('prediction_or_actual')).label,
                public__pb2.Label)
            if r.WhichOneof('prediction_or_actual') == 'prediction':
                predictions += 1
            if r.WhichOneof('prediction_or_actual') == 'prediction':
                actuals += 1
    assert uri == 'https://api.arize.com/v1/bulk'
    print(predictions)
    assert actuals == predictions == labels.shape[0]


def test_log_batch_actuals_and_predictions_missmatched_shapes():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    id_ex, feature_ex, label_ex = None, None, None
    try:
        records, uri = client.log(model_id=expected['model'],
                                  prediction_ids=ids[0:10],
                                  prediction_labels=labels,
                                  features=features,
                                  actual_labels=labels)
    except Exception as err:
        id_ex = err
    try:
        records = client.log(model_id=expected['model'],
                             prediction_ids=ids,
                             prediction_labels=labels,
                             features=features[0:10],
                             actual_labels=labels)
    except Exception as err:
        feature_ex = err
    try:
        records, uri = client.log(model_id=expected['model'],
                                  prediction_ids=ids,
                                  prediction_labels=labels,
                                  features=features,
                                  actual_labels=labels[0:10])
    except Exception as err:
        label_ex = err
    assert isinstance(id_ex, ValueError)
    assert isinstance(feature_ex, ValueError)
    assert isinstance(label_ex, ValueError)


def test_handle_log_batch_prediction_with_features_name_overwrites():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    features_name_overwrite = [
        'mask_' + str(i) for i in range(len(features.columns))
    ]
    records, uri = client._handle_log(
        model_id=expected['model'],
        model_version=None,
        prediction_ids=ids,
        prediction_labels=labels,
        features=features,
        actual_labels=None,
        features_name_overwrite=features_name_overwrite,
        time_overwrite=None)
    assert len(records) > 0
    for bulk in records:
        assert isinstance(bulk, public__pb2.BulkRecord)
        for r in bulk.records:
            assert isinstance(r, public__pb2.Record)
            assert not bool(r.organization_key)
            assert not bool(r.model_id)
            assert bool(r.prediction.features)
            for feature in r.prediction.features:
                assert feature in features_name_overwrite
    assert uri == 'https://api.arize.com/v1/bulk'


def test_log_batch_prediction_with_features_name_overwrites_missmatched_size():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    features_name_overwrite = [
        'mask_' + str(i) for i in range(len(features.columns) - 1)
    ]
    ex = None
    try:
        _ = client.log(
            model_id=expected['model'],
            prediction_ids=ids,
            prediction_labels=labels,
            features=features,
            features_name_overwrite=features_name_overwrite,
        )
    except Exception as err:
        ex = err
    assert isinstance(ex, ValueError)


def test_log_batch_prediction_default_columns_int_names():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    assert isinstance(features.columns[0], str)
    features_default_columns = pd.DataFrame(features[:].values)
    ex = None
    try:
        _ = client.log(model_id=expected['model'],
                       model_version=None,
                       prediction_ids=ids,
                       prediction_labels=labels,
                       features=features_default_columns,
                       actual_labels=None,
                       features_name_overwrite=None,
                       time_overwrite=None)
    except Exception as err:
        ex = err
    assert isinstance(ex, TypeError)


def test_log_batch_prediction_no_actuals_or_predictions():
    client = setup_client()
    _, _, ids = mock_dataframes(file_to_open)
    ex = None
    try:
        records, uri = client.log(model_id=expected['model'],
                                  model_version=None,
                                  prediction_ids=ids,
                                  prediction_labels=None,
                                  features=None,
                                  actual_labels=None,
                                  features_name_overwrite=None,
                                  time_overwrite=None)
    except Exception as err:
        ex = err
    assert isinstance(ex, TypeError)


def test_handle_log_batch_prediction_with_time_overwrites():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    time = [1593626247 + i for i in range(features.shape[0])]
    time_df = pd.DataFrame(time)
    records, uri = client._handle_log(model_id=expected['model'],
                                      model_version=None,
                                      prediction_ids=ids,
                                      prediction_labels=labels,
                                      features=features,
                                      time_overwrite=time_df,
                                      features_name_overwrite=None,
                                      actual_labels=None)
    assert len(records) > 0
    for bulk in records:
        assert isinstance(bulk, public__pb2.BulkRecord)
        for r in bulk.records:
            assert isinstance(r, public__pb2.Record)
            assert not bool(r.organization_key)
            assert not bool(r.model_id)
            assert bool(r.prediction.features)
            assert r.prediction.timestamp is not None
    assert uri == 'https://api.arize.com/v1/bulk'


def test_handle_log_prediction_with_time_overwrites():
    client = setup_client()
    record, uri = client._handle_log(
        model_id=expected['model'],
        model_version=None,
        prediction_ids=expected['prediction_id'],
        prediction_labels=expected['value_binary'],
        features=expected['features'],
        actual_labels=None,
        features_name_overwrite=None,
        time_overwrite=1593626247)
    assert len(record) == 1
    assert isinstance(record[0].prediction, public__pb2.Prediction)
    assert bool(record[0].prediction.features)
    assert uri == 'https://api.arize.com/v1/log'
    assert record[0].prediction.timestamp.seconds == 1593626247


def test_log_batch_non_supported_data_types():
    client = setup_client()
    features, labels, ids = mock_dataframes(file_to_open)
    features_nparray = features.to_numpy()
    ids_series = pd.Index(list('abcde'))
    labels_series = pd.Index([1, 2, 3, 4, 5])
    label_ex, feature_ex, id_ex = None, None, None
    try:
        records = client.log(model_id=expected['model'],
                             model_version=None,
                             prediction_ids=ids_series,
                             prediction_labels=labels,
                             features=features,
                             actual_labels=labels)
    except Exception as e1:
        id_ex = e1

    try:
        client = setup_client()
        records = client.log(model_id=expected['model'],
                             model_version=None,
                             prediction_ids=ids,
                             prediction_labels=labels_series,
                             features=features,
                             actual_labels=labels)
    except Exception as e2:
        label_ex = e2

    try:
        _ = client.log(model_id=expected['model'],
                       model_version=None,
                       prediction_ids=ids,
                       prediction_labels=labels,
                       features=features_nparray,
                       actual_labels=labels)
    except Exception as e3:
        feature_ex = e3

    assert isinstance(id_ex, TypeError)
    assert isinstance(label_ex, TypeError)
    assert isinstance(feature_ex, TypeError)


def test_handle_log_series():
    client = setup_client()
    features, labels, ids = mock_series(file_to_open)
    time = [1593626247 + i for i in range(features.shape[0])]
    records, uri = client._handle_log(model_id=expected['model'],
                                      model_version=None,
                                      prediction_ids=ids,
                                      prediction_labels=labels,
                                      features=features,
                                      features_name_overwrite=None,
                                      actual_labels=None,
                                      time_overwrite=time)
    assert len(records) > 0
    for bulk in records:
        assert isinstance(bulk, public__pb2.BulkRecord)
        for r in bulk.records:
            assert isinstance(r, public__pb2.Record)
            assert not bool(r.organization_key)
            assert not bool(r.model_id)
            assert bool(r.prediction.features)
            assert r.prediction.timestamp is not None
    assert uri == 'https://api.arize.com/v1/bulk'
