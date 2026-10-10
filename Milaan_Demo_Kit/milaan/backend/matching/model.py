"""
model.py – Phase B: ML-based matching scorer.

Architecture
────────────
• Pairwise binary classifier: for each (order, txn) candidate pair,
  predict P(this txn pays this order).
• Model: LightGBM (fast, handles mixed features, no scaling needed).
• Calibration: Platt scaling (CalibratedClassifierCV) so probabilities
  are trustworthy enough to use as shipping thresholds.
• Threshold selection: Ship threshold is chosen on a VALIDATION set so
  that false-Ship rate ≤ target; everything below goes to Ambiguous.

Training
────────
  trainer = Trainer()
  trainer.fit(feature_rows, labels)
  trainer.save("models/lgbm_matcher.pkl")

Inference
─────────
  scorer = Scorer.load("models/lgbm_matcher.pkl")
  probs  = scorer.predict_proba(feature_rows)
"""
from __future__ import annotations

import os
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit

try:
    import lightgbm as lgb
    _HAS_LGB = True
except ImportError:
    _HAS_LGB = False
    warnings.warn("LightGBM not installed; falling back to LogisticRegression.")

from matching.config import ML_SHIP_THRESHOLD, ML_AMBIGUOUS_THRESHOLD, MODEL_PATH
from matching.features import extract_all_features
from matching.schemas import Label, MatchResult, Order, Transaction


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

LABEL_MAP = {Label.SHIP: 1, Label.AMBIGUOUS: 0, Label.REVIEW: 0, Label.PENDING: 0}


# ─────────────────────────────────────────────
# Trainer
# ─────────────────────────────────────────────

class Trainer:
    """Train and calibrate the ML scorer."""

    def __init__(self, ship_fpr_target: float = 0.005):
        """
        Parameters
        ----------
        ship_fpr_target : float
            Maximum acceptable false-Ship rate on the validation set.
            The Ship probability threshold is chosen to satisfy this constraint.
        """
        self.ship_fpr_target = ship_fpr_target
        self.model_            = None
        self.feature_names_:  list[str] = []
        self.ship_threshold_:  float    = ML_SHIP_THRESHOLD
        self.amb_threshold_:   float    = ML_AMBIGUOUS_THRESHOLD

    # ── Data prep ─────────────────────────────────────────────────────────────

    @staticmethod
    def prepare_dataset(
        labeled_rows: list[dict],
    ) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        """
        Parameters
        ----------
        labeled_rows : list[dict]
            Each dict: {"order_id": …, "txn_id": …, "features": {…}, "label": Label}

        Returns
        -------
        X : pd.DataFrame   feature matrix
        y : np.ndarray     binary labels (1 = true match)
        groups : np.ndarray  order_id encoded as int, for group-aware splitting
        """
        records = []
        for row in labeled_rows:
            rec = dict(row["features"])
            rec["_order_id"] = row["order_id"]
            rec["_label"]    = int(row["label"] == Label.SHIP or row["label"] == "SHIP")
            records.append(rec)

        df     = pd.DataFrame(records)
        y      = df.pop("_label").values
        groups = pd.factorize(df.pop("_order_id"))[0]
        return df, y, groups

    # ── Fit ───────────────────────────────────────────────────────────────────

    def fit(
        self,
        labeled_rows: list[dict],
        val_fraction: float = 0.20,
    ) -> "Trainer":
        """
        Train the model and select the Ship threshold.

        Split is group-aware (by order_id) to prevent leakage.
        """
        X, y, groups = self.prepare_dataset(labeled_rows)
        self.feature_names_ = list(X.columns)

        # Group-aware train/val split
        splitter = GroupShuffleSplit(n_splits=1, test_size=val_fraction, random_state=42)
        train_idx, val_idx = next(splitter.split(X, y, groups))

        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y[train_idx],      y[val_idx]

        # ── Base model ────────────────────────────────────────────────────────
        if _HAS_LGB:
            base = lgb.LGBMClassifier(
                n_estimators=500,
                learning_rate=0.05,
                num_leaves=31,
                min_child_samples=10,
                class_weight="balanced",
                random_state=42,
                verbose=-1,
            )
        else:
            base = LogisticRegression(class_weight="balanced", max_iter=500)

        # ── Calibration ───────────────────────────────────────────────────────
        self.model_ = CalibratedClassifierCV(base, cv=5, method="sigmoid")
        self.model_.fit(X_train, y_train)

        # ── Threshold selection on validation set ─────────────────────────────
        self.ship_threshold_  = self._select_ship_threshold(X_val, y_val)
        self.amb_threshold_   = ML_AMBIGUOUS_THRESHOLD

        print(
            f"[model] Ship threshold selected: {self.ship_threshold_:.3f} "
            f"(target FPR ≤ {self.ship_fpr_target:.1%})"
        )
        return self

    def _select_ship_threshold(self, X_val: pd.DataFrame, y_val: np.ndarray) -> float:
        """
        Choose the lowest probability threshold where false-Ship rate ≤ target.
        We sweep from high to low and stop when the constraint is met.
        """
        probs = self.model_.predict_proba(X_val)[:, 1]
        best_thresh = 0.99  # conservative default

        for thresh in np.arange(0.99, 0.50, -0.01):
            preds      = (probs >= thresh).astype(int)
            n_shipped  = preds.sum()
            if n_shipped == 0:
                continue
            false_ships = ((preds == 1) & (y_val == 0)).sum()
            fpr         = false_ships / n_shipped
            if fpr <= self.ship_fpr_target:
                best_thresh = thresh

        return float(best_thresh)

    def save(self, path: str = MODEL_PATH) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "model":           self.model_,
                "feature_names":   self.feature_names_,
                "ship_threshold":  self.ship_threshold_,
                "amb_threshold":   self.amb_threshold_,
            }, f)
        print(f"[model] Saved to {path}")


