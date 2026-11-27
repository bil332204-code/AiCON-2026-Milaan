from starlette.responses import JSONResponse
from .limits import RateLimiter, client_ip

AUTH_PATHS = {"/api/auth/login", "/api/auth/register", "/api/auth/verify-email", "/api/auth/resend-code",
              "/api/auth/request-password-reset", "/api/auth/reset-password", "/api/auth/totp/verify-login"}
PRIVATE_PAGES = {"/workspace", "/login", "/signup", "/reset-password"}
# One policy for every page. Scripts only from this origin, plus the pinned, integrity-checked
# OCR engine on jsDelivr (it runs its worker from a blob: URL and needs WebAssembly).
CSP = ("default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'wasm-unsafe-eval'; "
       "worker-src 'self' blob:; connect-src 'self' https://cdn.jsdelivr.net blob: data:{extra}; "
       "img-src 'self' blob: data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; frame-ancestors 'none'; base-uri 'self'; "
       "object-src 'none'; form-action 'self'")


def security_headers(path, production, connect_extra=""):
    if path.startswith("/api/") or path in PRIVATE_PAGES:
        cache = b"no-store"
    else:  # public pages and static files: revalidate with ETag/Last-Modified instead of re-downloading
        cache = b"no-cache"
    headers = [(b"x-content-type-options", b"nosniff"), (b"cache-control", cache),
               (b"referrer-policy", b"no-referrer"), (b"x-frame-options", b"DENY"),
               (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
               (b"cross-origin-opener-policy", b"same-origin"),
               (b"content-security-policy", CSP.format(extra=connect_extra).encode())]
    # Render terminates public TLS; HSTS only belongs on configured production.
    if production:
        headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
    return headers


class GuardMiddleware:
    """Bounded input + single-instance rate limits keyed on the real client IP.

    Behind Render every socket peer is 127.0.0.1, so the client address comes from the
    trusted proxy headers (see limits.client_ip); keying on the peer would make one bucket
    shared by every visitor."""
    def __init__(self, app, limit, testing=False, production=False, trust_proxy=True, connect_extra=""):
        self.app, self.limit, self.testing, self.production = app, limit, testing, production
        self.trust_proxy, self.connect_extra = trust_proxy, connect_extra
        self.per_ip = RateLimiter(15, 60)
        # Ceiling across all clients: protects CPU (scrypt) from a distributed flood.
        self.overall = RateLimiter(600, 60)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": return await self.app(scope, receive, send)
        method, path = scope["method"], scope["path"]
        ip = client_ip(scope, self.trust_proxy)
        scope.setdefault("state", {})["client_ip"] = ip
        async def guarded_send(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k.lower() for k, _ in headers}
                for key, value in security_headers(path, self.production, self.connect_extra):
                    if key not in present: headers.append((key, value))
            await send(message)
        if not self.testing and method == "POST" and path in AUTH_PATHS:
            limited = not self.per_ip.hit(ip) or not self.overall.hit("all")
            if limited: return await JSONResponse({"detail": "Too many attempts from your network; wait a minute"}, 429)(scope, receive, guarded_send)
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
    public = {'/', '/index.html', '/guide', '/privacy', '/terms', '/about', '/fake-payment-screenshot'}
    pages = public | {'/login', '/signup', '/workspace', '/reset-password'}
    aliases = {'/index.html': '/', '/privacy.html': '/privacy', '/terms.html': '/terms', '/about.html': '/about',
               '/fake-payment-screenshot.html': '/fake-payment-screenshot'}

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
                if path not in self.public:
                    headers.append((b'x-robots-tag',b'noindex, nofollow'))
            await send(message)
        await self.app(scope,receive,canonical_send)
