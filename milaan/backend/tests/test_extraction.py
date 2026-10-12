import json
import httpx
import pytest
from app import extraction
from app.config import Settings

FIELDS = {'is_payment_receipt':True, 'amount_pkr':'3500', 'datetime_local':'2026-10-09T14:22:00+05:00', 'transaction_id':'TX123456', 'status_text':'Successful', 'unreadable_fields':[]}

def test_two_reads_agree_and_disagree(monkeypatch):
    monkeypatch.setattr(extraction, 'extract_once', lambda *args: dict(FIELDS))
    assert extraction.double_read(b'image', Settings())[2] is True
    monkeypatch.setattr(extraction, 'extract_once', lambda image, settings, n: {**FIELDS, 'amount_pkr':'3500' if n==1 else '350'})
    assert extraction.double_read(b'image', Settings())[2] is False

def test_rest_request_and_untrusted_json(monkeypatch):
    settings = Settings(gemini_key='fake-test-key', gemini_model='fake-test-model')
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, headers, json):
            assert 'fake-test-key' not in url
            assert headers['x-goog-api-key']=='fake-test-key'
            assert 'responseJsonSchema' in json['generationConfig']
            return httpx.Response(200, json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':__import__('json').dumps(FIELDS)}]}}]})
    monkeypatch.setattr(extraction.httpx, 'Client', Client)
    assert extraction.extract_once(b'image',settings,1)['amount_pkr']=='3500'
    monkeypatch.setattr(Client, 'post', lambda *a, **kw: httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ship_everything":true}'}]}}]}))
    with pytest.raises(extraction.ExtractionUnavailable, match='INVALID_MODEL_OUTPUT'): extraction.extract_once(b'image',settings,1)

def test_provider_timeout_abstains(monkeypatch):
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self,*args,**kwargs): raise httpx.ReadTimeout('sensitive provider details')
    monkeypatch.setattr(extraction.httpx, 'Client', Client)
    with pytest.raises(extraction.ExtractionUnavailable, match='PROVIDER_UNAVAILABLE'):
        extraction.extract_once(b'image', Settings(gemini_key='fake-test-key',gemini_model='fake-model'),1)
