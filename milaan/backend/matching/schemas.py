"""
Shared data contracts for Module 3 – Matching Engine.
These schemas are the single source of truth used by all modules.
Module 1 (data layer) creates Orders and Transactions.
Module 2 (parser) emits Transaction objects.
Module 3 (matching engine) emits MatchResult objects.
Module 4 (frontend + anomalies) consumes MatchResult objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────
# Label enum
# ─────────────────────────────────────────────

class Label(str, Enum):
    SHIP      = "SHIP"       # Payment confirmed – safe to ship
    AMBIGUOUS = "AMBIGUOUS"  # Plausible match, human confirmation recommended
    REVIEW    = "REVIEW"     # No clear match – manual review required
    PENDING   = "PENDING"    # Order too new; payment may still arrive


# ─────────────────────────────────────────────
# Order (from Module 1)
# ─────────────────────────────────────────────

@dataclass
class Order:
    order_id:      str
    customer_name: str
    amount:        float          # PKR, expected payment total
    created_at:    datetime
    status:        str            # e.g. "pending", "paid", "shipped"
    phone:         Optional[str] = None
    notes:         Optional[str] = None   # any extra info for matching


# ─────────────────────────────────────────────
# Transaction (from Module 2)
# ─────────────────────────────────────────────

class TxnType(str, Enum):
    CREDIT   = "credit"
    DEBIT    = "debit"
    REVERSAL = "reversal"

@dataclass
class Transaction:
    txn_id:    str
    datetime:  datetime
    amount:    float
    sender:    str              # as printed on bank statement
    reference: str             # memo / reference field
    type:      TxnType
    bank:      Optional[str] = None


# ─────────────────────────────────────────────
# MatchResult (output of Module 3)
# ─────────────────────────────────────────────

@dataclass
class MatchResult:
    order_id:   str
    txn_ids:    list[str]       # one or more txn_ids (split payments → many)
    score:      float           # 0.0–1.0 confidence
    label:      Label
    reason:     str             # human-readable explanation shown in dashboard
    features:   dict = field(default_factory=dict)   # stored for ML and explainability
    engine:     str  = "rules"  # "rules" | "ml"


# ─────────────────────────────────────────────
# Correction (feedback loop – from Module 4)
# ─────────────────────────────────────────────

@dataclass
class Correction:
    order_id:        str
    original_label:  Label
    corrected_label: Label
    txn_ids:         list[str]
    features:        dict
    corrected_at:    datetime = field(default_factory=datetime.utcnow)
    corrected_by:    str      = "seller"
