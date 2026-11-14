"""Transactional mail over Resend HTTPS only. Never log payloads or provider errors."""
import secrets
import time
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx

RESEND_ENDPOINT = 'https://api.resend.com/emails'


class EmailDeliveryError(RuntimeError):
    def __init__(self, category, provider_status=None, provider_code='unknown', field_hint='none'):
        self.category = category
        # Fixed classification values only; never log provider body, recipients or credentials.
        self.provider_status = provider_status
        self.provider_code = provider_code
        self.field_hint = field_hint
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
                raise EmailDeliveryError('rejected', response.status_code, code, hint)
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


def send_existing_account_notice(settings, email):
    """Someone tried to sign up with an address that already has an account. The signup
    reply looks the same either way, so only the real owner learns it happened."""
    _send(settings, email, 'Someone tried to create a Milaan account with your email',
          'Someone tried to create a new Milaan account using this email address, which already has an account.\n\n'
          'If it was you, sign in instead, or use "Forgot password?" on the sign-in page: '
          + settings.public_origin + '/login\n\nIf it was not you, you can ignore this email. Your account was not changed.')


def send_signin_alert(settings, email):
    _send(settings, email, 'Several failed sign-in attempts on your Milaan account',
          'There were several failed attempts to sign in to your Milaan account in the last few minutes, '
          'from more than one network.\n\nIf this was not you, your password has not been shared by Milaan, '
          'but consider changing it and turning on two-step sign-in in Settings: ' + settings.public_origin + '/login\n')
