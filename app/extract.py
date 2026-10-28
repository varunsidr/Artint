"""Fetch user-supplied PUBLIC HTTP(S) article URLs and extract readable content."""
import hashlib
import ipaddress
import json
import re
import socket
import time
import threading
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
import trafilatura
from bs4 import BeautifulSoup, UnicodeDammit
from app.capture_quality import error_code, explicit_metadata, inspect_capture, tokens

UA = "ArticleIntelligenceStarter/0.1 (+local educational research)"
MAX_HTML_BYTES = 5_000_000
MAX_ROBOTS_BYTES = 256_000
FETCH_MODES = {'auto': 'Auto', 'html': 'HTML only'}
FETCH_HELP = 'Auto tries normal extraction first, then a headless browser for public pages that need JavaScript. HTML only skips the browser.'
_ROBOTS_CACHE = {}
_ROBOTS_LOCK = threading.Lock()
_RATE_LOCK = threading.Lock()
_NEXT_REQUEST = {}

class ExtractionError(Exception):
    def __init__(self, message, *, code=None):
        super().__init__(message)
        self.code = code or error_code(message)


class IncompleteArticle(ExtractionError):
    """A successful HTML response did not contain a usable article body."""


def access_gate(html):
    """Conservative gate detection; rendering must not turn a block into a retry."""
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script', type='application/ld+json'):
        if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', script.get_text(), re.I):
            return 'Publisher marks this content as subscription-only.'
    text = soup.get_text(' ', strip=True)
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if (re.search(r'^captcha\s*$|access denied|^just a moment[.!\s]*$|verify (?:that )?you are human', title, re.I)
            or re.search(r'cf-chl-|/cdn-cgi/challenge-platform', html, re.I)
            or (len(text.split()) < 80 and re.search(r'g-recaptcha|h-captcha|verify (?:that )?you are human', html, re.I))):
        return 'Publisher presented an access challenge.'
    if len(text.split()) < 300 and re.search(
            r'subscribe to (?:continue|read|unlock)|sign in to (?:continue|read)|log in to (?:continue|read)|'
            r'you (?:have|’ve|\'ve) reached (?:your|the) (?:free )?(?:article|reading) limit', text, re.I):
        return 'Publisher requires a subscription or sign-in to read this article.'
    return None


def needs_javascript(html):
    soup = BeautifulSoup(html, 'html.parser')
    return bool(soup.find('script') and (
        soup.select_one('#root,#app,#__next,#__nuxt,[data-reactroot],[ng-app]')
        or re.search(r'enable javascript|requires javascript|loading (?:article|content)', soup.get_text(' ', strip=True), re.I)
        or len(soup.get_text(' ', strip=True).split()) < 80))

def validate_public_url(url):
    try:
        u = urlparse(url.strip())
        port = u.port
    except ValueError as exc:
        raise ExtractionError('Provide a valid public HTTP(S) URL and port.', code='invalid_url') from exc
    if u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password:
        raise ExtractionError("Provide a public http(s) URL without embedded credentials")
    try:
        addresses = socket.getaddrinfo(u.hostname, port or (443 if u.scheme == 'https' else 80))
    except socket.gaierror as exc:
        raise ExtractionError(f"Cannot resolve host: {exc}") from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ExtractionError("Local, private, or non-public network URLs are blocked")
    return u

def _rate_limit(url, interval=1.0):
    host = urlparse(url).netloc.lower()
    with _RATE_LOCK:
        now = time.monotonic()
        ready = max(now, _NEXT_REQUEST.get(host, now))
        _NEXT_REQUEST[host] = ready + interval
    if ready > now:
        time.sleep(ready - now)


