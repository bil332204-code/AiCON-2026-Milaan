from collections import defaultdict, deque
import time, threading
from starlette.responses import JSONResponse

class GuardMiddleware:
    """Bounded input + basic single-instance rate limits. No untrusted proxy IP headers."""
    def __init__(self, app, limit, testing=False, production=False):
        self.app, self.limit, self.testing, self.production = app, limit, testing, production
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": return await self.app(scope, receive, send)
        method, path = scope["method"], scope["path"]
        async def guarded_send(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.extend([(b"x-content-type-options", b"nosniff"), (b"cache-control", b"no-store"),
                    (b"referrer-policy", b"no-referrer"), (b"x-frame-options", b"DENY"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"content-security-policy", b"frame-ancestors 'none'; base-uri 'self'; object-src 'none'")])
                # Render terminates public TLS; HSTS only belongs on configured production.
                if self.production:
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
            await send(message)
        if not self.testing and method == "POST" and path in {"/api/auth/login", "/api/auth/register", "/api/auth/verify-email", "/api/auth/resend-code", "/api/auth/request-password-reset", "/api/auth/reset-password"}:
            key = scope.get("client", ("unknown",))[0]
            with self.lock:
                t = time.monotonic()
                if len(self.hits) > 10000: self.hits.clear()
                q = self.hits[key]
                while q and q[0] < t - 60: q.popleft()
                limited = len(q) >= 15
                if not limited: q.append(t)
            if limited: return await JSONResponse({"detail": "Too many authentication attempts; wait a minute"}, 429)(scope, receive, guarded_send)
        if method in {"POST", "PUT", "PATCH"}:
            parts, total = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect": return
                body = message.get("body", b""); total += len(body)
                if total > self.limit:
                    return await JSONResponse({"detail": "Request exceeds 12 MB"}, 413)(scope, receive, guarded_send)
                parts.append(body)
                if not message.get("more_body", False): break
            pending = True
            async def replay():
                nonlocal pending
                if pending:
                    pending = False
                    return {"type": "http.request", "body": b"".join(parts), "more_body": False}
                return await receive()
            return await self.app(scope, replay, guarded_send)
        return await self.app(scope, receive, guarded_send)


class CanonicalOriginMiddleware:
    """Use the configured public origin for browser documents, never forwarded hosts.

    Redirect only safe document requests. API calls retain their existing authentication
    and origin checks; never redirect credentials or request bodies across origins.
    Render health probes remain available independently of their internal Host.
    """
    pages = {'/', '/index.html', '/login', '/signup', '/workspace', '/reset-password', '/guide', '/privacy', '/terms', '/about'}
    aliases = {'/index.html': '/', '/privacy.html': '/privacy', '/terms.html': '/terms', '/about.html': '/about'}

    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or self.settings.app_env != 'production':
            return await self.app(scope, receive, send)
        from urllib.parse import urlsplit
        from starlette.responses import RedirectResponse
        origin = self.settings.public_origin
        host = dict(scope['headers']).get(b'host', b'').decode('latin-1').lower()
        canonical = urlsplit(origin).netloc.lower()
        path, method = scope['path'], scope['method']
        if path != '/api/health' and host != canonical:
            if method in {'GET', 'HEAD'} and path in self.pages | self.aliases.keys():
                query = scope.get('query_string', b'').decode('latin-1')
                target = origin + self.aliases.get(path, path)
                if query: target += '?' + query
                return await RedirectResponse(target, status_code=307, headers={'Cache-Control':'no-store'})(scope, receive, send)
        async def canonical_send(message):
            if message['type'] == 'http.response.start' and path in self.pages:
                headers = message.setdefault('headers', [])
                target = origin + ('/' if path == '/index.html' else path)
                headers.append((b'link', ('<'+target+'>; rel="canonical"').encode('ascii')))
                if path not in {'/', '/index.html', '/guide', '/privacy', '/terms', '/about'}:
                    headers.append((b'x-robots-tag',b'noindex, nofollow'))
            await send(message)
        await self.app(scope,receive,canonical_send)
