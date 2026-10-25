"""Storage and API failure contracts, run against local files and optional real HTTP S3."""
from datetime import timedelta
import io
import tempfile
import uuid
import pytest
from sqlalchemy import select, func
from app.models import Batch, Claim, ReceiptDeletion, now
from app.storage import StorageUnavailable, StorageMissing, valid_key, drain_deletions
from app.jobs import cleanup, run_once
from conftest import load_real_flow, register


def test_receipt_is_private_sanitized_and_downloaded_only_after_ownership_check(env, auth, jpeg):
    client, database, settings = env
    signed = []
    if settings.storage_backend == 's3':
        def capture_signature(request, **kwargs):
            signed.append(request.headers.get('Authorization', b'').startswith(b'AWS4-HMAC-SHA256'))
        client.app.state.receipt_storage.client.meta.events.register('before-send.s3.PutObject', capture_signature)
    batch, _, claim = load_real_flow(client, auth, jpeg)
    path = '/api/claims/' + claim['id'] + '/image'
    assert 'image_path' not in claim
    assert settings.s3_bucket not in str(claim) if settings.storage_backend == 's3' else True
    assert client.get(path).status_code == 401
    other = register(client, 'other-synthetic@example.com')
    assert client.get(path, headers=other).status_code == 404
    image = client.get(path, headers=auth)
    assert image.status_code == 200 and image.headers['content-type'] == 'image/jpeg'
    assert 'no-store' in image.headers['cache-control']
    assert image.content.startswith(b'\xff\xd8')
    if settings.storage_backend == 's3':
        import httpx
        storage = client.app.state.receipt_storage
        with database.sessions() as db: key = db.get(Claim, claim['id']).image_path
        response = httpx.get(settings.s3_endpoint_url + '/' + storage.bucket + '/' + storage.prefix + key, trust_env=False)
        assert response.status_code == 403  # Default private bucket, no anonymous GET.
        assert signed == [True]
        assert not settings.storage_dir.exists()
        from fastapi.testclient import TestClient
        from app.main import create_app
        with TestClient(create_app(settings)) as fresh_application:
            assert fresh_application.get(path, headers=auth).content == image.content


def test_delete_failure_is_durable_and_retry_erases_object_after_claim_is_gone(env, auth, jpeg, monkeypatch):
    client, database, _ = env
    _, _, claim = load_real_flow(client, auth, jpeg)
    storage = client.app.state.receipt_storage
    with database.sessions() as db: key = db.get(Claim, claim['id']).image_path
    original = storage.delete
    def unavailable(key): raise StorageUnavailable()
    monkeypatch.setattr(storage, 'delete', unavailable)
    response = client.delete('/api/claims/' + claim['id'], headers=auth, params={'expected_version': claim['version']})
    assert response.status_code == 200
    with database.transaction() as db:
        assert db.get(Claim, claim['id']) is None
        pending = db.scalar(select(ReceiptDeletion))
        assert pending.object_key == key and pending.attempts == 1
        pending.next_attempt_at = now() - timedelta(seconds=1)
    assert storage.get(key)
    monkeypatch.setattr(storage, 'delete', original)
    drain_deletions(database, storage)
    with database.sessions() as db: assert db.scalar(select(func.count()).select_from(ReceiptDeletion)) == 0
    with pytest.raises(StorageMissing): storage.get(key)


def test_partial_put_failure_rolls_back_claim_and_erases_potential_object(env, auth, jpeg, monkeypatch):
    client, database, _ = env
    batch, order, _ = load_real_flow(client, auth, jpeg)
    storage = client.app.state.receipt_storage
    original = storage.put
    def ambiguous(key, content):
        original(key, content)
        raise StorageUnavailable()
    monkeypatch.setattr(storage, 'put', ambiguous)
    response = client.post(f'/api/batches/{batch["id"]}/claims', headers=auth,
        files={'file': ('synthetic.jpg', jpeg, 'image/jpeg')},
        data={'order_id': order['id'], 'expected_revision': batch['revision']})
    assert response.status_code == 503
    assert response.json()['detail'] == 'Receipt storage temporarily unavailable; retry later'
    assert len(list(storage.objects())) == 1
    with database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Claim)) == 1
        assert db.get(Batch, batch['id']).revision == batch['revision']


def test_download_missing_and_provider_error_have_distinct_sanitized_responses(env, auth, jpeg, monkeypatch):
    client, database, _ = env
    _, _, claim = load_real_flow(client, auth, jpeg)
    storage = client.app.state.receipt_storage
    def unavailable(key): raise StorageUnavailable()
    with monkeypatch.context() as patch:
        patch.setattr(storage, 'get', unavailable)
        assert client.get('/api/claims/'+claim['id']+'/image', headers=auth).status_code == 503
    with database.sessions() as db: key = db.get(Claim, claim['id']).image_path
    storage.delete(key)
    assert client.get('/api/claims/'+claim['id']+'/image', headers=auth).status_code == 404


def test_expiry_and_orphan_cleanup_leave_referenced_and_recent_receipts(env, auth, jpeg, monkeypatch):
    client, database, settings = env
    batch, _, claim = load_real_flow(client, auth, jpeg)
    storage = client.app.state.receipt_storage
    recent, orphan = str(uuid.uuid4())+'.jpg', str(uuid.uuid4())+'.jpg'
    storage.put(recent, jpeg); storage.put(orphan, jpeg)
    with database.sessions() as db: referenced = db.get(Claim, claim['id']).image_path
    real_objects = storage.objects
    monkeypatch.setattr(storage, 'objects', lambda: ((k, now()-timedelta(hours=2) if k != recent else now()) for k, _ in real_objects()))
    monkeypatch.setattr('app.jobs.receipt_storage', lambda _: storage)
    cleanup(database, settings)
    assert {key for key, _ in real_objects()} == {referenced, recent}
    with database.transaction() as db: db.get(Batch, batch['id']).expires_at = now()-timedelta(seconds=1)
    cleanup(database, settings)
    assert {key for key, _ in real_objects()} == {recent}
    assert client.get('/api/claims/'+claim['id']+'/image', headers=auth).status_code == 404


