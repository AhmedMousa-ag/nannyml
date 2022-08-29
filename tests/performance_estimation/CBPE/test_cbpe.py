#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0

"""Unit testing for CBPE."""

import typing
from typing import Tuple

import numpy as np
import pandas as pd
import pytest
from pytest_mock import MockerFixture

from nannyml.calibration import Calibrator, IsotonicCalibrator
from nannyml.datasets import (
    load_synthetic_binary_classification_dataset,
    load_synthetic_multiclass_classification_dataset,
)
from nannyml.exceptions import InvalidArgumentsException
from nannyml.performance_estimation import CBPE
from nannyml.performance_estimation.confidence_based.results import CBPEPerformanceEstimatorResult


@pytest.fixture
def binary_classification_data() -> Tuple[pd.DataFrame, pd.DataFrame]:  # noqa: D103
    ref_df, ana_df, _ = load_synthetic_binary_classification_dataset()
    ref_df['y_pred'] = ref_df['y_pred_proba'].apply(lambda p: int(p >= 0.8))
    return ref_df, ana_df


@pytest.fixture
def multiclass_classification_data() -> Tuple[pd.DataFrame, pd.DataFrame]:  # noqa: D103
    ref_df, ana_df, _ = load_synthetic_multiclass_classification_dataset()
    return ref_df, ana_df


@pytest.fixture
def estimates(binary_classification_data) -> CBPEPerformanceEstimatorResult:  # noqa: D103
    reference, analysis = binary_classification_data
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc'],
    )
    estimator.fit(reference)
    return estimator.estimate(pd.concat([reference, analysis]))  # type: ignore


def test_cbpe_will_calibrate_scores_when_needed(binary_classification_data):  # noqa: D103
    ref_df = binary_classification_data[0]

    sut = CBPE(
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc'],
    )
    sut.fit(ref_df)

    assert sut.needs_calibration


def test_cbpe_will_not_calibrate_scores_when_not_needed(binary_classification_data):  # noqa: D103
    ref_df = binary_classification_data[0]
    # If predictions equal targets no calibration will be required
    ref_df['y_pred_proba'] = ref_df['work_home_actual']

    sut = CBPE(
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc'],
    )
    sut.fit(ref_df)

    assert sut.needs_calibration is False


def test_cbpe_will_not_fail_on_work_from_home_sample(binary_classification_data):  # noqa: D103
    reference, analysis = binary_classification_data
    try:
        estimator = CBPE(
            timestamp_column_name='timestamp',
            y_true='work_home_actual',
            y_pred='y_pred',
            y_pred_proba='y_pred_proba',
            metrics=['roc_auc'],
        )
        estimator.fit(reference)
        _ = estimator.estimate(analysis)
    except Exception as exc:
        pytest.fail(f'unexpected exception was raised: {exc}')


def test_cbpe_raises_invalid_arguments_exception_when_giving_invalid_metric_value():  # noqa: D103
    with pytest.raises(InvalidArgumentsException, match="unknown metric key 'foo' given."):
        _ = CBPE(
            timestamp_column_name='timestamp',
            y_true='work_home_actual',
            y_pred='y_pred',
            y_pred_proba='y_pred_proba',
            metrics=['roc_auc', 'foo'],
        )


def test_cbpe_raises_invalid_arguments_exception_when_given_empty_metrics_list():  # noqa: D103
    with pytest.raises(
        InvalidArgumentsException, match="no metrics provided. Please provide a non-empty list of metrics."
    ):
        _ = CBPE(
            timestamp_column_name='timestamp',
            y_true='work_home_actual',
            y_pred='y_pred',
            y_pred_proba='y_pred_proba',
            metrics=[],
        )


def test_cbpe_raises_invalid_arguments_exception_when_given_none_metrics_list():  # noqa: D103
    with pytest.raises(
        InvalidArgumentsException, match="no metrics provided. Please provide a non-empty list of metrics."
    ):
        _ = CBPE(
            timestamp_column_name='timestamp',
            y_true='work_home_actual',
            y_pred='y_pred',
            y_pred_proba='y_pred_proba',
            metrics=None,
        )


