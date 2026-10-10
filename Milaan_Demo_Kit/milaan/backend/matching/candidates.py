"""
candidates.py – Blocking / candidate generation.

For each order, we reject transactions that cannot possibly be a match
before computing any features. This reduces O(orders × txns) comparisons
to something tractable.

Blocking criteria (all must hold):
  1. Time window: txn.datetime within [order.created_at - BEFORE, + AFTER]
  2. Amount tolerance: |txn.amount - order.amount| ≤ max(ABS, order.amount * FRACTION)
  3. Transaction type: only CREDIT (a payment coming in); reversals handled separately
"""
from __future__ import annotations

from datetime import timedelta

from matching.config import (
    WINDOW_HOURS_BEFORE,
    WINDOW_HOURS_AFTER,
    AMOUNT_TOLERANCE_FRACTION,
    AMOUNT_TOLERANCE_ABS,
)
from matching.schemas import Order, Transaction, TxnType


def _amount_ok(order_amount: float, txn_amount: float) -> bool:
    """Return True if txn_amount is within the configured tolerance of order_amount."""
    tolerance = max(AMOUNT_TOLERANCE_ABS, order_amount * AMOUNT_TOLERANCE_FRACTION)
    return abs(txn_amount - order_amount) <= tolerance


def _time_ok(order: Order, txn: Transaction) -> bool:
    """Return True if the transaction falls within the configured time window."""
    earliest = order.created_at - timedelta(hours=WINDOW_HOURS_BEFORE)
    latest   = order.created_at + timedelta(hours=WINDOW_HOURS_AFTER)
    return earliest <= txn.datetime <= latest


def get_candidates(
    order: Order,
    transactions: list[Transaction],
    *,
    include_reversals: bool = False,
) -> list[Transaction]:
    """
    Return the subset of *transactions* that could plausibly match *order*.

    Parameters
    ----------
    order : Order
    transactions : list[Transaction]
        Full pool of available transactions.
    include_reversals : bool
        Set True only when Module 4 is looking for refund linkages.

    Returns
    -------
    list[Transaction]
        Filtered list sorted by time gap (ascending).
    """
    allowed_types = {TxnType.CREDIT}
    if include_reversals:
        allowed_types.add(TxnType.REVERSAL)

    candidates = [
        txn for txn in transactions
        if txn.type in allowed_types
        and _time_ok(order, txn)
        and _amount_ok(order.amount, txn.amount)
    ]

    # Sort by absolute time gap so the "closest in time" is first
    candidates.sort(key=lambda t: abs((t.datetime - order.created_at).total_seconds()))
    return candidates


def get_all_candidates(
    orders: list[Order],
    transactions: list[Transaction],
) -> dict[str, list[Transaction]]:
    """
    Run candidate generation for every order.

    Returns
    -------
    dict[order_id → list[Transaction]]
    """
    return {
        order.order_id: get_candidates(order, transactions)
        for order in orders
    }
