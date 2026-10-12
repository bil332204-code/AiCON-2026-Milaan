"""
rules.py – Phase A: Rule-based matching baseline.

Deliberately kept simple and defensible. Thresholds are read from
config.py so they can be tuned on a validation split without changing
this file.

Decision table
──────────────
Condition                                                          → Label
─────────────────────────────────────────────────────────────────────────
Amount exact AND name_combined ≥ SHIP_THRESHOLD AND 1 candidate   → SHIP
Amount exact AND name_combined ∈ [REVIEW_THRESHOLD, SHIP_THRESHOLD) → AMBIGUOUS
  OR (exact + high name + multiple plausible candidates)
Amount exact AND name_combined < REVIEW_THRESHOLD                  → REVIEW
Amount NOT exact (within tolerance) AND name ≥ SHIP_THRESHOLD     → AMBIGUOUS
Amount NOT exact AND name < REVIEW_THRESHOLD                       → REVIEW
No candidate AND order younger than SETTLEMENT_DAYS               → PENDING
No candidate AND order older than SETTLEMENT_DAYS                 → REVIEW
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from matching.config import (
    RULE_AMOUNT_EXACT_FRACTION,
    RULE_AMOUNT_EXACT_ABS,
    RULE_NAME_SHIP_THRESHOLD,
    RULE_NAME_REVIEW_THRESHOLD,
    SETTLEMENT_DAYS,
)
from matching.features import extract_features
from matching.names import name_similarity
from matching.schemas import Label, MatchResult, Order, Transaction


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _amount_exact(order_amount: float, txn_amount: float) -> bool:
    diff = abs(txn_amount - order_amount)
    return diff <= RULE_AMOUNT_EXACT_ABS or diff / max(order_amount, 1) <= RULE_AMOUNT_EXACT_FRACTION


def _is_pending(order: Order) -> bool:
    """True if the order is too young to expect settlement."""
    now = datetime.now(timezone.utc)
    age_days = (now - order.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400
    return age_days < SETTLEMENT_DAYS


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def apply_rules(
    order:      Order,
    candidates: list[Transaction],
) -> MatchResult:
    """
    Apply the rule-based decision table for a single order.

    Parameters
    ----------
    order : Order
    candidates : list[Transaction]
        Pre-filtered candidate transactions (from candidates.py).

    Returns
    -------
    MatchResult
    """
    if not candidates:
        label  = Label.PENDING if _is_pending(order) else Label.REVIEW
        reason = (
            "no candidate transactions found; order within settlement window"
            if label == Label.PENDING
            else "no candidate transactions found after settlement window"
        )
        return MatchResult(
            order_id=order.order_id,
            txn_ids=[],
            score=0.0,
            label=label,
            reason=reason,
            engine="rules",
        )

    # Compute name scores for every candidate and pick the best
    scored = []
    for txn in candidates:
        ns       = name_similarity(order.customer_name, txn.sender)
        name_sim = ns.combined()
        exact    = _amount_exact(order.amount, txn.amount)
        feats    = extract_features(order, txn, all_candidates=candidates)
        scored.append((txn, name_sim, exact, feats))

    # Sort by name_sim descending (amount exact first as a tie-break)
    scored.sort(key=lambda x: (x[2], x[1]), reverse=True)

    best_txn, best_name, best_exact, best_feats = scored[0]
    n_plausible = sum(1 for _, ns, ex, _ in scored if ns >= RULE_NAME_REVIEW_THRESHOLD)

    # ── Decision table ────────────────────────────────────────────────────────
    if best_exact:
        if best_name >= RULE_NAME_SHIP_THRESHOLD and n_plausible == 1:
            label  = Label.SHIP
            score  = 0.95
            reason = (
                f"amount exact, name {best_name:.2f}, "
                f"{abs((best_txn.datetime - order.created_at).total_seconds() / 3600):.1f}h gap"
            )
        elif best_name >= RULE_NAME_REVIEW_THRESHOLD or n_plausible > 1:
            label  = Label.AMBIGUOUS
            score  = 0.65
            reason = (
                f"amount exact, name {best_name:.2f}"
                + (f", {n_plausible} plausible candidates" if n_plausible > 1 else "")
            )
        else:
            label  = Label.REVIEW
            score  = 0.30
            reason = f"amount exact but name similarity low ({best_name:.2f})"
    else:
        rel_diff = abs(best_txn.amount - order.amount) / max(order.amount, 1)
        if best_name >= RULE_NAME_SHIP_THRESHOLD:
            label  = Label.AMBIGUOUS
            score  = 0.60
            reason = f"amount mismatch ({rel_diff:.1%}), name {best_name:.2f}"
        else:
            label  = Label.REVIEW
            score  = 0.20
            reason = f"amount mismatch ({rel_diff:.1%}), name {best_name:.2f}"

    return MatchResult(
        order_id=order.order_id,
        txn_ids=[best_txn.txn_id],
        score=score,
        label=label,
        reason=reason,
        features=best_feats,
        engine="rules",
    )


def run_rules(
    orders:     list[Order],
    candidates: dict[str, list[Transaction]],
) -> list[MatchResult]:
    """
    Apply rule-based matching to all orders.

    Parameters
    ----------
    orders : list[Order]
    candidates : dict[order_id → list[Transaction]]

    Returns
    -------
    list[MatchResult]
    """
    return [apply_rules(order, candidates.get(order.order_id, [])) for order in orders]
