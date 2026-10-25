"""Public document metadata uses configuration, never request headers or query data."""
from html import escape
from pathlib import Path
import re
from fastapi.responses import HTMLResponse

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend/dist'
PUBLIC_PAGES = {
    '/': ('index.html', 'Milaan — Every payment, in its place.'),
    '/guide': ('index.html', 'Seller guide · Milaan'),
    '/privacy': ('privacy.html', 'Privacy Policy · Milaan'),
    '/terms': ('terms.html', 'Terms & Conditions · Milaan'),
    '/about': ('about.html', 'About & Contact · Milaan'),
}


def public_document(path, origin, registration_open=True):
    filename, title = PUBLIC_PAGES[path]
    content = (FRONTEND / filename).read_text(encoding='utf-8')
    description = re.search(r'<meta name="description" content="([^"]*)">', content).group(1)
    if path == '/guide':
        description = ('Learn to compare orders, payment screenshots and statements with '
                       'Milaan. Seller instructions in English and Roman Urdu.')
        content = re.sub(r'<meta name="description" content="[^"]*">',
                         lambda _: f'<meta name="description" content="{escape(description, quote=True)}">', content)
    content = re.sub(r'<title>.*?</title>', lambda _: f'<title>{escape(title)}</title>', content)
    content = re.sub(r'<link rel="canonical"[^>]*>\s*', '', content)
    url = escape(origin.rstrip('/') + path, quote=True)
    metadata = (f'<link rel="canonical" href="{url}">\n'
                f'<meta property="og:url" content="{url}">\n'
                f'<meta property="og:title" content="{escape(title, quote=True)}">\n'
                f'<meta property="og:description" content="{description}">\n'
                '<meta property="og:type" content="website">\n')
    metadata += '<meta name="milaan-registration-state" content="' + ('open' if registration_open else 'closed') + '">
'
    return HTMLResponse(content.replace('</head>', metadata + '</head>', 1))
