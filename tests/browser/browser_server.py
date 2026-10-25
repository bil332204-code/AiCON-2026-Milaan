"""Test-only SMTP transport. Not included in the deployable app or Docker image."""
import json
import os
from pathlib import Path
import threading
from app import main
from app.config import Settings
from app.models import User
from app.security import password_hash
from sqlalchemy import select

mailbox=Path(os.environ['MILAAN_TEST_OUTBOX']);lock=threading.Lock()
def capture(kind,email,value):
    # Only synthetic Playwright accounts are permitted in this harness.
    if not email.endswith('@example.com'): raise RuntimeError('Synthetic email addresses only')
    with lock:
        fd=os.open(mailbox,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        with os.fdopen(fd,'a') as file:file.write(json.dumps({'kind':kind,'email':email,'value':value})+'\n')
main.send_verification=lambda settings,email,code:capture('verification',email,code)
main.send_password_reset=lambda settings,email,token:capture('reset',email,token)
# Fixed-IP tests exercise many auth flows. Production rate limiting is separately
# tested with testing=False; account lockouts, cookies and CSRF remain active here.
settings=Settings(testing=True)
app=main.create_app(settings)
with app.state.database.transaction() as db:
    for email in ['browser@example.com','legacy-desktop@example.com','legacy-mobile@example.com']:
        if not db.scalar(select(User).where(User.email==email)):
            db.add(User(email=email,password_hash=password_hash('synthetic-browser-test-password'),display_name='Synthetic browser operator'))
