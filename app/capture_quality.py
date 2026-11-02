"""Inspectable capture diagnostics. Automated signals are not human validation."""
import json
import re
import unicodedata
from datetime import date, timedelta

from bs4 import BeautifulSoup
from app.article_cleanup import VERSION as CLEANUP_VERSION, remove_publisher_promotions

VERSION = '2'

ERROR_ACTIONS = {
    'invalid_url': 'Use a complete public HTTP or HTTPS article URL.',
    'private_url': 'Use a public publisher URL; local and private addresses are blocked.',
    'dns_error': 'Check the publisher address and your network connection.',
    'robots_denied': 'This publisher does not permit fetching this URL.',
    'robots_unavailable': 'Publisher access rules could not be verified. Try again later.',
    'http_blocked': 'The publisher blocked access. Open the original source to check availability.',
    'http_unavailable': 'The publisher could not serve this page. Check its address or try again later.',
    'rate_limited': 'The publisher is rate limiting requests. Wait before trying again.',
    'network_error': 'Check the connection or try the publisher again later.',
    'timeout': 'The page exceeded the supported fetch budget. Try again later.',
    'response_too_large': 'This page exceeds the supported response size.',
    'redirect_error': 'Use the final public article URL directly.',
    'unsupported_content': 'Use an individual HTML article rather than a file or directory.',
    'access_restricted': 'A subscription, sign-in or access challenge prevents capture.',
    'incomplete_body': 'The readable body is too short. Check for an excerpt or missing content.',
    'not_article': 'Choose an individual article rather than a listing or navigation page.',
    'browser_unavailable': 'Install Chrome/Edge or Playwright Chromium, or choose HTML only.',
    'browser_failed': 'The browser could not capture readable public content.',
    'extraction_error': 'Check the original page; its layout may not be supported.',
    'pdf_failed': 'Check the PDF output directory and available disk space.',
    'unexpected_error': 'The item failed. Other items can continue; check the original source.',
}


def error_code(message):
    """Compatibility classifier; new policy errors can also declare an explicit code."""
    message = str(message).lower()
    rules = [
        ('private_url', r'private|non-public|local,.*network'),
        ('invalid_url', r'public http|credentials|invalid.*url|choose auto'),
        ('dns_error', r'cannot resolve'),
        ('robots_denied', r'robots.*disallows'),
        ('robots_unavailable', r'robots|crawl delay'),
        ('rate_limited', r'\b429\b'),
        ('http_blocked', r'\b40[13]\b'),
        ('access_restricted', r'subscription|sign-in|access challenge'),
        ('response_too_large', r'size limit|too large|exceeds.*mb|transfer limit'),
        ('timeout', r'time.*(?:budget|limit)|timed? ?out'),
        ('redirect_error', r'redirect'),
        ('unsupported_content', r'not an html|non-html'),
        ('browser_unavailable', r'install.*(?:playwright|requirements)|no supported browser'),
        ('incomplete_body', r'too short|no readable|80.*30,?000 words'),
        ('network_error', r'network error|connection|http.*error'),
        ('browser_failed', r'browser'),
    ]
    return next((code for code, pattern in rules if re.search(pattern, message)), 'extraction_error')


def failure_details(exc):
    code = getattr(exc, 'code', None) or (error_code(exc) if isinstance(exc, (ValueError, RuntimeError))
                                          or exc.__class__.__name__ in ('ExtractionError', 'IncompleteArticle')
                                          else 'unexpected_error')
    return {'code': code, 'message': str(exc)[:500], 'action': ERROR_ACTIONS.get(code, ERROR_ACTIONS['extraction_error'])}


def explicit_metadata(soup):
    """Read only bounded article metadata; never use JSON articleBody as text."""
    values, sources = {}, {}
    selectors = {
        'title': 'meta[property="og:title"],meta[name="twitter:title"]',
        'author': 'meta[name="author"],meta[name="parsely-author"],meta[name="citation_author"],meta[name="dc.creator"]',
        'published': 'meta[property="article:published_time"],meta[itemprop="datePublished"],meta[name="pubdate"],meta[name="citation_publication_date"]',
    }
    for field, selector in selectors.items():
        node = soup.select_one(selector)
        if node and node.get('content', '').strip():
            values[field], sources[field] = node['content'].strip()[:500], 'html_meta'
    article_types = {'Article', 'NewsArticle', 'BlogPosting', 'Report', 'ScholarlyArticle', 'AnalysisNewsArticle'}
    def walk(value, depth=0):
        if depth > 8:
            return
        if isinstance(value, list):
            for item in value[:100]:
                yield from walk(item, depth + 1)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if isinstance(types, list) and any(isinstance(kind, str) and kind.split('/')[-1] in article_types for kind in types):
                yield value
            for key in ('@graph', 'mainEntity', 'itemListElement'):
                if key in value:
                    yield from walk(value[key], depth + 1)
    for script in soup.select('script[type="application/ld+json"]')[:20]:
        raw = script.get_text()
        if len(raw) > 200_000:
            continue
        try:
            records = list(walk(json.loads(raw)))
        except (ValueError, RecursionError):
            continue
        for record in records[:10]:
            authors = record.get('author', [])
            authors = authors if isinstance(authors, list) else [authors]
            names = [item.get('name', '') if isinstance(item, dict) else item for item in authors[:10]]
            names = [name.strip() for name in names if isinstance(name, str) and name.strip() and not name.startswith(('http:', 'https:'))]
            candidates = {'title': record.get('headline'), 'author': ', '.join(names), 'published': record.get('datePublished')}
            for field, value in candidates.items():
                if field not in values and isinstance(value, str) and value.strip():
                    values[field], sources[field] = value.strip()[:500], 'article_jsonld'
    if 'published' in values:
        match = re.match(r'^\d{4}-\d{2}-\d{2}', values['published'])
        try:
            values['published'] = date.fromisoformat(match.group() if match else '').isoformat()
        except ValueError:
            values.pop('published'); sources.pop('published')
    return values, sources


