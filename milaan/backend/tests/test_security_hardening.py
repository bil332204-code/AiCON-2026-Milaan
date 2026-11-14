"""Regression tests for the November 2026 security audit fixes (F-01 ... F-22)."""
import io
import time
import zlib
from datetime import timedelta

import pytest
from PIL import Image

from conftest import register, fresh_batch, load_real_flow, confirm, reconcile
from app.models import Batch, User, CreditLedger, now
from app import totp


def pdf_with_stream(megabytes):
    payload = zlib.compress(b"0 0 m\n" * (megabytes * 1024 * 1024 // 6), 9)
    return (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length " + str(len(payload)).encode() + b"/Filter/FlateDecode>>stream\n" + payload +
            b"\nendstream endobj\ntrailer<</Root 1 0 R>>\n%%EOF")


# F-01: a decompression bomb is refused quickly, in a sandbox, with a seller-facing message
def test_pdf_decompression_bomb_is_rejected_quickly(env):
    client, _, _ = env
    headers = register(client)
    started = time.monotonic()
    r = client.post("/api/statements/read-pdf", headers=headers, files={"file": ("bomb.pdf", pdf_with_stream(150), "application/pdf")})
    assert r.status_code == 422 and "too large or complex" in r.json()["detail"]
    assert time.monotonic() - started < 10


def test_pdf_sandbox_gets_no_application_secrets(monkeypatch):
    import subprocess
    from app import statement_pdf
    seen = {}
    real = subprocess.run
    def spy(*args, **kwargs):
        seen.update(kwargs["env"]); return real(*args, **kwargs)
    monkeypatch.setenv("RESEND_API_KEY", "re_should_not_leak")
    monkeypatch.setattr(statement_pdf.subprocess, "run", spy)
    with pytest.raises(statement_pdf.StatementPDFError):
        statement_pdf.read_statement_pdf(b"%PDF-1.4\n%%EOF")
    assert "RESEND_API_KEY" not in seen and "DATABASE_URL" not in seen


# F-02: only JPEG/PNG/WEBP parsers ever run
def test_other_image_parsers_never_run(env):
    from app.storage import clean_image
    for fmt in ("TIFF", "BMP", "GIF", "ICO", "PPM"):
        out = io.BytesIO(); Image.new("RGB", (16, 16)).save(out, fmt)
        with pytest.raises(ValueError):
            clean_image(out.getvalue())
    big = io.BytesIO(); Image.new("RGB", (4000, 3000), "white").save(big, "JPEG")
    cleaned, _ = clean_image(big.getvalue())
    assert max(Image.open(io.BytesIO(cleaned)).size) <= 2400


# F-03: a bank credit stays used after its batch is deleted or expires
def test_credit_cannot_ship_twice_after_batch_is_deleted(env, jpeg):
    client, db, _ = env
    h = register(client)
    b1, _, c1 = load_real_flow(client, h, jpeg, reference="TXN777777")
    confirm(client, h, c1, reference="TXN777777")
    assert reconcile(env, h, b1["id"], key="run-one-0001")["items"][0]["final_status"] == "ship"
    assert client.delete(f"/api/batches/{b1['id']}", headers=h).status_code == 204
    other = io.BytesIO(); Image.new("RGB", (101, 99), "white").save(other, "JPEG")
    b2, _, c2 = load_real_flow(client, h, other.getvalue(), reference="TXN777777")
    confirm(client, h, c2, reference="TXN777777")
    item = reconcile(env, h, b2["id"], key="run-two-0001")["items"][0]
    assert item["final_status"] == "review" and item["reason_code"] == "CREDIT_ALREADY_USED"
    # A manual SHIP of the same credit is refused too
    r = client.post(f"/api/matches/{item['id']}/decision", headers=h,
                    json={"expected_version": item["version"], "decision": "ship", "statement_line_id": item["candidate_ids"][0], "reason": "try again"})
    assert r.status_code == 409


def test_expiry_cleanup_moves_used_credits_to_the_ledger(env, jpeg):
    from app.jobs import cleanup
    client, db, settings = env
    h = register(client)
    b1, _, c1 = load_real_flow(client, h, jpeg, reference="TXN888888")
    confirm(client, h, c1, reference="TXN888888")
    reconcile(env, h, b1["id"], key="run-exp-0001")
    with db.transaction() as s:
        s.get(Batch, b1["id"]).expires_at = now() - timedelta(minutes=1)
    cleanup(db, settings)
    with db.sessions() as s:
        assert s.get(Batch, b1["id"]) is None
        rows = s.query(CreditLedger).all()
        assert len(rows) == 1 and rows[0].transaction_id == "TXN888888" and rows[0].amount_paisa == 350000


# F-10: decisions outlive the batch
def test_decision_history_survives_batch_deletion_and_is_private(env, jpeg):
    client, _, _ = env
    a, b = register(client, "a@example.com"), register(client, "b@example.com")
    batch, _, claim = load_real_flow(client, a, jpeg)
    confirm(client, a, claim)
    reconcile(env, a, batch["id"])
    client.delete(f"/api/batches/{batch['id']}", headers=a)
    items = client.get("/api/decisions", headers=a).json()["items"]
    assert [(d["order_ref"], d["decision"], d["source"]) for d in items] == [("ORDER-01", "ship", "automatic")]
    assert client.get("/api/decisions", headers=b).json()["items"] == []
    csv = client.get("/api/decisions.csv", headers=a).text
    assert "ORDER-01" in csv and "TXN123456" in csv


# F-09: two agreeing AI reads still need the seller to confirm
def test_ai_reads_never_count_as_a_human_check(env, jpeg, monkeypatch):
    from app.jobs import run_once
    client, db, settings = env
    settings.extraction_provider, settings.gemini_key, settings.gemini_model = "gemini", "k", "m"
    fields = {"is_payment_receipt": True, "provider_app": "x", "amount_pkr": "3500", "datetime_local": "2026-10-09T14:22:00+05:00",
              "transaction_id": "TXN123456", "sender_name": None, "receiver_hint": None, "status_text": "Successful", "unreadable_fields": []}
    monkeypatch.setattr("app.jobs.double_read", lambda data, config: (fields, fields, True))
    h = register(client)
    batch, _, claim = load_real_flow(client, h, jpeg)
    r = client.post(f"/api/batches/{batch['id']}/extract", headers={**h, "Idempotency-Key": "extract-0001"}, json={"consent_to_cloud": True})
    assert r.status_code == 202 and run_once(db, settings)
    after = client.get(f"/api/batches/{batch['id']}/claims", headers=h).json()["items"][0]
    assert after["fields_checked"] is False and after["extraction_status"] == "needs_review"


def test_daily_ai_reading_cap(env, jpeg):
    client, _, settings = env
    settings.extraction_provider, settings.gemini_key, settings.gemini_model, settings.max_daily_extractions = "gemini", "k", "m", 0
    h = register(client)
    batch, _, _ = load_real_flow(client, h, jpeg)
    r = client.post(f"/api/batches/{batch['id']}/extract", headers={**h, "Idempotency-Key": "extract-0002"}, json={"consent_to_cloud": True})
    assert r.status_code == 429


# F-07: per-seller receipt quota
def test_receipt_quota(env, jpeg):
    client, _, settings = env
    settings.max_seller_receipts = 1
    h = register(client)
    batch, order, _ = load_real_flow(client, h, jpeg)
    r = client.post(f"/api/batches/{batch['id']}/claims", headers=h, files={"file": ("r.jpg", jpeg, "image/jpeg")},
                    data={"expected_revision": batch["revision"], "order_id": order["id"]})
    assert r.status_code == 409 and "most allowed" in r.json()["detail"]


def test_heavy_slots_run_one_job_per_user_and_refuse_when_the_wait_runs_out():
    from app.limits import HeavySlots, Busy
    slots = HeavySlots(1, wait=0.05)
    with slots.hold("seller"):
        with pytest.raises(Busy):
            with slots.hold("seller"):
                pass
        with pytest.raises(Busy):  # the only global slot is taken
            with slots.hold("someone-else"):
                pass
    with slots.hold("seller"):
        pass


# F-12: export and deletion
def test_account_export_and_permanent_deletion(env, jpeg):
    client, db, settings = env
    h = register(client)
    batch, _, claim = load_real_flow(client, h, jpeg)
    exported = client.get("/api/account/export", headers=h)
    assert exported.status_code == 200 and exported.json()["batches"][0]["orders"][0]["order_ref"] == "ORDER-01"
    assert client.post("/api/account/delete", headers=h, json={"password": "wrong-password", "confirm": "DELETE"}).status_code == 403
    assert client.post("/api/account/delete", headers=h, json={"password": "safe-test-password", "confirm": "DELETE"}).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
    with db.sessions() as s:
        assert s.query(User).count() == 0 and s.query(Batch).count() == 0
    from app.storage import receipt_storage
    assert list(receipt_storage(settings).objects()) == []


# F-14: no interactive docs in production
def test_api_docs_are_off_in_production(tmp_path):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    settings = Settings(database_url=f"sqlite:///{tmp_path}/d.db", migration_database_url="", storage_backend="local",
                        storage_dir=tmp_path / "u", run_worker=False, testing=True, demo_seller_email="", demo_seller_password="")
    settings.app_env = "production"  # bypass production-only infrastructure checks for this routing test
    app = create_app(settings)
    paths = {route.path for route in app.routes}
    assert not {"/docs", "/redoc", "/openapi.json"} & paths


# F-15: signup does not reveal whether an email has an account
def test_signup_reply_is_the_same_for_existing_accounts(env, monkeypatch):
    client, _, settings = env
    sent = []
    monkeypatch.setattr("app.main.send_verification", lambda s, email, code: sent.append(("code", email)))
    monkeypatch.setattr("app.main.send_existing_account_notice", lambda s, email: sent.append(("notice", email)))
    register(client, "owner@example.com")
    settings.require_email_verification = True
    new = client.post("/api/auth/register", json={"email": "new@example.com", "password": "safe-test-password", "display_name": "N"})
    old = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "safe-test-password", "display_name": "N"})
    assert new.status_code == old.status_code
    assert set(new.json()) == set(old.json())
    time.sleep(0.2)
    assert ("notice", "owner@example.com") in sent


