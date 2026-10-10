"""
feedback.py – Feedback loop: store seller corrections, trigger retraining.

Every time a seller moves an order between buckets on the dashboard,
Module 4 calls record_correction().  When enough corrections accumulate,
retrain() is called automatically.

Corrections are appended to a JSONL file for auditability and portability.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from matching.config import FEEDBACK_PATH, RETRAIN_TRIGGER
from matching.schemas import Correction, Label


# ─────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────

def record_correction(correction: Correction, path: str = FEEDBACK_PATH) -> int:
    """
    Append a seller correction to the feedback JSONL store.

    Returns
    -------
    int
        Total number of corrections stored (used to decide when to retrain).
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    record = {
        "order_id":        correction.order_id,
        "original_label":  correction.original_label.value,
        "corrected_label": correction.corrected_label.value,
        "txn_ids":         correction.txn_ids,
        "features":        correction.features,
        "corrected_at":    correction.corrected_at.isoformat(),
        "corrected_by":    correction.corrected_by,
        # Binary label for retraining: 1 = seller confirmed as SHIP
        "ml_label":        int(correction.corrected_label == Label.SHIP),
    }

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return _count_corrections(path)


def _count_corrections(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def load_corrections(path: str = FEEDBACK_PATH) -> list[dict]:
    """Load all stored corrections as a list of dicts."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def corrections_as_labeled_rows(path: str = FEEDBACK_PATH) -> list[dict]:
    """
    Convert stored corrections into the format expected by Trainer.fit().
    Skips corrections where features are empty (shouldn't happen in production).
    """
    rows = []
    for rec in load_corrections(path):
        if not rec.get("features"):
            continue
        rows.append({
            "order_id": rec["order_id"],
            "txn_id":   rec["txn_ids"][0] if rec["txn_ids"] else "",
            "features": rec["features"],
            "label":    Label(rec["corrected_label"]),
        })
    return rows


# ─────────────────────────────────────────────
# Retraining trigger
# ─────────────────────────────────────────────

def maybe_retrain(
    base_labeled_rows: list[dict],
    model_path: str,
    feedback_path: str = FEEDBACK_PATH,
    trigger: int = RETRAIN_TRIGGER,
    ship_fpr_target: float = 0.005,
) -> bool:
    """
    Check if enough corrections have accumulated; if so, retrain and save.

    Parameters
    ----------
    base_labeled_rows : list[dict]
        Original labeled dataset from the synthetic generator.
    model_path : str
        Where to save the new model (overwrites; old version should be backed up).
    trigger : int
        Minimum number of corrections before retraining.
    ship_fpr_target : float
        False-Ship rate constraint for the new model.

    Returns
    -------
    bool
        True if a retrain was triggered and completed.
    """
    n = _count_corrections(feedback_path)
    if n < trigger:
        print(f"[feedback] {n}/{trigger} corrections – no retrain yet.")
        return False

    print(f"[feedback] {n} corrections ≥ {trigger} – retraining...")

    from matching.model import Trainer

    correction_rows = corrections_as_labeled_rows(feedback_path)
    combined_rows   = base_labeled_rows + correction_rows

    trainer = Trainer(ship_fpr_target=ship_fpr_target)
    trainer.fit(combined_rows)

    # Back up old model
    old_path = model_path + ".prev"
    if os.path.exists(model_path):
        os.replace(model_path, old_path)
        print(f"[feedback] Old model backed up to {old_path}")

    trainer.save(model_path)
    print(f"[feedback] New model saved. Ship threshold: {trainer.ship_threshold_:.3f}")
    return True


# ─────────────────────────────────────────────
# Demo simulation helper
# ─────────────────────────────────────────────

def simulate_corrections(
    match_results,
    ground_truth: dict[str, Label],
    n: int = 50,
    feedback_path: str = FEEDBACK_PATH,
) -> int:
    """
    Simulate N seller corrections for demo purposes.

    Picks results where model label ≠ ground truth label and
    records the ground-truth label as the seller's correction.

    Returns
    -------
    int
        Number of corrections actually recorded (may be < n if fewer errors).
    """
    count = 0
    for result in match_results:
        if count >= n:
            break
        gt = ground_truth.get(result.order_id)
        if gt is None or gt == result.label:
            continue

        correction = Correction(
            order_id        = result.order_id,
            original_label  = result.label,
            corrected_label = gt,
            txn_ids         = result.txn_ids,
            features        = result.features,
            corrected_at    = datetime.now(timezone.utc),
        )
        record_correction(correction, path=feedback_path)
        count += 1

    return count
