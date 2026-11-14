from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Text, Integer, BigInteger, Boolean, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(100))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    # Optional authenticator-app (TOTP) second step. Secret is base32; never returned once enabled.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

class SessionToken(Base):
    __tablename__ = "session_tokens"
    session_kind: Mapped[str] = mapped_column(String(10), default="bearer", server_default="bearer")
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    latest_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("batch_id", "order_ref"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    order_ref: Mapped[str] = mapped_column(String(100))
    customer_name: Mapped[str] = mapped_column(String(150))
    customer_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    amount_due_paisa: Mapped[int] = mapped_column(BigInteger)
    account_id: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    placed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (UniqueConstraint("batch_id", "account_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(String(100))
    provider_pair: Mapped[str] = mapped_column(String(150), default="unknown")
    coverage_start: Mapped[datetime] = mapped_column(DateTime)
    coverage_end: Mapped[datetime] = mapped_column(DateTime)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    references_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    filename: Mapped[str] = mapped_column(String(200))

class StatementLine(Base):
    __tablename__ = "statement_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    statement_id: Mapped[str] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(String(100))
    posted_at: Mapped[datetime] = mapped_column(DateTime)
    amount_paisa: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[str] = mapped_column(String(6))
    counterparty: Mapped[str] = mapped_column(String(200), default="")
    transaction_id: Mapped[str] = mapped_column(String(150), default="")
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    credit_key: Mapped[str] = mapped_column(String(64), index=True)

class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(String(100))
    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    image_path: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    read_a: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    read_b: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fields_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_mode: Mapped[str] = mapped_column(String(20), default="manual")
    extraction_status: Mapped[str] = mapped_column(String(30), default="pending")
    extraction_error: Mapped[str | None] = mapped_column(String(100), nullable=True)

class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("batch_id", "kind", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    input_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    lease: Mapped[str | None] = mapped_column(String(36), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)

class Run(Base):
    __tablename__ = "reconciliation_runs"
    __table_args__ = (UniqueConstraint("batch_id", "input_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    input_revision: Mapped[int] = mapped_column(Integer)
    rules_version: Mapped[str] = mapped_column(String(30), default="milaan-rules-1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("run_id", "order_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    machine_verdict: Mapped[str] = mapped_column(String(10))
    final_status: Mapped[str] = mapped_column(String(10))
    reason_code: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    candidate_ids: Mapped[list] = mapped_column(JSON, default=list)
    selected_line_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewer_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (UniqueConstraint("match_id", "credit_key", name="uq_allocation_match_credit"),
                      CheckConstraint("amount_paisa > 0", name="ck_allocation_positive"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    credit_key: Mapped[str] = mapped_column(String(64), index=True)
    statement_line_id: Mapped[str] = mapped_column(ForeignKey("statement_lines.id", ondelete="CASCADE"))
    amount_paisa: Mapped[int] = mapped_column(BigInteger)

class AllocationReview(Base):
    __tablename__ = "allocation_reviews"
    __table_args__ = (UniqueConstraint("batch_id", "idempotency_key", name="uq_allocation_review_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_digest: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Content(Base):
    __tablename__ = "content"
    __table_args__ = (UniqueConstraint("owner_id", "key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class PendingSignup(Base):
    __tablename__ = "pending_signups"
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE", name="fk_pending_signup_user"), nullable=True)
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    challenge_id: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(100))
    code_hash: Mapped[str] = mapped_column(String(256))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime)
    window_start: Mapped[datetime] = mapped_column(DateTime)
    send_count: Mapped[int] = mapped_column(Integer, default=1)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

class PasswordReset(Base):
    __tablename__ = "password_resets"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime)
    window_start: Mapped[datetime] = mapped_column(DateTime)
    send_count: Mapped[int] = mapped_column(Integer)


class ReceiptDeletion(Base):
    """Independent of claims/batches so cascades cannot erase deletion retries."""
    __tablename__ = "receipt_deletions"
    __table_args__ = (UniqueConstraint("storage_identity", "object_key", name="uq_receipt_deletion_object"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    object_key: Mapped[str] = mapped_column(String(100))
    storage_identity: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class CreditLedger(Base):
    """Bank credits already used to fund orders. Outlives the 7-day batches (copied in when a
    batch is deleted or expires) so the same credit cannot fund a new order later."""
    __tablename__ = "credit_ledger"
    __table_args__ = (CheckConstraint("amount_paisa > 0", name="ck_credit_ledger_positive"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    credit_key: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[str] = mapped_column(String(100))
    credit_amount_paisa: Mapped[int] = mapped_column(BigInteger)
    amount_paisa: Mapped[int] = mapped_column(BigInteger)
    order_ref: Mapped[str] = mapped_column(String(100))
    transaction_id: Mapped[str] = mapped_column(String(150), default="")
    batch_name: Mapped[str] = mapped_column(String(150), default="")
    used_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    retain_until: Mapped[datetime] = mapped_column(DateTime, index=True)


class DecisionLog(Base):
    """Minimal long-lived record of SHIP/HOLD/REVIEW decisions (no images, no customer names)."""
    __tablename__ = "decision_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    batch_name: Mapped[str] = mapped_column(String(150), default="")
    order_ref: Mapped[str] = mapped_column(String(100))
    amount_paisa: Mapped[int] = mapped_column(BigInteger)
    decision: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text, default="")
    transaction_id: Mapped[str] = mapped_column(String(150), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    retain_until: Mapped[datetime] = mapped_column(DateTime, index=True)
