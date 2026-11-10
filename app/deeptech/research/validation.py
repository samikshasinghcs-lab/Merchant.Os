"""Input validation and schema drift helpers for ingestion pipelines."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class ValidationIssue:
    row_index: int
    field: str
    code: str
    message: str

class RecordValidator:
    def __init__(self,required: Iterable[str],allowed: Iterable[str]|None=None):
        self.required=set(required); self.allowed=set(allowed) if allowed is not None else None
        if not self.required: raise ValueError("required schema cannot be empty")
    def validate(self,rows: Sequence[Mapping[str,object]]) -> tuple[ValidationIssue,...]:
        issues=[]
        for index,row in enumerate(rows):
            for field in sorted(self.required-set(row)): issues.append(ValidationIssue(index,field,"MISSING_REQUIRED","required field is missing"))
            if self.allowed is not None:
                for field in sorted(set(row)-self.allowed): issues.append(ValidationIssue(index,field,"UNKNOWN_FIELD","field is not in the approved schema"))
        return tuple(issues)
    def assert_valid(self,rows: Sequence[Mapping[str,object]]) -> None:
        issues=self.validate(rows)
        if issues: raise ValueError(f"dataset has {len(issues)} schema issue(s)")
    def schema_diff(self,observed_fields: Iterable[str]) -> dict:
        observed=set(observed_fields)
        expected=self.allowed or self.required
        return {"missing":tuple(sorted(expected-observed)),"unexpected":tuple(sorted(observed-expected)),"compatible":expected==observed}
