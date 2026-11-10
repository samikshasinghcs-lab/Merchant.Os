import json, pytest
from app.deeptech.assurance import HashChain
from app.deeptech.causal import binary_association, candidate_root_cause_hypotheses

def test_hash_chain_append_verify():
    chain=HashChain(); chain.append("PAYMENT_REVIEWED","user:1","payment:1",{"amount":"12.00"})
    valid,details=chain.verify(); assert valid and details["event_count"]==1

def test_hash_chain_links_events():
    chain=HashChain(); first=chain.append("A","actor","subject",{}); second=chain.append("B","actor","subject",{})
    assert second.previous_hash==first.event_hash

def test_hash_chain_round_trip(tmp_path):
    chain=HashChain(); chain.append("A","actor","subject",{"x":1})
    path=tmp_path/"audit.jsonl"; chain.export_jsonl(path)
    assert HashChain.from_jsonl(path).verify()[0]

def test_hash_chain_detects_tampering(tmp_path):
    chain=HashChain(); chain.append("A","actor","subject",{"x":1})
    path=tmp_path/"audit.jsonl"; chain.export_jsonl(path)
    raw=json.loads(path.read_text()); raw["payload"]["x"]=2; path.write_text(json.dumps(raw)+"\n")
    with pytest.raises(ValueError): HashChain.from_jsonl(path)

def test_hash_chain_requires_actor():
    with pytest.raises(ValueError): HashChain().append("A","","subject",{})

def test_association_detects_difference():
    rows=[{"exposed":True,"bad":True} for _ in range(20)]+[{"exposed":True,"bad":False} for _ in range(5)]+[{"exposed":False,"bad":True} for _ in range(5)]+[{"exposed":False,"bad":False} for _ in range(20)]
    result=binary_association(rows,"exposed","bad")
    assert result.risk_difference>0 and result.interpretation=="OBSERVATIONAL_ASSOCIATION_ONLY"

def test_association_caveats_present():
    result=binary_association([{"e":1,"y":1},{"e":0,"y":0}],"e","y")
    assert result.caveats

def test_root_cause_hypotheses_ranked():
    rows=[{"batch":True,"outcome":True} for _ in range(12)]+[{"batch":False,"outcome":False} for _ in range(12)]
    assert candidate_root_cause_hypotheses(rows,["batch"],"outcome",10)
