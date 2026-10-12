from datetime import timedelta
from sqlalchemy import select
from app.models import PendingSignup, User, now

BODY = {'email': 'verify@example.com', 'password': 'safe-test-password', 'display_name': 'Seller'}

def setup(env, monkeypatch):
    client, database, settings = env
    settings.require_email_verification = True
    sent = []
    monkeypatch.setattr('app.main.send_verification', lambda s, email, code: sent.append((email, code)))
    return client, database, sent

def signup(client):
    r = client.post('/api/auth/register', json=BODY)
    assert r.status_code == 201, r.text
    assert 'access_token' not in r.json()
    return r.json()['challenge_id']

def verify(client, challenge, code):
    return client.post('/api/auth/verify-email', json={'challenge_id': challenge, 'code': code})

def ready_to_resend(db):
    with db.sessions() as session:
        row = session.scalar(select(PendingSignup))
        row.last_sent_at = now()-timedelta(seconds=61)
        session.commit()

def test_account_created_only_after_code_and_code_is_single_use(env, monkeypatch):
    c, db, sent = setup(env, monkeypatch)
    challenge = signup(c)
    assert len(sent) == 1 and len(sent[0][1]) == 6
    with db.sessions() as s:
        assert s.scalar(select(User)) is None
        row = s.scalar(select(PendingSignup))
        assert sent[0][1] not in row.code_hash
    assert c.post('/api/auth/login', json={k: BODY[k] for k in ['email','password']}).status_code == 401
    r = verify(c, challenge, sent[0][1])
    assert r.status_code == 200
    assert c.get('/api/auth/me', headers={'Authorization': 'Bearer '+r.json()['access_token']}).status_code == 200
    assert verify(c, challenge, sent[0][1]).status_code == 400
    assert c.post('/api/auth/login', json={k: BODY[k] for k in ['email','password']}).status_code == 200

def test_wrong_code_attempts_persist_and_lock(env, monkeypatch):
    c, db, sent = setup(env, monkeypatch); challenge = signup(c)
    bad = '000000' if sent[0][1] != '000000' else '999999'
    for _ in range(5): assert verify(c, challenge, bad).status_code == 400
    assert verify(c, challenge, sent[0][1]).status_code == 429
    with db.sessions() as s: assert s.scalar(select(PendingSignup)).attempts == 5

def test_expiry_resend_cooldown_invalidation_and_hourly_limit(env, monkeypatch):
    c, db, sent = setup(env, monkeypatch); challenge = signup(c); old = sent[-1][1]
    assert c.post('/api/auth/resend-code', json={'challenge_id':challenge}).status_code == 429
    with db.sessions() as s:
        s.scalar(select(PendingSignup)).expires_at = now()-timedelta(seconds=1); s.commit()
    assert verify(c, challenge, old).status_code == 400
    for _ in range(4):
        ready_to_resend(db)
        assert c.post('/api/auth/resend-code', json={'challenge_id':challenge}).status_code == 200
    ready_to_resend(db)
    assert c.post('/api/auth/resend-code', json={'challenge_id':challenge}).status_code == 429
    if old != sent[-1][1]: assert verify(c, challenge, old).status_code == 400
    assert verify(c, challenge, sent[-1][1]).status_code == 200

def test_delivery_failure_does_not_create_account_or_expose_code(env, monkeypatch):
    c, db, sent = setup(env, monkeypatch)
    def fail(*args): raise RuntimeError('secret SMTP password and code')
    monkeypatch.setattr('app.main.send_verification', fail)
    r = c.post('/api/auth/register', json=BODY)
    assert r.status_code == 503 and 'secret SMTP' not in r.text
    with db.sessions() as s:
        assert s.scalar(select(User)) is None and s.scalar(select(PendingSignup)) is None

def test_restart_signup_replaces_challenge_and_credentials(env, monkeypatch):
    c, db, sent = setup(env, monkeypatch); first = signup(c); first_code = sent[-1][1]
    ready_to_resend(db)
    second = c.post('/api/auth/register', json={**BODY,'password':'new-safe-password'}).json()['challenge_id']
    assert first != second and verify(c, first, first_code).status_code == 400
    assert verify(c, second, sent[-1][1]).status_code == 200
    assert c.post('/api/auth/login', json={'email':BODY['email'],'password':'new-safe-password'}).status_code == 200
