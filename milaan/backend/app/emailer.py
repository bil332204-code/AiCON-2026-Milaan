"""Transactional mail over Resend HTTPS only. Never log payloads or provider errors."""
import secrets
import time
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx

RESEND_ENDPOINT = 'https://api.resend.com/emails'


class EmailDeliveryError(RuntimeError):
    def __init__(self, category, provider_status=None, provider_code='unknown', field_hint='none', safe_summary='none'):
        self.category = category
        # Fixed classification values only; never log provider body, recipients or credentials.
        self.provider_status = provider_status
        self.provider_code = provider_code
        self.field_hint = field_hint
        self.safe_summary = safe_summary
        super().__init__('Transactional email delivery failed')


def _safe_rejection_classification(response):
    """Return fixed safe labels; intentionally discard raw Resend provider messages."""
    try:
        data = response.json()
    except (ValueError, TypeError):
        data = None
    if not isinstance(data, dict):
        return 'unknown', 'none'
    code = data.get('name')
    allowed = {'validation_error', 'invalid_idempotency_key', 'invalid_from_address',
               'missing_required_field', 'invalid_parameter', 'restricted_api_key',
               'invalid_api_key', 'invalid_email', 'invalid_access'}
    code = code if isinstance(code, str) and code in allowed else 'unknown'
    message = data.get('message')
    field = 'none'
    if isinstance(message, str):
        message = message.lower()
        for name in ('idempotency', 'domain', 'recipient', 'sender', 'from', 'to', 'subject', 'text', 'html'):
            if re.search(r'(?<![a-z])' + name + r'(?![a-z])', message):
                field = name
                break
    return code, field


def _safe_provider_summary(response):
    """Short strictly sanitized hint for owner-only logs; never store raw response text."""
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return 'unavailable'
    if not isinstance(payload, dict) or not isinstance(payload.get('message'), str):
        return 'unavailable'
    message = payload['message']
    if len(message) > 350 or not message.isascii():
        return 'redacted'
    # Reject anything suggesting a response echoed request contents, tokens or credentials.
    if re.search(r'(?i)(?:bearer|api.?key|password reset|#token|otp|secret|authorization)', message):
        return 'redacted'
    message = re.sub(r'(?i)[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}', '[email]', message)
    message = re.sub(r'(?i)https?://[^\s]+', '[url]', message)
    message = re.sub(r'\b[a-zA-Z0-9_+/=\-]{24,}\b', '[value]', message)
    message = re.sub(r'\b\d{6,}\b', '[number]', message)
    message = re.sub(r'[^a-zA-Z0-9 .,;:!?\'"/()<>\[\]\-_]', ' ', message)
    return message[:160] or 'unavailable'


def _client():
    # Explicit TLS, no redirects (Authorization must never follow another host),
    # no ambient proxy binding, no SMTP sockets, no background delivery queue.
    return httpx.Client(timeout=httpx.Timeout(5, connect=3, pool=2),
                        verify=True, follow_redirects=False, trust_env=False)


def _send(settings, recipient, subject, text):
    if not settings.resend_api_key or not settings.email_from:
        raise EmailDeliveryError('unconfigured')
    payload = {'from': settings.email_from, 'to': [recipient], 'subject': subject, 'text': text}
    # Same logical send retains its key across our bounded retry. Never derive it
    # from an OTP or recipient: a leaked key must not permit OTP brute forcing.
    headers = {'Authorization': 'Bearer ' + settings.resend_api_key,
               'Idempotency-Key': 'milaan-' + secrets.token_hex(24)}
    with _client() as client:
        for attempt in range(2):
            try:
                response = client.post(RESEND_ENDPOINT, headers=headers, json=payload)
            except httpx.TransportError:
                if attempt == 0:
                    time.sleep(.25)
                    continue
                raise EmailDeliveryError('unavailable') from None
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    # Do not sleep through a provider's long rate-limit window.
                    # A later user request remains subject to persisted cooldowns.
                    delay = response.headers.get('Retry-After', '.25')
                    try: delay = float(delay)
                    except ValueError:
                        try:
                            date = parsedate_to_datetime(delay)
                            if date.tzinfo is None: date = date.replace(tzinfo=timezone.utc)
                            delay = max(0, (date - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            delay = 2  # Invalid advice must not trigger an immediate retry.
                    if 0 <= delay <= 1:
                        time.sleep(delay)
                        continue
                raise EmailDeliveryError('unavailable', response.status_code)
            if response.status_code not in {200, 201}:
                code, hint = _safe_rejection_classification(response)
                summary = _safe_provider_summary(response)
                raise EmailDeliveryError('rejected', response.status_code, code, hint, summary)
            try: message_id = response.json().get('id')
            except (ValueError, AttributeError): message_id = None
            if not isinstance(message_id, str) or not message_id or len(message_id) > 128:
                raise EmailDeliveryError('invalid_response')
            # Accepted by Resend is not evidence of inbox delivery.
            return


def send_verification(settings, email, code):
    _send(settings, email, 'Your Milaan verification code',
          f'Your Milaan verification code is: {code}\n\nIt expires in 10 minutes. '
          'If you did not request this, ignore this email. Never share this code.')


def send_password_reset(settings, email, token):
    # Fragment tokens never appear in application HTTP access logs/referrers.
    url = settings.public_origin + '/reset-password#token=' + token
    _send(settings, email, 'Reset your Milaan password',
          'Reset your password using this one-time link (expires in 15 minutes):\n\n'
          + url + '\n\nIf you did not request this, ignore this email. Never share the link.')
