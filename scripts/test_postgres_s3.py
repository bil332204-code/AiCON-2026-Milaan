"""Synthetic-only integration runner. Creates and removes isolated local Docker services.

No Neon credentials, hosted database, Render service or public port is used.
Run with the project's Python environment. Docker must be available.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
POSTGRES = 'postgres:17-alpine'
S3 = 'motoserver/moto:5.1.15'


def docker(*args, **kw):
    return subprocess.run(['docker', *args], text=True, capture_output=True, check=True, **kw)


def port(name, internal):
    return json.loads(docker('inspect', name).stdout)[0]['NetworkSettings']['Ports'][internal][0]['HostPort']


def main():
    names = ['milaan-integration-' + uuid.uuid4().hex[:12] for _ in range(2)]
    password = secrets.token_hex(24)
    # Override inherited provider bindings rather than read any real credentials.
    env = {**os.environ, 'APP_ENV': 'development', 'ALLOW_REGISTRATION': 'true',
        'SESSION_COOKIE_SECURE': 'false', 'REQUIRE_EMAIL_VERIFICATION': 'false',
        'DEMO_SELLER_EMAIL': '', 'DEMO_SELLER_PASSWORD': '', 'STORAGE_BACKEND': 's3',
        'RUN_WORKER_IN_API': 'false', 'S3_BUCKET': 'synthetic-private-receipts',
        'S3_REGION': 'us-east-1', 'S3_ACCESS_KEY_ID': secrets.token_hex(12),
        'S3_SECRET_ACCESS_KEY': secrets.token_hex(24), 'S3_SESSION_TOKEN': '',
        'S3_PREFIX': 'synthetic/' + uuid.uuid4().hex + '/', 'S3_ADDRESSING_STYLE': 'path',
        'SMTP_HOST': '', 'GEMINI_API_KEY': '', 'PUBLIC_ORIGIN': 'http://127.0.0.1:8000'}
    try:
        docker('run', '--detach', '--rm', '--name', names[0], '-p', '127.0.0.1::5432',
            '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_DB=synthetic', POSTGRES,
            env={**os.environ, 'POSTGRES_PASSWORD': password})
        docker('run', '--detach', '--rm', '--name', names[1], '-p', '127.0.0.1::5000', S3)
        pg_port, s3_port = port(names[0], '5432/tcp'), port(names[1], '5000/tcp')
        env['DATABASE_URL'] = f'postgresql+psycopg://postgres:{password}@127.0.0.1:{pg_port}/synthetic'
        env['MIGRATION_DATABASE_URL'] = env['DATABASE_URL']
        env['MILAAN_INTEGRATION_DATABASE_URL'] = env['DATABASE_URL']
        env['S3_ENDPOINT_URL'] = f'http://127.0.0.1:{s3_port}'
        for attempt in range(80):
            ready = subprocess.run(['docker', 'exec', names[0], 'pg_isready', '-U', 'postgres', '-d', 'synthetic'], capture_output=True).returncode == 0
            try:
                with urllib.request.urlopen(env['S3_ENDPOINT_URL'], timeout=1): pass
                if ready: break
            except Exception: pass
            time.sleep(.25)
        else: raise RuntimeError('Local integration services did not start')
        # Use exactly the application's authenticated S3 client over HTTP.
        subprocess.run([sys.executable, '-c', "from app.config import Settings; from app.storage import receipt_storage; s=receipt_storage(Settings()); s.client.create_bucket(Bucket=s.bucket)"], cwd=ROOT/'milaan/backend', env=env, check=True)
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', 'matching/tests', *sys.argv[1:]], cwd=ROOT/'milaan/backend', env=env)
        return result.returncode
    finally:
        for name in names:
            subprocess.run(['docker', 'rm', '--force', '--volumes', name], capture_output=True)


if __name__ == '__main__':
    raise SystemExit(main())
