from .browser_auth import check_origin, check_csrf, session_result
from .allocations import lock_seller, remaining_credit, add_allocation
from .allocation_review import review_allocations
from contextlib import asynccontextmanager
from datetime import timedelta, datetime, timezone
from pathlib import Path
import json, threading, secrets, hashlib, logging
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, delete, func, inspect, text
from sqlalchemy.exc import IntegrityError
from .config import Settings
from .database import Database
from .models import PasswordReset, PendingSignup, User, SessionToken, Batch, Order, Statement, StatementLine, Claim, Job, Match, Run, Allocation, AuditEvent, Content, Product, CartItem, MarketplaceOrder, MarketplaceOrderItem, now, uid
from .schemas import ResetRequest, ResetPassword, AllocationPlan, ImportProvenance, VerifyEmail, ResendEmail, Register, Login, BatchCreate, OrderInput, OrderUpdate, ClaimUpdate, Decision, Reset, ExtractionRequest, ContentWrite, RetryExtraction, ProductCreate, ProductUpdate, StockUpdate, CartItemAdd, CartItemUpdate, CheckoutRequest, OrderStatusUpdate
from .emailer import EmailDeliveryError, send_verification, send_password_reset
from .security import password_hash, verify_password, issue_session, token_digest, csrf_token
from .parsing import paisa, parse_time, parse_orders, parse_statement, csv_export
from .storage import clean_image, receipt_storage, StorageMissing, StorageUnavailable, enqueue_deletion, drain_deletions
from .middleware import GuardMiddleware, CanonicalOriginMiddleware
from .jobs import audit, worker_loop

DUMMY_PASSWORD_HASH = password_hash(secrets.token_urlsafe(32))

DEFAULT_CONTENT = {
    "branding": {"product_name": "Milaan", "tagline": "Every payment, in its place.", "hero_title": "Find the match. Before you ship."},
    "workspace": {"shop_name": "My shop", "currency": "PKR", "timezone": "Asia/Karachi"},
    "messages": {"review": "Please share the full transaction reference and a clear payment screenshot.", "matched": "Thank you. Your payment matches our statement records."},
    "faq": {"items": [{"question": "Does Milaan verify with the bank?", "answer": "No. It reconciles against your uploaded statement."}]},
}

def record(obj):
    if obj is None: return None
    data = {}
    for column in inspect(obj).mapper.column_attrs:
        value = getattr(obj, column.key)
        data[column.key] = value.isoformat() + "Z" if isinstance(value, datetime) else value
    return data

def user_record(user):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "email_verified": bool(user.email_verified_at),
        "is_admin": bool(getattr(user, "is_admin", False)),
    }

def import_provenance(raw, declared):
    metadata = {"stored_csv_sha256": hashlib.sha256(raw).hexdigest()}
    if declared:
        try:
            metadata["client_declared_source"] = ImportProvenance.model_validate_json(declared).model_dump()
        except ValueError:
            raise HTTPException(422, "Invalid import provenance metadata")
    return metadata


