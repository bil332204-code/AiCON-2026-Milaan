import hashlib, hmac, secrets
from datetime import timedelta
from .models import SessionToken, now

def password_hash(password):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${key.hex()}"

def verify_password(password, stored):
    try:
        _, salt, expected = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False

def token_digest(token): return hashlib.sha256(token.encode()).hexdigest()

def issue_session(db, user_id, hours):
    raw = secrets.token_urlsafe(48)
    expiry = now() + timedelta(hours=hours)
    db.add(SessionToken(token_hash=token_digest(raw), user_id=user_id, expires_at=expiry))
    return {"access_token": raw, "token_type": "bearer", "expires_at": expiry.isoformat() + "Z"}
