"""Reproducible Monte Carlo financial scenario engine (not a forecast guarantee)."""
from __future__ import annotations
from decimal import Decimal
from random import Random
from statistics import mean, median
from typing import Iterable
from .models import Scenario, SimulationResult

class FinancialDigitalTwin:
    """A transparent scenario simulator using explicit user-supplied assumptions.

    Order counts and AOV are treated as fixed inputs. Refund/dispute occurrence is
    sampled as independent Bernoulli events per order; this simplifying assumption
    is disclosed in every result and should be replaced with fitted distributions
    only when sufficient merchant history exists.
    """
    def __init__(self, seed: int = 20261110):
        self.seed = int(seed)

    def simulate(self, scenario: Scenario, iterations: int = 10_000, seed: int | None = None) -> SimulationResult:
        if iterations < 100 or iterations > 1_000_000:
            raise ValueError("iterations must be between 100 and 1,000,000")
        rng = Random(self.seed if seed is None else int(seed))
        revenue = float(scenario.average_order_value) * scenario.order_count
        variable_cost = revenue * scenario.variable_cost_rate
        processing = revenue * scenario.payment_fee_rate
        outcomes: list[float] = []
        for _ in range(iterations):
            refunds = sum(rng.random() < scenario.refund_rate for _ in range(scenario.order_count))
            disputes = sum(rng.random() < scenario.dispute_rate for _ in range(scenario.order_count))
            refund_cost = refunds * float(scenario.average_order_value) * scenario.refund_loss_multiplier
            dispute_cost = disputes * float(scenario.average_order_value) * scenario.dispute_loss_multiplier
            net = revenue - variable_cost - processing - refund_cost - dispute_cost - float(scenario.fixed_cost)
            outcomes.append(net)
        ordered = sorted(outcomes)
        def pct(q: float) -> float:
            index = (len(ordered) - 1) * q
            low = int(index); high = min(low + 1, len(ordered) - 1)
            fraction = index - low
            return ordered[low] * (1 - fraction) + ordered[high] * fraction
        actual_seed = self.seed if seed is None else int(seed)
        return SimulationResult(
            scenario_name=scenario.name, iterations=iterations,
            mean_net_revenue=mean(outcomes), median_net_revenue=median(outcomes),
            p05_net_revenue=pct(.05), p95_net_revenue=pct(.95),
            probability_of_loss=sum(value < 0 for value in outcomes) / iterations,
            assumptions={
                "order_count_fixed": scenario.order_count,
                "average_order_value": str(scenario.average_order_value),
                "refund_rate": scenario.refund_rate, "dispute_rate": scenario.dispute_rate,
                "variable_cost_rate": scenario.variable_cost_rate, "payment_fee_rate": scenario.payment_fee_rate,
                "fixed_cost": str(scenario.fixed_cost),
                "sampling": "independent Bernoulli per order; fixed order count and AOV",
                "limitations": "scenario analysis only; not a calibrated prediction or accounting ledger",
            }, seed=actual_seed,
        )

    def compare(self, scenarios: Iterable[Scenario], iterations: int = 10_000) -> list[SimulationResult]:
        return [self.simulate(scenario, iterations=iterations, seed=self.seed + index) for index, scenario in enumerate(scenarios)]
