from app.deeptech.research.conformal_prediction import (
    GroupwiseConformalCalibrator,
    SplitConformalRegressor,
    evaluate_coverage,
    finite_sample_quantile,
)


def test_finite_sample_quantile_uses_order_statistic():
    assert finite_sample_quantile([1, 4, 2, 3], 0.5) == 3


def test_split_conformal_interval_and_coverage():
    predictor = lambda row: row["x"] * 2
    calibrator = SplitConformalRegressor(predictor, confidence=0.8)
    rows = [{"x": float(i)} for i in range(1, 11)]
    targets = [2 * row["x"] + (1 if i % 2 else -1) for i, row in enumerate(rows)]
    calibrator.calibrate(rows, targets)
    intervals = calibrator.predict_many(rows[:3])
    report = evaluate_coverage(intervals, targets[:3])
    assert report.count == 3
    assert report.mean_width >= 0
    assert intervals[0].contains(2.0)


def test_calibrator_requires_fit():
    calibrator = SplitConformalRegressor(lambda row: row["x"])
    try:
        calibrator.predict_interval({"x": 1})
    except RuntimeError:
        pass
    else:
        raise AssertionError("prediction before calibration must fail")


def test_groupwise_calibration_rejects_small_or_unknown_group():
    calibrator = GroupwiseConformalCalibrator(0.9, minimum_group_size=3)
    calibrator.fit(["a"] * 3 + ["b"], [1, 2, 3, 4], [2, 3, 4, 5])
    assert calibrator.calibrated_groups == ("a",)
    assert calibrator.interval("a", 10).contains(11)
    try:
        calibrator.interval("b", 10)
    except KeyError:
        pass
    else:
        raise AssertionError("undersized group must not be calibrated")


def test_invalid_calibration_inputs_are_rejected():
    calibrator = SplitConformalRegressor(lambda row: row["x"])
    for rows, targets in [([], []), ([{"x": 1}], []), ([{"x": float("nan")}], [1])]:
        try:
            calibrator.calibrate(rows, targets)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid calibration data must fail")