def test_cbpe_raises_missing_metadata_exception_when_predictions_are_required_but_not_given(  # noqa: D103
    binary_classification_data,
):
    reference, _ = binary_classification_data
    estimator = CBPE(
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='predictions',
        y_pred_proba='y_pred_proba',
        metrics=['f1'],
    )  # requires predictions!
    with pytest.raises(InvalidArgumentsException, match='predictions'):
        estimator.fit(reference)


def test_cbpe_defaults_to_isotonic_calibrator_when_none_given():  # noqa: D103
    estimator = CBPE(
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['f1'],
    )
    assert isinstance(estimator.calibrator, IsotonicCalibrator)


def test_cbpe_uses_custom_calibrator_when_provided():  # noqa: D103
    class TestCalibrator(Calibrator):
        def fit(self, y_pred_proba: np.ndarray, y_true: np.ndarray):
            pass

        def calibrate(self, y_pred_proba: np.ndarray):
            pass

    estimator = CBPE(
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc'],
        calibrator=TestCalibrator(),
    )
    assert isinstance(estimator.calibrator, TestCalibrator)


def test_cbpe_uses_calibrator_to_calibrate_predicted_probabilities_when_needed(  # noqa: D103
    binary_classification_data, mocker: MockerFixture
):
    reference, analysis = binary_classification_data

    calibrator = IsotonicCalibrator()
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc'],
        calibrator=calibrator,
    ).fit(reference)
    assert typing.cast(CBPE, estimator).needs_calibration

    spy = mocker.spy(calibrator, 'calibrate')

    estimator.estimate(analysis)
    spy.assert_called_once()


def test_cbpe_doesnt_use_calibrator_to_calibrate_predicted_probabilities_when_not_needed(  # noqa: D103
    binary_classification_data, mocker: MockerFixture
):
    reference, analysis = binary_classification_data

    calibrator = IsotonicCalibrator()
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc'],
        calibrator=calibrator,
    ).fit(reference)

    typing.cast(CBPE, estimator).needs_calibration = False  # Override this to disable calibration

    spy = mocker.spy(calibrator, 'calibrate')
    estimator.estimate(analysis)
    spy.assert_not_called()


def test_cbpe_raises_missing_metadata_exception_when_predicted_probabilities_are_required_but_not_given(  # noqa: D103
    binary_classification_data,
):
    reference, _ = binary_classification_data

    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='probabilities',
        metrics=['roc_auc'],
    )
    with pytest.raises(InvalidArgumentsException, match='probabilities'):
        estimator.fit(reference)


@pytest.mark.parametrize('metric', ['roc_auc', 'f1', 'precision', 'recall', 'specificity', 'accuracy'])
def test_cbpe_runs_for_all_metrics(binary_classification_data, metric):  # noqa: D103
    reference, analysis = binary_classification_data
    try:
        estimator = CBPE(  # type: ignore
            timestamp_column_name='timestamp',
            y_true='work_home_actual',
            y_pred='y_pred',
            y_pred_proba='y_pred_proba',
            metrics=['roc_auc'],
        ).fit(reference)
        _ = estimator.estimate(pd.concat([reference, analysis]))
    except Exception as e:
        pytest.fail(f'an unexpected exception occurred: {e}')


def test_cbpe_results_plot_raises_invalid_arguments_exception_given_invalid_plot_kind(estimates):  # noqa: D103
    with pytest.raises(InvalidArgumentsException):
        estimates.plot(kind="foo")


def test_cbpe_results_plot_raises_invalid_arguments_exception_given_no_plot_kind(estimates):  # noqa: D103
    with pytest.raises(InvalidArgumentsException):
        estimates.plot()


def test_cbpe_results_plot_raises_invalid_arguments_exception_given_no_metric_for_performance_plot(  # noqa: D103
    estimates,
):
    with pytest.raises(InvalidArgumentsException):
        estimates.plot(kind="performance")


