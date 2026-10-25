"""Transactional mail over Resend HTTPS only. Never log payloads or provider errors."""
import secrets
import time
import httpx

RESEND_ENDPOINT = 'https://api.resend.com/emails'


class EmailDeliveryError(RuntimeError):
    def __init__(self, category):
        self.category = category
        super().__init__('Transactional email delivery failed')


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
                    except ValueError: delay = .25
                    if 0 <= delay <= 1:
                        time.sleep(delay)
                        continue
                raise EmailDeliveryError('unavailable')
            if response.status_code not in {200, 201}:
                raise EmailDeliveryError('rejected')
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
