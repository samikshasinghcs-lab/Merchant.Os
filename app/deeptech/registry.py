"""Lightweight immutable metadata registry for reproducible analytical artifacts."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from typing import Any, Mapping

@dataclass(frozen=True, slots=True)
class ModelCard:
    name: str
    version: str
    artifact_sha256: str
    created_at: str
    intended_use: str
    prohibited_use: str
    training_data_ref: str
    evaluation_ref: str
    features: tuple[str,...]
    limitations: tuple[str,...]

    @classmethod
    def create(cls, name: str, version: str, artifact: bytes, intended_use: str, prohibited_use: str, training_data_ref: str, evaluation_ref: str, features: tuple[str,...], limitations: tuple[str,...]) -> "ModelCard":
        if not all((name,version,intended_use,prohibited_use,training_data_ref,evaluation_ref)):
            raise ValueError("model card requires complete provenance and intended-use fields")
        return cls(name,version,hashlib.sha256(artifact).hexdigest(),datetime.now(timezone.utc).isoformat(),intended_use,prohibited_use,training_data_ref,evaluation_ref,features,limitations)

class ModelRegistry:
    """File-backed metadata index; model artifacts themselves remain separately stored."""
    def __init__(self, path: str | Path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if not self.path.exists(): self.path.write_text("[]",encoding="utf-8")

    def list_cards(self) -> list[dict[str,Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def register(self, card: ModelCard) -> None:
        cards=self.list_cards()
        key=(card.name,card.version)
        if any((item["name"],item["version"])==key for item in cards):
            raise ValueError("model name/version already registered")
        cards.append(asdict(card))
        temporary=self.path.with_suffix(self.path.suffix+".tmp")
        temporary.write_text(json.dumps(cards,sort_keys=True,indent=2),encoding="utf-8")
        temporary.replace(self.path)

    def get(self,name: str,version: str) -> dict[str,Any] | None:
        return next((item for item in self.list_cards() if item["name"]==name and item["version"]==version),None)
