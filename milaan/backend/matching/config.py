"""
Central configuration for the matching engine.
All thresholds live here so they can be tuned on a validation split
without touching business logic. They can also be overridden via
environment variables or a YAML file at runtime.
"""
from __future__ import annotations
import os

# ─────────────────────────────────────────────
# Time window (blocking step)
# ─────────────────────────────────────────────
# Maximum hours BEFORE an order was placed that a payment can still be matched
# (pre-payment / advance payment scenario)
WINDOW_HOURS_BEFORE: int   = int(os.getenv("WINDOW_HOURS_BEFORE", 24))
# Maximum hours AFTER an order was placed to look for a payment
WINDOW_HOURS_AFTER:  int   = int(os.getenv("WINDOW_HOURS_AFTER",  168))   # 7 days
# Orders younger than this (business days) get PENDING rather than REVIEW
SETTLEMENT_DAYS:     float = float(os.getenv("SETTLEMENT_DAYS", 2.5))

# ─────────────────────────────────────────────
# Amount tolerance (blocking step)
# ─────────────────────────────────────────────
AMOUNT_TOLERANCE_FRACTION: float = float(os.getenv("AMOUNT_TOLERANCE_FRACTION", 0.20))
# Absolute floor tolerance (e.g. rounding ±5 PKR is always fine)
AMOUNT_TOLERANCE_ABS:      float = float(os.getenv("AMOUNT_TOLERANCE_ABS", 5.0))

# ─────────────────────────────────────────────
# Rule-based thresholds (Phase A)
# ─────────────────────────────────────────────
# Name similarity to auto-SHIP on exact amount match
RULE_NAME_SHIP_THRESHOLD:      float = float(os.getenv("RULE_NAME_SHIP_THRESHOLD",      0.85))
# Name similarity below which we escalate to REVIEW even with correct amount
RULE_NAME_REVIEW_THRESHOLD:    float = float(os.getenv("RULE_NAME_REVIEW_THRESHOLD",    0.60))
# Amount "exact" tolerance as a fraction (e.g. 0.01 = within 1%)
RULE_AMOUNT_EXACT_FRACTION:    float = float(os.getenv("RULE_AMOUNT_EXACT_FRACTION",    0.01))
# Absolute amount exact tolerance (PKR)
RULE_AMOUNT_EXACT_ABS:         float = float(os.getenv("RULE_AMOUNT_EXACT_ABS",         10.0))

# ─────────────────────────────────────────────
# ML thresholds (Phase B)
# ─────────────────────────────────────────────
# Probability above which the ML scorer labels SHIP
ML_SHIP_THRESHOLD:      float = float(os.getenv("ML_SHIP_THRESHOLD",      0.90))
# Probability above which we label AMBIGUOUS (below → REVIEW)
ML_AMBIGUOUS_THRESHOLD: float = float(os.getenv("ML_AMBIGUOUS_THRESHOLD", 0.55))

# ─────────────────────────────────────────────
# Model persistence
# ─────────────────────────────────────────────
MODEL_PATH:     str = os.getenv("MODEL_PATH",     "models/lgbm_matcher.pkl")
FEEDBACK_PATH:  str = os.getenv("FEEDBACK_PATH",  "data/feedback.jsonl")
# Minimum corrections before a retrain is triggered
RETRAIN_TRIGGER: int = int(os.getenv("RETRAIN_TRIGGER", 50))

# ─────────────────────────────────────────────
# Name normalization
# ─────────────────────────────────────────────
# Honorifics stripped during normalization
HONORIFICS: set[str] = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "haji", "hajji",
    "malik", "ch", "chaudhry", "syed", "agha", "aga",
}
