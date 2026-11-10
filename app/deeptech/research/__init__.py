"""MerchantOS Research Engine: deterministic financial intelligence primitives.

This package is an experimental decision-support layer. It never executes
payments, mutates provider state, or grants authorization. All outputs are
explanatory and must pass through the established policy and approval services.
"""
from .types import Observation, Finding, Metric, ModelResult
from .money import Money, MoneyBag
from .pipeline import IntelligencePipeline

__all__ = ["Observation", "Finding", "Metric", "ModelResult", "Money", "MoneyBag", "IntelligencePipeline"]
