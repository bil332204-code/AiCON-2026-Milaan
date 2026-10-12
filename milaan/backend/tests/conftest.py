import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.models import Base

@pytest.fixture
def env(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path}/test.db", storage_dir=tmp_path/"uploads", run_worker=False, testing=True, require_email_verification=False,
                        extraction_provider="manual", gemini_key="", gemini_model="")
    app = create_app(settings)
    Base.metadata.create_all(app.state.database.engine)
    with TestClient(app) as client:
        yield client, app.state.database, settings

def register(client, email="seller@example.com"):
    response = client.post("/api/auth/register", json={"email": email, "password": "safe-test-password", "display_name": "Test Seller"})
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}

@pytest.fixture
def auth(env): return register(env[0])

@pytest.fixture
def jpeg():
    out = io.BytesIO(); Image.new("RGB", (100, 100), "white").save(out, "JPEG")
    return out.getvalue()

def fresh_batch(client, headers):
    response = client.post("/api/batches", headers=headers, json={"name": "Integration test"})
    assert response.status_code == 201, response.text
    return response.json()

def load_real_flow(client, headers, jpeg, reference="TXN123456", account="wallet-main", name="Ali"):
    batch = fresh_batch(client, headers); bid = batch["id"]
    r = client.post(f"/api/batches/{bid}/orders/item", headers=headers,
                    json={"order_ref": "ORDER-01", "customer_name": name, "amount_due": "3500", "account_id": account})
    assert r.status_code == 201, r.text
    batch, order = r.json()["batch"], r.json()["order"]
    csv = f"posted_at,direction,amount,counterparty,transaction_id\n2026-10-09T14:22:00+05:00,CREDIT,3500,Ali,{reference}\n"
    r = client.post(f"/api/batches/{bid}/statement", headers=headers, files={"file": ("statement.csv", csv, "text/csv")},
                    data={"expected_revision": batch["revision"], "account_id": account, "coverage_start": "2026-10-09T08:00:00+05:00",
                          "coverage_end": "2026-10-09T20:00:00+05:00", "complete": "true", "references_verified": "true"})
    assert r.status_code == 201, r.text
    batch = r.json()["batch"]
    r = client.post(f"/api/batches/{bid}/claims", headers=headers, files={"file": ("receipt.jpg", jpeg, "image/jpeg")},
                    data={"expected_revision": batch["revision"], "order_id": order["id"]})
    assert r.status_code == 201, r.text
    return r.json()["batch"], order, r.json()["claim"]

def confirm(client, headers, claim, reference="TXN123456"):
    r = client.patch(f'/api/claims/{claim["id"]}', headers=headers, json={"expected_version": claim["version"], "confirmed": True,
                     "fields": {"is_payment_receipt": True, "amount_pkr": "3500", "datetime_local": "2026-10-09T14:22:00+05:00",
                                "transaction_id": reference, "status_text": "Successful"}})
    assert r.status_code == 200, r.text
    return r.json()

def reconcile(env, headers, bid, key="test-run-0001"):
    from app.jobs import run_once
    client, db, settings = env
    r = client.post(f"/api/batches/{bid}/reconcile", headers={**headers, "Idempotency-Key": key})
    assert r.status_code == 202, r.text
    assert run_once(db, settings)
    job = client.get('/api/jobs/'+r.json()["id"], headers=headers).json()
    assert job["status"] == "done", job
    return client.get(f"/api/batches/{bid}/results", headers=headers).json()
