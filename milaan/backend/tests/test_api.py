from datetime import timedelta
from sqlalchemy import select, func
from app.models import Batch, Claim, Order, Match, Allocation, Job, now
from app.jobs import cleanup, run_once, take_job
from conftest import register, fresh_batch, load_real_flow, confirm, reconcile

def test_auth_logout_and_secret_redaction(env, auth):
    c, _, _ = env
    assert c.get('/api/auth/me', headers=auth).json()["email"] == "seller@example.com"
    assert c.get('/api/auth/me').status_code == 401
    invalid = c.post('/api/auth/register', json={"email": "bad", "password": "secret123", "display_name": "S"})
    assert invalid.status_code == 422 and "secret123" not in invalid.text
    assert c.post('/api/auth/login', json={"email": "seller@example.com", "password": "wrong"}).status_code == 401
    assert c.post('/api/auth/logout', headers=auth).status_code == 204
    assert c.get('/api/auth/me', headers=auth).status_code == 401

def test_demo_complete_workflow_idempotency_and_reset(env, auth):
    c, db, _ = env
    b = c.post('/api/batches/demo', headers=auth).json()
    data = reconcile(env, auth, b["id"])
    assert data["summary"] == {"orders": 12, "ship": 5, "hold": 2, "review": 5}
    r = c.post(f'/api/batches/{b["id"]}/reconcile', headers={**auth, "Idempotency-Key": "test-run-0001"})
    assert r.status_code == 202 and r.json()["status"] == "done" and "lease" not in r.json()
    with db.sessions() as s: assert s.scalar(select(func.count()).select_from(Allocation)) == 5
    exported = c.get(f'/api/batches/{b["id"]}/export.csv', headers=auth)
    assert exported.status_code == 200 and 'sample_data' in exported.text and 'True' in exported.text
    ship = next(x for x in data['items'] if x['final_status'] == 'ship')
    decision = {"expected_version": 1, "decision": "hold", "reason": "Seller requested a second check"}
    assert c.post('/api/matches/'+ship['id']+'/decision', headers=auth, json=decision).status_code == 200
    assert c.post('/api/matches/'+ship['id']+'/decision', headers=auth, json=decision).status_code == 409
    r = c.post(f'/api/batches/{b["id"]}/reset', headers=auth, json={"expected_revision": data['batch']['revision'], "reason": "Import a newer statement"})
    assert r.status_code == 200
    assert c.get(f'/api/batches/{b["id"]}/results', headers=auth).json()['items'] == []
    with db.sessions() as s: assert s.scalar(select(func.count()).select_from(Allocation)) == 0
    new = reconcile(env, auth, b['id'], 'test-run-0002')
    assert new['summary']['ship'] == 5
    assert c.get(f'/api/batches/{b["id"]}/audit', headers=auth).status_code == 200

def test_cross_user_isolation(env, auth, jpeg):
    c, _, _ = env
    b, o, claim = load_real_flow(c, auth, jpeg)
    other = register(c, "other@example.com")
    assert c.get('/api/batches', headers=other).json()['items'] == []
    paths = [f'/api/batches/{b["id"]}', f'/api/batches/{b["id"]}/orders', f'/api/batches/{b["id"]}/claims', f'/api/claims/{claim["id"]}/image']
    for path in paths: assert c.get(path, headers=other).status_code == 404
    assert c.delete('/api/batches/'+b['id'], headers=other).status_code == 404
    assert c.get('/api/claims/'+claim['id']+'/image', headers=auth).status_code == 200
    assert c.get('/api/claims/'+claim['id']+'/image').status_code == 401
    assert c.get('/api/integrations/status', headers=auth).json()['bank_connected'] is False

def test_real_upload_confirmation_and_cross_batch_credit_reuse(env, auth, jpeg):
    c, _, _ = env
    b, o, claim = load_real_flow(c, auth, jpeg, name="=malicious-formula")
    update = confirm(c, auth, claim)
    assert c.patch('/api/claims/'+claim['id'], headers=auth, json={"expected_version": 1, "fields": {}, "confirmed": False}).status_code == 409
    result = reconcile(env, auth, b['id'])
    assert result['summary']['ship'] == 1
    assert c.patch('/api/claims/'+claim['id'], headers=auth, json={"expected_version": 2, "fields": {}, "confirmed": False}).status_code == 409
    assert "'=malicious-formula" in c.get(f'/api/batches/{b["id"]}/export.csv', headers=auth).text
    b2, _, c2 = load_real_flow(c, auth, jpeg)
    confirm(c, auth, c2)
    result2 = reconcile(env, auth, b2['id'])
    assert result2['items'][0]['reason_code'] == 'CREDIT_ALREADY_USED'
    m = result2['items'][0]
    assert c.post('/api/matches/'+m['id']+'/decision', headers=auth, json={"expected_version": 1, "decision": "ship", "statement_line_id": m['candidates'][0]['id'], "reason": "Try to use same credit"}).status_code == 409

