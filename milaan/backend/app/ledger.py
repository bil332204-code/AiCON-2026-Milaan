"""Long-lived seller records that outlive 7-day batches.

* Credit ledger: when a batch with allocations is deleted or expires, its used bank credits
  are copied here, so an old payment screenshot cannot fund a new order later.
* Decision log: SHIP/HOLD decisions with the reason and reference, for disputes.
Neither keeps images or customer names.
"""
from datetime import timedelta
from sqlalchemy import select, delete, func
from .models import Allocation, Batch, CreditLedger, DecisionLog, Order, StatementLine, now


def retain_until(settings):
    return now() + timedelta(days=settings.ledger_days)


def archive_batch(db, batch, settings):
    """Copy a batch's allocations into the ledger before the batch is removed."""
    rows = db.execute(select(Allocation, StatementLine, Order)
                      .join(StatementLine, StatementLine.id == Allocation.statement_line_id)
                      .join(Order, Order.id == Allocation.order_id)
                      .where(Allocation.batch_id == batch.id)).all()
    keep = retain_until(settings)
    for allocation, line, order in rows:
        db.add(CreditLedger(owner_id=batch.owner_id, credit_key=allocation.credit_key, account_id=line.account_id,
                            credit_amount_paisa=line.amount_paisa, amount_paisa=allocation.amount_paisa,
                            order_ref=order.order_ref[:100], transaction_id=(line.transaction_id or "")[:150],
                            batch_name=(batch.name or "")[:150], used_at=now(), retain_until=keep))
    return len(rows)


def used_credit_keys(db, owner_id):
    live = set(db.scalars(select(Allocation.credit_key).where(Allocation.owner_id == owner_id)))
    kept = set(db.scalars(select(CreditLedger.credit_key).where(CreditLedger.owner_id == owner_id,
                                                                  CreditLedger.retain_until > now())))
    return live | kept


def ledger_rows(db, owner_id, credit_key):
    return list(db.scalars(select(CreditLedger).where(CreditLedger.owner_id == owner_id,
                                                      CreditLedger.credit_key == credit_key,
                                                      CreditLedger.retain_until > now())))


def used_amounts(db, owner_id, credit_keys, excluding_matches=()):
    """Total paisa already used per credit key: live allocations + retained ledger rows."""
    keys = list(set(credit_keys))
    if not keys:
        return {}
    totals = {k: 0 for k in keys}
    query = select(Allocation.credit_key, func.sum(Allocation.amount_paisa)).where(
        Allocation.owner_id == owner_id, Allocation.credit_key.in_(keys))
    if excluding_matches:
        query = query.where(Allocation.match_id.not_in(list(excluding_matches)))
    for key, amount in db.execute(query.group_by(Allocation.credit_key)):
        totals[key] += int(amount or 0)
    for key, amount in db.execute(select(CreditLedger.credit_key, func.sum(CreditLedger.amount_paisa)).where(
            CreditLedger.owner_id == owner_id, CreditLedger.credit_key.in_(keys),
            CreditLedger.retain_until > now()).group_by(CreditLedger.credit_key)):
        totals[key] += int(amount or 0)
    return totals


def log_decision(db, settings, *, owner_id, batch, order, decision, source, reason="", transaction_id=""):
    db.add(DecisionLog(owner_id=owner_id, batch_name=(batch.name or "")[:150], order_ref=order.order_ref[:100],
                       amount_paisa=order.amount_due_paisa, decision=decision, source=source,
                       reason=(reason or "")[:1000], transaction_id=(transaction_id or "")[:150],
                       created_at=now(), retain_until=retain_until(settings)))


def purge_expired(db):
    db.execute(delete(CreditLedger).where(CreditLedger.retain_until <= now()))
    db.execute(delete(DecisionLog).where(DecisionLog.retain_until <= now()))


def remove_batch(db, batch, settings):
    """Archive used credits, then delete. Callers enqueue receipt deletions first."""
    archive_batch(db, batch, settings)
    db.delete(batch)


__all__ = ["archive_batch", "used_credit_keys", "ledger_rows", "used_amounts", "log_decision",
           "purge_expired", "remove_batch", "Batch"]
