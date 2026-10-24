"""Server-side cookies, CSRF, recovery and persistent account security (synthetic users)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
from sqlalchemy import select
from app.models import User, SessionToken, PasswordReset, now
from app.security import token_digest, verify_password
from app.config import Settings
from conftest import register

EMAIL='cookie@example.com'
PASSWORD='synthetic-unique-passphrase'


def account(client):
    from unittest.mock import patch
    settings=client.app.state.settings;previous=settings.require_email_verification;settings.require_email_verification=True
    sent=[]
    try:
        with patch('app.main.send_verification',lambda s,email,code:sent.append(code)):
            response=client.post('/api/auth/register',json={'email':EMAIL,'password':PASSWORD,'display_name':'Synthetic'})
        assert response.status_code==201
        verified=client.post('/api/auth/verify-email',json={'challenge_id':response.json()['challenge_id'],'code':sent[-1]})
        assert verified.status_code==200
        return verified.json()
    finally:settings.require_email_verification=previous


def cookie_login(client,remember=False):
    response=client.post('/api/auth/login',json={'email':EMAIL,'password':PASSWORD,'session_mode':'cookie','remember_me':remember})
    assert response.status_code==200
    assert 'access_token' not in response.json()
    return response


def test_cookie_session_is_refreshable_http_only_and_csrf_protected(env):
    client,db,settings=env;account(client)
    assert client.get('/workspace',follow_redirects=False).status_code==303
    response=cookie_login(client)
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    assert 'Max-Age' not in response.headers['set-cookie']
    restored=client.get('/api/auth/session').json()
    assert restored['user']['email']==EMAIL and restored['csrf_token']==response.json()['csrf_token']
    assert client.get('/workspace').status_code==200
    path='/api/batches';body={'name':'Private cookie batch'}
    assert client.post(path,json=body).status_code==403
    assert client.post(path,json=body,headers={'X-CSRF-Token':'wrong'}).status_code==403
    csrf={'X-CSRF-Token':restored['csrf_token']}
    assert client.post(path,json=body,headers={**csrf,'Origin':'https://untrusted.example'}).status_code==403
    assert client.post(path,json=body,headers=csrf).status_code==201
    raw=client.cookies.get(settings.cookie_name)
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+raw}).status_code==401
    assert client.post('/api/auth/logout',headers=csrf).status_code==204
    assert client.get('/api/auth/me').status_code==401


def test_remember_me_has_finite_expiry_and_expired_cookie_cannot_open_workspace(env):
    client,db,settings=env;account(client)
    response=cookie_login(client,True)
    assert 'Max-Age=2592000' in response.headers['set-cookie']
    raw=client.cookies.get(settings.cookie_name)
    with db.transaction() as session:session.get(SessionToken,token_digest(raw)).expires_at=now()-timedelta(seconds=1)
    assert client.get('/api/auth/session').status_code==401
    assert client.get('/workspace',follow_redirects=False).status_code==303


def test_account_lockout_persists_and_legacy_password_hashes_upgrade_without_new_ids(env):
    client,db,_=env;original=account(client)
    salt=b'1234567890123456'
    legacy='scrypt$'+salt.hex()+'$'+hashlib.scrypt(PASSWORD.encode(),salt=salt,n=16384,r=8,p=1,dklen=32).hex()
    with db.transaction() as session:session.get(User,original['user']['id']).password_hash=legacy
    cookie_login(client)
    with db.sessions() as session:
        user=session.get(User,original['user']['id']);assert user.password_hash.startswith('scrypt-v2$')
    for _ in range(5):assert client.post('/api/auth/login',json={'email':EMAIL,'password':'wrong'}).status_code==401
    assert client.post('/api/auth/login',json={'email':EMAIL,'password':PASSWORD}).status_code==401
    with db.transaction() as session:session.get(User,original['user']['id']).login_locked_until=now()-timedelta(seconds=1)
    assert cookie_login(client).status_code==200


def test_reset_is_hashed_single_use_and_revokes_all_sessions(env,monkeypatch):
    client,db,settings=env;original=account(client);cookie_login(client)
    sent=[];monkeypatch.setattr('app.main.send_password_reset',lambda s,email,token:sent.append(token))
    known=client.post('/api/auth/request-password-reset',json={'email':EMAIL})
    unknown=client.post('/api/auth/request-password-reset',json={'email':'missing@example.com'})
    assert known.json()==unknown.json() and len(sent)==1 and sent[0] not in known.text
    client.post('/api/auth/request-password-reset',json={'email':EMAIL});assert len(sent)==1
    with db.sessions() as session:
        reset=session.get(PasswordReset,original['user']['id']);assert reset.token_hash==token_digest(sent[0]) and reset.token_hash!=sent[0]
    new_password='synthetic-new-unique-passphrase'
    assert client.post('/api/auth/reset-password',json={'token':'x'*64,'password':new_password}).status_code==400
    response=client.post('/api/auth/reset-password',json={'token':sent[0],'password':new_password})
    assert response.status_code==200 and sent[0] not in response.text
    assert client.get('/api/auth/session').status_code==401
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+original['access_token']}).status_code==401
    assert client.post('/api/auth/reset-password',json={'token':sent[0],'password':new_password}).status_code==400
    assert client.post('/api/auth/login',json={'email':EMAIL,'password':PASSWORD}).status_code==401
    assert client.post('/api/auth/login',json={'email':EMAIL,'password':new_password}).status_code==200
    with db.sessions() as session: assert session.get(PasswordReset,original['user']['id']) is None


def test_reset_expiry_and_concurrent_use_fail_safely(env,monkeypatch):
    client,db,_=env;original=account(client);sent=[]
    monkeypatch.setattr('app.main.send_password_reset',lambda s,email,token:sent.append(token))
    client.post('/api/auth/request-password-reset',json={'email':EMAIL})
    body={'token':sent[0],'password':'synthetic-replacement-password'}
    with db.transaction() as session:session.get(PasswordReset,original['user']['id']).expires_at=now()-timedelta(seconds=1)
    assert client.post('/api/auth/reset-password',json=body).status_code==400
    with db.transaction() as session:
        session.get(PasswordReset,original['user']['id']).expires_at=now()+timedelta(minutes=15)
        session.get(User,original['user']['id']).email_verified_at=None
    assert client.post('/api/auth/reset-password',json=body).status_code==400
    with db.transaction() as session:session.get(User,original['user']['id']).email_verified_at=now()
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:client.post('/api/auth/reset-password',json=body),range(2)))
    assert sorted(response.status_code for response in responses)==[200,400]


def test_cookie_does_not_authorize_other_sellers_and_logout_all_revokes_bearer(env):
    client,_,_=env;original=account(client);cookie_login(client)
    csrf={'X-CSRF-Token':client.get('/api/auth/session').json()['csrf_token']}
    batch=client.post('/api/batches',json={'name':'Synthetic private'},headers=csrf).json()
    other=register(client,'other-cookie-user@example.com')
    assert client.get('/api/batches/'+batch['id'],headers=other).status_code==404
    assert client.post('/api/auth/logout-all',headers=csrf).status_code==204
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+original['access_token']}).status_code==401


def test_secure_cookie_flag_and_production_validation(env):
    client,_,settings=env;account(client);settings.cookie_secure=True
    response=cookie_login(client)
    assert '__Host-milaan_session=' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    import pytest
    for overrides in [{'public_origin':'http://example.com','cookie_secure':True}, {'public_origin':'https://example.com','cookie_secure':False}]:
        with pytest.raises(ValueError): Settings(app_env='production',require_email_verification=True,**overrides)
    Settings(app_env='production',public_origin='https://example.com',cookie_secure=True,require_email_verification=True)


def test_real_auth_rate_limit_rejects_sixteenth_request(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.models import Base
    settings=Settings(database_url=f'sqlite:///{tmp_path}/rate.db',storage_dir=tmp_path/'images',run_worker=False,testing=False,demo_seller_email='',demo_seller_password='')
    app=create_app(settings);Base.metadata.create_all(app.state.database.engine)
    with TestClient(app) as client:
        statuses=[client.post('/api/auth/login',json={'email':'missing@example.com','password':'synthetic'}).status_code for _ in range(16)]
    assert statuses[:15]==[401]*15 and statuses[15]==429


def test_results_remain_safe_during_concurrent_batch_deletion(env,auth):
    from conftest import reconcile
    client,_,_=env
    batch=client.post('/api/batches/demo',headers=auth).json();reconcile(env,auth,batch['id'])
    with ThreadPoolExecutor(max_workers=3) as pool:
        reads=[pool.submit(client.get,f'/api/batches/{batch["id"]}/results',headers=auth) for _ in range(8)]
        removed=pool.submit(client.delete,f'/api/batches/{batch["id"]}',headers=auth)
        assert removed.result().status_code==204
        assert all(read.result().status_code in [200,404] for read in reads)


def test_reset_email_uses_verified_tls_transport_and_fragment_link(env,monkeypatch):
    from app.emailer import send_password_reset
    settings=env[2];settings.smtp_host='smtp.example.com';settings.smtp_from='no-reply@example.com';settings.smtp_security='starttls';settings.smtp_user=''
    events=[]
    class SMTP:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def starttls(self,context):events.append(('tls',context.check_hostname))
        def send_message(self,message):events.append(('message',message.get_content()))
    monkeypatch.setattr('app.emailer.smtplib.SMTP',SMTP)
    send_password_reset(settings,'synthetic@example.com','synthetic-one-time-token')
    assert events[0]==('tls',True)
    assert settings.public_origin+'/reset-password#token=synthetic-one-time-token' in events[1][1]


def test_invalid_unicode_password_is_validation_error_not_server_failure(env):
    import json
    response=env[0].post('/api/auth/register',content=json.dumps({'email':'unicode@example.com','display_name':'Synthetic','password':'\ud800'*12}).encode(),headers={'Content-Type':'application/json'})
    assert response.status_code==422
    assert response.json()['detail'][0]['loc']==['body','password']
    assert response.json()['detail'][0]['type']=='string_unicode'


def test_legacy_email_requires_authenticated_owner_confirmation_before_recovery(env,monkeypatch):
    client,_,_=env
    original=client.post('/api/auth/register',json={'email':EMAIL,'password':PASSWORD,'display_name':'Legacy synthetic'}).json()
    auth={'Authorization':'Bearer '+original['access_token']}
    sent=[];resets=[]
    monkeypatch.setattr('app.main.send_verification',lambda s,email,code:sent.append(code))
    monkeypatch.setattr('app.main.send_password_reset',lambda s,email,token:resets.append(token))
    assert client.post('/api/auth/request-password-reset',json={'email':EMAIL}).status_code==200 and not resets
    challenge=client.post('/api/auth/verify-account-email/start',headers=auth).json()['challenge_id']
    assert client.post('/api/auth/verify-email',json={'challenge_id':challenge,'code':sent[-1]}).status_code==400
    verified=client.post('/api/auth/verify-account-email',headers=auth,json={'challenge_id':challenge,'code':sent[-1]})
    assert verified.status_code==200 and verified.json()['id']==original['user']['id'] and verified.json()['email_verified'] is True
    client.post('/api/auth/request-password-reset',json={'email':EMAIL});assert len(resets)==1
