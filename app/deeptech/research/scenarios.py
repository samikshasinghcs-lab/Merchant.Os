"""Named stress scenarios and parameter validation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    scenario_id: str
    description: str
    shocks: Mapping[str,float]
    severity: str
    def __post_init__(self):
        if not self.scenario_id or not self.description or not self.shocks: raise ValueError("scenario identity and shocks required")
        if self.severity not in {"low","moderate","severe","extreme"}: raise ValueError("invalid severity")
        if any(not __import__("math").isfinite(float(v)) for v in self.shocks.values()): raise ValueError("shocks must be finite")

class ScenarioLibrary:
    def __init__(self): self._scenarios={}
    def register(self,scenario: ScenarioDefinition) -> None:
        if scenario.scenario_id in self._scenarios: raise ValueError("scenario already exists")
        self._scenarios[scenario.scenario_id]=scenario
    def get(self,scenario_id: str) -> ScenarioDefinition: return self._scenarios[scenario_id]
    def list(self) -> tuple[ScenarioDefinition,...]: return tuple(self._scenarios[key] for key in sorted(self._scenarios))
    def apply(self,scenario_id: str,baseline: Mapping[str,float]) -> dict:
        scenario=self.get(scenario_id)
        unknown=set(scenario.shocks)-set(baseline)
        if unknown: raise ValueError(f"scenario references unknown dimensions: {sorted(unknown)}")
        result={key:float(value) for key,value in baseline.items()}
        for key,shock in scenario.shocks.items(): result[key]*=(1+shock)
        return result

def standard_scenarios() -> ScenarioLibrary:
    library=ScenarioLibrary()
    library.register(ScenarioDefinition("refund_surge","Refund rate increases materially",{"refund_rate":.5},"moderate"))
    library.register(ScenarioDefinition("dispute_surge","Dispute rate doubles",{"dispute_rate":1.0},"severe"))
    library.register(ScenarioDefinition("demand_shock","Order volume declines",{"order_volume":-.3},"severe"))
    library.register(ScenarioDefinition("fee_increase","Payment processing costs rise",{"fee_rate":.2},"moderate"))
    return library
