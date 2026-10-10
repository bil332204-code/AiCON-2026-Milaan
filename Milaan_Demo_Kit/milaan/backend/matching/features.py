"""
features.py – Feature extraction for (Order, Transaction) pairs.

Returns a flat dict of numeric features consumed by:
  • Phase A (rules.py)  – uses a subset (name_combined, amount_diff, …)
  • Phase B (model.py)  – uses the full dict as the feature vector

All features are deterministic floats between well-known ranges so no
extra scaling is required for tree models like LightGBM.
"""
from __future__ import annotations

import re
from datetime import datetime

from matching.names import name_similarity
from matching.schemas import Order, Transaction


# ─────────────────────────────────────────────
# Reference / memo helpers
# ─────────────────────────────────────────────

def _ref_contains_order_id(ref: str, order_id: str) -> float:
    """1.0 if reference text contains the order ID, else 0.0."""
    return float(bool(ref and order_id and order_id.lower() in ref.lower()))


def _ref_contains_phone(ref: str, phone: str | None) -> float:
    """1.0 if reference text contains the last 7+ digits of the phone number."""
    if not ref or not phone:
        return 0.0
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return 0.0
    return float(digits[-7:] in re.sub(r"\D", "", ref))


# ─────────────────────────────────────────────
# Main feature extractor
# ─────────────────────────────────────────────

def extract_features(
    order:      Order,
    txn:        Transaction,
    all_candidates: list[Transaction],
    *,
    n_orders_competing: int = 1,
) -> dict[str, float]:
    """
    Compute all features for one (order, transaction) candidate pair.

    Parameters
    ----------
    order : Order
    txn : Transaction
    all_candidates : list[Transaction]
        All candidate txns for *this* order (used for competition features).
    n_orders_competing : int
        Number of orders that have *txn* as a candidate (inter-order competition).

    Returns
    -------
    dict[str, float]
        Feature names → float values.
    """
    feats: dict[str, float] = {}

    # ── Amount features ──────────────────────────────────────────────────────
    abs_diff       = abs(txn.amount - order.amount)
    rel_diff       = abs_diff / max(order.amount, 1.0)
    exact_flag     = float(rel_diff <= 0.01 and abs_diff <= 10.0)
    partial_50     = float(abs(txn.amount - order.amount / 2) / max(order.amount / 2, 1) <= 0.05)
    over_payment   = float(txn.amount > order.amount)
    under_payment  = float(txn.amount < order.amount)

    feats["amount_abs_diff"]    = abs_diff
    feats["amount_rel_diff"]    = rel_diff
    feats["amount_exact"]       = exact_flag
    feats["amount_partial_50"]  = partial_50
    feats["amount_over"]        = over_payment
    feats["amount_under"]       = under_payment

    # ── Time features ────────────────────────────────────────────────────────
    gap_seconds = (txn.datetime - order.created_at).total_seconds()
    gap_hours   = gap_seconds / 3600.0

    feats["time_gap_hours"]     = gap_hours
    feats["time_gap_abs_hours"] = abs(gap_hours)
    feats["time_before_order"]  = float(gap_hours < 0)           # advance payment
    feats["time_weekend"]       = float(txn.datetime.weekday() >= 5)
    feats["time_day_of_week"]   = float(txn.datetime.weekday())

    # ── Name features (all sub-scores) ───────────────────────────────────────
    ns = name_similarity(order.customer_name, txn.sender)
    feats.update(ns.as_dict())

    # ── Reference / memo features ────────────────────────────────────────────
    feats["ref_has_order_id"] = _ref_contains_order_id(txn.reference, order.order_id)
    feats["ref_has_phone"]    = _ref_contains_phone(txn.reference, order.phone)

    # ── Competition features (critical for ambiguity detection) ──────────────
    n_cands = len(all_candidates)
    if n_cands > 1:
        # Score this candidate relative to all others for the same order
        # (proxy: use amount_rel_diff as a cheap rank signal)
        sorted_cands = sorted(all_candidates, key=lambda t: abs(t.amount - order.amount))
        rank = next((i for i, t in enumerate(sorted_cands) if t.txn_id == txn.txn_id), 0)
        feats["competition_n_candidates"]    = float(n_cands)
        feats["competition_candidate_rank"]  = float(rank)
        feats["competition_is_best"]         = float(rank == 0)

        # Score gap to second-best (lower diff = closer amounts)
        if n_cands >= 2:
            best_diff   = abs(sorted_cands[0].amount - order.amount)
            second_diff = abs(sorted_cands[1].amount - order.amount)
            feats["competition_amount_gap_to_2nd"] = abs(second_diff - best_diff)
        else:
            feats["competition_amount_gap_to_2nd"] = float(abs_diff)
    else:
        feats["competition_n_candidates"]       = 1.0
        feats["competition_candidate_rank"]     = 0.0
        feats["competition_is_best"]            = 1.0
        feats["competition_amount_gap_to_2nd"]  = float(abs_diff)

    feats["competition_n_orders_for_txn"] = float(n_orders_competing)

    return feats


def extract_all_features(
    orders:      list[Order],
    candidates:  dict[str, list[Transaction]],
) -> list[tuple[str, str, dict[str, float]]]:
    """
    Compute features for every (order, candidate_txn) pair.

    Also computes n_orders_competing per txn (how many orders list this txn).

    Returns
    -------
    list of (order_id, txn_id, feature_dict)
    """
    # Count how many orders each txn appears in
    txn_order_count: dict[str, int] = {}
    for txn_list in candidates.values():
        for txn in txn_list:
            txn_order_count[txn.txn_id] = txn_order_count.get(txn.txn_id, 0) + 1

    # Build order lookup
    order_map = {o.order_id: o for o in orders}

    rows = []
    for order_id, txn_list in candidates.items():
        order = order_map[order_id]
        for txn in txn_list:
            feats = extract_features(
                order, txn,
                all_candidates=txn_list,
                n_orders_competing=txn_order_count.get(txn.txn_id, 1),
            )
            rows.append((order_id, txn.txn_id, feats))
    return rows
