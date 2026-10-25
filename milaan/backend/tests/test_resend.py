"""Real Resend adapter with synthetic HTTP transport; never sends actual email."""
import json
import httpx
import pytest
from sqlalchemy import select
from app import emailer
from app.models import PendingSignup, User, PasswordReset
from app.security import token_digest
from conftest import register
from test_database_config import production


def transport(monkeypatch, handler):
    monkeypatch.setattr(emailer, '_client', lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(emailer.time, 'sleep', lambda _:None)


def configure(env):
    settings = env[2]
    settings.resend_api_key = 'synthetic-resend-secret'
    settings.email_from = 'Milaan <no-reply@example.com>'
    return settings


def test_verification_and_recovery_use_resend_and_keep_tokens_in_message_body(env, monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={'id':'synthetic-message-id'})
    transport(monkeypatch,handler);settings=configure(env)
    emailer.send_verification(settings,'synthetic@example.com','123456')
    emailer.send_password_reset(settings,'synthetic@example.com','synthetic-reset-token')
    for request in requests:
        assert str(request.url) == 'https://api.resend.com/emails'
        assert request.method == 'POST'
        assert request.headers['Authorization'] == 'Bearer synthetic-resend-secret'
        assert request.headers['Idempotency-Key'].startswith('milaan-')
        assert json.loads(request.content)['from'] == settings.email_from
        assert json.loads(request.content)['to'] == ['synthetic@example.com']
    assert requests[0].headers['Idempotency-Key'] != requests[1].headers['Idempotency-Key']
    assert '123456' in json.loads(requests[0].content)['text']
    assert settings.public_origin+'/reset-password#token=synthetic-reset-token' in json.loads(requests[1].content)['text']
    assert 'synthetic-resend-secret' not in repr(settings)


@pytest.mark.parametrize('failure',[429,500,503,'timeout'])
def test_transient_retry_reuses_identical_payload_and_idempotency_key(env,monkeypatch,failure):
    requests=[]
    def handler(request):
        requests.append(request)
        if len(requests)==1:
            if failure=='timeout':raise httpx.ReadTimeout('secret-provider-detail',request=request)
            return httpx.Response(failure,headers={'Retry-After':'0'},text='secret-provider-detail')
        return httpx.Response(201,json={'id':'synthetic-id'})
    transport(monkeypatch,handler)
    emailer.send_verification(configure(env),'synthetic@example.com','123456')
    assert len(requests)==2 and requests[0].content==requests[1].content
    assert requests[0].headers['Idempotency-Key']==requests[1].headers['Idempotency-Key']


@pytest.mark.parametrize('status,body,attempts',[(401,{'error':'secret'},1),(403,{},1),(422,{},1),(302,{},1),(200,{},1),(200,[],1),(503,{},2),(429,{},2)])
def test_provider_errors_are_bounded_and_sanitized(env,monkeypatch,status,body,attempts):
    requests=[]
    def handler(request):
        requests.append(request);return httpx.Response(status,json=body,headers={'Location':'https://untrusted.example.com'})
    transport(monkeypatch,handler)
    with pytest.raises(emailer.EmailDeliveryError) as error:
        emailer.send_verification(configure(env),'synthetic@example.com','123456')
    assert len(requests)==attempts
    assert str(error.value)=='Transactional email delivery failed'
    assert error.value.provider_status == (status if status not in {200} else None)


def test_resend_400_exposes_only_fixed_diagnostic_labels(env,monkeypatch):
    transport(monkeypatch,lambda _:httpx.Response(
        400,json={'name':'validation_error',
                  'message':'Invalid `from` address: private-reset-token@example.com OTP 123456'}))
    with pytest.raises(emailer.EmailDeliveryError) as error:
        emailer.send_verification(configure(env),'synthetic@example.com','123456')
    assert error.value.provider_status == 400
    assert error.value.provider_code == 'validation_error'
    assert error.value.field_hint == 'from'
    assert 'private-reset-token' not in str(error.value)
    assert '123456' not in repr(error.value)


def test_sanitized_provider_summary_does_not_log_tokens_or_addresses():
    response = httpx.Response(400, json={'name': 'validation_error',
        'message': "Cannot send email with this delivery address user+sample@example.com"})
    summary = emailer._safe_provider_summary(response)
    assert 'user+sample' not in summary and 'example.com' not in summary
    assert '[email]' in summary
    dangerous = httpx.Response(400,json={'message':'OTP 123456 at https://milaan.app/#token=private'})
    assert emailer._safe_provider_summary(dangerous)=='redacted'


def test_long_rate_limit_does_not_sleep_or_retry(env,monkeypatch):
    calls=[]
    transport(monkeypatch,lambda r:(calls.append(r) or httpx.Response(429,headers={'Retry-After':'60'})))
    with pytest.raises(emailer.EmailDeliveryError):emailer.send_verification(configure(env),'synthetic@example.com','123456')
    assert len(calls)==1


def test_client_enforces_https_tls_no_redirect_or_proxy(monkeypatch):
    real=httpx.Client; captured={}
    def factory(**kwargs):captured.update(kwargs);return real(transport=httpx.MockTransport(lambda _:httpx.Response(200)),**kwargs)
    monkeypatch.setattr(emailer.httpx,'Client',factory)
    with emailer._client():pass
    assert captured['verify'] is True and captured['trust_env'] is False and captured['follow_redirects'] is False
    assert captured['timeout'].connect==3 and captured['timeout'].read==5


def test_missing_key_fails_before_network(env,monkeypatch):
    env[2].resend_api_key=''
    def forbidden():raise AssertionError('Unexpected network access')
    monkeypatch.setattr(emailer,'_client',forbidden)
    with pytest.raises(emailer.EmailDeliveryError):emailer.send_verification(env[2],'synthetic@example.com','123456')


def test_signup_verification_and_password_reset_through_real_adapter(env,monkeypatch):
    client,db,settings=env;configure(env);settings.require_email_verification=True
    messages=[]
    def handler(request):messages.append(json.loads(request.content));return httpx.Response(200,json={'id':'synthetic'})
    transport(monkeypatch,handler)
    signup=client.post('/api/auth/register',json={'email':'resend@example.com','password':'synthetic-long-password','display_name':'Synthetic'})
    assert signup.status_code==201
    code=messages[-1]['text'].split('is: ')[1].split('\n')[0]
    with db.sessions() as s:
        row=s.scalar(select(PendingSignup));assert code not in row.code_hash
        assert s.scalar(select(User)) is None
    verified=client.post('/api/auth/verify-email',json={'challenge_id':signup.json()['challenge_id'],'code':code})
    assert verified.status_code==200
    client.post('/api/auth/request-password-reset',json={'email':'resend@example.com'})
    token=messages[-1]['text'].split('#token=')[1].split('\n')[0]
    with db.sessions() as s:assert s.scalar(select(PasswordReset)).token_hash==token_digest(token)
    assert client.post('/api/auth/reset-password',json={'token':token,'password':'synthetic-changed-password'}).status_code==200
    assert client.post('/api/auth/reset-password',json={'token':token,'password':'synthetic-changed-password'}).status_code==400
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+verified.json()['access_token']}).status_code==401


