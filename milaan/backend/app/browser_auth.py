"""Host-only HttpOnly cookies; unsafe cookie requests need same-origin checks and CSRF."""
import hmac
from fastapi import HTTPException
from .security import csrf_token, issue_session


def check_origin(request, settings):
    origin = request.headers.get('origin')
    allowed = {settings.public_origin}
    if settings.app_env == 'development':
        allowed |= set(settings.cors_origins) | {str(request.base_url).rstrip('/')}
    if origin and origin not in allowed:
        raise HTTPException(403, 'This browser origin is not permitted')
    if not origin and request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'Cross-site authentication is not permitted')


def check_csrf(request, settings, raw):
    check_origin(request, settings)
    if not hmac.compare_digest(request.headers.get('x-csrf-token', '').encode('utf-8'), csrf_token(raw).encode('ascii')):
        raise HTTPException(403, 'Browser session security token missing or stale; reload and retry')


def session_result(db, user_id, mode, request, response, settings, remember=False):
    if mode == 'cookie': check_origin(request, settings)
    hours = settings.remember_hours if mode == 'cookie' and remember else settings.session_hours
    token = issue_session(db, user_id, hours, kind=mode)
    if mode == 'bearer': return token
    response.set_cookie(settings.cookie_name, token['access_token'], httponly=True,
                        secure=settings.cookie_secure, samesite='lax', path='/',
                        max_age=hours*3600 if remember else None)
    return {'csrf_token':csrf_token(token['access_token']),'expires_at':token['expires_at']}
