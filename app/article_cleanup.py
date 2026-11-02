"""Conservative DOM cleanup for standalone publisher promotion blocks."""
import re
from urllib.parse import urljoin, urlsplit


VERSION = 'publisher-promotion-v1'
_HOME = re.compile(
    r'^(?:Go to|Visit)\s+.{1,120}?\s+for more\s+(?:[\w,&-]+\s+){0,8}news'
    r'(?:\s+from[^.!?]{1,180})?\.\s*', re.I)
_FOLLOW = re.compile(
    r'Follow us on\s+.{1,500}?\s+(?:or\s+)?subscribe to our\s+'
    r'(?:(?:weekly|daily|email|free)\s+)?newsletter\s+to ensure you\s+'
    r'(?:don[\'’]t|do not) miss out on any\s+future updates\.\s*'
    r'(?:Send tips to\s+[^\s@]+@[^\s@]+\.[a-z]{2,}\.?)?', re.I)
_SOCIAL = {'whatsapp.com', 't.me', 'telegram.me', 'twitter.com', 'x.com',
           'facebook.com', 'instagram.com', 'linkedin.com'}
_STRUCTURE = ['p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
              'ul', 'ol', 'table', 'blockquote', 'pre', 'code', 'q', 'figure', 'img']


def _host(url):
    try:
        return (urlsplit(url).hostname or '').lower().removeprefix('www.')
    except ValueError:
        return ''


def remove_publisher_promotions(soup, page_url):
    """Remove complete CTA-only blocks, preserving quotations and article structure.

    Match a narrow publisher-home/news + social/newsletter template. Individual
    social links, words like "subscribe", and mixed editorial blocks do not qualify.
    The caller retains the original document for capture diagnostics/provenance.
    """
    removed = 0
    publisher = _host(page_url)
    for node in soup.find_all(['p', 'div', 'section']):
        if (not node.name or node.find(_STRUCTURE)
                or node.find_parent(['blockquote', 'pre', 'code', 'q'])):
            continue
        text = ' '.join(node.get_text(' ', strip=True).split())
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        if len(text) > 1200:
            continue
        links = []
        for anchor in node.find_all('a', href=True):
            try:
                link = urlsplit(urljoin(page_url, anchor['href']))
            except ValueError:
                continue
            if link.scheme in ('http', 'https'):
                links.append((_host(link.geturl()), link.path, anchor.get_text(' ', strip=True)))
        home = _HOME.match(text)
        if home:
            own_home = publisher and any(host == publisher and path in ('', '/') for host, path, _ in links)
            if not own_home:
                continue
            remainder = text[home.end():]
        else:
            remainder = text
        if remainder:
            social = {host for host, _, _ in links} & _SOCIAL
            newsletter = any(re.search(r'\b(?:subscribe|newsletter)\b', label, re.I)
                             for _, _, label in links)
            if not (_FOLLOW.fullmatch(remainder) and len(social) >= 2 and newsletter):
                continue
        elif not home:
            continue
        node.decompose()
        removed += 1
    return removed
