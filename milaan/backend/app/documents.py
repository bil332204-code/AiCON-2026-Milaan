"""Public document metadata uses configuration, never request headers or query data."""
from html import escape
from pathlib import Path
import json
import re
from fastapi.responses import HTMLResponse

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend/dist'
PUBLIC_PAGES = {
    '/': ('index.html', 'Milaan · Check Easypaisa, JazzCash & Bank Payment Screenshots'),
    '/guide': ('index.html', 'Seller guide · Milaan'),
    '/privacy': ('privacy.html', 'Privacy Policy · Milaan'),
    '/terms': ('terms.html', 'Terms & Conditions · Milaan'),
    '/about': ('about.html', 'About & Contact · Milaan'),
    '/fake-payment-screenshot': ('fake-payment-screenshot.html',
                                 'How to Spot a Fake Easypaisa or JazzCash Screenshot · Milaan'),
    '/transaction-id': ('transaction-id.html', 'What Is a Transaction ID in Easypaisa & JazzCash? · Milaan'),
}


def structured_data(origin):
    """schema.org data for the home page so Google can show the brand name and app details."""
    base = origin.rstrip('/')
    data = {
        '@context': 'https://schema.org',
        '@graph': [
            {'@type': 'Organization', '@id': base + '/#organization', 'name': 'Milaan', 'url': base + '/',
             'logo': base + '/share-card.png', 'description': 'Payment screenshot checks for online sellers in Pakistan.'},
            {'@type': 'WebSite', '@id': base + '/#website', 'name': 'Milaan', 'alternateName': 'milaan.app',
             'url': base + '/', 'inLanguage': 'en', 'publisher': {'@id': base + '/#organization'}},
            {'@type': 'SoftwareApplication', 'name': 'Milaan', 'url': base + '/',
             'applicationCategory': 'BusinessApplication', 'operatingSystem': 'Web browser',
             'description': ('Checks customer payment screenshots from Easypaisa, JazzCash and banks against '
                             'the seller\'s statement and marks each order SHIP, HOLD or REVIEW.'),
             'areaServed': 'PK',
             'publisher': {'@id': base + '/#organization'}},
        ],
    }
    # Escape "<" so the JSON can never close the script element early.
    return json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')


def public_document(path, origin, registration_open=True):
    filename, title = PUBLIC_PAGES[path]
    content = (FRONTEND / filename).read_text(encoding='utf-8')
    description = re.search(r'<meta name="description" content="([^"]*)">', content).group(1)
    if path == '/guide':
        description = ('How to check customer payment screenshots against your bank or wallet '
                       'statement with Milaan. Guide in English and Roman Urdu.')
        content = re.sub(r'<meta name="description" content="[^"]*">',
                         lambda _: f'<meta name="description" content="{escape(description, quote=True)}">', content)
    content = re.sub(r'<title>.*?</title>', lambda _: f'<title>{escape(title)}</title>', content)
    content = re.sub(r'<link rel="canonical"[^>]*>\s*', '', content)
    url = escape(origin.rstrip('/') + path, quote=True)
    metadata = (f'<link rel="canonical" href="{url}">\n'
                f'<meta property="og:url" content="{url}">\n'
                f'<meta property="og:title" content="{escape(title, quote=True)}">\n'
                f'<meta property="og:description" content="{description}">\n'
                '<meta property="og:type" content="website">\n'
                '<meta property="og:site_name" content="Milaan">\n'
                '<meta property="og:locale" content="en_PK">\n'
                f'<meta property="og:image" content="{escape(origin.rstrip("/") + "/share-card.png",quote=True)}">\n'
                '<meta property="og:image:type" content="image/png">\n'
                '<meta property="og:image:width" content="1200">\n'
                '<meta property="og:image:height" content="630">\n'
                '<meta name="twitter:card" content="summary_large_image">\n'
                f'<meta name="twitter:title" content="{escape(title,quote=True)}">\n'
                f'<meta name="twitter:description" content="{escape(description,quote=True)}">\n'
                f'<meta name="twitter:image" content="{escape(origin.rstrip("/") + "/share-card.png",quote=True)}">\n')
    if path == '/':
        metadata += '<script type="application/ld+json">' + structured_data(origin) + '</script>\n'
    metadata += '<meta name="milaan-registration-state" content="' + ('open' if registration_open else 'closed') + '">\n'
    return HTMLResponse(content.replace('</head>', metadata + '</head>', 1))

def app_shell(registration_open=True):
    """Account-shell state comes from the server, including direct /signup links."""
    content = (FRONTEND / 'index.html').read_text(encoding='utf-8')
    state = 'open' if registration_open else 'closed'
    return HTMLResponse(content.replace('</head>',
                        f'<meta name="milaan-registration-state" content="{state}">\n</head>', 1))
