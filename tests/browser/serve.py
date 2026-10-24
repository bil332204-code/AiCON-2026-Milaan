"""Dedicated test server; never reads the user's DB or operator configuration."""
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile

def stop_test_server(signum, frame):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop_test_server)

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='milaan-browser-') as tmp:
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{tmp}/browser.db',
           'STORAGE_DIR': tmp+'/uploads', 'EXTRACTION_PROVIDER': 'manual',
           'GEMINI_API_KEY': '', 'REQUIRE_EMAIL_VERIFICATION': 'true',
           'DEMO_SELLER_EMAIL': 'browser@example.com',
           'DEMO_SELLER_PASSWORD': 'synthetic-browser-test-password',
           'RUN_WORKER_IN_API': 'true', 'APP_ENV':'development', 'SESSION_COOKIE_SECURE':'false', 'PUBLIC_ORIGIN':'http://127.0.0.1:8765', 'MILAAN_TEST_OUTBOX': '/tmp/milaan-browser-test-outbox.jsonl'}
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                   cwd=ROOT/'milaan/backend', env=env, check=True)
    Path(env['MILAAN_TEST_OUTBOX']).unlink(missing_ok=True)
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'browser_server:app', '--app-dir', str(ROOT/'tests/browser'),
                              '--host', '127.0.0.1', '--port', '8765', '--log-level', 'warning'],
                             cwd=ROOT/'milaan/backend', env=env)
    try:
        server.wait()
    finally:
        server.terminate()
        server.wait(timeout=10)
        Path(env['MILAAN_TEST_OUTBOX']).unlink(missing_ok=True)
