"""
matching/__init__.py

Public API – a single function:

    match(orders, txns, engine="rules", scorer=None) -> list[MatchResult]

Both the REST API (Module 1) and the evaluation harness use this exact
function, so results are always produced through an identical code path.
"""
from __future__ import annotations

from matching.candidates import get_all_candidates

from matching.rules import run_rules
from matching.schemas import MatchResult, Order, Transaction


def match(
    orders:  list[Order],
    txns:    list[Transaction],
    *,
    engine:  str    = "rules",
    scorer:  Scorer | None = None,
) -> list[MatchResult]:
    """
    Reconcile a list of orders against a list of bank transactions.

    Parameters
    ----------
    orders : list[Order]
        Pending orders awaiting payment confirmation.
    txns : list[Transaction]
        Normalized bank transactions (from Module 2).
    engine : "rules" | "ml"
        Which scoring engine to use.
    scorer : Scorer | None
        Required when engine="ml". Load with Scorer.load(path).

    Returns
    -------
    list[MatchResult]
        One MatchResult per order, in the same order as `orders`.

    Examples
    --------
    # Rule-based
    results = match(orders, txns, engine="rules")

    # ML
    from matching import Scorer
    scorer  = Scorer.load("models/lgbm_matcher.pkl")
    results = match(orders, txns, engine="ml", scorer=scorer)
    """
    candidates = get_all_candidates(orders, txns)

    if engine == "rules":
        return run_rules(orders, candidates)

    if engine == "ml":
        from matching.model import run_ml
        if scorer is None:
            raise ValueError("scorer must be provided when engine='ml'.")
        return run_ml(orders, candidates, scorer)

    raise ValueError(f"Unknown engine '{engine}'. Choose 'rules' or 'ml'.")


# Re-export key types so callers only need to import from `matching`
from matching.schemas import (    # noqa: F401, E402
    Order,
    Transaction,
    MatchResult,
    Label,
    TxnType,
    Correction,
)


def __getattr__(name):
    if name in {"Scorer", "Trainer"}:
        from matching import model
        return getattr(model,name)
    raise AttributeError(name)
