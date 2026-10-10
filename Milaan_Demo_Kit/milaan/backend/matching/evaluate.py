"""
evaluate.py – Evaluation harness comparing rule-based vs ML engines.

Usage
─────
  from matching.evaluate import evaluate_engine, compare_engines, print_report

  results_rules = evaluate_engine(orders, ground_truth, engine="rules")
  results_ml    = evaluate_engine(orders, ground_truth, engine="ml", scorer=scorer)
  compare_engines(results_rules, results_ml)

Ground truth format
───────────────────
  ground_truth: dict[order_id → Label]   (the correct label for each order)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from matching.schemas import Label, MatchResult


# ─────────────────────────────────────────────
# Metrics dataclass
# ─────────────────────────────────────────────

@dataclass
class EvalMetrics:
    engine:             str
    n_orders:           int
    auto_resolve_rate:  float          # % SHIP or PENDING (no human needed)
    false_ship_rate:    float          # falsely shipped / total shipped
    missed_ship_rate:   float          # correct payments sent to Ambiguous/Review
    ship_precision:     float
    ship_recall:        float
    ship_f1:            float
    confusion:          dict = field(default_factory=dict)  # label→label counts
    per_scenario:       dict = field(default_factory=dict)  # scenario→metrics


# ─────────────────────────────────────────────
# Core evaluator
# ─────────────────────────────────────────────

def evaluate_results(
    results:      list[MatchResult],
    ground_truth: dict[str, Label],
    scenarios:    dict[str, list[str]] | None = None,
) -> EvalMetrics:
    """
    Compute all evaluation metrics.

    Parameters
    ----------
    results : list[MatchResult]
    ground_truth : dict[order_id → Label]
    scenarios : dict[scenario_name → list[order_id]]
        Optional grouping of orders by test scenario for per-scenario breakdown.

    Returns
    -------
    EvalMetrics
    """
    engine = results[0].engine if results else "unknown"
    n      = len(results)

    # ── Basic counters ────────────────────────────────────────────────────────
    n_ship         = 0  # predicted SHIP
    n_true_ship    = 0  # ground truth SHIP
    n_tp_ship      = 0  # predicted SHIP AND ground truth SHIP
    n_fp_ship      = 0  # predicted SHIP BUT ground truth NOT SHIP (false-Ship)
    n_fn_ship      = 0  # NOT predicted SHIP BUT ground truth SHIP (missed-Ship)
    n_auto_resolve = 0  # SHIP or PENDING (no human needed)

    confusion: dict[tuple[str, str], int] = defaultdict(int)

    for result in results:
        gt = ground_truth.get(result.order_id)
        if gt is None:
            continue

        pred = result.label
        confusion[(gt.value, pred.value)] += 1

        if pred in (Label.SHIP, Label.PENDING):
            n_auto_resolve += 1

        if pred == Label.SHIP:
            n_ship += 1
            if gt == Label.SHIP:
                n_tp_ship += 1
            else:
                n_fp_ship += 1

        if gt == Label.SHIP:
            n_true_ship += 1
            if pred != Label.SHIP:
                n_fn_ship += 1

    false_ship_rate  = n_fp_ship / max(n_ship, 1)
    missed_ship_rate = n_fn_ship / max(n_true_ship, 1)
    precision        = n_tp_ship / max(n_ship, 1)
    recall           = n_tp_ship / max(n_true_ship, 1)
    f1               = (2 * precision * recall / max(precision + recall, 1e-9))

    # ── Per-scenario breakdown ────────────────────────────────────────────────
    per_scenario: dict[str, dict] = {}
    if scenarios:
        result_map = {r.order_id: r for r in results}
        for scenario_name, order_ids in scenarios.items():
            sc_results = [result_map[oid] for oid in order_ids if oid in result_map]
            sc_gt      = {oid: ground_truth[oid] for oid in order_ids if oid in ground_truth}
            if not sc_results:
                continue
            sc_metrics = evaluate_results(sc_results, sc_gt)
            per_scenario[scenario_name] = {
                "n":                sc_metrics.n_orders,
                "auto_resolve_pct": sc_metrics.auto_resolve_rate * 100,
                "false_ship_pct":   sc_metrics.false_ship_rate   * 100,
                "ship_f1":          sc_metrics.ship_f1,
            }

    return EvalMetrics(
        engine            = engine,
        n_orders          = n,
        auto_resolve_rate = n_auto_resolve / max(n, 1),
        false_ship_rate   = false_ship_rate,
        missed_ship_rate  = missed_ship_rate,
        ship_precision    = precision,
        ship_recall       = recall,
        ship_f1           = f1,
        confusion         = dict(confusion),
        per_scenario      = per_scenario,
    )


# ─────────────────────────────────────────────
# Ablation helper
# ─────────────────────────────────────────────

def ablation_study(
    orders:       list,
    candidates:   dict,
    ground_truth: dict,
    scorer,
    feature_groups_to_drop: list[list[str]],
    group_names: list[str],
) -> list[EvalMetrics]:
    """
    Run the ML engine repeatedly, each time zeroing out a feature group,
    to measure each group's contribution.

    Parameters
    ----------
    feature_groups_to_drop : list[list[str]]
        Each sub-list is a group of feature names to zero out.
    group_names : list[str]
        Human-readable name for each group.

    Returns
    -------
    list[EvalMetrics]
        One per ablation (excluding the baseline, which caller runs separately).
    """
    from matching.model import run_ml
    from matching.features import extract_all_features

    ablation_results = []

    for group, name in zip(feature_groups_to_drop, group_names):
        # Monkey-patch: zero the target features before scoring
        original_predict = scorer.predict_proba

        def patched_predict(feat_dicts, _group=group):
            zeroed = [{**d, **{k: 0.0 for k in _group if k in d}} for d in feat_dicts]
            return original_predict(zeroed)

        scorer.predict_proba = patched_predict
        results = run_ml(orders, candidates, scorer)
        scorer.predict_proba = original_predict  # restore

        metrics = evaluate_results(results, ground_truth)
        metrics.engine = f"ml_no_{name}"
        ablation_results.append(metrics)

    return ablation_results


# ─────────────────────────────────────────────
# Report printer
# ─────────────────────────────────────────────

def print_report(
    rules_metrics: EvalMetrics,
    ml_metrics:    EvalMetrics,
    ablations:     list[EvalMetrics] | None = None,
) -> None:
    """Print a formatted evaluation report to stdout."""

    sep = "─" * 60

    def _row(label: str, rules_val, ml_val, fmt=".1%"):
        print(f"  {label:<35} {rules_val:{fmt}}    {ml_val:{fmt}}")

    print(f"\n{'═'*60}")
    print(f"  RECONCILIATION ENGINE – EVALUATION REPORT")
    print(f"{'═'*60}")
    print(f"  {'Metric':<35} {'Rules':>8}    {'ML':>8}")
    print(sep)
    _row("Auto-resolve rate",      rules_metrics.auto_resolve_rate,  ml_metrics.auto_resolve_rate)
    _row("False-Ship rate ⚠",      rules_metrics.false_ship_rate,    ml_metrics.false_ship_rate)
    _row("Missed-Ship rate",        rules_metrics.missed_ship_rate,   ml_metrics.missed_ship_rate)
    _row("SHIP precision",          rules_metrics.ship_precision,     ml_metrics.ship_precision)
    _row("SHIP recall",             rules_metrics.ship_recall,        ml_metrics.ship_recall)
    _row("SHIP F1",                 rules_metrics.ship_f1,            ml_metrics.ship_f1)
    print(sep)

    # Delta
    delta = ml_metrics.auto_resolve_rate - rules_metrics.auto_resolve_rate
    fsr_r = rules_metrics.false_ship_rate
    fsr_m = ml_metrics.false_ship_rate
    print(f"\n  ★ At a false-Ship rate of {fsr_m:.2%}, ML resolves "
          f"{delta:+.1%} more orders automatically than rule-based.")
    print(f"    Rule-based false-Ship rate: {fsr_r:.2%}")

    # Per-scenario
    if rules_metrics.per_scenario:
        print(f"\n  PER-SCENARIO BREAKDOWN")
        print(f"  {'Scenario':<30} {'Rules auto%':>11} {'ML auto%':>8} {'Rules FP%':>9} {'ML FP%':>7}")
        print(sep)
        all_scenarios = set(rules_metrics.per_scenario) | set(ml_metrics.per_scenario)
        for sc in sorted(all_scenarios):
            r  = rules_metrics.per_scenario.get(sc, {})
            m  = ml_metrics.per_scenario.get(sc, {})
            print(f"  {sc:<30} {r.get('auto_resolve_pct', 0):>10.1f}% "
                  f"{m.get('auto_resolve_pct', 0):>7.1f}% "
                  f"{r.get('false_ship_pct', 0):>8.2f}% "
                  f"{m.get('false_ship_pct', 0):>6.2f}%")

    # Ablations
    if ablations:
        print(f"\n  ABLATION STUDY (ML baseline vs. feature removal)")
        print(f"  {'Engine':<35} {'Auto-resolve':>12} {'False-Ship':>10} {'F1':>6}")
        print(sep)

        def _abl_row(m: EvalMetrics):
            print(f"  {m.engine:<35} {m.auto_resolve_rate:>11.1%} "
                  f"{m.false_ship_rate:>9.2%} {m.ship_f1:>6.3f}")

        _abl_row(ml_metrics)
        for a in ablations:
            _abl_row(a)

    print(f"\n{'═'*60}\n")
