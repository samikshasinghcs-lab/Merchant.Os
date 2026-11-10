"""Append-only double-entry research ledger with balancing invariants."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Iterable, Mapping
from .money import Money, decimal_value

@dataclass(frozen=True, slots=True)
class Posting:
    account: str
    amount: Money
    side: str
    def __post_init__(self) -> None:
        if not self.account: raise ValueError("account required")
        if self.side not in {"debit","credit"}: raise ValueError("side must be debit or credit")
        if self.amount.amount<0: raise ValueError("posting amount must be non-negative")

@dataclass(frozen=True, slots=True)
class JournalEntry:
    entry_id: str
    tenant_id: str
    occurred_at: datetime
    description: str
    postings: tuple[Posting,...]
    reference: str = ""
    def __post_init__(self) -> None:
        if not self.entry_id or not self.tenant_id or not self.description: raise ValueError("entry identity and description required")
        if self.occurred_at.tzinfo is None: raise ValueError("occurred_at must be timezone-aware")
        if len(self.postings)<2: raise ValueError("double-entry requires at least two postings")
        currencies={p.amount.currency for p in self.postings}
        if len(currencies)!=1: raise ValueError("journal entry cannot mix currencies")
        debit=sum((p.amount.amount for p in self.postings if p.side=="debit"),Decimal(0))
        credit=sum((p.amount.amount for p in self.postings if p.side=="credit"),Decimal(0))
        if debit!=credit: raise ValueError("journal entry is not balanced")
    @property
    def currency(self) -> str: return self.postings[0].amount.currency
    def digest(self) -> str:
        payload={"entry_id":self.entry_id,"tenant_id":self.tenant_id,"occurred_at":self.occurred_at.astimezone(timezone.utc).isoformat(),"description":self.description,"reference":self.reference,"postings":[{"account":p.account,"amount":str(p.amount.amount),"currency":p.amount.currency,"side":p.side} for p in self.postings]}
        return sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class Ledger:
    def __init__(self,tenant_id: str) -> None:
        if not tenant_id: raise ValueError("tenant_id required")
        self.tenant_id=tenant_id; self._entries=[]; self._ids=set()
    def append(self,entry: JournalEntry) -> str:
        if entry.tenant_id!=self.tenant_id: raise PermissionError("cross-tenant ledger write rejected")
        if entry.entry_id in self._ids: raise ValueError("duplicate journal entry")
        digest=entry.digest(); self._entries.append((entry,digest)); self._ids.add(entry.entry_id); return digest
    def entries(self) -> tuple[JournalEntry,...]: return tuple(entry for entry,_ in self._entries)
    def balance(self,account: str,currency: str) -> Decimal:
        total=Decimal(0)
        for entry,_ in self._entries:
            for posting in entry.postings:
                if posting.account==account and posting.amount.currency==currency.upper():
                    total+=posting.amount.amount if posting.side=="debit" else -posting.amount.amount
        return total
    def trial_balance(self,currency: str) -> Mapping[str,Decimal]:
        accounts={p.account for e,_ in self._entries for p in e.postings if p.amount.currency==currency.upper()}
        return {account:self.balance(account,currency) for account in sorted(accounts)}
    def verify(self) -> bool:
        return all(entry.digest()==digest for entry,digest in self._entries)
