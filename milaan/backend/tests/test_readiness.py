"""Code-only issue #8 regressions; no hosted requests or real mail."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import httpx
import pytest
from app import emailer
from test_browser_auth import account, cookie_login
from test_resend import configure, transport


def test_malformed_csrf_header_is_denied_without_server_error(env):
    client, _, _ = env
    account(client);cookie_login(client)
    for value in [b'\xff',b'\xc3\xa9',b'wrong']:
        response=client.post('/api/batches',json={'name':'Synthetic'},headers=[(b'x-csrf-token',value)])
        assert response.status_code==403
    csrf=client.get('/api/auth/session').json()['csrf_token']
    assert client.post('/api/batches',json={'name':'Synthetic'},headers={'X-CSRF-Token':csrf}).status_code==201


@pytest.mark.parametrize('advice',['invalid',format_datetime(datetime.now(timezone.utc)+timedelta(hours=1)), 'inf'])
def test_resend_respects_date_or_invalid_retry_advice(env,monkeypatch,advice):
    calls=[]
    transport(monkeypatch,lambda r:(calls.append(r) or httpx.Response(429,headers={'Retry-After':advice})))
    with pytest.raises(emailer.EmailDeliveryError):emailer.send_verification(configure(env),'synthetic@example.com','123456')
    assert len(calls)==1


def test_canonical_documents_and_reset_links_use_trusted_origin(env):
    client,_,settings=env
    settings.app_env='production';settings.public_origin='https://milaan.example.com'
    for path in ['/', '/guide', '/login', '/signup', '/workspace', '/reset-password']:
        response=client.get('https://www.milaan.example.com'+path+'?next=%2Fworkspace',follow_redirects=False,
                            headers={'X-Forwarded-Host':'evil.example.com'})
        assert response.status_code==307
        assert response.headers['location']=='https://milaan.example.com'+path+'?next=%2Fworkspace'
    home=client.get('https://milaan.example.com/')
    assert home.status_code==200 and home.headers['link']=='<https://milaan.example.com/>; rel="canonical"'
    login=client.get('https://milaan.example.com/login')
    assert login.headers['x-robots-tag']=='noindex, nofollow'


def test_alias_api_never_redirects_credentials_and_health_probe_remains_available(env):
    client,_,settings=env
    settings.app_env='production';settings.public_origin='https://milaan.example.com'
    response=client.post('https://www.milaan.example.com/api/auth/login',json={'email':'synthetic@example.com','password':'synthetic'})
    assert response.status_code==401 and 'location' not in response.headers
    assert client.get('/api/health').status_code==200
    settings.app_env='development'
    assert client.get('/').status_code==200


@pytest.mark.parametrize('stamp',['0001-01-01T00:00:00+14:00','9999-12-31T23:59:00-12:00'])
def test_timestamp_outside_utc_range_is_validation_error(stamp):
    from app.parsing import parse_time
    with pytest.raises(ValueError): parse_time(stamp)


def test_oversized_statement_amount_fails_without_mutation(env,auth):
    from conftest import fresh_batch
    client,_,_=env;batch=fresh_batch(client,auth)
    csv='posted_at,direction,amount,counterparty,transaction_id\n2026-10-09T12:00:00+05:00,CREDIT,'+'9'*50000+',Synthetic,SYNTHETIC-123\n'
    response=client.post('/api/batches/'+batch['id']+'/statement',headers=auth,
        files={'file':('synthetic.csv',csv,'text/csv')},data={'expected_revision':batch['revision'],'account_id':'synthetic',
        'coverage_start':'2026-10-09T00:00:00+05:00','coverage_end':'2026-10-10T00:00:00+05:00'})
    assert response.status_code==422
    assert client.get('/api/batches/'+batch['id']+'/statements',headers=auth).json()['items']==[]
