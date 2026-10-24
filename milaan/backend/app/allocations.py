"""All allocation writers serialize per seller, then check retained credit budgets.

SQLite uses BEGIN IMMEDIATE; PostgreSQL writers lock the seller row. Deletion
releases shares by removing rows, so reset/expiry cascades cannot leave counters stale.
"""
from sqlalchemy import select, func
from .models import Allocation, User, StatementLine


def lock_seller(db, owner_id):
    db.scalar(select(User).where(User.id == owner_id).with_for_update())


def remaining_credit(db, line, owner_id, excluding=()):
    query = select(Allocation).where(Allocation.credit_key == line.credit_key)
    if excluding:
        query = query.where(Allocation.match_id.not_in(excluding))
    allocations = list(db.scalars(query))
    # A reused strong reference cannot inflate the original retained source amount.
    for allocation in allocations:
        source = db.get(StatementLine, allocation.statement_line_id)
        if allocation.owner_id != owner_id or not source or source.account_id != line.account_id or source.amount_paisa != line.amount_paisa:
            raise ValueError('Source credit conflicts with retained evidence; correct the statement')
    return line.amount_paisa - sum(a.amount_paisa for a in allocations)


def add_allocation(db, *, owner_id, batch_id, match_id, order_id, claim_id, line, amount):
    if amount <= 0 or amount > remaining_credit(db, line, owner_id):
        raise ValueError('The retained credit does not have enough unallocated funds')
    allocation = Allocation(owner_id=owner_id, batch_id=batch_id, match_id=match_id,
                            order_id=order_id, claim_id=claim_id, statement_line_id=line.id,
                            credit_key=line.credit_key, amount_paisa=amount)
    db.add(allocation)
    db.flush()
    return allocation
