"""RFC 6238 time-based one-time passwords (authenticator apps), SHA-1, 30 s, 6 digits."""
import base64, hashlib, hmac, secrets, struct, time
from urllib.parse import quote

STEP, DIGITS = 30, 6


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def _code(secret, counter):
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 10 ** DIGITS:0{DIGITS}d}"


def verify(secret, code, last_step=None, at=None):
    """Return the matched time step (allowing one step of clock drift), or None.
    A step at or before `last_step` is refused so a seen code cannot be replayed."""
    if not secret or not isinstance(code, str) or len(code) != DIGITS or not code.isdigit():
        return None
    now = int((at if at is not None else time.time()) // STEP)
    for step in (now - 1, now, now + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(_code(secret, step), code):
            return step
    return None


def provisioning_uri(secret, email, issuer="Milaan"):
    label = quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP}"


def code_now(secret, at=None):
    """Test helper: the current code for a secret."""
    return _code(secret, int((at if at is not None else time.time()) // STEP))
