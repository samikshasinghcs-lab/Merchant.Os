"""Observational association analysis that deliberately avoids causal overclaiming."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt, erfc
from typing import Iterable, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class AssociationResult:
    exposure: str
    outcome: str
    exposed_outcome_rate: float
    unexposed_outcome_rate: float
    risk_difference: float
    risk_ratio: float | None
    odds_ratio: float | None
    chi_square: float
    p_value_approx: float
    sample_size: int
    interpretation: str
    caveats: tuple[str, ...]

def _safe_rate(success: int, total: int) -> float:
    return success / total if total else 0.0

def binary_association(rows: Iterable[Mapping[str, object]], exposure: str, outcome: str) -> AssociationResult:
    """Compute a 2x2 association table and Pearson chi-square approximation.

    This is not causal identification. Confounding, selection bias, temporal order,
    multiple testing and sparse cells can invalidate a naive interpretation.
    """
    cells = {"a": 0, "b": 0, "c": 0, "d": 0}
    n = 0
    for row in rows:
        if exposure not in row or outcome not in row:
            continue
        e, y = bool(row[exposure]), bool(row[outcome]); n += 1
        if e and y: cells["a"] += 1
        elif e and not y: cells["b"] += 1
        elif not e and y: cells["c"] += 1
        else: cells["d"] += 1
    a,b,c,d = (cells[k] for k in ("a","b","c","d"))
    exposed_total, unexposed_total = a+b, c+d
    r1, r0 = _safe_rate(a, exposed_total), _safe_rate(c, unexposed_total)
    risk_ratio = r1/r0 if r0 > 0 else None
    odds_ratio = (a*d)/(b*c) if b*c else None
    total = n
    row1, row0 = a+b, c+d
    col1, col0 = a+c, b+d
    expected = [row1*col1/total, row1*col0/total, row0*col1/total, row0*col0/total] if total else [0]*4
    observed = [a,b,c,d]
    chi = sum((o-e)**2/e for o,e in zip(observed, expected) if e > 0)
    p = erfc(sqrt(chi/2)) if total else 1.0  # df=1 asymptotic tail probability
    return AssociationResult(
        exposure=exposure, outcome=outcome, exposed_outcome_rate=r1,
        unexposed_outcome_rate=r0, risk_difference=r1-r0,
        risk_ratio=risk_ratio, odds_ratio=odds_ratio, chi_square=chi,
        p_value_approx=p, sample_size=n,
        interpretation="OBSERVATIONAL_ASSOCIATION_ONLY",
        caveats=("Not causal evidence.", "Confounding and selection bias are not controlled.",
                 "Chi-square p-value is asymptotic; use exact methods for sparse cells.",
                 "Pre-register hypotheses and correct for multiple comparisons."),
    )

def candidate_root_cause_hypotheses(rows: Sequence[Mapping[str, object]], candidate_fields: Sequence[str], outcome: str, minimum_group: int = 10) -> list[AssociationResult]:
    """Screen candidate binary fields; output ranked hypotheses, never causal claims."""
    if minimum_group < 2:
        raise ValueError("minimum_group must be at least 2")
    results = []
    for field in candidate_fields:
        present = sum(1 for row in rows if field in row and outcome in row)
        if present < minimum_group:
            continue
        result = binary_association(rows, field, outcome)
        if result.sample_size >= minimum_group:
            results.append(result)
    return sorted(results, key=lambda item: (abs(item.risk_difference), item.sample_size), reverse=True)
