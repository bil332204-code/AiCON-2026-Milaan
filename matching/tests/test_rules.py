"""
tests/test_rules.py – Unit tests for the rule-based matching engine.
"""
import pytest
from datetime import datetime, timezone, timedelta

from matching.schemas import Order, Transaction, TxnType, Label
from matching.rules import apply_rules


def _order(name="Ali Khan", amount=1000.0, hours_ago=5):
    return Order(
        order_id="ORD-TEST",
        customer_name=name,
        amount=amount,
        created_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        status="pending",
    )

def _txn(txn_id="TXN-001", sender="Ali Khan", amount=1000.0, delay_hours=2):
    return Transaction(
        txn_id=txn_id,
        datetime=datetime.now(timezone.utc) - timedelta(hours=5) + timedelta(hours=delay_hours),
        amount=amount,
        sender=sender,
        reference="",
        type=TxnType.CREDIT,
    )


class TestRules:
    def test_clean_match_ships(self):
        order  = _order()
        txn    = _txn()
        result = apply_rules(order, [txn])
        assert result.label == Label.SHIP
        assert result.score > 0.9

    def test_no_candidates_new_order_pending(self):
        order  = _order(hours_ago=1)   # very new
        result = apply_rules(order, [])
        assert result.label == Label.PENDING

    def test_no_candidates_old_order_review(self):
        order  = _order(hours_ago=200)  # 8+ days
        result = apply_rules(order, [])
        assert result.label == Label.REVIEW

    def test_low_name_similarity_review(self):
        order  = _order(name="Ali Khan")
        txn    = _txn(sender="Fatima Sheikh")   # completely different
        result = apply_rules(order, [txn])
        assert result.label == Label.REVIEW

    def test_transliteration_variant_ships(self):
        order  = _order(name="Muhammad Ali")
        txn    = _txn(sender="Mohammed Ali")
        result = apply_rules(order, [txn])
        # Normalized names should be similar enough
        assert result.label in (Label.SHIP, Label.AMBIGUOUS)

    def test_multiple_candidates_ambiguous(self):
        order = _order()
        txn1  = _txn(txn_id="TXN-001", sender="Ali Khan")
        txn2  = _txn(txn_id="TXN-002", sender="Ali Khaan")  # variant
        result = apply_rules(order, [txn1, txn2])
        assert result.label in (Label.AMBIGUOUS, Label.SHIP)

    def test_amount_mismatch_no_ship(self):
        order  = _order(amount=1000.0)
        txn    = _txn(amount=500.0)   # 50% short
        result = apply_rules(order, [txn])
        assert result.label != Label.SHIP

    def test_result_has_reason_string(self):
        order  = _order()
        txn    = _txn()
        result = apply_rules(order, [txn])
        assert isinstance(result.reason, str) and len(result.reason) > 0

    def test_result_features_populated(self):
        order  = _order()
        txn    = _txn()
        result = apply_rules(order, [txn])
        assert "name_combined" in result.features or len(result.features) > 0