def _robots(root):
    with _ROBOTS_LOCK:
        cached = _ROBOTS_CACHE.get(root)
        if cached and time.monotonic() - cached[0] < 600:
            return cached[1]
    body, _, status = _bounded_resource(root + '/robots.txt', MAX_ROBOTS_BYTES, robots=True)
    policy = RobotFileParser()
    if status in (404, 410):
        policy.allow_all = True
    elif status in (401, 403):
        policy.disallow_all = True
    else:
        if body.lstrip().lower().startswith(('<!doctype html', '<html')):
            raise ExtractionError('Cannot verify robots.txt: server returned an HTML page')
        policy.parse(body.splitlines())
    with _ROBOTS_LOCK:
        if len(_ROBOTS_CACHE) >= 256:
            _ROBOTS_CACHE.pop(next(iter(_ROBOTS_CACHE)))
        _ROBOTS_CACHE[root] = (time.monotonic(), policy)
    return policy


def _bounded_resource(url, max_bytes, robots=False):
    """Bound and validate robots traffic as well as every article redirect."""
    started = time.monotonic()
    for _ in range(5):
        parsed = validate_public_url(url)
        interval = 1.0
        if not robots:
            policy = _robots(f'{parsed.scheme}://{parsed.netloc}')
            if not policy.can_fetch(UA, url):
                raise ExtractionError('robots.txt disallows fetching this URL')
            rate = policy.request_rate(UA)
            interval = max(1.0, policy.crawl_delay(UA) or 0, rate.seconds / rate.requests if rate else 0)
            if interval > 30:
                raise ExtractionError('Publisher crawl delay exceeds the supported interactive fetch budget')
        _rate_limit(url, interval)
        try:
            with requests.get(url, headers={'User-Agent': UA, 'Accept': 'text/plain' if robots else 'text/html'},
                              timeout=(5, 12), stream=True, allow_redirects=False) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    dest = r.headers.get('Location')
                    if not dest:
                        raise ExtractionError('Redirect missing Location')
                    url = urljoin(url, dest)
                    continue
                if robots and r.status_code in (401, 403, 404, 410):
                    return '', url, r.status_code
                r.raise_for_status()
                typ = r.headers.get('Content-Type', '').lower()
                if not robots and 'text/html' not in typ and 'application/xhtml+xml' not in typ:
                    raise ExtractionError(f"Not an HTML article ({typ or 'unknown content type'})")
                chunks, total = [], 0
                for chunk in r.iter_content(64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ExtractionError('robots.txt exceeds 256 KB size limit' if robots else 'HTML exceeds 5 MB size limit')
                    if time.monotonic() - started > 45:
                        raise ExtractionError('Response exceeded the total fetch time budget')
                    chunks.append(chunk)
                encoding = [r.encoding] if 'charset=' in typ and r.encoding else None
                decoded = UnicodeDammit(b''.join(chunks), known_definite_encodings=encoding,
                                       is_html=not robots).unicode_markup
                return decoded or '', url, r.status_code
        except requests.RequestException as exc:
            status = exc.response.status_code if getattr(exc, 'response', None) is not None else None
            code = ('rate_limited' if status == 429 else 'http_blocked' if status in (401, 403)
                    else 'http_unavailable' if status else 'timeout' if isinstance(exc, requests.Timeout) else 'network_error')
            raise ExtractionError(f"Network error: {exc}", code=code) from exc
    raise ExtractionError('Too many redirects')


def _request_html(url):
    body, final_url, _ = _bounded_resource(url, MAX_HTML_BYTES)
    return body, final_url

def _article_from_html(html, final_url, fetch_method='html'):
    data = trafilatura.extract(html, url=final_url, output_format='json', with_metadata=True,
                               include_links=True, include_images=True, include_tables=True, include_comments=False)
    if not data:
        raise IncompleteArticle('No readable article body could be extracted.')
    info = json.loads(data)
    content = (info.get('text') or '').strip()
    if len(tokens(content)) < 80:
        raise IncompleteArticle('Extracted text is too short: fewer than 80 readable words or CJK characters. Check the original for an excerpt.')
    soup = BeautifulSoup(html, 'html.parser')
    metadata, metadata_sources = explicit_metadata(soup)
    # Published metadata takes precedence over a heuristic date that may come
    # from an update timestamp or a neighbouring story. Other fields fill gaps.
    for field, key in (('title', 'title'), ('author', 'author'), ('published', 'date')):
        if metadata.get(field) and (not info.get(key) or field == 'published'):
            info[key] = metadata[field]
        elif info.get(key):
            metadata_sources[field] = 'extractor'
    links = sorted({urljoin(final_url, a['href']) for a in soup.select('article a[href]')
                    if a.get('href') and urlparse(urljoin(final_url, a['href'])).scheme in ('http','https')})[:200]
    images = sorted({urljoin(final_url, tag['src']) for tag in soup.select('article img[src]')
                     if tag.get('src') and urlparse(urljoin(final_url, tag['src'])).scheme in ('http','https')})[:100]
    domain = urlparse(final_url).hostname or 'unknown'
    article = dict(id=hashlib.sha256(final_url.encode()).hexdigest()[:16], url=final_url,
        title=info.get('title') or (soup.title.get_text(' ', strip=True) if soup.title else domain),
        source=info.get('sitename') or domain,
        author=info.get('author') or '', published=info.get('date') or '',
        fetched_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), text=content,
        word_count=len(tokens(content)), links_json=json.dumps(links),
        images_json=json.dumps(images), pdf_path='', fetch_method=fetch_method)
    quality = inspect_capture(article, html)
    # When the generic extractor adds substantial text outside one explicit
    # article, compare a scoped extraction. Keep it only if source-paragraph
    # coverage is retained. Do not switch to precision mode on every page.
    if any(w['code'] == 'possible_extra_content' for w in quality['warnings']):
        regions = soup.select('[itemprop="articleBody"]') or soup.select('article')
        if len(regions) == 1:
            scoped = '<html>' + (str(soup.head) if soup.head else '') + '<body>' + str(regions[0]) + '</body></html>'
            alternate = trafilatura.extract(scoped, url=final_url, output_format='json',
                                            include_links=True, include_images=True, include_tables=True,
                                            include_comments=False, favor_precision=True)
            if alternate:
                alternative_text = (json.loads(alternate).get('text') or '').strip()
                candidate = dict(article, text=alternative_text, word_count=len(tokens(alternative_text)))
                candidate_quality = inspect_capture(candidate, html)
                old_coverage = quality['evidence'].get('paragraph_coverage') or 0
                new_coverage = candidate_quality['evidence'].get('paragraph_coverage') or 0
                if (80 <= candidate['word_count'] < article['word_count'] / 1.5
                        and new_coverage >= max(.85, old_coverage - .02)):
                    article, quality = candidate, candidate_quality
                    metadata_sources['body'] = 'article_region'
    quality['metadata_sources'] = metadata_sources
    article['quality_json'] = json.dumps(quality, ensure_ascii=False)
    return article


def extract_article(url, *, mode='auto'):
    if mode not in FETCH_MODES:
        raise ExtractionError('Choose Auto or HTML-only extraction.')
    html, final_url = _request_html(url.strip())
    return extract_document(html, final_url, mode=mode)


def extract_document(html, final_url, *, mode='html'):
    """Parse an already policy-checked response; HTML mode supports offline replay."""
    if mode not in ('auto', 'html'):
        raise ExtractionError('Choose Auto or HTML-only extraction.')
    # Network failures, robots denials, HTTP blocks and size limits propagate;
    # none of them is a reason to start a browser.
    gate = access_gate(html)
    if gate:
        raise ExtractionError(gate)
    article, incomplete = None, None
    try:
        article = _article_from_html(html, final_url)
    except IncompleteArticle as exc:
        incomplete = exc
    use_browser = mode == 'auto' and needs_javascript(html) and (article is None or article['word_count'] < 80)
    if use_browser:
        from app.browser_render import render_article_html
        rendered, rendered_url = render_article_html(final_url, html)
        gate = access_gate(rendered)
        if gate:
            raise ExtractionError(gate)
        return _article_from_html(rendered, rendered_url, 'browser')
    if article is not None:
        return article
    raise incomplete
