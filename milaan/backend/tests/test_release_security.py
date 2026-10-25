"""Regression checks for existing release safety controls (synthetic input only)."""
import asyncio
import io
import csv
from types import SimpleNamespace
from fastapi import HTTPException
from PIL import Image
from app.parsing import csv_export
from app.storage import clean_image
from app.browser_auth import check_csrf
from app.middleware import GuardMiddleware


def test_csv_export_cannot_start_spreadsheet_formulas():
    values = ['=1+1', '+1+1', '-1+1', '@SUM(A1:A2)', '\t=1', '\r=1', ' \t=1', 'ordinary']
    output = csv_export(['customer_name'], [[value] for value in values])
    decoded = list(csv.reader(io.StringIO(output)))
    assert [row[0] for row in decoded[1:]] == [
        "'" + value if index < 7 else value for index, value in enumerate(values)]


def test_receipt_image_is_reencoded_without_private_exif():
    original = io.BytesIO()
    image = Image.new('RGB', (40, 30), 'white')
    exif = Image.Exif()
    exif[0x010E] = "SYNTHETIC PRIVATE METADATA"
    image.save(original, 'JPEG', exif=exif)
    cleaned = clean_image(original.getvalue())
    with Image.open(io.BytesIO(cleaned)) as result:
        assert result.format == 'JPEG'
        assert not result.getexif()
        assert result.size == (40, 30)


def test_non_ascii_csrf_header_denied_with_403(env):
    _, _, settings = env
    fake = SimpleNamespace(headers={'origin': settings.public_origin, 'x-csrf-token': 'é'})
    try:
        check_csrf(fake, settings, 'synthetic-token')
        raise AssertionError('Nonmatching CSRF cannot be accepted')
    except HTTPException as exception:
        assert exception.status_code == 403


def test_standard_security_response_headers():
    emitted = []
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})
    async def capture(message):
        emitted.append(message)
    async def request():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    scope={'type':'http','method':'GET','path':'/','client':('127.0.0.1',12345),'headers':[]}
    asyncio.run(GuardMiddleware(app, limit=1000, testing=True, production=True)(scope, request, capture))
    headers=dict(emitted[0]['headers'])
    assert headers[b'x-content-type-options'] == b'nosniff'
    assert headers[b'x-frame-options'] == b'DENY'
    assert headers[b'referrer-policy'] == b'no-referrer'
    assert b'max-age=' in headers[b'strict-transport-security']
    assert b"frame-ancestors 'none'" in headers[b'content-security-policy']


def test_anon_cannot_access_saved_financial_records(env):
    client, _, _ = env
    assert client.get('/api/batches').status_code == 401
    assert client.get('/api/auth/me').status_code == 401