def test_cbpe_results_plot_raises_invalid_arguments_exception_given_invalid_metric_for_performance_plot(  # noqa: D103
    estimates,
):
    with pytest.raises(InvalidArgumentsException, match="unknown 'metric' value: 'foo'."):
        estimates.plot(kind="performance", metric="foo")


@pytest.mark.parametrize('metric', ['roc_auc', 'f1', 'precision', 'recall', 'specificity', 'accuracy'])
def test_cbpe_for_binary_classification_does_not_fail_when_fitting_with_subset_of_reference_data(  # noqa: D103
    binary_classification_data, metric
):
    reference = binary_classification_data[0].loc[40000:, :]
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc', 'f1', 'precision', 'recall', 'specificity', 'accuracy'],
    )
    try:
        estimator.fit(reference_data=reference)
    except KeyError:
        pytest.fail(
            'fitting on subset resulted in KeyError => misaligned indices between data and stratified shuffle'
            'split results.'
        )


def reduce_confidence_bounds(monkeypatch, estimator, results):
    min_confidence = results.data['lower_confidence_roc_auc'].min()
    max_confidence = results.data['upper_confidence_roc_auc'].max()

    new_lower_bound = min_confidence + 0.001
    new_upper_bound = max_confidence - 0.001
    monkeypatch.setattr(estimator, 'confidence_lower_bound', new_lower_bound)
    monkeypatch.setattr(estimator, 'confidence_upper_bound', new_upper_bound)

    return estimator, new_lower_bound, new_upper_bound


def test_cbpe_for_binary_classification_does_not_output_confidence_bounds_outside_appropriate_interval(
    monkeypatch, binary_classification_data
):
    reference, analysis = binary_classification_data
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=['roc_auc'],
    ).fit(reference)
    results = estimator.estimate(pd.concat([reference, analysis]))
    estimator, new_lower_bound, new_upper_bound = reduce_confidence_bounds(monkeypatch, estimator, results)
    results = estimator.estimate(analysis)
    assert all(results.data['lower_confidence_roc_auc'] >= new_lower_bound)
    assert all(results.data['upper_confidence_roc_auc'] <= new_upper_bound)


def test_cbpe_for_multiclass_classification_does_not_output_confidence_bounds_outside_appropriate_interval(
    monkeypatch, multiclass_classification_data
):
    reference, analysis = multiclass_classification_data
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='y_true',
        y_pred='y_pred',
        y_pred_proba={
            'prepaid_card': 'y_pred_proba_prepaid_card',
            'highstreet_card': 'y_pred_proba_highstreet_card',
            'upmarket_card': 'y_pred_proba_upmarket_card',
        },
        metrics=['roc_auc'],
    ).fit(reference)
    results = estimator.estimate(pd.concat([reference, analysis]))
    estimator, new_lower_bound, new_upper_bound = reduce_confidence_bounds(monkeypatch, estimator, results)
    results = estimator.estimate(analysis)
    assert all(results.data['lower_confidence_roc_auc'] >= new_lower_bound)
    assert all(results.data['upper_confidence_roc_auc'] <= new_upper_bound)


@pytest.mark.parametrize(
    'metric, sampling_error',
    [
        ('roc_auc', 0.001811),
        ('f1', 0.007549),
        ('precision', 0.003759),
        ('recall', 0.006546),
        ('specificity', 0.003413),
        ('accuracy', 0.003746),
    ],
)
def test_cbpe_for_binary_classification_chunked_by_size_should_include_constant_sampling_error_for_metric(
    binary_classification_data, metric, sampling_error
):
    reference, analysis = binary_classification_data
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=[metric],
    ).fit(reference)
    results = estimator.estimate(analysis)

    assert f'sampling_error_{metric}' in results.data.columns
    assert all(
        np.round(results.data[f'sampling_error_{metric}'], 4)
        == pd.Series(np.round(sampling_error, 4), index=range(len(results.data)))
    )