def test_extraction_reads_through_storage_without_local_file(env, auth, jpeg, monkeypatch):
    client, database, settings = env
    batch, _, _ = load_real_flow(client, auth, jpeg)
    settings.extraction_provider, settings.gemini_key, settings.gemini_model = 'gemini', 'synthetic-key', 'synthetic-model'
    read = []
    def double_read(data, config):
        assert data.startswith(b'\xff\xd8'); read.append(True)
        return {}, {}, False
    monkeypatch.setattr('app.jobs.double_read', double_read)
    response = client.post('/api/batches/'+batch['id']+'/extract', headers={**auth, 'Idempotency-Key':'synthetic-storage-extract'}, json={'consent_to_cloud':True})
    assert response.status_code == 202, response.text
    assert run_once(database, settings) and read == [True]


def test_large_upload_never_rolls_over_to_temporary_files(env, auth, jpeg, monkeypatch):
    client, _, _ = env
    batch, order, _ = load_real_flow(client, auth, jpeg)
    def forbidden(*args, **kwargs): raise AssertionError('Financial upload spilled to temporary disk')
    monkeypatch.setattr(tempfile.SpooledTemporaryFile, 'rollover', forbidden)
    # JPEG accepts trailing bytes; raw input exceeds Starlette's normal 1 MiB spool.
    raw = jpeg + b'\x00' * (2 * 1024 * 1024)
    response = client.post('/api/batches/'+batch['id']+'/claims', headers=auth,
        files={'file': ('synthetic-large.jpg', raw, 'image/jpeg')},
        data={'order_id':order['id'], 'expected_revision':batch['revision']})
    assert response.status_code == 201, response.text


def test_key_validation_rejects_paths_and_foreign_objects():
    for key in ['../receipt.jpg', '/receipt.jpg', 'folder/'+str(uuid.uuid4())+'.jpg', 'not-a-key.jpg', '', None]:
        with pytest.raises(ValueError): valid_key(key)
    assert valid_key(str(uuid.uuid4())+'.jpg')


def test_s3_signed_client_errors_are_sanitized_and_body_is_closed(monkeypatch):
    from app.config import Settings
    from app.storage import S3ReceiptStorage
    from botocore.stub import Stubber
    from botocore.response import StreamingBody
    monkeypatch.setenv('AWS_PROFILE', 'this-profile-does-not-exist')
    settings = Settings(storage_backend='s3', s3_endpoint_url='https://storage.example.com', s3_region='test',
        s3_bucket='synthetic', s3_access_key_id='synthetic', s3_secret_access_key='synthetic-secret')
    storage = S3ReceiptStorage(settings); key = str(uuid.uuid4())+'.jpg'
    params = {'Bucket':storage.bucket, 'Key':storage.prefix+key}
    with Stubber(storage.client) as stub:
        stub.add_client_error('get_object', service_error_code='AccessDenied', service_message='secret-provider-detail', expected_params=params)
        with pytest.raises(StorageUnavailable) as error: storage.get(key)
        assert 'secret-provider-detail' not in str(error.value)
        stub.add_client_error('get_object', service_error_code='NoSuchKey', expected_params=params)
        with pytest.raises(StorageMissing): storage.get(key)
        stream = io.BytesIO(b'jpeg')
        stub.add_response('get_object', {'Body':StreamingBody(stream,4), 'ContentLength':4}, params)
        assert storage.get(key) == b'jpeg' and stream.closed
        stub.add_client_error('delete_object', service_error_code='AccessDenied', expected_params=params)
        with pytest.raises(StorageUnavailable): storage.delete(key)


def test_erase_queue_is_idempotent_and_never_uses_another_namespace(env, jpeg):
    from app.storage import enqueue_deletion
    client, database, _ = env
    storage = client.app.state.receipt_storage
    key = str(uuid.uuid4())+'.jpg'; storage.put(key, jpeg)
    with database.transaction() as db:
        enqueue_deletion(db, storage, key); enqueue_deletion(db, storage, key)
        db.add(ReceiptDeletion(object_key=key, storage_identity='0'*64))
    drain_deletions(database, storage)
    with database.sessions() as db:
        remaining = db.scalars(select(ReceiptDeletion)).all()
        assert len(remaining) == 1 and remaining[0].storage_identity == '0'*64
    with pytest.raises(StorageMissing): storage.get(key)


def test_cleanup_failure_does_not_stop_reconciliation_worker(env, monkeypatch):
    import threading
    from app.jobs import worker_loop
    stop = threading.Event(); processed = []
    def failure(*args): raise StorageUnavailable()
    def work(*args):
        processed.append(True); stop.set(); return True
    monkeypatch.setattr('app.jobs.cleanup', failure)
    monkeypatch.setattr('app.jobs.run_once', work)
    worker_loop(env[1], env[2], stop)
    assert processed == [True]


def test_registration_stays_closed_without_disabling_existing_login(env, auth):
    client, _, settings = env
    settings.registration_open = False
    assert client.post('/api/auth/register', json={'email':'closed@example.com','password':'synthetic-closed-password','display_name':'Synthetic'}).status_code == 403
    assert client.post('/api/auth/login', json={'email':'seller@example.com','password':'safe-test-password'}).status_code == 200
    assert client.get('/api/auth/me', headers=auth).status_code == 200
