"""Conservative, explicit many-to-many allocation review; never automatic approval."""
import hashlib
from datetime import timedelta
from collections import Counter
from fastapi import HTTPException
from sqlalchemy import select, delete, func
from .models import Allocation, AllocationReview, Match, Claim, Order, Statement, StatementLine, Job
from .allocations import lock_seller, remaining_credit, add_allocation
from .parsing import paisa, parse_time, full_ref, norm_ref
from .matcher import successful_status
from .jobs import audit


def checked_source(db, batch, order, part):
    line, claim = db.get(StatementLine, part.statement_line_id), db.get(Claim, part.claim_id)
    if not line or not claim or line.batch_id != batch.id or claim.batch_id != batch.id:
        raise HTTPException(422, 'Choose a statement credit and receipt in this batch')
    if line.account_id != order.account_id or claim.account_id != order.account_id or line.direction != 'CREDIT' or line.currency != 'PKR':
        raise HTTPException(422, 'The evidence and order must use the same receiving account and PKR credit')
    fields = claim.fields
    try:
        amount, at = paisa(fields.get('amount_pkr')), parse_time(fields.get('datetime_local'))
    except (ValueError, TypeError):
        raise HTTPException(422, 'Receipt amount and timestamp must be checked first')
    if not claim.fields_checked or not fields.get('is_payment_receipt') or not successful_status(fields.get('status_text')):
        raise HTTPException(422, 'Only confirmed receipts with recognized successful payment status can support an allocation')
    ref = fields.get('transaction_id')
    if not full_ref(ref) or norm_ref(ref) != norm_ref(line.transaction_id) or amount != line.amount_paisa:
        raise HTTPException(422, 'The full receipt reference and amount must match the source credit')
    statement = db.get(Statement, line.statement_id)
    if not statement or not statement.complete or not statement.references_verified or not statement.coverage_start <= at <= statement.coverage_end:
        raise HTTPException(422, 'Confirm complete statement coverage and sender/receiver reference correspondence first')
    if abs(line.posted_at-at) > timedelta(hours=24):
        raise HTTPException(422, 'Delayed or conflicting posting dates need corrected evidence before allocation')
    duplicates = db.scalar(select(func.count()).select_from(StatementLine).where(
        StatementLine.batch_id == batch.id, StatementLine.credit_key == line.credit_key, StatementLine.direction == 'CREDIT'))
    hashes = db.scalar(select(func.count()).select_from(Claim).where(Claim.batch_id == batch.id, Claim.sha256 == claim.sha256))
    if duplicates != 1 or hashes != 1:
        raise HTTPException(409, 'Resolve duplicate source credits or duplicate receipt uploads first; share one source receipt explicitly')
    debits = list(db.scalars(select(StatementLine).where(StatementLine.batch_id == batch.id,
                         StatementLine.account_id == line.account_id, StatementLine.direction == 'DEBIT')))
    if any(norm_ref(d.transaction_id) == norm_ref(ref) for d in debits):
        raise HTTPException(409, 'A same-reference debit may be a refund or reversal; resolve the source evidence first')
    return line, claim


def review_allocations(db, batch, user, body, key):
    if not body.confirmed_relationships:
        raise HTTPException(422, 'Explicitly confirm the relationships between all selected orders, receipts and source credits')
    if not 8 <= len(key) <= 100:
        raise HTTPException(422, 'Use an Idempotency-Key with 8 to 100 characters')
    lock_seller(db, user.id)
    if not batch.latest_run_id or batch.revision != body.expected_revision:
        raise HTTPException(409, 'Reconcile current inputs and reload the batch before reviewing allocations')
    digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    previous = db.scalar(select(AllocationReview).where(AllocationReview.batch_id == batch.id, AllocationReview.idempotency_key == key))
    if previous:
        if previous.request_digest != digest:
            raise HTTPException(409, 'This idempotency key already identifies a different allocation plan')
        return previous.response
    if db.scalar(select(Job.id).where(Job.batch_id == batch.id, Job.status.in_(['queued', 'running'])).limit(1)):
        raise HTTPException(409, 'Wait for the active batch job')
    ids = [item.match_id for item in body.orders]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, 'Each order may appear only once in an allocation plan')
    prepared, sources, requested = [], {}, Counter()
    for item in body.orders:
        match = db.get(Match, item.match_id)
        if not match or match.batch_id != batch.id:
            raise HTTPException(404, 'Result not found')
        db.refresh(match)
        if match.run_id != batch.latest_run_id or match.version != item.expected_version:
            raise HTTPException(409, 'Result is stale; reload current results')
        order = db.get(Order, match.order_id)
        parts, seen = [], set()
        for part in item.parts:
            line, claim = checked_source(db, batch, order, part)
            if line.credit_key in seen:
                raise HTTPException(422, 'A source credit may appear only once per order; use a single share amount')
            seen.add(line.credit_key)
            try: amount = paisa(part.amount_pkr)
            except ValueError as exc: raise HTTPException(422, str(exc))
            sources[line.credit_key] = line
            requested[line.credit_key] += amount
            parts.append((line, claim, amount))
        paid = sum(amount for _, _, amount in parts)
        if paid > order.amount_due_paisa:
            raise HTTPException(422, 'Do not allocate more than the order total; leave overpayment unassigned for review')
        prepared.append((match, order, parts, paid))
    for credit_key, amount in requested.items():
        try: remaining = remaining_credit(db, sources[credit_key], user.id, excluding=ids)
        except ValueError as exc: raise HTTPException(409, str(exc))
        if amount > remaining:
            raise HTTPException(409, 'The plan would allocate a source credit more than once or exceed its remaining funds')
    # All checks precede writes; the seller lock covers both validation and replacement.
    db.execute(delete(Allocation).where(Allocation.match_id.in_(ids)))
    db.flush()
    items = []
    for match, order, parts, paid in prepared:
        allocations = []
        for line, claim, amount in parts:
            add_allocation(db, owner_id=user.id, batch_id=batch.id, match_id=match.id,
                           order_id=order.id, claim_id=claim.id, line=line, amount=amount)
            allocations.append({'statement_line_id': line.id, 'claim_id': claim.id, 'amount_paisa': amount})
        previous_status = match.final_status
        match.final_status = 'ship' if paid == order.amount_due_paisa else 'review'
        match.selected_line_id = parts[0][0].id if len(parts) == 1 else None
        match.reviewer_reason, match.version = body.reason, match.version + 1
        # Keep the machine verdict/reason unchanged; human funding decisions are separate evidence.
        match.evidence = [e for e in match.evidence if e.get('check') != 'reviewed_allocation'] + [{
            'check': 'reviewed_allocation', 'ok': paid == order.amount_due_paisa, 'allocated_paisa': paid,
            'outstanding_paisa': order.amount_due_paisa-paid, 'parts': allocations}]
        items.append({'match_id': match.id, 'version': match.version, 'final_status': match.final_status,
                      'allocated_paisa': paid, 'outstanding_paisa': order.amount_due_paisa-paid, 'allocations': allocations})
        audit(db, batch.id, user.id, 'allocation_reviewed', {'match_id': match.id, 'previous': previous_status,
              'decision': match.final_status, 'reason': body.reason, 'version': match.version, 'allocations': allocations})
    response = {'batch_id': batch.id, 'items': items}
    db.add(AllocationReview(batch_id=batch.id, idempotency_key=key, request_digest=digest, response=response))
    db.commit()
    return response
