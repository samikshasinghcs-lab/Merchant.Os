import math, pytest
from app.deeptech.statistics import quantile, median_absolute_deviation, robust_z_score, ewma, cusum
from app.deeptech.anomaly import RobustAnomalyDetector, AnomalyConfig

def test_quantile_interpolates(): assert quantile([0,10],.5)==5

def test_quantile_rejects_invalid():
    with pytest.raises(ValueError): quantile([1],1.1)

def test_mad(): assert median_absolute_deviation([1,2,3])==1

def test_robust_z_detects_outlier(): assert robust_z_score(100,[1,2,3,4,5])>10

def test_constant_baseline_outlier_infinite(): assert math.isinf(robust_z_score(9,[2,2,2]))

def test_ewma(): assert len(ewma([1,2,3],.5))==3

def test_cusum_detects_shift(): assert cusum([0]*30+[10]*30,threshold=3)

def test_detector_requires_fit(make_tx):
    with pytest.raises(RuntimeError): RobustAnomalyDetector().score_one(make_tx())

def test_detector_flags_large_amount(make_tx):
    history=[make_tx(i,amount=str(10+i%2)) for i in range(20)]
    detector=RobustAnomalyDetector().fit(history)
    result=detector.score_one(make_tx(30,amount="1000"))
    assert result.score>0 and result.signals

def test_detector_separates_merchants(make_tx):
    history=[make_tx(i,amount="10") for i in range(20)]
    detector=RobustAnomalyDetector().fit(history)
    other=make_tx(30,merchant_id="other",amount="1000")
    assert detector.score_one(other).baseline["sample_size"]==0

def test_detector_config_validation():
    with pytest.raises(ValueError): AnomalyConfig(minimum_baseline=1)
