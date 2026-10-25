"""Public seller-facing trust content; does not touch private financial records."""
import pytest
from app.parsing import csv_export


@pytest.mark.parametrize("route,title", [
    ("/privacy","Privacy"),
    ("/terms","Terms of Use"),
    ("/about","About & Contact"),
])
def test_legal_pages_are_public_and_reachable_without_login(env,route,title):
    client,_,_=env
    response=client.get(route)
    assert response.status_code==200
    assert 'text/html' in response.headers['content-type']
    from html import escape
    assert f'<title>{escape(title)} · Milaan</title>' in response.text
    assert f'<link rel="canonical" href="https://milaan.app{route}">' in response.text
    assert 'BRACKETED' in response.text or '[LEGAL ENTITY]' in response.text
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
                     '[SUPPORT EMAIL]','[BACKUP RETENTION]']:
        assert required in text, required
    assert 'guaranteed instant deletion' not in text.lower()
