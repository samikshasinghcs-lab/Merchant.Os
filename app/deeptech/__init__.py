"""MerchantOS DeepTech: deterministic financial intelligence primitives.

This package deliberately separates observation, statistical inference, simulation,
policy, and execution. Nothing in this package can move money or authorize refunds.
"""

__version__ = "0.2.0"

from .models import Transaction, TransactionStatus, AnomalyFinding, Scenario, SimulationResult
from .fingerprints import transaction_fingerprint, feature_vector
from .anomaly import RobustAnomalyDetector, AnomalyConfig
from .graph import TransactionGraph
from .digital_twin import FinancialDigitalTwin
from .assurance import HashChain, AuditEvent

__all__ = [
    "Transaction", "TransactionStatus", "AnomalyFinding", "Scenario", "SimulationResult",
    "transaction_fingerprint", "feature_vector", "RobustAnomalyDetector", "AnomalyConfig",
    "TransactionGraph", "FinancialDigitalTwin", "HashChain", "AuditEvent",
]
