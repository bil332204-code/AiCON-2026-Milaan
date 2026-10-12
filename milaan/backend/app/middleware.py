from collections import defaultdict, deque
import time, threading
from starlette.responses import JSONResponse

class GuardMiddleware:
    """Bounded input + basic single-instance rate limits. No untrusted proxy IP headers."""
    def __init__(self, app, limit, testing=False):
        self.app, self.limit, self.testing = app, limit, testing
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": return await self.app(scope, receive, send)
        method, path = scope["method"], scope["path"]
        async def guarded_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend([(b"x-content-type-options", b"nosniff"), (b"cache-control", b"no-store"), (b"referrer-policy", b"no-referrer")])
            await send(message)
        if not self.testing and method == "POST" and path in {"/api/auth/login", "/api/auth/register", "/api/auth/verify-email", "/api/auth/resend-code"}:
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
