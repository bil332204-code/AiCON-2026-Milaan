"""
synthetic.py – Synthetic dataset generator for Module 3 development and evaluation.

Generates orders + matching bank transactions with realistic noise.
Noise types (controlled by flags):
  • misspelled_name   – character swap/drop/insert in sender name
  • urdu_transliteration – Muhammad→Mohammed→Muhammed, Hussain→Hussein, etc.
  • truncated_name    – bank cuts name at N characters
  • split_payment     – one order paid in 2+ transactions
  • multi_order       – one transaction covers 2+ orders (handled by Module 4)
  • delayed_payment   – payment arrives outside normal window
  • refund            – REVERSAL transaction for a cancelled order
  • family_member_pays – different sender name, same order
  • hard_negative      – same amount, completely different sender

Ground truth: each row records the correct label, which txn_ids match, etc.

Usage
─────
    from matching.synthetic import generate_dataset

    orders, txns, ground_truth, scenarios = generate_dataset(
        n_clean=200, noise_config={...}, seed=42
    )
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from matching.schemas import Label, Order, Transaction, TxnType


# ─────────────────────────────────────────────
# Name pools (South-Asian, Urdu / mixed)
# ─────────────────────────────────────────────

_FIRST_NAMES = [
    "Muhammad", "Ali", "Ahmed", "Hassan", "Bilal", "Fahad",
    "Usman", "Zubair", "Tariq", "Imran", "Asad", "Kamran",
    "Sana", "Ayesha", "Fatima", "Amna", "Zainab", "Hira",
    "Omar", "Raza", "Waqar", "Adeel", "Saad", "Jawad",
]

_LAST_NAMES = [
    "Khan", "Malik", "Sheikh", "Akhtar", "Mirza", "Qureshi",
    "Chaudhry", "Siddiqui", "Butt", "Raza", "Hussain", "Shah",
    "Ansari", "Baig", "Javed", "Nawaz", "Iqbal", "Aslam",
]

_VARIANTS: dict[str, list[str]] = {
    "Muhammad": ["Mohammed", "Mohammad", "Muhammed", "Md"],
    "Ahmed":    ["Ahmad", "Ahmd"],
    "Hussain":  ["Hussein", "Husain"],
    "Hassan":   ["Hasan"],
    "Usman":    ["Osman"],
    "Zubair":   ["Zubayr"],
    "Khan":     ["Khaan"],
    "Fahad":    ["Fahd"],
    "Bilal":    ["Billu"],
}

_FAMILY_NAMES = ["Father", "Brother", "Wife", "Sister", "Mother"]


# ─────────────────────────────────────────────
# Noise helpers
# ─────────────────────────────────────────────

def _misspell(name: str, rng: random.Random) -> str:
    """Introduce a random character-level error."""
    if len(name) < 3:
        return name
    op = rng.choice(["swap", "drop", "insert", "replace"])
    i  = rng.randint(1, len(name) - 2)
    if op == "swap"    and i + 1 < len(name):
        lst = list(name); lst[i], lst[i+1] = lst[i+1], lst[i]; return "".join(lst)
    if op == "drop":
        return name[:i] + name[i+1:]
    if op == "insert":
        return name[:i] + rng.choice(string.ascii_lowercase) + name[i:]
    if op == "replace":
        return name[:i] + rng.choice(string.ascii_lowercase) + name[i+1:]
    return name


def _transliterate_variant(name: str, rng: random.Random) -> str:
    """Replace a token with a known Urdu transliteration variant."""
    tokens = name.split()
    result = []
    for tok in tokens:
        variants = _VARIANTS.get(tok, [])
        result.append(rng.choice(variants) if variants and rng.random() < 0.7 else tok)
    return " ".join(result)


def _truncate_name(name: str, max_len: int = 15) -> str:
    """Simulate bank character-limit truncation."""
    name_no_space = name.replace(" ", "")[:max_len]
    return name_no_space.upper()


def _random_name(rng: random.Random) -> str:
    first = rng.choice(_FIRST_NAMES)
    last  = rng.choice(_LAST_NAMES)
    # ~40% chance of a middle name
    if rng.random() < 0.4:
        mid = rng.choice(_FIRST_NAMES)
        return f"{first} {mid} {last}"
    return f"{first} {last}"


def _make_order(order_id: str, rng: random.Random, base_dt: datetime) -> Order:
    amount    = rng.choice([500, 1000, 1500, 2000, 2500, 3000, 5000, 7500, 10000])
    amount   += rng.randint(0, 99)       # cents-like noise
    created   = base_dt + timedelta(hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
    return Order(
        order_id      = order_id,
        customer_name = _random_name(rng),
        amount        = float(amount),
        created_at    = created,
        status        = "pending",
        phone         = f"03{rng.randint(0, 9)}{rng.randint(1000000, 9999999)}",
    )


def _make_txn(
    txn_id: str,
    order:  Order,
    rng:    random.Random,
    *,
    amount_override: float | None = None,
    sender_override: str   | None = None,
    delay_hours:     float        = 0.0,
    txn_type: TxnType             = TxnType.CREDIT,
) -> Transaction:
    amount = amount_override if amount_override is not None else order.amount
    sender = sender_override if sender_override is not None else order.customer_name
    dt     = order.created_at + timedelta(hours=delay_hours + rng.uniform(0, 1))
    return Transaction(
        txn_id    = txn_id,
        datetime  = dt,
        amount    = float(amount),
        sender    = sender,
        reference = f"Payment for order {order.order_id}" if rng.random() < 0.3 else "",
        type      = txn_type,
        bank      = rng.choice(["HBL", "MCB", "UBL", "Meezan"]),
    )


# ─────────────────────────────────────────────
# Dataset generator
# ─────────────────────────────────────────────

@dataclass
class NoiseConfig:
    misspelled_name:      int = 30   # # of orders with name typos
    urdu_transliteration: int = 30   # # with transliteration variants
    truncated_name:       int = 20   # # where bank truncated the name
    split_payment:        int = 20   # # paid in 2 transactions
    delayed_payment:      int = 20   # # where payment arrives late
    family_member_pays:   int = 15   # # where sender ≠ customer
    refund:               int = 10   # # with a REVERSAL txn
    hard_negative:        int = 30   # # orders with a same-amount decoy txn


def generate_dataset(
    n_clean:      int         = 150,
    noise_config: NoiseConfig = None,
    seed:         int         = 42,
    start_date:   datetime    = None,
) -> tuple[list[Order], list[Transaction], dict[str, Label], dict[str, list[str]]]:
    """
    Generate a synthetic reconciliation dataset.

    Returns
    -------
    orders       : list[Order]
    transactions : list[Transaction]
    ground_truth : dict[order_id → Label]
    scenarios    : dict[scenario_name → list[order_id]]
        For use with evaluate.evaluate_results(..., scenarios=scenarios).
    """
    if noise_config is None:
        noise_config = NoiseConfig()
    if start_date is None:
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

    rng          = random.Random(seed)
    orders:      list[Order]       = []
    txns:        list[Transaction] = []
    ground_truth: dict[str, Label] = {}
    scenarios:    dict[str, list[str]] = {}

    order_counter = 0
    txn_counter   = 0

    def _next_order_id() -> str:
        nonlocal order_counter
        order_counter += 1
        return f"ORD-{order_counter:05d}"

    def _next_txn_id() -> str:
        nonlocal txn_counter
        txn_counter += 1
        return f"TXN-{txn_counter:05d}"

    def _add_scenario(name: str, order_id: str):
        scenarios.setdefault(name, []).append(order_id)

    # Day offset so orders span multiple days
    day = 0

    # ── 1. Clean matches ──────────────────────────────────────────────────────
    scenario_key = "clean_match"
    for _ in range(n_clean):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        txn     = _make_txn(_next_txn_id(), order, rng, delay_hours=rng.uniform(0.5, 6))
        orders.append(order); txns.append(txn)
        ground_truth[order.order_id] = Label.SHIP
        _add_scenario(scenario_key, order.order_id)

    # ── 2. Misspelled names ───────────────────────────────────────────────────
    scenario_key = "misspelled_name"
    for _ in range(noise_config.misspelled_name):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        noisy   = _misspell(order.customer_name, rng)
        txn     = _make_txn(_next_txn_id(), order, rng, sender_override=noisy, delay_hours=rng.uniform(1, 8))
        orders.append(order); txns.append(txn)
        ground_truth[order.order_id] = Label.SHIP   # should still resolve
        _add_scenario(scenario_key, order.order_id)

    # ── 3. Urdu transliteration ───────────────────────────────────────────────
    scenario_key = "urdu_transliteration"
    for _ in range(noise_config.urdu_transliteration):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        variant = _transliterate_variant(order.customer_name, rng)
        txn     = _make_txn(_next_txn_id(), order, rng, sender_override=variant, delay_hours=rng.uniform(1, 8))
        orders.append(order); txns.append(txn)
        ground_truth[order.order_id] = Label.SHIP
        _add_scenario(scenario_key, order.order_id)

    # ── 4. Truncated names ────────────────────────────────────────────────────
    scenario_key = "truncated_name"
    for _ in range(noise_config.truncated_name):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        trunc   = _truncate_name(order.customer_name, max_len=rng.randint(10, 18))
        txn     = _make_txn(_next_txn_id(), order, rng, sender_override=trunc, delay_hours=rng.uniform(1, 6))
        orders.append(order); txns.append(txn)
        ground_truth[order.order_id] = Label.SHIP
        _add_scenario(scenario_key, order.order_id)

    # ── 5. Split payments (2 txns for 1 order) ───────────────────────────────
    # We generate both halves as transactions; Module 4 does the grouping,
    # but we include them in the pool so Module 3 sees partial amounts.
    scenario_key = "split_payment"
    for _ in range(noise_config.split_payment):
        base_dt  = start_date + timedelta(days=day); day += 1
        order    = _make_order(_next_order_id(), rng, base_dt)
        half1    = round(order.amount * rng.uniform(0.4, 0.6), 2)
        half2    = order.amount - half1
        txn1     = _make_txn(_next_txn_id(), order, rng, amount_override=half1, delay_hours=rng.uniform(1, 4))
        txn2     = _make_txn(_next_txn_id(), order, rng, amount_override=half2, delay_hours=rng.uniform(4, 24))
        orders.append(order); txns.extend([txn1, txn2])
        # Module 3 alone will see AMBIGUOUS; Module 4 resolves to SHIP
        ground_truth[order.order_id] = Label.AMBIGUOUS
        _add_scenario(scenario_key, order.order_id)

    # ── 6. Delayed payments ───────────────────────────────────────────────────
    scenario_key = "delayed_payment"
    for _ in range(noise_config.delayed_payment):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        delay   = rng.uniform(100, 160)   # 4-7 days
        txn     = _make_txn(_next_txn_id(), order, rng, delay_hours=delay)
        orders.append(order); txns.append(txn)
        ground_truth[order.order_id] = Label.SHIP
        _add_scenario(scenario_key, order.order_id)

    # ── 7. Family member pays ─────────────────────────────────────────────────
    scenario_key = "family_member_pays"
    for _ in range(noise_config.family_member_pays):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        family_name = _random_name(rng)   # completely different name
        txn     = _make_txn(_next_txn_id(), order, rng, sender_override=family_name, delay_hours=rng.uniform(1, 12))
        orders.append(order); txns.append(txn)
        # High amount match, low name match → AMBIGUOUS is correct
        ground_truth[order.order_id] = Label.AMBIGUOUS
        _add_scenario(scenario_key, order.order_id)

    # ── 8. Refunds ────────────────────────────────────────────────────────────
    scenario_key = "refund"
    for _ in range(noise_config.refund):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        order.status = "cancelled"
        txn     = _make_txn(_next_txn_id(), order, rng,
                            delay_hours=rng.uniform(24, 72), txn_type=TxnType.REVERSAL)
        orders.append(order); txns.append(txn)
        ground_truth[order.order_id] = Label.REVIEW  # reversal → review
        _add_scenario(scenario_key, order.order_id)

    # ── 9. Hard negatives (decoy transactions) ────────────────────────────────
    scenario_key = "hard_negative"
    for _ in range(noise_config.hard_negative):
        base_dt = start_date + timedelta(days=day); day += 1
        order   = _make_order(_next_order_id(), rng, base_dt)
        # Real matching txn
        real_txn = _make_txn(_next_txn_id(), order, rng, delay_hours=rng.uniform(1, 6))
        # Decoy: same amount, completely different sender
        decoy_txn = _make_txn(
            _next_txn_id(), order, rng,
            sender_override=_random_name(rng),
            delay_hours=rng.uniform(0.5, 8)
        )
        orders.append(order); txns.extend([real_txn, decoy_txn])
        ground_truth[order.order_id] = Label.SHIP   # real_txn should win
        _add_scenario(scenario_key, order.order_id)

    # Shuffle to avoid ordering artifacts
    rng.shuffle(orders)
    rng.shuffle(txns)

    return orders, txns, ground_truth, scenarios
