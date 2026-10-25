"""Real PostgreSQL integration, enabled only by the isolated Docker runner."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid
import pytest
from sqlalchemy import create_engine, text, select
from sqlalchemy.engine import make_url
from app.database import Database
from app.models import Base, User, Job, ReceiptDeletion, now
from app.security import password_hash
from app.jobs import take_job

pytestmark = pytest.mark.skipif(not os.getenv('MILAAN_INTEGRATION_DATABASE_URL'), reason='Run scripts/test_postgres_s3.py for isolated PostgreSQL/S3 integration')


@contextmanager
def schema_url():
    target = os.environ['MILAAN_INTEGRATION_DATABASE_URL']
    engine = create_engine(target)
    schema = 'synthetic_migration_' + uuid.uuid4().hex
    with engine.begin() as c: c.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(target).update_query_dict({'options': '-csearch_path='+schema}).render_as_string(hide_password=False)
    try: yield url
    finally:
        with engine.begin() as c: c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_actual_migration_history_and_direct_url_preserve_legacy_identity():
    with schema_url() as url:
        env = {**os.environ, 'MIGRATION_DATABASE_URL':url,
            'DATABASE_URL':'postgresql://unused:unused@127.0.0.1:1/unavailable'}
        backend = Path(__file__).resolve().parents[2]
        def migrate(*args, check=True):
            result = subprocess.run([sys.executable,'-m','alembic',*args], cwd=backend, env=env, capture_output=True, text=True)
            if check: assert result.returncode == 0, result.stderr
            return result
        migrate('upgrade','20261024_payment_parts')
        engine = create_engine(url)
        with engine.begin() as c:
            c.execute(text("INSERT INTO users (id,email,password_hash,display_name,is_admin,created_at) VALUES ('legacy','legacy@example.com','synthetic-old-hash','Synthetic',false,CURRENT_TIMESTAMP)"))
            c.execute(text("INSERT INTO session_tokens (token_hash,user_id,expires_at) VALUES ('synthetic-bearer','legacy',CURRENT_TIMESTAMP+INTERVAL '1 day')"))
        migrate('upgrade','head'); migrate('check')
        with engine.begin() as c:
            assert c.execute(text('SELECT id,password_hash,email_verified_at FROM users')).all() == [('legacy','synthetic-old-hash',None)]
            assert c.execute(text('SELECT session_kind FROM session_tokens')).scalar() == 'bearer'
            c.execute(text("INSERT INTO receipt_deletions VALUES ('synthetic-deletion','00000000000000000000000000000000.jpg','unused',0,CURRENT_TIMESTAMP)"))
        failure = migrate('downgrade','20261025_verified_email',check=False)
        assert failure.returncode != 0 and 'Drain receipt deletions' in failure.stderr
        with engine.begin() as c: c.execute(text('DELETE FROM receipt_deletions'))
        migrate('downgrade','20261024_payment_parts'); migrate('upgrade','head'); migrate('check')
        with engine.connect() as c:
            assert c.execute(text('SELECT id,password_hash FROM users')).all() == [('legacy','synthetic-old-hash')]
            assert c.execute(text('SELECT token_hash FROM session_tokens')).scalar() == 'synthetic-bearer'
        engine.dispose()


def test_postgres_lock_timeout_and_transaction_pool_safety(env):
    _, database, _ = env
    assert not database.sqlite
    with database.sessions() as db:
        assert db.execute(text('SHOW statement_timeout')).scalar() == '30s'
        assert db.execute(text('SHOW lock_timeout')).scalar() == '10s'
        raw = db.connection().connection.driver_connection
        assert raw.prepare_threshold is None
    # Concurrent workers take different jobs using SKIP LOCKED.
    from conftest import register
    client = env[0]; headers = register(client)
    ids = []
    for index in range(2):
        batch = client.post('/api/batches/demo',headers=headers).json()
        job = client.post('/api/batches/'+batch['id']+'/reconcile',headers={**headers,'Idempotency-Key':'parallel-synthetic-'+str(index)})
        assert job.status_code == 202; ids.append(job.json()['id'])
    barrier = threading.Barrier(2)
    def take():
        barrier.wait()
        return take_job(database, env[2])
    with ThreadPoolExecutor(2) as workers: selected = list(workers.map(lambda _:take(),range(2)))
    assert {row[0] for row in selected} == set(ids)


def test_concurrent_mutation_serializes_batch_revisions(env, auth, jpeg):
    from conftest import load_real_flow
    client, database, _ = env
    batch, order, _ = load_real_flow(client, auth, jpeg)
    barrier = threading.Barrier(2)
    def upload(_):
        barrier.wait()
        return client.post('/api/batches/'+batch['id']+'/claims',headers=auth,
            files={'file':('synthetic-concurrent.jpg',jpeg,'image/jpeg')},
            data={'order_id':order['id'],'expected_revision':batch['revision']}).status_code
    with ThreadPoolExecutor(2) as workers: codes = list(workers.map(upload,range(2)))
    assert sorted(codes) == [201,409]
