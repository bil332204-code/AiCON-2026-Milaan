#!/usr/bin/env python3
"""Fail CI for common untracked-sensitive paths accidentally committed to Git."""
from pathlib import PurePosixPath
import subprocess

tracked = subprocess.check_output(['git','ls-files','--cached','-z']).decode('utf-8').split('\0')
blocked = []
for entry in filter(None,tracked):
    file = PurePosixPath(entry)
    name = file.name.lower()
    if name.startswith('.env') and not name.endswith('.example'):
        blocked.append(entry)
    if name.endswith(('.db','.sqlite','.sqlite3','.pem','.p12','.pfx','.key','.db-wal','.db-shm')):
        blocked.append(entry)
    if file.parts and any(part.lower() in {'private-uploads','receipts','backups','exports'} for part in file.parts[:-1]):
        blocked.append(entry)
print('Tracked path safety: {} files examined; {} blocked path(s)'.format(len(list(filter(None,tracked))),len(blocked)))
if blocked: raise SystemExit(1)