@pytest.mark.parametrize(
    'metric, sampling_error',
    [
        ('roc_auc', [0.001819, 0.001043, 0.001046, 0.001046, 0.040489]),
        ('f1', [0.007585, 0.004348, 0.004360, 0.004362, 0.168798]),
        ('precision', [0.003777, 0.002165, 0.002171, 0.002172, 0.084046]),
        ('recall', [0.006578, 0.003770, 0.003781, 0.003783, 0.146378]),
        ('specificity', [0.003430, 0.001966, 0.001971, 0.001972, 0.076324]),
        ('accuracy', [0.003764, 0.002158, 0.002164, 0.002165, 0.083769]),
    ],
)
def test_cbpe_for_binary_classification_chunked_by_period_should_include_variable_sampling_error_for_metric(
    binary_classification_data, metric, sampling_error
):
    reference, analysis = binary_classification_data
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='work_home_actual',
        y_pred='y_pred',
        y_pred_proba='y_pred_proba',
        metrics=[metric],
        chunk_period='Y',
    ).fit(reference)
    results = estimator.estimate(analysis)
    print(results.data[f'sampling_error_{metric}'])

    assert f'sampling_error_{metric}' in results.data.columns
    assert np.array_equal(np.round(results.data[f'sampling_error_{metric}'], 4), np.round(sampling_error, 4))


@pytest.mark.parametrize(
    'metric, sampling_error',
    [
        ('roc_auc', 0.002143),
        ('f1', 0.005652),
        ('precision', 0.005566),
        ('recall', 0.005565),
        ('specificity', 0.003002),
        ('accuracy', 0.005566),
    ],
)
def test_cbpe_for_multiclass_classification_chunked_by_size_should_include_constant_sampling_error_for_metric(
    multiclass_classification_data, metric, sampling_error
):
    reference, analysis = multiclass_classification_data
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='y_true',
        y_pred='y_pred',
        y_pred_proba={
            'prepaid_card': 'y_pred_proba_prepaid_card',
            'highstreet_card': 'y_pred_proba_highstreet_card',
            'upmarket_card': 'y_pred_proba_upmarket_card',
        },
        metrics=[metric],
    ).fit(reference)
    results = estimator.estimate(analysis)

    assert f'sampling_error_{metric}' in results.data.columns
    assert all(
        np.round(results.data[f'sampling_error_{metric}'], 4)
        == pd.Series(np.round(sampling_error, 4), index=range(len(results.data)))
    )


@pytest.mark.parametrize(
    'metric, sampling_error',
    [
        ('roc_auc', [0.001379, 0.001353, 0.001371, 0.001339, 0.008100]),
        ('f1', [0.003637, 0.003569, 0.003615, 0.003531, 0.021364]),
        ('precision', [0.003582, 0.003515, 0.003560, 0.003477, 0.021037]),
        ('recall', [0.003581, 0.003514, 0.003559, 0.003476, 0.021033]),
        ('specificity', [0.001932, 0.001896, 0.001920, 0.001875, 0.011348]),
        ('accuracy', [0.003582, 0.003515, 0.003560, 0.003477, 0.021039]),
    ],
)
def test_cbpe_for_multiclass_classification_chunked_by_period_should_include_variable_sampling_error_for_metric(
    multiclass_classification_data, metric, sampling_error
):
    reference, analysis = multiclass_classification_data
    estimator = CBPE(  # type: ignore
        timestamp_column_name='timestamp',
        y_true='y_true',
        y_pred='y_pred',
        y_pred_proba={
            'prepaid_card': 'y_pred_proba_prepaid_card',
            'highstreet_card': 'y_pred_proba_highstreet_card',
            'upmarket_card': 'y_pred_proba_upmarket_card',
        },
        metrics=[metric],
        chunk_period='M',
    ).fit(reference)
    results = estimator.estimate(analysis)
    print(results.data[f'sampling_error_{metric}'])

    assert f'sampling_error_{metric}' in results.data.columns
    assert np.array_equal(np.round(results.data[f'sampling_error_{metric}'], 4), np.round(sampling_error, 4))