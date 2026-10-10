"""
assign.py – Conflict resolution for matching.

Problem: a single transaction may be a plausible candidate for multiple
orders. We need to ensure each transaction is assigned to at most one order.

Two strategies are provided:
  1. greedy_assign: fast O(n log n) – good for production
  2. hungarian_assign: optimal O(n³) – good for small batches and demo

Both accept the same input and produce the same output format.
"""
from __future__ import annotations

import numpy as np


def greedy_assign(
    order_scores: dict[str, list[tuple[str, float, dict]]],
) -> dict[str, tuple[str, float, dict]]:
    """
    Greedy conflict resolution: sort all (order, txn, prob) triples by
    probability descending, then claim the best unclaimed txn for each order.

    Parameters
    ----------
    order_scores : dict
        order_id → list of (txn_id, probability, feature_dict)

    Returns
    -------
    dict
        order_id → (txn_id, probability, feature_dict) for assigned orders.
        Orders with no valid assignment are omitted (caller handles them).
    """
    # Flatten and sort all triples by probability
    triples: list[tuple[float, str, str, dict]] = []
    for order_id, candidates in order_scores.items():
        for txn_id, prob, feats in candidates:
            triples.append((prob, order_id, txn_id, feats))
    triples.sort(reverse=True)

    claimed_txns:   set[str] = set()
    claimed_orders: set[str] = set()
    assignment:     dict[str, tuple[str, float, dict]] = {}

    for prob, order_id, txn_id, feats in triples:
        if order_id in claimed_orders or txn_id in claimed_txns:
            continue
        assignment[order_id] = (txn_id, prob, feats)
        claimed_txns.add(txn_id)
        claimed_orders.add(order_id)

    return assignment


def hungarian_assign(
    order_scores: dict[str, list[tuple[str, float, dict]]],
) -> dict[str, tuple[str, float, dict]]:
    """
    Optimal assignment using the Hungarian algorithm (scipy linear_sum_assignment).
    Maximises the sum of probabilities across all assignments.

    Falls back to greedy_assign if scipy is not available.

    Parameters
    ----------
    order_scores : dict
        Same format as greedy_assign.

    Returns
    -------
    dict
        Same format as greedy_assign.
    """
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        import warnings
        warnings.warn("scipy not installed; falling back to greedy_assign.")
        return greedy_assign(order_scores)

    order_ids = list(order_scores.keys())
    # Collect the union of all txn_ids
    txn_id_set: set[str] = set()
    for cands in order_scores.values():
        for txn_id, _, _ in cands:
            txn_id_set.add(txn_id)
    txn_ids = list(txn_id_set)

    n_orders = len(order_ids)
    n_txns   = len(txn_ids)

    order_idx = {oid: i for i, oid in enumerate(order_ids)}
    txn_idx   = {tid: j for j, tid in enumerate(txn_ids)}

    # Cost matrix: we *maximize* probability, so cost = 1 - prob
    cost = np.ones((n_orders, n_txns))  # default = 1 (no match)
    feat_store: dict[tuple[int, int], dict] = {}

    for order_id, cands in order_scores.items():
        i = order_idx[order_id]
        for txn_id, prob, feats in cands:
            j = txn_idx[txn_id]
            cost[i, j] = 1.0 - prob
            feat_store[(i, j)] = (txn_id, prob, feats)

    row_ind, col_ind = linear_sum_assignment(cost)

    assignment: dict[str, tuple[str, float, dict]] = {}
    for i, j in zip(row_ind, col_ind):
        if (i, j) in feat_store and cost[i, j] < 1.0:
            txn_id, prob, feats = feat_store[(i, j)]
            assignment[order_ids[i]] = (txn_id, prob, feats)

    return assignment
