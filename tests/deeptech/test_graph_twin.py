from decimal import Decimal
import pytest
from app.deeptech.graph import TransactionGraph
from app.deeptech.digital_twin import FinancialDigitalTwin
from app.deeptech.models import Scenario

def test_graph_counts_and_neighbors(make_tx):
    graph=TransactionGraph.from_transactions([make_tx(0),make_tx(1)])
    assert graph.node_count>=3 and graph.neighbors("merchant:merchant-a")

def test_graph_components(make_tx):
    graph=TransactionGraph.from_transactions([make_tx(0),make_tx(1),make_tx(9,merchant_id="merchant-z",customer_id="other",channel="mobile",country="GB",product_id="sku-z")])
    assert len(graph.connected_components())==2

def test_graph_pagerank_sums_to_one(make_tx):
    graph=TransactionGraph.from_transactions([make_tx(i) for i in range(10)])
    ranks=graph.weighted_pagerank()
    assert abs(sum(ranks.values())-1)<1e-6

def test_graph_candidate_identifiers(make_tx):
    graph=TransactionGraph.from_transactions([make_tx(i,customer_id="repeat") for i in range(4)])
    assert graph.candidate_shared_identifiers(min_transactions=3)

def test_graph_no_nodes_returns_empty():
    assert TransactionGraph().weighted_pagerank()=={}

def test_twin_reproducible():
    scenario=Scenario("base",100,Decimal("20"),refund_rate=.1,dispute_rate=.02)
    twin=FinancialDigitalTwin(seed=7)
    assert twin.simulate(scenario,1000)==twin.simulate(scenario,1000)

def test_twin_reports_assumptions():
    result=FinancialDigitalTwin().simulate(Scenario("base",100,Decimal("20")),100)
    assert "sampling" in result.assumptions and result.iterations==100

def test_twin_validates_iterations():
    with pytest.raises(ValueError): FinancialDigitalTwin().simulate(Scenario("base",1,Decimal("1")),10)

def test_scenario_validates_rates():
    with pytest.raises(ValueError): Scenario("bad",10,Decimal("10"),refund_rate=1.2)

def test_graph_rejects_duplicate_transaction_ids(make_tx):
    with pytest.raises(ValueError):
        TransactionGraph.from_transactions([make_tx(1), make_tx(1)])

def test_graph_tenant_scopes_customer_identifiers(make_tx):
    graph=TransactionGraph.from_transactions([make_tx(1,merchant_id="merchant-a",customer_id="same"),make_tx(2,merchant_id="merchant-b",customer_id="same")])
    assert "customer:merchant-a:same" in graph.transaction_ids("merchant:merchant-a") or "customer:merchant-a:same" in graph.neighbors("merchant:merchant-a")
    assert "customer:merchant-b:same" in graph.neighbors("merchant:merchant-b")

def test_graph_keeps_currency_totals_separate(make_tx):
    graph=TransactionGraph.from_transactions([make_tx(1,amount="10",currency="USD"),make_tx(2,amount="20",currency="EUR")])
    summary=graph.node_summary("merchant:merchant-a")
    assert summary["gross_amount_by_currency"]=={"EUR":"20","USD":"10"}