# F-17: optional authenticator-app step, with replay protection
def test_two_step_sign_in(env):
    client, _, _ = env
    h = register(client, "two@example.com")
    setup = client.post("/api/auth/totp/setup", headers=h).json()
    secret = setup["secret"]
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert client.post("/api/auth/totp/enable", headers=h, json={"code": "000000" if totp.code_now(secret) != "000000" else "111111"}).status_code == 400
    code = totp.code_now(secret)
    assert client.post("/api/auth/totp/enable", headers=h, json={"code": code}).json()["two_step_enabled"] is True
    first = client.post("/api/auth/login", json={"email": "two@example.com", "password": "safe-test-password"}).json()
    assert first["totp_required"] is True and "access_token" not in first
    # The code that enabled two-step cannot be replayed to sign in.
    replay = client.post("/api/auth/totp/verify-login", json={"challenge_id": first["challenge_id"], "code": code})
    assert replay.status_code == 400
    future = totp.code_now(secret, at=time.time() + 30)
    if future == code: future = totp.code_now(secret, at=time.time() + 60)
    ok = client.post("/api/auth/totp/verify-login", json={"challenge_id": first["challenge_id"], "code": future})
    assert ok.status_code == 200 and ok.json()["access_token"]


def test_breached_passwords_are_refused_when_checking_is_on(env, monkeypatch):
    client, _, settings = env
    settings.check_breached_passwords = True
    monkeypatch.setattr("app.main.is_breached", lambda password: password == "password1234")
    r = client.post("/api/auth/register", json={"email": "p@example.com", "password": "password1234", "display_name": "P"})
    assert r.status_code == 422 and "breaches" in r.json()["detail"]


def test_client_ip_trusts_only_private_proxies():
    from app.limits import client_ip
    scope = lambda peer, **h: {"client": (peer, 1), "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in h.items()]}
    assert client_ip(scope("127.0.0.1", cf_connecting_ip="203.0.113.5")) == "203.0.113.5"
    # X-Forwarded-For is appended to, never reset, by Render, so it is ignored.
    assert client_ip(scope("10.0.0.2", x_forwarded_for="198.51.100.1, 203.0.113.7")) == "10.0.0.2"
    assert client_ip(scope("127.0.0.1", cf_connecting_ip="203.0.113.5"), trust_proxy=False) == "127.0.0.1"
    assert client_ip(scope("203.0.113.9", cf_connecting_ip="1.2.3.4")) == "203.0.113.9"
