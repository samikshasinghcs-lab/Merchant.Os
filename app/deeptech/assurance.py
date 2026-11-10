"""Tamper-evident, append-only hash-chain primitives for audit evidence."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, hmac, json, threading
from pathlib import Path
from typing import Any, Iterable, Mapping
from .fingerprints import canonical_json

GENESIS_HASH = "0" * 64

@dataclass(frozen=True, slots=True)
class AuditEvent:
    sequence: int
    event_id: str
    event_type: str
    occurred_at: str
    actor_ref: str
    subject_ref: str
    payload: Mapping[str, Any]
    previous_hash: str
    event_hash: str

    def unsigned(self) -> dict[str, Any]:
        return {"sequence": self.sequence, "event_id": self.event_id, "event_type": self.event_type,
                "occurred_at": self.occurred_at, "actor_ref": self.actor_ref,
                "subject_ref": self.subject_ref, "payload": dict(self.payload), "previous_hash": self.previous_hash}

class HashChain:
    """Single-process hash chain. Production deployments need durable DB/WORM storage,
    concurrency control, key management, retention policy and external anchoring.
    A hash chain detects edits but does not prevent an attacker from rewriting the
    entire chain if they control both data and trusted checkpoints.
    """
    def __init__(self, events: Iterable[AuditEvent] = ()):
        self._events = list(events)
        self._lock = threading.RLock()
        valid, _ = self.verify()
        if not valid:
            raise ValueError("initial audit chain is invalid")

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @staticmethod
    def _digest(unsigned: Mapping[str, Any]) -> str:
        return hashlib.sha256(canonical_json(unsigned)).hexdigest()

    def append(self, event_type: str, actor_ref: str, subject_ref: str, payload: Mapping[str, Any], event_id: str | None = None, occurred_at: datetime | None = None) -> AuditEvent:
        if not event_type or not actor_ref or not subject_ref:
            raise ValueError("event_type, actor_ref and subject_ref are required")
        with self._lock:
            previous = self._events[-1].event_hash if self._events else GENESIS_HASH
            sequence = len(self._events) + 1
            timestamp = (occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
            unsigned = {"sequence": sequence, "event_id": event_id or f"evt_{sequence:08d}",
                        "event_type": event_type, "occurred_at": timestamp,
                        "actor_ref": actor_ref, "subject_ref": subject_ref,
                        "payload": dict(payload), "previous_hash": previous}
            digest = self._digest(unsigned)
            event = AuditEvent(**unsigned, event_hash=digest)
            self._events.append(event)
            return event

    def verify(self) -> tuple[bool, dict[str, Any]]:
        with self._lock:
            previous = GENESIS_HASH
            for index, event in enumerate(self._events, start=1):
                unsigned = event.unsigned()
                if event.sequence != index:
                    return False, {"reason": "SEQUENCE_GAP", "sequence": index}
                if event.previous_hash != previous:
                    return False, {"reason": "PREVIOUS_HASH_MISMATCH", "sequence": index}
                expected = self._digest(unsigned)
                if not hmac.compare_digest(expected, event.event_hash):
                    return False, {"reason": "EVENT_HASH_MISMATCH", "sequence": index}
                previous = event.event_hash
            return True, {"event_count": len(self._events), "head_hash": previous}

    def export_jsonl(self, path: str | Path) -> Path:
        target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        with self._lock, temporary.open("w", encoding="utf-8") as stream:
            for event in self._events:
                stream.write(json.dumps({**event.unsigned(), "event_hash": event.event_hash}, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
        temporary.replace(target)
        return target

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "HashChain":
        events = []
        with Path(path).open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                raw = json.loads(line)
                try:
                    events.append(AuditEvent(**raw))
                except TypeError as exc:
                    raise ValueError(f"invalid audit record at line {line_number}") from exc
        return cls(events)
