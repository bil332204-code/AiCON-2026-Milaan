from .allocations import lock_seller, add_allocation
"""Database-backed queue; API thread or the standalone worker can consume jobs."""
from datetime import timedelta
import threading, time, logging
from sqlalchemy import select, delete
from .models import Job, Batch, Claim, Order, Statement, StatementLine, Run, Match, Allocation, AuditEvent, SessionToken, PasswordReset, now, uid
from .matcher import compute_matches, RULES_VERSION
from .extraction import double_read, ExtractionUnavailable
from .storage import receipt_storage, StorageMissing, StorageUnavailable, enqueue_deletion, drain_deletions
from .ledger import used_credit_keys, remove_batch, purge_expired, log_decision

log = logging.getLogger("milaan.jobs")

def audit(db, batch_id, actor, action, detail=None):
    db.add(AuditEvent(batch_id=batch_id, actor_id=actor, action=action, detail=detail or {}))

def take_job(database, settings):
    with database.transaction() as db:
        stale = now() - timedelta(seconds=settings.worker_lease_seconds)
        for old in db.scalars(select(Job).where(Job.status == "running", Job.updated_at < stale).with_for_update(skip_locked=True)):
            old.status, old.lease, old.error = "queued", None, "RETRIED_AFTER_INTERRUPTION"
        job = db.scalar(select(Job).where(Job.status == "queued").order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job: return None
        job.status, job.lease, job.updated_at = "running", uid(), now()
        return job.id, job.lease

def current_job(db, job_id, lease):
    job = db.get(Job, job_id)
    return job if job and job.status == "running" and job.lease == lease else None

def process_job(database, settings, job_id, lease):
    with database.sessions() as db:
        job = current_job(db, job_id, lease)
        if not job: return
        kind, batch_id = job.kind, job.batch_id
        claim_ids = list(db.scalars(select(Claim.id).where(Claim.batch_id == batch_id, Claim.extraction_status == "pending")))
    if kind == "extract":
        for index, claim_id in enumerate(claim_ids):
            with database.sessions() as db:
                if not current_job(db, job_id, lease): return
                claim = db.get(Claim, claim_id)
                if not claim: continue
                path = claim.image_path
            error = None
            try:
                if not path: raise ExtractionUnavailable("IMAGE_NOT_AVAILABLE")
                a, b, checked = double_read(receipt_storage(settings).get(path), settings)
            except ExtractionUnavailable as exc:
                error = str(exc)
            except (OSError, StorageMissing, StorageUnavailable):
                error = "IMAGE_NOT_AVAILABLE"
            with database.transaction() as db:
                job = current_job(db, job_id, lease)
                if not job: return
                claim = db.get(Claim, claim_id)
                if claim:
                    claim.version += 1
                    claim.extraction_mode = "gemini"
                    if error:
                        claim.extraction_status, claim.extraction_error, claim.fields_checked = "failed", error, False
                    else:
                        claim.read_a, claim.read_b, claim.fields = a, b, a
                        # Two agreeing model reads are a suggestion, not a human check: the
                        # seller must confirm the fields before they can support SHIP.
                        claim.fields_checked = False
                        claim.extraction_status = "needs_review"
                        claim.extraction_error = None if checked else "READS_DISAGREE_OR_INCOMPLETE"
                job.progress, job.updated_at = index + 1, now()
        with database.transaction() as db:
            job = current_job(db, job_id, lease)
            if not job: return
            batch = db.scalar(select(Batch).where(Batch.id == batch_id).with_for_update())
            batch.revision += 1
            job.status, job.updated_at = "done", now()
            audit(db, batch_id, batch.owner_id, "extraction_completed", {"job_id": job_id, "images": len(claim_ids), "provider": "gemini"})
    elif kind == "reconcile":
        # Load a snapshot, release the connection, compute (CPU-heavy, can take minutes on a
        # small instance), then write in a short transaction that re-checks the inputs.
        # Holding a transaction open while computing would hit Postgres's idle timeout.
        snapshot, computed = None, None
        with database.sessions() as db:
            job = current_job(db, job_id, lease)
            if not job: return
            batch = db.get(Batch, batch_id)
            if not batch or batch.revision != job.input_revision:
                raise ValueError("INPUT_REVISION_CHANGED")
            if not db.scalar(select(Run.id).where(Run.batch_id == batch_id, Run.input_revision == job.input_revision)):
                snapshot = (list(db.scalars(select(Order).where(Order.batch_id == batch_id))),
                            list(db.scalars(select(Claim).where(Claim.batch_id == batch_id))),
                            list(db.scalars(select(Statement).where(Statement.batch_id == batch_id))),
                            list(db.scalars(select(StatementLine).where(StatementLine.batch_id == batch_id))),
                            used_credit_keys(db, batch.owner_id))
        # Session closed (objects stay loaded): no connection is held while computing.
        if snapshot:
            orders, claims, statements, lines, used = snapshot
            computed = compute_matches(orders, claims, statements, lines, used)
        with database.transaction() as db:
            job = current_job(db, job_id, lease)
            if not job: return
            batch = db.scalar(select(Batch).where(Batch.id == batch_id).with_for_update())
            if not batch or batch.revision != job.input_revision:
                raise ValueError("INPUT_REVISION_CHANGED")
            existing = db.scalar(select(Run).where(Run.batch_id == batch_id, Run.input_revision == job.input_revision))
            if existing:
                batch.latest_run_id = existing.id
                job.status, job.updated_at = "done", now()
                return
            if computed is None:
                raise ValueError("RUN_DISAPPEARED")
            lock_seller(db, batch.owner_id)
            # Credits used elsewhere while we computed cannot be shipped again.
            now_used = used_credit_keys(db, batch.owner_id)
            lookup = {l.id: l for l in lines}
            order_lookup = {o.id: o for o in orders}
            for data in computed:
                if data["final_status"] == "ship" and lookup[data["selected_line_id"]].credit_key in now_used:
                    data.update(machine_verdict="review", final_status="review", selected_line_id=None,
                                reason_code="CREDIT_ALREADY_USED",
                                reason="A candidate credit is already assigned in this seller's retained records.")
            run = Run(batch_id=batch_id, input_revision=job.input_revision, rules_version=RULES_VERSION)
            db.add(run); db.flush()
            for data in computed:
                match = Match(batch_id=batch_id, run_id=run.id, **data)
                db.add(match); db.flush()
                order = order_lookup[match.order_id]
                if match.final_status == "ship":
                    line = lookup[match.selected_line_id]
                    add_allocation(db, owner_id=batch.owner_id, batch_id=batch_id, match_id=match.id, order_id=match.order_id,
                                   claim_id=match.claim_id, line=line, amount=line.amount_paisa)
                    log_decision(db, settings, owner_id=batch.owner_id, batch=batch, order=order, decision="ship",
                                 source="automatic", reason=match.reason_code, transaction_id=line.transaction_id)
                elif match.final_status == "hold":
                    log_decision(db, settings, owner_id=batch.owner_id, batch=batch, order=order, decision="hold",
                                 source="automatic", reason=match.reason_code)
            batch.latest_run_id = run.id
            job.status, job.progress, job.total, job.updated_at = "done", len(orders), len(orders), now()
            audit(db, batch_id, batch.owner_id, "reconciled", {"run_id": run.id, "orders": len(orders), "rules_version": RULES_VERSION})

def run_once(database, settings):
    selected = take_job(database, settings)
    if not selected: return False
    job_id, lease = selected
    try: process_job(database, settings, job_id, lease)
    except Exception:
        log.error("Job %s failed; inspect its sanitized error code", job_id)
        with database.transaction() as db:
            job = current_job(db, job_id, lease)
            if job: job.status, job.error, job.updated_at = "failed", "JOB_FAILED_RETRY_WITH_NEW_KEY", now()
    return True

def cleanup(database, settings):
    storage = receipt_storage(settings)
    with database.transaction() as db:
        for batch in db.scalars(select(Batch).where(Batch.expires_at <= now()).with_for_update()):
            for key in db.scalars(select(Claim.image_path).where(Claim.batch_id == batch.id, Claim.image_path.is_not(None))):
                enqueue_deletion(db, storage, key)
            remove_batch(db, batch, settings)
        purge_expired(db)
        db.execute(delete(SessionToken).where(SessionToken.expires_at <= now()))
        db.execute(delete(PasswordReset).where(PasswordReset.expires_at <= now(), PasswordReset.window_start < now()-timedelta(hours=1)))
    drain_deletions(database, storage)
    # Crash-created uploads have no committed Claim. Grace exceeds bounded I/O.
    # Namespace is dedicated to this deployment; never scan the entire bucket.
    for key, modified in storage.objects():
        if modified > now() - timedelta(hours=1): continue
        with database.transaction() as db:
            if not db.scalar(select(Claim.id).where(Claim.image_path == key)):
                enqueue_deletion(db, storage, key)
    drain_deletions(database, storage)

def worker_loop(database, settings, stop: threading.Event):
    last_cleanup = 0.0
    while not stop.is_set():
        try:
            if time.monotonic() - last_cleanup > 60:
                last_cleanup = time.monotonic()
                try: cleanup(database, settings)
                except Exception: log.error("Retention cleanup failed; durable erasures will retry without blocking jobs")
            if not run_once(database, settings): stop.wait(1)
        except Exception:
            log.error("Worker polling failed; retrying without exposing record data")
            stop.wait(3)
