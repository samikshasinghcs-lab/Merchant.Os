import pytest
from app.deeptech.evaluation import binary_metrics,brier_score,calibration_table,precision_recall_curve,temporal_split
from app.deeptech.drift import population_stability_index,drift_report
from app.deeptech.privacy import pseudonymize,privacy_transform
from app.deeptech.registry import ModelCard,ModelRegistry
from app.deeptech.benchmark import benchmark_callable

def test_binary_metrics():
    m=binary_metrics([1,1,0,0],[1,0,1,0]); assert m.true_positive==1 and m.f1==.5

def test_brier_score(): assert brier_score([0,1],[.1,.9])==pytest.approx(.01)

def test_brier_validates_probability():
    with pytest.raises(ValueError): brier_score([0],[2])

def test_calibration_bins(): assert len(calibration_table([0,1],[.1,.9],bins=5))==5

def test_pr_curve(): assert precision_recall_curve([0,1],[.1,.9])[-1]["recall"]==1

def test_temporal_split_no_future_leakage():
    train,test=temporal_split([{"t":3},{"t":1},{"t":2},{"t":4}],"t")
    assert max(x["t"] for x in train)<min(x["t"] for x in test)

def test_psi_detects_shift(): assert population_stability_index(list(range(100)),list(range(100,200)))>0.1

def test_drift_report_schema():
    report=drift_report({"amount":list(range(20))},{"amount":list(range(20,40))})
    assert "amount" in report["metrics"]

def test_privacy_pseudonym_stable(): assert pseudonymize("cust1","customer",b"0123456789abcdef")==pseudonymize("cust1","customer",b"0123456789abcdef")

def test_privacy_transform_removes_pii():
    out=privacy_transform({"customer_id":"abc","email":"a@b.com","amount":"10"},b"0123456789abcdef")
    assert "email" not in out and out["customer_id"]!="abc" and out["amount"]=="10"

def test_privacy_transform_never_preserves_credentials():
    out=privacy_transform({"email":"a@example.test","api_secret":"secret","safe_label":"x"},b"0123456789abcdef",preserve_keys={"email","api_secret","safe_label"})
    assert out == {"safe_label":"x"}

def test_pseudonymizer_rejects_short_key():
    import pytest
    with pytest.raises(ValueError): pseudonymize("customer","id",b"short")

def test_model_registry_roundtrip(tmp_path):
    card=ModelCard.create("risk","1.0",b"artifact","triage","not credit decisions","dataset:v1","eval:v1",("amount",),("not calibrated",))
    registry=ModelRegistry(tmp_path/"registry.json"); registry.register(card)
    assert registry.get("risk","1.0")["artifact_sha256"]==card.artifact_sha256

def test_registry_rejects_duplicate(tmp_path):
    card=ModelCard.create("risk","1",b"x","triage","x","data","eval",(),())
    registry=ModelRegistry(tmp_path/"registry.json"); registry.register(card)
    with pytest.raises(ValueError): registry.register(card)

def test_benchmark_returns_samples():
    result=benchmark_callable("noop",lambda:None,repetitions=2,warmups=0)
    assert len(result["samples_ms"])==2