def readable(text):
    text = re.sub(r'!?\[([^\]]*)\]\([^\n]*?\)', r'\1', text or '')
    return re.sub(r'https?://\S+', '', text)


def tokens(text):
    # Whitespace-only counts make a whole CJK article look like an excerpt.
    text = unicodedata.normalize('NFKC', readable(text)).casefold()
    return re.findall(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]|[^\W_\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]+', text)


def body_reference(soup):
    """DOM paragraphs are an observable reference, not independent ground truth."""
    root = soup.select_one('[itemprop="articleBody"]') or soup.find('article')
    kind = 'article'
    if root is None:
        root, kind = soup.select_one('main,[role="main"]'), 'main'
    if root is None:
        return {'kind': 'unavailable', 'paragraphs': []}
    copy = BeautifulSoup(str(root), 'html.parser')
    for node in copy.select('script,style,noscript,nav,footer,aside,form,button,[hidden],[aria-hidden="true"]'):
        node.decompose()
    paragraphs = []
    blocks = 'p,li,tr,pre,blockquote'
    for node in copy.select(blocks)[:2000]:
        # Count a paragraph inside a list/quote once. Lists and table rows are
        # reading content too; a paragraph-only reference falsely flags essays.
        if node.select_one(blocks):
            continue
        words = tokens(node.get_text(' ', strip=True))
        if len(words) >= 12:
            paragraphs.append(words)
    return {'kind': kind, 'paragraphs': paragraphs}


def inspect_capture(article, html=None):
    warnings = []
    def add(code, message, severity='warning'):
        warnings.append({'code': code, 'message': message, 'severity': severity})
    text_tokens = tokens(article.get('text', ''))
    if len(text_tokens) < 80:
        add('short_body', 'The reading copy contains fewer than 80 readable words or CJK characters.')
    if not article.get('author'):
        add('missing_author', 'The publisher did not provide a usable author name.', 'info')
    published = article.get('published', '')
    if not published:
        add('missing_publication_date', 'Publication date is unavailable. Date filters will exclude this article.')
    else:
        try:
            if date.fromisoformat(published[:10]) > date.today() + timedelta(days=1):
                add('future_publication_date', 'The extracted publication date is in the future; check the original.')
        except ValueError:
            add('invalid_publication_date', 'The publication date could not be interpreted reliably.')
    evidence = {'readable_units': len(text_tokens), 'reference_kind': 'unavailable'}
    replacement_count = (article.get('text') or '').count('\ufffd')
    if replacement_count:
        add('encoding_replacements', 'Some characters could not be decoded. Check the original for damaged text.',
            'warning' if replacement_count >= 3 else 'info')
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        removed = remove_publisher_promotions(soup, article.get('url', ''))
        evidence['cleanup'] = {'version': CLEANUP_VERSION, 'publisher_promotion_blocks_removed': removed}
        if not soup.title and not soup.find('h1'):
            add('missing_title', 'No page title or headline was found; the saved title may be a fallback.')
        reference = body_reference(soup)
        paragraphs = reference['paragraphs']
        reference_words = sum(len(words) for words in paragraphs)
        joined = ' ' + ' '.join(text_tokens) + ' '
        # Three spaced anchors tolerate link/formatting boundaries while checking
        # the beginning, middle and end of each substantial source paragraph.
        matched = []
        for words in paragraphs:
            anchors = [words[:5], words[len(words)//2:len(words)//2+5], words[-5:]]
            matched.append(sum((' ' + ' '.join(anchor) + ' ') in joined for anchor in anchors) >= 2)
        covered = sum(len(words) for words, found in zip(paragraphs, matched) if found)
        coverage = round(covered / reference_words, 3) if reference_words else None
        evidence.update(reference_kind=reference['kind'], reference_paragraphs=len(paragraphs),
                        matched_paragraphs=sum(matched), reference_units=reference_words, paragraph_coverage=coverage)
        if reference_words >= 200 and len(paragraphs) >= 3 and coverage < .65:
            add('possible_missing_content', 'Several substantial page paragraphs may be missing. Compare this copy with the original.')
        if reference_words >= 200 and len(text_tokens) > reference_words * 1.8:
            add('possible_extra_content', 'This copy is much longer than the detected article region; it may include unrelated text.')
    return {'version': VERSION, 'status': 'needs_review' if any(w['severity'] == 'warning' for w in warnings) else 'checks_passed',
            'warnings': warnings, 'evidence': evidence, 'reviewed': False}


def saved_quality(article):
    try:
        value = json.loads(article.get('quality_json') or '{}')
        if isinstance(value, dict) and value.get('version') == VERSION and value.get('status') in ('needs_review', 'checks_passed'):
            return value
    except (TypeError, ValueError):
        pass
    return {'status': 'not_checked', 'warnings': [], 'reviewed': False}
