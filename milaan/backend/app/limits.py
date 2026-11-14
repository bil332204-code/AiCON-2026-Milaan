"""In-process abuse limits: client IP behind trusted proxies, sliding-window counters and
bounded slots for memory-heavy work. Single-instance by design; state resets on restart."""
from collections import defaultdict, deque
from contextlib import contextmanager
import ipaddress
import threading
import time

_PRIVATE = [ipaddress.ip_network(n) for n in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                                               "100.64.0.0/10", "::1/128", "fc00::/7", "fe80::/10")]


def _ip(value):
    try:
        return ipaddress.ip_address(value.strip())
    except (ValueError, AttributeError):
        return None


def trusted_peer(peer):
    """Only a local/private hop (Render's router, Caddy) may tell us the real client IP."""
    address = _ip(peer)
    return bool(address and any(address in network for network in _PRIVATE))


def client_ip(scope, trust_proxy=True):
    """Real client address. Behind Render, every socket peer is 127.0.0.1, so a limit keyed
    on the peer would be one bucket shared by every visitor. Cloudflare sets and overwrites
    CF-Connecting-IP; other trusted proxies append the client to X-Forwarded-For."""
    peer = (scope.get("client") or ("unknown",))[0]
    if not trust_proxy or not trusted_peer(peer):
        return peer
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    candidate = _ip(headers.get("cf-connecting-ip", ""))
    if candidate:
        return str(candidate)
    forwarded = [part for part in headers.get("x-forwarded-for", "").split(",") if part.strip()]
    # Walk from the nearest hop outwards; the first non-private address is the client.
    for part in reversed(forwarded):
        candidate = _ip(part)
        if candidate and not any(candidate in network for network in _PRIVATE):
            return str(candidate)
    return peer


class RateLimiter:
    """Sliding window: at most `limit` events per `window` seconds for each key."""

    def __init__(self, limit, window, max_keys=50_000):
        self.limit, self.window, self.max_keys = limit, window, max_keys
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def _trim(self, key, now):
        queue = self.hits[key]
        while queue and queue[0] <= now - self.window:
            queue.popleft()
        return queue

    def hit(self, key):
        """Record one event; return False when the key is already over its limit."""
        with self.lock:
            now = time.monotonic()
            if len(self.hits) > self.max_keys:
                for stale in [k for k, q in self.hits.items() if not q or q[-1] <= now - self.window]:
                    del self.hits[stale]
                if len(self.hits) > self.max_keys:
                    self.hits.clear()
            queue = self._trim(key, now)
            if len(queue) >= self.limit:
                return False
            queue.append(now)
            return True

    def blocked(self, key):
        with self.lock:
            return len(self._trim(key, time.monotonic())) >= self.limit

    def count(self, key):
        with self.lock:
            return len(self._trim(key, time.monotonic()))

    def reset(self, key):
        with self.lock:
            self.hits.pop(key, None)


class Busy(Exception):
    def __init__(self, per_user):
        self.per_user = per_user


class HeavySlots:
    """Caps concurrent memory-heavy requests (PDF parsing, image decoding) so a burst of
    uploads cannot exhaust a small instance. Each user's heavy requests run one at a time;
    a request waits briefly for its turn and is refused with Busy if the wait runs out."""

    def __init__(self, slots, wait=15):
        self.semaphore = threading.BoundedSemaphore(slots)
        self.wait = wait
        self.users, self.waiting = {}, defaultdict(int)
        self.lock = threading.Lock()

    @contextmanager
    def hold(self, user_id):
        with self.lock:
            if self.waiting[user_id] >= 3:  # never queue an unbounded pile per user
                raise Busy(per_user=True)
            self.waiting[user_id] += 1
            user_lock = self.users.setdefault(user_id, threading.Lock())
        try:
            if not user_lock.acquire(timeout=self.wait):
                raise Busy(per_user=True)
            try:
                if not self.semaphore.acquire(timeout=self.wait):
                    raise Busy(per_user=False)
                try:
                    yield
                finally:
                    self.semaphore.release()
            finally:
                user_lock.release()
        finally:
            with self.lock:
                self.waiting[user_id] -= 1
                if not self.waiting[user_id]:
                    del self.waiting[user_id]
                    self.users.pop(user_id, None)