# ─────────────────────────────────────────────
# Scorer (inference)
# ─────────────────────────────────────────────

class Scorer:
    """Load a trained model and score candidate pairs."""

    def __init__(self, model, feature_names: list[str], ship_threshold: float, amb_threshold: float):
        self.model_          = model
        self.feature_names_  = feature_names
        self.ship_threshold_ = ship_threshold
        self.amb_threshold_  = amb_threshold

    @classmethod
    def load(cls, path: str = MODEL_PATH) -> "Scorer":
        with open(path, "rb") as f:
            state = pickle.load(f)
        return cls(
            model          = state["model"],
            feature_names  = state["feature_names"],
            ship_threshold = state["ship_threshold"],
            amb_threshold  = state["amb_threshold"],
        )

    def predict_proba(self, feature_dicts: list[dict]) -> np.ndarray:
        """
        Parameters
        ----------
        feature_dicts : list[dict]
            One dict per (order, txn) pair, keyed by feature name.

        Returns
        -------
        np.ndarray of shape (n,)
            P(true match) for each pair.
        """
        df = pd.DataFrame(feature_dicts)
        # Align columns; fill unseen features with 0
        for col in self.feature_names_:
            if col not in df.columns:
                df[col] = 0.0
        df = df[self.feature_names_]
        return self.model_.predict_proba(df)[:, 1]

    def score_to_label(self, prob: float) -> Label:
        if prob >= self.ship_threshold_:
            return Label.SHIP
        if prob >= self.amb_threshold_:
            return Label.AMBIGUOUS
        return Label.REVIEW


# ─────────────────────────────────────────────
# Convenience: run ML matching
# ─────────────────────────────────────────────

def run_ml(
    orders:     list[Order],
    candidates: dict[str, list[Transaction]],
    scorer:     Scorer,
) -> list[MatchResult]:
    """
    Score all (order, candidate_txn) pairs and return one MatchResult per order.

    Uses a greedy assignment so each transaction is claimed by at most one order.
    """
    from matching.assign import greedy_assign

    # Extract features for all pairs
    pair_rows = extract_all_features(orders, candidates)

    if not pair_rows:
        return []

    order_ids = [r[0] for r in pair_rows]
    txn_ids   = [r[1] for r in pair_rows]
    feat_dicts= [r[2] for r in pair_rows]

    probs = scorer.predict_proba(feat_dicts)

    # Collect per-order best candidates
    order_scores: dict[str, list[tuple[str, float, dict]]] = {}
    for oid, tid, feats, prob in zip(order_ids, txn_ids, feat_dicts, probs):
        order_scores.setdefault(oid, []).append((tid, float(prob), feats))

    # Conflict resolution (greedy by probability)
    assignments = greedy_assign(order_scores)

    # Build order lookup
    order_map = {o.order_id: o for o in orders}
    txn_map   = {t.txn_id: t for tlist in candidates.values() for t in tlist}

    results = []
    for order_id, (txn_id, prob, feats) in assignments.items():
        order = order_map[order_id]
        label = scorer.score_to_label(prob)
        txn   = txn_map.get(txn_id)
        gap_h = abs((txn.datetime - order.created_at).total_seconds() / 3600) if txn else 0

        results.append(MatchResult(
            order_id=order_id,
            txn_ids=[txn_id] if txn_id else [],
            score=prob,
            label=label,
            reason=(
                f"ML p={prob:.3f}, name_combined={feats.get('name_combined', 0):.2f}, "
                f"gap={gap_h:.1f}h"
            ),
            features=feats,
            engine="ml",
        ))

    # Orders with no candidates at all
    assigned_ids = set(assignments)
    for order in orders:
        if order.order_id not in assigned_ids:
            from datetime import datetime, timezone
            now    = datetime.now(timezone.utc)
            age_d  = (now - order.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400
            from matching.config import SETTLEMENT_DAYS
            label  = Label.PENDING if age_d < SETTLEMENT_DAYS else Label.REVIEW
            results.append(MatchResult(
                order_id=order.order_id,
                txn_ids=[],
                score=0.0,
                label=label,
                reason="no candidates found",
                engine="ml",
            ))

    return results