def test_content_is_versioned_and_owner_scoped(env, auth):
    c, _, _ = env
    assert c.get('/api/content', headers=auth).json()['branding']['version'] == 0
    payload = {"expected_version": 0, "value": {"product_name": "My shop"}}
    assert c.put('/api/content/branding', headers=auth, json=payload).json()['version'] == 1
    assert c.put('/api/content/branding', headers=auth, json=payload).status_code == 409
    other = register(c, "other@example.com")
    assert c.get('/api/content', headers=other).json()['branding']['value']['product_name'] == 'Milaan'

def test_upload_validation_revision_and_body_limit(env, auth, jpeg):
    c, _, _ = env
    b = fresh_batch(c, auth)
    raw = 'order_ref,customer_name,amount_due,account_id\nO1,Ali,10,main\n'
    r = c.post(f'/api/batches/{b["id"]}/orders', headers=auth, files={'file': ('orders.csv', raw)}, data={'expected_revision': 1})
    assert r.status_code == 201, r.text
    oid = r.json()['items'][0]['id']
    assert c.post(f'/api/batches/{b["id"]}/claims', headers=auth, files={'file': ('evil.jpg', b'<script>')}, data={'expected_revision': 2, 'order_id': oid}).status_code == 422
    assert c.post(f'/api/batches/{b["id"]}/claims', headers=auth, files={'file': ('real.jpg', jpeg)}, data={'expected_revision': 1, 'order_id': oid}).status_code == 409
    assert c.post('/api/batches', headers=auth, content=b'x' * (12 * 1024 * 1024 + 1)).status_code == 413

def test_deletion_and_retention_remove_private_images(env, auth, jpeg):
    c, db, settings = env
    b, _, claim = load_real_flow(c, auth, jpeg)
    assert len(list(settings.storage_dir.glob('*.jpg'))) == 1
    with db.transaction() as s: s.get(Batch, b['id']).expires_at = now()-timedelta(seconds=1)
    assert c.get('/api/batches/'+b['id'], headers=auth).status_code == 404
    cleanup(db, settings)
    assert list(settings.storage_dir.glob('*.jpg')) == []
    with db.sessions() as s:
        assert s.get(Claim, claim['id']) is None
        assert s.scalar(select(func.count()).select_from(Order)) == 0
    b2, _, _ = load_real_flow(c, auth, jpeg)
    assert c.delete('/api/batches/'+b2['id'], headers=auth).status_code == 204
    assert list(settings.storage_dir.glob('*.jpg')) == []

def test_interrupted_job_recovery_and_mutation_block(env, auth):
    c, db, settings = env
    b = c.post('/api/batches/demo', headers=auth).json()
    r = c.post(f'/api/batches/{b["id"]}/reconcile', headers={**auth, 'Idempotency-Key': 'resume-job-0001'})
    job_id = r.json()['id']
    selected = take_job(db, settings)
    assert selected[0] == job_id
    assert c.post(f'/api/batches/{b["id"]}/reset', headers=auth, json={'expected_revision': 1, 'reason': 'Try editing while busy'}).status_code == 409
    with db.transaction() as s: s.get(Job, job_id).updated_at = now()-timedelta(seconds=400)
    assert run_once(db, settings)
    assert c.get('/api/jobs/'+job_id, headers=auth).json()['status'] == 'done'

def test_manual_mode_and_extraction_consent(env, auth, jpeg, monkeypatch):
    c, db, settings = env
    b, _, claim = load_real_flow(c, auth, jpeg)
    path = f'/api/batches/{b["id"]}/extract'
    h = {**auth, 'Idempotency-Key': 'extract-0001'}
    assert c.post(path, headers=h, json={'consent_to_cloud': True}).status_code == 503
    settings.extraction_provider, settings.gemini_key, settings.gemini_model = 'gemini', 'fake-unit-test-key', 'fake-model'
    assert c.post(path, headers=h, json={'consent_to_cloud': False}).status_code == 422
    from app.extraction import ExtractionUnavailable
    def fail(*args): raise ExtractionUnavailable('PROVIDER_UNAVAILABLE')
    monkeypatch.setattr('app.jobs.double_read', fail)
    assert c.post(path, headers=h, json={'consent_to_cloud': True}).status_code == 202
    run_once(db, settings)
    claims = c.get(f'/api/batches/{b["id"]}/claims', headers=auth).json()['items']
    assert claims[0]['extraction_status'] == 'failed' and not claims[0]['fields_checked']
    assert 'fake-unit-test-key' not in str(claims)
    retry = c.post('/api/claims/'+claim['id']+'/retry-extraction', headers=auth, json={'expected_version': claims[0]['version']})
    assert retry.status_code == 200 and retry.json()['claim']['extraction_status'] == 'pending'