def test_api_failures_do_not_expose_provider_body_or_account_existence(env,monkeypatch,caplog):
    client,db,settings=env;configure(env);settings.require_email_verification=True
    transport(monkeypatch,lambda _:httpx.Response(401,text='synthetic-resend-secret recipient OTP 123456'))
    response=client.post('/api/auth/register',json={'email':'resend@example.com','password':'synthetic-long-password','display_name':'Synthetic'})
    assert response.status_code==503 and 'SMTP' not in response.text and 'synthetic-resend-secret' not in response.text
    with db.sessions() as s:assert s.scalar(select(PendingSignup)) is None and s.scalar(select(User)) is None
    settings.require_email_verification=False
    registered=client.post('/api/auth/register',json={'email':'resend@example.com','password':'synthetic-long-password','display_name':'Synthetic'}).json()
    from app.models import now
    with db.transaction() as s:s.get(User,registered['user']['id']).email_verified_at=now()
    known=client.post('/api/auth/request-password-reset',json={'email':'resend@example.com'})
    unknown=client.post('/api/auth/request-password-reset',json={'email':'unknown@example.com'})
    assert known.status_code==unknown.status_code==200 and known.json()==unknown.json()
    assert 'synthetic-resend-secret' not in caplog.text and '123456' not in caplog.text
    assert 'reason=rejected, provider_status=401' in caplog.text
    assert 'synthetic-resend-secret recipient OTP 123456' not in caplog.text
    with db.sessions() as s:assert s.scalar(select(PasswordReset)).send_count==1


def test_registration_guard_requires_explicit_live_delivery_acknowledgement():
    with pytest.raises(ValueError):production(registration_open=True)
    with pytest.raises(ValueError):production(registration_open=True,resend_api_key='synthetic',email_from='Milaan <no-reply@example.com>')
    production(registration_open=True,resend_api_key='synthetic',email_from='Milaan <no-reply@example.com>',email_delivery_verified=True)


@pytest.mark.parametrize('sender',['bad','a@example.com,b@example.com','a@example.com\r\nBcc: b@example.com'])
def test_sender_validation_rejects_invalid_or_multiple_headers(sender):
    with pytest.raises(ValueError):production(email_from=sender)
