import hashlib, hmac, secrets
from datetime import timedelta
from .models import SessionToken, now

# Versioned OWASP-listed scrypt work factor; legacy hashes remain verifiable.
def password_hash(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=3, dklen=32, maxmem=64*1024*1024)
    return f"scrypt-v2${salt.hex()}${key.hex()}"


def verify_password(password, stored):
    try:
        version, salt, expected = stored.split('$')
        if version not in {'scrypt', 'scrypt-v2'}: return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                 n=32768 if version == 'scrypt-v2' else 16384, r=8,
                 p=3 if version == 'scrypt-v2' else 1, dklen=32, maxmem=64*1024*1024)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def token_digest(token): return hashlib.sha256(token.encode()).hexdigest()
def csrf_token(raw): return hmac.new(raw.encode(), b'milaan-csrf-v1', hashlib.sha256).hexdigest()


def issue_session(db, user_id, hours, kind='bearer'):
    raw = secrets.token_urlsafe(48)
    expiry = now() + timedelta(hours=hours)
    db.add(SessionToken(token_hash=token_digest(raw), user_id=user_id, expires_at=expiry, session_kind=kind))
    return {'access_token':raw,'token_type':'bearer','expires_at':expiry.isoformat()+'Z'}
