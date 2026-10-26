"""Public seller-facing trust content; does not touch private financial records."""
import pytest
from app.parsing import csv_export


@pytest.mark.parametrize("route,title", [
    ("/privacy","Privacy Policy"),
    ("/terms","Terms & Conditions"),
    ("/about","About & Contact"),
])
def test_legal_pages_are_public_and_reachable_without_login(env,route,title):
    client,_,_=env
    response=client.get(route)
    assert response.status_code==200
    assert 'text/html' in response.headers['content-type']
    from html import escape
    assert f'<title>{escape(title)} · Milaan</title>' in response.text
    assert f'<link rel="canonical" href="{env[2].public_origin}{route}">' in response.text
    assert 'Draft for' in response.text
    assert 'Bilal Ahmed' in response.text and 'Pakistan' in response.text
    assert 'not yet a registered company' in response.text
    assert 'not configured yet' in response.text
    assert 'mailto:' not in response.text
    assert 'no-reply@milaan.app' not in response.text
    for path in ['/guide','/privacy','/terms','/about']:
        assert f'href="{path}"' in response.text
    assert '<script' not in response.text


def test_home_and_guide_include_reference_explanation_and_bilingual_steps(env):
    client,_,_=env
    for route in ['/', '/guide']:
        response=client.get(route)
        assert response.status_code==200
        assert 'Transaction ID' in response.text
        assert 'Order number' in response.text
        assert 'Transaction ID / Reference number' not in response.text
        assert 'Milaan does not generate it' in response.text
        assert 'lang="ur-Latn"' in response.text
        assert 'data-guide-language="en"' in response.text
        assert 'data-guide-language="ur"' in response.text
        assert 'backend configuration' not in response.text.lower()
        assert 'configuring the backend' not in response.text.lower()
        assert 'MLN is fictional demo data' in response.text
        for path in ['/privacy','/terms','/about']:
            assert f'href="{path}"' in response.text


@pytest.mark.parametrize("prefix",['=', '+','-', '@','\t','\r',' \t='])
def test_export_neutralizes_formula_prefixes(prefix):
    dangerous=prefix+'42'
    text=csv_export(['customer_name'],[[dangerous]])
    import csv,io
    data=list(csv.reader(io.StringIO(text)))
    assert data[1][0]=="'"+dangerous


def test_privacy_discloses_source_documented_retention_and_processors(env):
    response=env[0].get('/privacy')
    assert response.status_code==200
    text=response.text
    for required in ['168 hours (seven days)','private receipt files','original EXIF metadata',
                     'Google\'s Gemini','external OCR engine','Resend HTTPS API',
                     'account verification and password recovery emails only',
                     'not configured yet','backups']:
        assert required in text, required
    assert 'guaranteed instant deletion' not in text.lower()


@pytest.mark.parametrize('route', ['/', '/guide', '/privacy', '/terms', '/about'])
def test_public_metadata_uses_configured_origin_not_request_or_query(env, route):
    client, _, settings = env
    settings.app_env = 'production'
    settings.public_origin = 'https://staging.example.com'
    response = client.get(settings.public_origin + route + '?token=do-not-index',
                          headers={'X-Forwarded-Host': 'untrusted.example.com'})
    assert response.status_code == 200
    url = settings.public_origin + route
    assert f'<link rel="canonical" href="{url}">' in response.text
    assert f'<meta property="og:url" content="{url}">' in response.text
    assert response.headers['link'] == f'<{url}>; rel="canonical"'
    assert 'do-not-index' not in response.text
    assert 'untrusted.example.com' not in response.text
    if route == '/guide':
        assert '<title>Seller guide · Milaan</title>' in response.text
        assert 'Seller instructions in English and Roman Urdu.' in response.text


@pytest.mark.parametrize('alias,route', [('/index.html','/'), ('/privacy.html','/privacy'),
                                        ('/terms.html','/terms'), ('/about.html','/about')])
def test_static_document_aliases_cannot_bypass_canonical_host(env, alias, route):
    client, _, settings = env
    settings.app_env = 'production'
    settings.public_origin = 'https://staging.example.com'
    query = '?next=%2Fguide'
    response = client.get('https://alias.example.com' + alias + query, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == settings.public_origin + route + query
    local = client.get(settings.public_origin + alias + query, follow_redirects=False)
    assert local.status_code == 307 and local.headers['location'] == route + query


@pytest.mark.parametrize('route', ['/', '/guide', '/privacy', '/terms', '/about', '/login'])
def test_public_document_head_requests_keep_security_and_canonical_headers(env, route):
    client, _, settings = env
    settings.app_env = 'production'
    settings.public_origin = 'https://milaan.example.com'
    response = client.head(settings.public_origin + route)
    assert response.status_code == 200 and response.content == b''
    assert response.headers['link'] == f'<{settings.public_origin}{route}>; rel="canonical"'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert 'no-store' in response.headers['cache-control']
    assert client.head(settings.public_origin + '/workspace', follow_redirects=False).status_code == 303

def test_registration_gate_is_publicly_honest_without_opening_signup(env):
    client, _, settings = env
    settings.registration_open = False
    response = client.get("/")
    assert response.status_code == 200
    assert '<meta name="milaan-registration-state" content="closed">' in response.text
    settings.registration_open = True
    assert '<meta name="milaan-registration-state" content="open">' in client.get("/").text

def test_public_guide_links_downloadable_synthetic_csvs(env):
    client,_,_=env
    guide=client.get("/guide")
    assert "Statement CSV help" in guide.text
    assert "Statement CSV ka tareeqa" in guide.text
    for path, expected in [("/samples/orders.csv","order_ref"),("/samples/statement.csv","transaction_id")]:
        response=client.get(path)
        assert response.status_code == 200
        assert expected in response.text

def test_legal_roman_urdu_summary_is_clearly_non_authoritative(env):
    client,_,_=env
    for path in ["/privacy","/terms","/about"]:
        page=client.get(path).text
        assert 'lang="ur-Latn"' in page and "sirf khulasa" in page
        assert "English draft" in page

def test_social_metadata_sitemap_and_helpful_missing_route(env):
    client,_,settings=env
    for route in ["/","/guide","/privacy","/terms","/about"]:
        page=client.get(route)
        assert page.status_code==200
        assert 'property="og:image"' in page.text
        assert 'name="twitter:card" content="summary_large_image"' in page.text
        assert f'{settings.public_origin}/share-card.png' in page.text
    for target, text in [("/share-card.png",None),("/robots.txt","Sitemap:"),("/sitemap.xml","<urlset")]:
        response=client.get(target)
        assert response.status_code==200
        if text is not None: assert text in response.text
    unknown=client.get("/not-a-real-page", follow_redirects=False)
    assert unknown.status_code==404
    assert 'Page not found' in unknown.text

def test_social_raster_is_valid_1200_by_630(env):
    from io import BytesIO
    from PIL import Image
    response=env[0].get('/share-card.png')
    assert response.status_code==200
    assert response.headers['content-type'].startswith('image/png')
    with Image.open(BytesIO(response.content)) as picture:
        assert picture.size == (1200,630)
        picture.verify()