def create_app(settings=None):
    settings = settings or Settings()
    database = Database(settings.database_url, pool_size=settings.database_pool_size, max_overflow=settings.database_max_overflow)
    storage = receipt_storage(settings)
    # GuardMiddleware bounds the complete body before multipart parsing. Keep every
    # accepted upload in RAM: Starlette otherwise spills >1 MiB bank files to /tmp.
    from starlette.formparsers import MultiPartParser
    MultiPartParser.spool_max_size = max(MultiPartParser.spool_max_size, settings.max_request_bytes)
    @asynccontextmanager
    async def lifespan(app):
        if not inspect(database.engine).has_table("users") or not inspect(database.engine).has_table("pending_signups") or not inspect(database.engine).has_table("receipt_deletions"):
            raise RuntimeError("Database is not migrated. Run: python -m alembic upgrade head")
        if not settings.testing and settings.demo_seller_email and settings.demo_seller_password:
            if len(settings.demo_seller_password)<10:raise RuntimeError("Set an admin password of at least 10 characters")
            with database.transaction() as db:
                if not db.scalar(select(User).where(User.email==settings.demo_seller_email.lower())):
                    db.add(User(email=settings.demo_seller_email.lower(),password_hash=password_hash(settings.demo_seller_password),display_name="Demo operator",is_admin=True))
        stop, thread = threading.Event(), None
        if settings.run_worker:
            thread = threading.Thread(target=worker_loop, args=(database, settings, stop), daemon=True)
            thread.start()
        yield
        stop.set()
        if thread: thread.join(timeout=3)
        database.engine.dispose()
    app = FastAPI(title="Milaan Backend", version="1.0.0", description="Persistent seller-scoped reconciliation API. Amounts are integer paisa. Times returned as UTC.", lifespan=lifespan)
    app.state.database, app.state.settings, app.state.receipt_storage = database, settings, storage
    app.add_middleware(GuardMiddleware, limit=settings.max_request_bytes, testing=settings.testing)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-CSRF-Token"], expose_headers=["Content-Disposition"])
    app.add_middleware(CanonicalOriginMiddleware, settings=settings)
    bearer = HTTPBearer(auto_error=False)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        # Never echo passwords, provider keys or uploaded financial data in error payloads.
        return JSONResponse({"detail": [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]}, 422)

    @app.exception_handler(StorageUnavailable)
    async def storage_unavailable(request, exc):
        return JSONResponse({"detail": "Receipt storage temporarily unavailable; retry later"}, 503)

    @app.exception_handler(IntegrityError)
    async def integrity(request, exc):
        return JSONResponse({"detail": "Record conflict. Reload current data; the operation was rolled back."}, 409)

    def get_db(request: Request):
        with database.sessions() as db:
            try:
                if request.method in {"POST", "PUT", "PATCH", "DELETE"}: database.begin(db)
                yield db
            finally:
                db.rollback()

    def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
        kind = 'bearer' if credentials else 'cookie'
        raw = credentials.credentials if credentials else request.cookies.get(settings.cookie_name)
        if not raw: raise HTTPException(401, 'Sign in to continue', headers={'WWW-Authenticate':'Bearer'})
        session = db.get(SessionToken, token_digest(raw))
        if not session or session.expires_at <= now() or session.session_kind != kind:
            raise HTTPException(401, 'Session is invalid or expired')
        if kind == 'cookie' and request.method not in {'GET','HEAD','OPTIONS'}:
            check_csrf(request, settings, raw)
        user = db.get(User, session.user_id)
        if not user: raise HTTPException(401, 'Session is invalid')
        request.state.session_raw, request.state.auth_session = raw, session
        return user

    def require_admin(user=Depends(current_user)):
        is_adm = bool(getattr(user, "is_admin", False) or (user.email == settings.demo_seller_email))
        if not is_adm: raise HTTPException(403, "Administrator access required")
        return user

    def own_batch(db, batch_id, user, lock=False):
        q = select(Batch).where(Batch.id == batch_id, Batch.owner_id == user.id, Batch.expires_at > now()).execution_options(populate_existing=True)
        if lock: q = q.with_for_update()
        batch = db.scalar(q)
        if not batch: raise HTTPException(404, "Batch not found")
        return batch

    def mutable(db, batch_id, user, expected=None):
        batch = own_batch(db, batch_id, user, True)
        if expected is not None and batch.revision != expected: raise HTTPException(409, "Batch revision changed. Reload first.")
        if db.scalar(select(Job.id).where(Job.batch_id == batch.id, Job.status.in_(["queued", "running"])).limit(1)):
            raise HTTPException(409, "Batch has an active job. Wait before changing inputs.")
        if batch.latest_run_id: raise HTTPException(409, "Reset the current results explicitly before editing source records.")
        return batch

    def own_claim(db, claim_id, user, lock=False):
        claim = db.get(Claim, claim_id)
        if not claim: raise HTTPException(404, "Claim not found")
        batch = own_batch(db, claim.batch_id, user, lock)
        return claim, batch

    @app.get("/api/health", tags=["system"])
    def health(db=Depends(get_db)):
        db.execute(text("SELECT 1"))
        return {"status": "ok", "version": "1.0.0", "database": "reachable"}

    def verification_response(pending):
        return {"verification_required": True, "challenge_id": pending.challenge_id,
                "email": pending.email, "expires_in": 600, "resend_after": 60}

    def check_send_limit(pending):
        if (now() - pending.last_sent_at).total_seconds() < 60:
            raise HTTPException(429, "Wait 60 seconds before requesting another code")
        if (now() - pending.window_start).total_seconds() >= 3600:
            pending.window_start, pending.send_count = now(), 0
        if pending.send_count >= 5:
            raise HTTPException(429, "Email code limit reached. Try again in one hour")

    def deliver_code(pending):
        code = f"{secrets.randbelow(1000000):06d}"
        pending.code_hash = password_hash(code)
        pending.expires_at = now() + timedelta(minutes=10)
        pending.last_sent_at, pending.attempts = now(), 0
        pending.send_count += 1
        try:
            send_verification(settings, pending.email, code)
        except Exception:
            raise HTTPException(503, "Could not send the verification email. Try again later or contact the server owner.") from None

    @app.post("/api/auth/resend-code", tags=["auth"])
    def resend_code(body: ResendEmail, db=Depends(get_db)):
        if not settings.registration_open: raise HTTPException(403, "Registration is disabled")
        pending = db.scalar(select(PendingSignup).where(PendingSignup.challenge_id == body.challenge_id, PendingSignup.user_id.is_(None)).with_for_update())
        if not pending: raise HTTPException(400, "Signup expired or completed. Start signup again")
        check_send_limit(pending)
        deliver_code(pending)
        db.commit()
        return verification_response(pending)

    @app.post("/api/auth/verify-email", tags=["auth"])
    def verify_email(body: VerifyEmail, request: Request, response: Response, db=Depends(get_db)):
        if body.session_mode == "cookie": check_origin(request, settings)
        if not settings.registration_open: raise HTTPException(403, "Registration is disabled")
        pending = db.scalar(select(PendingSignup).where(PendingSignup.challenge_id == body.challenge_id, PendingSignup.user_id.is_(None)).with_for_update())
        if not pending: raise HTTPException(400, "Signup expired or completed. Start signup again")
        if pending.expires_at <= now(): raise HTTPException(400, "Code expired. Request a new code")
        if pending.attempts >= 5: raise HTTPException(429, "Too many incorrect codes. Request a new code")
        if not verify_password(body.code, pending.code_hash):
            pending.attempts += 1
            db.commit()
            raise HTTPException(400, "Incorrect code. Check your email")
        user = User(email=pending.email, password_hash=pending.password_hash, display_name=pending.display_name, email_verified_at=now())
        db.add(user); db.flush()
        token = session_result(db, user.id, body.session_mode, request, response, settings)
        db.delete(pending)
        db.commit()
        return {**token, "user": user_record(user)}

    @app.post("/api/auth/register", status_code=201, tags=["auth"])
    def register(body: Register, request: Request, response: Response, db=Depends(get_db)):
        if body.session_mode == "cookie": check_origin(request, settings)
        if not settings.registration_open: raise HTTPException(403, "Registration is disabled")
        if db.scalar(select(User).where(User.email == str(body.email).lower())): raise HTTPException(409, "Account cannot be created with this email")
        if settings.require_email_verification:
            email = str(body.email).lower()
            pending = db.scalar(select(PendingSignup).where(PendingSignup.email == email).with_for_update())
            if pending:
                check_send_limit(pending)
                pending.challenge_id = secrets.token_urlsafe(32)
                pending.password_hash = password_hash(body.password)
                pending.display_name = body.display_name
            else:
                pending = PendingSignup(email=email, challenge_id=secrets.token_urlsafe(32),
                    password_hash=password_hash(body.password), display_name=body.display_name,
                    window_start=now(), send_count=0, attempts=0)
                db.add(pending)
            deliver_code(pending)
            db.commit()
            return verification_response(pending)
        user = User(email=str(body.email).lower(), password_hash=password_hash(body.password), display_name=body.display_name)
        db.add(user); db.flush()
        token = session_result(db, user.id, body.session_mode, request, response, settings)
        db.commit()
        return {**token, "user": user_record(user)}

    @app.post('/api/auth/login', tags=['auth'])
    def login(body: Login, request: Request, response: Response, db=Depends(get_db)):
        if body.session_mode == 'cookie': check_origin(request, settings)
        user = db.scalar(select(User).where(User.email == str(body.email).lower()).with_for_update())
        locked = bool(user and user.login_locked_until and user.login_locked_until > now())
        valid = verify_password(body.password, user.password_hash if user and not locked else DUMMY_PASSWORD_HASH)
        if not user or locked or not valid:
            if user and not locked:
                if user.login_locked_until: user.failed_logins, user.login_locked_until = 0, None
                user.failed_logins += 1
                if user.failed_logins >= 5: user.login_locked_until = now()+timedelta(minutes=15)
                db.commit()
            raise HTTPException(401, 'Incorrect email or password, or account temporarily unavailable. Try again later.')
        user.failed_logins, user.login_locked_until = 0, None
        if not user.password_hash.startswith('scrypt-v2$'): user.password_hash = password_hash(body.password)
        token = session_result(db, user.id, body.session_mode, request, response, settings, body.remember_me)
        db.commit()
        return {**token, 'user':user_record(user)}

    @app.post('/api/auth/logout', status_code=204, tags=['auth'])
    def logout(request: Request, user=Depends(current_user), db=Depends(get_db)):
        db.execute(delete(SessionToken).where(SessionToken.token_hash == token_digest(request.state.session_raw)))
        db.commit()
        response = Response(status_code=204)
        response.delete_cookie(settings.cookie_name, path='/', secure=settings.cookie_secure, httponly=True, samesite='lax')
        return response

    @app.post('/api/auth/logout-all', status_code=204, tags=['auth'])
    def logout_all(request: Request, user=Depends(current_user), db=Depends(get_db)):
        db.execute(delete(SessionToken).where(SessionToken.user_id == user.id)); db.commit()
        response = Response(status_code=204)
        response.delete_cookie(settings.cookie_name, path='/', secure=settings.cookie_secure, httponly=True, samesite='lax')
        return response

    @app.get('/api/auth/session', tags=['auth'])
    def browser_session(request: Request, user=Depends(current_user)):
        return {'user':user_record(user), 'csrf_token':csrf_token(request.state.session_raw) if request.state.auth_session.session_kind == 'cookie' else None,
                'expires_at':request.state.auth_session.expires_at.isoformat()+'Z'}

    @app.get('/api/auth/me', tags=['auth'])
    def me(user=Depends(current_user)): return user_record(user)

    @app.post('/api/auth/verify-account-email/start', tags=['auth'])
    def start_account_email_verification(user=Depends(current_user), db=Depends(get_db)):
        user = db.scalar(select(User).where(User.id == user.id).with_for_update())
        if user.email_verified_at: return {'email_verified':True}
        pending = db.scalar(select(PendingSignup).where(PendingSignup.email == user.email).with_for_update())
        if pending: check_send_limit(pending)
        else:
            pending = PendingSignup(email=user.email, window_start=now(), send_count=0, attempts=0)
            db.add(pending)
        pending.user_id, pending.challenge_id = user.id, secrets.token_urlsafe(32)
        pending.password_hash, pending.display_name = user.password_hash, user.display_name
        deliver_code(pending);db.commit()
        return verification_response(pending)

    @app.post('/api/auth/verify-account-email', tags=['auth'])
    def verify_account_email(body: VerifyEmail, user=Depends(current_user), db=Depends(get_db)):
        user = db.scalar(select(User).where(User.id == user.id).with_for_update())
        pending = db.scalar(select(PendingSignup).where(PendingSignup.user_id == user.id,
                            PendingSignup.email == user.email, PendingSignup.challenge_id == body.challenge_id).with_for_update())
        if not pending or pending.expires_at <= now(): raise HTTPException(400, 'Verification expired; request a new code')
        if pending.attempts >= 5: raise HTTPException(429, 'Too many incorrect codes; request a new code')
        if not verify_password(body.code, pending.code_hash):
            pending.attempts += 1;db.commit();raise HTTPException(400, 'Incorrect code')
        user.email_verified_at = now();db.delete(pending);db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id));db.commit()
        return user_record(user)

    @app.post('/api/auth/request-password-reset', tags=['auth'])
    def request_password_reset(body: ResetRequest, request: Request, db=Depends(get_db)):
        check_origin(request, settings)
        message = {'message':'If that address has an account, check your inbox for reset instructions.'}
        user = db.scalar(select(User).where(User.email == str(body.email).lower()).with_for_update())
        if not user or not user.email_verified_at: return message
        pending = db.get(PasswordReset, user.id)
        if pending:
            if (now()-pending.last_sent_at).total_seconds()<60: return message
            if (now()-pending.window_start).total_seconds()>=3600: pending.window_start, pending.send_count = now(), 0
            if pending.send_count>=5: return message
        raw = secrets.token_urlsafe(48)
        if not pending:
            pending = PasswordReset(user_id=user.id,window_start=now(),send_count=0)
            db.add(pending)
        pending.token_hash, pending.expires_at, pending.last_sent_at = token_digest(raw), now()+timedelta(minutes=15), now()
        pending.send_count += 1
        try: send_password_reset(settings, user.email, raw)
        except EmailDeliveryError as exc:
            # Fixed categories / status codes only. Do not log PII, provider errors or reset tokens.
            logging.getLogger('milaan.auth').warning(
                'Password recovery email delivery failed (reason=%s, provider_status=%s)',
                exc.category, exc.provider_status)
        except Exception:
            logging.getLogger('milaan.auth').warning(
                'Password recovery email delivery failed (reason=unexpected)')
        db.commit()
        return message

    @app.post('/api/auth/reset-password', tags=['auth'])
    def reset_password(body: ResetPassword, request: Request, response: Response, db=Depends(get_db)):
        check_origin(request, settings)
        pending = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == token_digest(body.token)))
        if not pending: raise HTTPException(400, 'Reset link is invalid or expired. Request a new one.')
        # Lock order is user then reset record in both recovery endpoints.
        user = db.scalar(select(User).where(User.id == pending.user_id).with_for_update())
        pending = db.scalar(select(PasswordReset).where(PasswordReset.user_id == pending.user_id, PasswordReset.token_hash == token_digest(body.token)).with_for_update().execution_options(populate_existing=True))
        if not user or not user.email_verified_at or not pending or pending.expires_at <= now():
            raise HTTPException(400, 'Reset link is invalid or expired. Request a new one.')
        user.password_hash, user.failed_logins, user.login_locked_until = password_hash(body.password), 0, None
        db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
        db.delete(pending); db.commit()
        response.delete_cookie(settings.cookie_name,path='/',secure=settings.cookie_secure,httponly=True,samesite='lax')
        return {'message':'Password updated. Sign in again; all previous sessions have been revoked.'}

    @app.get("/api/integrations/status", tags=["system"])
    def integrations(user=Depends(current_user)):
        return {"extraction_provider": settings.extraction_provider, "gemini_configured": bool(settings.gemini_key and settings.gemini_model),
                "bank_connected": False, "retention_hours": settings.retention_hours, "background_worker_in_api": settings.run_worker}

    @app.get("/api/content", tags=["content"])
    def get_content(user=Depends(current_user), db=Depends(get_db)):
        saved = {c.key: c for c in db.scalars(select(Content).where(Content.owner_id == user.id))}
        return {key: {"value": saved[key].value if key in saved else value, "version": saved[key].version if key in saved else 0} for key, value in DEFAULT_CONTENT.items()}

    @app.put("/api/content/{key}", tags=["content"])
    def put_content(key: str, body: ContentWrite, user=Depends(current_user), db=Depends(get_db)):
        if key not in DEFAULT_CONTENT: raise HTTPException(404, "Supported keys: branding, workspace, messages, faq")
        if len(json.dumps(body.value)) > 16000: raise HTTPException(422, "Content exceeds 16 KB")
        item = db.scalar(select(Content).where(Content.owner_id == user.id, Content.key == key).with_for_update())
        if (item.version if item else 0) != body.expected_version: raise HTTPException(409, "Content version changed")
        if not item:
            item = Content(owner_id=user.id, key=key, value=body.value, version=1); db.add(item)
        else: item.value, item.version, item.updated_at = body.value, item.version + 1, now()
        db.commit()
        return {"key": key, "value": item.value, "version": item.version}

    @app.get("/api/batches", tags=["batches"])
    def batches(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(current_user), db=Depends(get_db)):
        q = select(Batch).where(Batch.owner_id == user.id, Batch.expires_at > now()).order_by(Batch.created_at.desc()).offset(offset).limit(limit)
        return {"items": [record(b) for b in db.scalars(q)], "offset": offset, "limit": limit}

    @app.post("/api/batches", status_code=201, tags=["batches"])
    def create_batch(body: BatchCreate, user=Depends(current_user), db=Depends(get_db)):
        if db.scalar(select(func.count()).select_from(Batch).where(Batch.owner_id == user.id)) >= settings.max_batches: raise HTTPException(409, "Batch limit reached; remove old batches")
        b = Batch(owner_id=user.id, name=body.name, expires_at=now()+timedelta(hours=settings.retention_hours))
        db.add(b); db.flush(); audit(db, b.id, user.id, "batch_created")
        db.commit(); return record(b)

    @app.post("/api/batches/demo", status_code=201, tags=["demo"])
    def create_demo(user=Depends(current_user), db=Depends(get_db)):
        if not settings.enable_demo: raise HTTPException(403, "Demo creation is disabled")
        if db.scalar(select(func.count()).select_from(Batch).where(Batch.owner_id == user.id)) >= settings.max_batches: raise HTTPException(409, "Batch limit reached")
        from .demo import seed_demo
        batch = seed_demo(db, user.id, settings)
        db.commit(); return record(batch)

    @app.get("/api/batches/{batch_id}", tags=["batches"])
    def get_batch(batch_id: str, user=Depends(current_user), db=Depends(get_db)):
        return record(own_batch(db, batch_id, user))

    @app.delete("/api/batches/{batch_id}", status_code=204, tags=["batches"])
    def delete_batch(batch_id: str, user=Depends(current_user), db=Depends(get_db)):
        batch = own_batch(db, batch_id, user, True)
        paths = list(db.scalars(select(Claim.image_path).where(Claim.batch_id == batch_id, Claim.image_path.is_not(None))))
        for path in paths: enqueue_deletion(db, storage, path)
        db.delete(batch); db.commit()
        drain_deletions(database, storage, limit=1)
        return Response(status_code=204)

    @app.post("/api/batches/{batch_id}/reset", tags=["batches"])
    def reset(batch_id: str, body: Reset, user=Depends(current_user), db=Depends(get_db)):
        b = own_batch(db, batch_id, user, True)
        if b.revision != body.expected_revision: raise HTTPException(409, "Batch revision changed")
        if db.scalar(select(Job.id).where(Job.batch_id == b.id, Job.status.in_(["queued", "running"])).limit(1)): raise HTTPException(409, "Wait for the current job")
        db.execute(delete(Allocation).where(Allocation.batch_id == batch_id))
        old = b.latest_run_id
        b.latest_run_id, b.revision = None, b.revision + 1
        audit(db, b.id, user.id, "results_reset", {"reason": body.reason, "old_run_id": old})
        db.commit(); return record(b)

    @app.get("/api/batches/{batch_id}/orders", tags=["orders"])
    def list_orders(batch_id: str, user=Depends(current_user), db=Depends(get_db)):
        own_batch(db, batch_id, user)
        return {"items": [record(o) for o in db.scalars(select(Order).where(Order.batch_id == batch_id).order_by(Order.order_ref))]}

    @app.post("/api/batches/{batch_id}/orders", status_code=201, tags=["orders"])
    async def upload_orders(batch_id: str, file: UploadFile = File(...), expected_revision: int = Form(...), provenance: str = Form("", max_length=4000), user=Depends(current_user), db=Depends(get_db)):
        b = mutable(db, batch_id, user, expected_revision)
        if db.scalar(select(Order.id).where(Order.batch_id == b.id).limit(1)): raise HTTPException(409, "Orders already exist. Edit individual orders or create a new batch.")
        raw = await file.read()
        metadata = import_provenance(raw, provenance)
        try: data = parse_orders(raw, settings.max_rows)
        except ValueError as e: raise HTTPException(422, str(e))
        orders = [Order(batch_id=b.id, **row) for row in data]
        db.add_all(orders); b.revision += 1
        audit(db, b.id, user.id, "orders_imported", {"count": len(orders), "rejected": 0, "provenance": metadata})
        db.commit(); return {"batch": record(b), "items": [record(o) for o in orders]}

    @app.post("/api/batches/{batch_id}/orders/item", status_code=201, tags=["orders"])
    def add_order(batch_id: str, body: OrderInput, user=Depends(current_user), db=Depends(get_db)):
        b = mutable(db, batch_id, user)
        if db.scalar(select(func.count()).select_from(Order).where(Order.batch_id == b.id)) >= settings.max_rows: raise HTTPException(409, "Order limit reached")
        try: amount = paisa(body.amount_due)
        except ValueError as e: raise HTTPException(422, str(e))
        o = Order(batch_id=b.id, order_ref=body.order_ref, customer_name=body.customer_name, amount_due_paisa=amount, account_id=body.account_id)
        db.add(o); b.revision += 1; audit(db, b.id, user.id, "order_added", {"order_ref": body.order_ref})
        db.commit(); return {"batch": record(b), "order": record(o)}

    @app.patch("/api/orders/{order_id}", tags=["orders"])
    def update_order(order_id: str, body: OrderUpdate, user=Depends(current_user), db=Depends(get_db)):
        o = db.get(Order, order_id)
        if not o: raise HTTPException(404, "Order not found")
        b = mutable(db, o.batch_id, user, body.expected_revision)
        try: o.amount_due_paisa = paisa(body.amount_due)
        except ValueError as e: raise HTTPException(422, str(e))
        o.order_ref, o.customer_name, o.account_id = body.order_ref, body.customer_name, body.account_id
        for c in db.scalars(select(Claim).where(Claim.order_id == o.id)):
            c.fields_checked = False; c.version += 1; c.account_id = o.account_id
        b.revision += 1; audit(db, b.id, user.id, "order_updated", {"order_id": o.id})
        db.commit(); return {"batch": record(b), "order": record(o)}

    @app.get("/api/batches/{batch_id}/statements", tags=["statements"])
    def statements(batch_id: str, user=Depends(current_user), db=Depends(get_db)):
        own_batch(db, batch_id, user)
        return {"items": [record(s) for s in db.scalars(select(Statement).where(Statement.batch_id == batch_id))]}

    @app.post("/api/batches/{batch_id}/statement", status_code=201, tags=["statements"])
    async def upload_statement(batch_id: str, file: UploadFile = File(...), expected_revision: int = Form(...),
                               account_id: str = Form(..., min_length=1, max_length=100), coverage_start: str = Form(...), coverage_end: str = Form(...),
                               complete: bool = Form(False), references_verified: bool = Form(False), provider_pair: str = Form("unknown", max_length=150),
                               provenance: str = Form("", max_length=4000), user=Depends(current_user), db=Depends(get_db)):
        b = mutable(db, batch_id, user, expected_revision)
        raw = await file.read()
        metadata = import_provenance(raw, provenance)
        try:
            start, end = parse_time(coverage_start), parse_time(coverage_end)
            if end <= start: raise ValueError("Coverage end must follow start")
            data = parse_statement(raw, user.id, account_id, settings.max_rows)
            if any(not start <= r["posted_at"] <= end for r in data): raise ValueError("A statement row falls outside its declared coverage")
        except ValueError as e: raise HTTPException(422, str(e))
        s = Statement(batch_id=b.id, account_id=account_id, provider_pair=provider_pair, coverage_start=start, coverage_end=end,
                      complete=complete, references_verified=references_verified, filename=Path(file.filename or "statement.csv").name[:200])
        db.add(s); db.flush()
        db.add_all(StatementLine(batch_id=b.id, statement_id=s.id, **row) for row in data)
        b.revision += 1; audit(db, b.id, user.id, "statement_imported", {"account_id": account_id, "rows": len(data), "coverage_declared": complete, "rejected": 0, "provenance": metadata})
        db.commit(); return {"batch": record(b), "statement": record(s), "line_count": len(data)}

    @app.get("/api/statements/{statement_id}/lines", tags=["statements"])
    def statement_lines(statement_id: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), user=Depends(current_user), db=Depends(get_db)):
        s = db.get(Statement, statement_id)
        if not s: raise HTTPException(404, "Statement not found")
        own_batch(db, s.batch_id, user)
        items = []
        for line in db.scalars(select(StatementLine).where(StatementLine.statement_id == s.id).order_by(StatementLine.posted_at).offset(offset).limit(limit)):
            out = record(line)
            used = db.scalar(select(func.coalesce(func.sum(Allocation.amount_paisa), 0)).where(Allocation.credit_key == line.credit_key))
            out["unallocated_paisa"] = max(0, line.amount_paisa-used) if line.direction == "CREDIT" else 0
            items.append(out)
        return {"items": items}

    @app.delete("/api/statements/{statement_id}", tags=["statements"])
    def delete_statement(statement_id: str, expected_revision: int = Query(...), user=Depends(current_user), db=Depends(get_db)):
        s = db.get(Statement, statement_id)
        if not s: raise HTTPException(404, "Statement not found")
        b = mutable(db, s.batch_id, user, expected_revision)
        db.delete(s); b.revision += 1; audit(db, b.id, user.id, "statement_removed")
        db.commit(); return {"batch": record(b)}

    @app.get("/api/batches/{batch_id}/claims", tags=["claims"])
    def claims(batch_id: str, user=Depends(current_user), db=Depends(get_db)):
        own_batch(db, batch_id, user)
        return {"items": [claim_record(c) for c in db.scalars(select(Claim).where(Claim.batch_id == batch_id))]}

    def claim_record(c):
        if c is None: return None
        out = record(c); out.pop("image_path", None)
        out["image_url"] = f"/api/claims/{c.id}/image" if c.image_path else None
        return out

    @app.post("/api/batches/{batch_id}/claims", status_code=201, tags=["claims"])
    async def upload_claim(batch_id: str, file: UploadFile = File(...), order_id: str = Form(...), expected_revision: int = Form(...), user=Depends(current_user), db=Depends(get_db)):
        b = mutable(db, batch_id, user, expected_revision)
        order = db.scalar(select(Order).where(Order.id == order_id, Order.batch_id == b.id))
        if not order: raise HTTPException(404, "Order not found in this batch")
        if db.scalar(select(func.count()).select_from(Claim).where(Claim.batch_id == b.id)) >= settings.max_claims: raise HTTPException(409, "Screenshot limit reached")
        try: cleaned, digest = clean_image(await file.read())
        except ValueError as e: raise HTTPException(422, str(e))
        claim_id = uid(); filename = claim_id + ".jpg"
        c = Claim(id=claim_id, batch_id=b.id, order_id=order.id, account_id=order.account_id,
                  filename=Path(file.filename or "receipt.jpg").name[:200], sha256=digest, image_path=filename)
        try:
            storage.put(filename, cleaned); db.add(c); b.revision += 1
            audit(db, b.id, user.id, "claim_uploaded", {"claim_id": c.id})
            db.commit()
        except Exception:
            db.rollback()
            # Even a timed-out PUT may have succeeded. Retry erasure durably.
            with database.transaction() as deletion_db: enqueue_deletion(deletion_db, storage, filename)
            drain_deletions(database, storage, limit=1)
            raise
        return {"batch": record(b), "claim": claim_record(c)}

    @app.get("/api/claims/{claim_id}/image", tags=["claims"])
    def image(claim_id: str, user=Depends(current_user), db=Depends(get_db)):
        c, _ = own_claim(db, claim_id, user)
        if not c.image_path: raise HTTPException(404, "Image not available")
        try: data = storage.get(c.image_path)
        except StorageMissing: raise HTTPException(404, "Image not available")
        return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.patch("/api/claims/{claim_id}", tags=["claims"])
    def update_claim(claim_id: str, body: ClaimUpdate, user=Depends(current_user), db=Depends(get_db)):
        c, _ = own_claim(db, claim_id, user)
        b = mutable(db, c.batch_id, user)
        db.refresh(c)
        if c.version != body.expected_version: raise HTTPException(409, "Claim version changed")
        if body.confirmed:
            try: paisa(body.fields.amount_pkr); parse_time(body.fields.datetime_local)
            except (ValueError, TypeError): raise HTTPException(422, "Confirmed fields need valid amount and complete timestamp")
        c.fields = body.fields.model_dump(); c.fields_checked = body.confirmed
        c.extraction_status, c.extraction_mode, c.extraction_error = "ready" if body.confirmed else "needs_review", "manual", None
        c.version += 1; b.revision += 1
        audit(db, b.id, user.id, "claim_corrected", {"claim_id": c.id, "confirmed": body.confirmed})
        db.commit(); return {"batch": record(b), "claim": claim_record(c)}

    @app.delete("/api/claims/{claim_id}", tags=["claims"])
    def delete_claim(claim_id: str, expected_version: int = Query(...), user=Depends(current_user), db=Depends(get_db)):
        c, _ = own_claim(db, claim_id, user); b = mutable(db, c.batch_id, user)
        db.refresh(c)
        if c.version != expected_version: raise HTTPException(409, "Claim version changed")
        path = c.image_path; db.delete(c); b.revision += 1; audit(db, b.id, user.id, "claim_removed", {"claim_id": claim_id})
        if path: enqueue_deletion(db, storage, path)
        db.commit()
        drain_deletions(database, storage, limit=1)
        return {"batch": record(b)}

    @app.post("/api/claims/{claim_id}/retry-extraction", tags=["claims"])
    def retry_extraction(claim_id: str, body: RetryExtraction, user=Depends(current_user), db=Depends(get_db)):
        c, _ = own_claim(db, claim_id, user); b = mutable(db, c.batch_id, user)
        db.refresh(c)
        if c.version != body.expected_version: raise HTTPException(409, "Claim version changed")
        if not c.image_path: raise HTTPException(422, "Upload an image first; synthetic claims have no image")
        c.extraction_status, c.extraction_error, c.fields_checked = "pending", None, False
        c.version += 1; b.revision += 1
        audit(db, b.id, user.id, "extraction_retry_requested", {"claim_id": c.id})
        db.commit(); return {"batch": record(b), "claim": claim_record(c)}

    def job_record(job):
        out = record(job); out.pop("lease", None); return out

    def enqueue(db, user, batch_id, kind, key):
        if not key or not 8 <= len(key) <= 100: raise HTTPException(422, "Send Idempotency-Key header (8-100 characters)")
        b = own_batch(db, batch_id, user, True)
        old = db.scalar(select(Job).where(Job.batch_id == b.id, Job.kind == kind, Job.idempotency_key == key))
        if old: return old
        mutable(db, batch_id, user)
        orders = db.scalar(select(func.count()).select_from(Order).where(Order.batch_id == b.id))
        lines = db.scalar(select(func.count()).select_from(StatementLine).where(StatementLine.batch_id == b.id))
        if kind == "reconcile" and (not orders or not lines): raise HTTPException(422, "Import orders and at least one statement line first")
        pending = db.scalar(select(func.count()).select_from(Claim).where(Claim.batch_id == b.id, Claim.extraction_status == "pending"))
        if kind == "extract" and not pending: raise HTTPException(422, "No pending claims. Correct existing extractions manually, or re-upload a receipt.")
        job = Job(batch_id=b.id, kind=kind, idempotency_key=key, input_revision=b.revision, total=pending if kind == "extract" else orders)
        db.add(job); db.flush(); audit(db, b.id, user.id, "job_queued", {"job_id": job.id, "kind": kind})
        db.commit(); return job

    @app.post("/api/batches/{batch_id}/extract", status_code=202, tags=["jobs"])
    def extract(batch_id: str, body: ExtractionRequest, idempotency_key: str = Header(...), user=Depends(current_user), db=Depends(get_db)):
        own_batch(db, batch_id, user)
        if settings.extraction_provider != "gemini" or not settings.gemini_key or not settings.gemini_model:
            raise HTTPException(503, "Gemini is not configured. Set server-side GEMINI_API_KEY, GEMINI_MODEL and EXTRACTION_PROVIDER=gemini, or enter fields manually.")
        if not body.consent_to_cloud: raise HTTPException(422, "Explicit consent_to_cloud=true is required; images will be sent to Google")
        return job_record(enqueue(db, user, batch_id, "extract", idempotency_key))

    @app.post("/api/batches/{batch_id}/reconcile", status_code=202, tags=["jobs"])
    def reconcile(batch_id: str, idempotency_key: str = Header(...), user=Depends(current_user), db=Depends(get_db)):
        return job_record(enqueue(db, user, batch_id, "reconcile", idempotency_key))

    @app.get("/api/jobs/{job_id}", tags=["jobs"])
    def get_job(job_id: str, user=Depends(current_user), db=Depends(get_db)):
        job = db.get(Job, job_id)
        if not job: raise HTTPException(404, "Job not found")
        own_batch(db, job.batch_id, user)
        out = record(job); out.pop("lease", None); return out

    def get_results(db, b):
        if not b.latest_run_id: return []
        items = []
        for m in db.scalars(select(Match).where(Match.run_id == b.latest_run_id).order_by(Match.order_id)):
            out = record(m); out["order"] = record(db.get(Order, m.order_id))
            if out["order"] is None: continue
            out["claim"] = claim_record(db.get(Claim, m.claim_id)) if m.claim_id else None
            out["candidates"] = [record(l) for l in db.scalars(select(StatementLine).where(StatementLine.id.in_(m.candidate_ids)))] if m.candidate_ids else []
            for candidate in out["candidates"]:
                used = db.scalar(select(func.coalesce(func.sum(Allocation.amount_paisa), 0)).where(Allocation.credit_key == candidate["credit_key"], Allocation.match_id != m.id))
                candidate["remaining_paisa"] = max(0, candidate["amount_paisa"] - used)
                candidate["available"] = candidate["remaining_paisa"] >= out["order"]["amount_due_paisa"]
            out["allocations"] = [record(a) for a in db.scalars(select(Allocation).where(Allocation.match_id == m.id))]
            out["allocated_paisa"] = sum(a["amount_paisa"] for a in out["allocations"])
            out["outstanding_paisa"] = max(0, out["order"]["amount_due_paisa"] - out["allocated_paisa"])
            items.append(out)
        return items

    @app.get("/api/batches/{batch_id}/results", tags=["results"])
    def results(batch_id: str, user=Depends(current_user), db=Depends(get_db)):
        b = own_batch(db, batch_id, user); items = get_results(db, b)
        return {"batch": record(b), "items": items, "summary": {"orders": len(items), **{s: sum(r["final_status"] == s for r in items) for s in ["ship", "hold", "review"]}}}

    @app.post("/api/batches/{batch_id}/allocation-review", tags=["results"])
    def allocation_plan(batch_id: str, body: AllocationPlan, idempotency_key: str = Header(...), user=Depends(current_user), db=Depends(get_db)):
        batch = own_batch(db, batch_id, user, True)
        return review_allocations(db, batch, user, body, idempotency_key)

    @app.post("/api/matches/{match_id}/decision", tags=["results"])
    def decision(match_id: str, body: Decision, user=Depends(current_user), db=Depends(get_db)):
        m = db.get(Match, match_id)
        if not m: raise HTTPException(404, "Match not found")
        b = own_batch(db, m.batch_id, user, True)
        # Re-read after taking the batch lock to prevent lost updates on PostgreSQL.
        db.refresh(m)
        if m.run_id != b.latest_run_id or m.version != body.expected_version: raise HTTPException(409, "Result is stale. Reload current results.")
        order = db.get(Order, m.order_id)
        lock_seller(db, user.id)
        chosen = None
        if body.decision == "ship":
            if not m.claim_id: raise HTTPException(422, "There is no uniquely linked claim")
            if m.reason_code == "DUPLICATE_CREDIT": raise HTTPException(409, "Correct the duplicate source statement first")
            if m.reason_code == "REVERSAL": raise HTTPException(409, "Resolve refund or reversal evidence before shipping")
            if body.statement_line_id not in m.candidate_ids: raise HTTPException(422, "Select a candidate statement credit")
            chosen = db.get(StatementLine, body.statement_line_id)
            if not chosen or chosen.batch_id != b.id or chosen.account_id != order.account_id or chosen.amount_paisa != order.amount_due_paisa or chosen.direction != "CREDIT":
                raise HTTPException(422, "Selected credit cannot cover this order")
            used = db.scalar(select(Allocation).where(Allocation.credit_key == chosen.credit_key, Allocation.match_id != m.id))
            if used: raise HTTPException(409, "This credit is already assigned")
        db.execute(delete(Allocation).where(Allocation.match_id == m.id)); db.flush()
        if chosen:
            add_allocation(db, owner_id=user.id, batch_id=b.id, match_id=m.id, order_id=m.order_id, claim_id=m.claim_id, line=chosen, amount=chosen.amount_paisa)
        m.evidence = [e for e in m.evidence if e.get("check") != "reviewed_allocation"]
        previous = m.final_status
        m.final_status, m.selected_line_id, m.reviewer_reason, m.version = body.decision, chosen.id if chosen else None, body.reason, m.version + 1
        audit(db, b.id, user.id, "review_decision", {"match_id": m.id, "previous": previous, "decision": body.decision, "reason": body.reason, "version": m.version})
        db.commit(); return record(m)

    @app.get("/api/batches/{batch_id}/export.csv", tags=["exports"])
    def export(batch_id: str, user=Depends(current_user), db=Depends(get_db)):
        b = own_batch(db, batch_id, user); rows = get_results(db, b)
        if not rows: raise HTTPException(409, "Run reconciliation first")
        data = csv_export(["order_ref", "customer_name", "amount_pkr", "final_status", "machine_verdict", "reason", "reviewer_reason", "statement_line_id", "sample_data", "allocated_pkr", "outstanding_pkr", "allocation_parts"],
                          [[r["order"]["order_ref"], r["order"]["customer_name"], f'{r["order"]["amount_due_paisa"]/100:.2f}', r["final_status"], r["machine_verdict"], r["reason"], r["reviewer_reason"], r["selected_line_id"], b.is_demo,
                            f'{r["allocated_paisa"]/100:.2f}', f'{r["outstanding_paisa"]/100:.2f}',
                            json.dumps([{"statement_line_id": a["statement_line_id"], "amount_paisa": a["amount_paisa"], "claim_id": a["claim_id"]} for a in r["allocations"]])] for r in rows])
        return Response(data, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="milaan-{b.id}.csv"'})

    @app.get("/api/batches/{batch_id}/audit", tags=["audit"])
    def events(batch_id: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), user=Depends(current_user), db=Depends(get_db)):
        own_batch(db, batch_id, user)
        return {"items": [record(e) for e in db.scalars(select(AuditEvent).where(AuditEvent.batch_id == batch_id).order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit))]}

    @app.get('/workspace', include_in_schema=False)
    def protected_workspace(request: Request, db=Depends(get_db)):
        raw = request.cookies.get(settings.cookie_name, '')
        session = db.get(SessionToken, token_digest(raw)) if raw else None
        if not session or session.session_kind != 'cookie' or session.expires_at <= now():
            return RedirectResponse('/login?next=/workspace', status_code=303)
        return FileResponse(Path(__file__).resolve().parents[2]/'frontend/dist/index.html')

    @app.get('/login', include_in_schema=False)
    @app.get('/signup', include_in_schema=False)
    @app.get('/reset-password', include_in_schema=False)
    @app.get('/guide', include_in_schema=False)
    def browser_page():
        return FileResponse(Path(__file__).resolve().parents[2]/'frontend/dist/index.html')

    from fastapi.staticfiles import StaticFiles
    frontend=Path(__file__).resolve().parents[2]/"frontend"/"dist"
    if frontend.exists():app.mount("/",StaticFiles(directory=frontend,html=True),name="milaan")
    return app

app = create_app()
