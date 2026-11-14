"""Refuse passwords that appear in known data breaches (Have I Been Pwned range API).
Only the first 5 hex characters of the SHA-1 hash leave the server (k-anonymity).
Fails open: if the service is slow or down, signup is not blocked."""
import hashlib
import httpx


def is_breached(password, timeout=3.0):
    digest = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()  # HIBP API format, not storage
    prefix, suffix = digest[:5], digest[5:]
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = client.get(f"https://api.pwnedpasswords.com/range/{prefix}",
                                  headers={"Add-Padding": "true", "User-Agent": "Milaan-password-check"})
        if response.status_code != 200:
            return False
        for line in response.text.splitlines():
            candidate, _, count = line.partition(":")
            if candidate.strip() == suffix and count.strip() not in {"", "0"}:
                return True
    except (httpx.HTTPError, ValueError):
        return False
    return False
