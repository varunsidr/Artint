"""Bounded personal news discovery using the public Bing News RSS feed.

Search responses are previews, never substitutes for extracted article text.
The provider is isolated here so a licensed search API can replace it later.
"""
import hashlib
import ipaddress
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from app.extract import UA

ENDPOINT = 'https://www.bing.com/news/search'
MAX_RESPONSE_BYTES = 2_000_000
MAX_PAGES = 20
SEARCH_BUDGET_SECONDS = 60
PUBLISHERS = {
    'The Guardian': 'theguardian.com', 'The Hindu': 'thehindu.com', 'BBC': 'bbc.com',
    'BBC UK': 'bbc.co.uk', 'Reuters': 'reuters.com', 'Associated Press': 'apnews.com',
    'Al Jazeera': 'aljazeera.com', 'The Indian Express': 'indianexpress.com',
    'Hindustan Times': 'hindustantimes.com', 'The New York Times': 'nytimes.com',
    'The Washington Post': 'washingtonpost.com', 'Financial Times': 'ft.com',
    'TechCrunch': 'techcrunch.com', 'Wired': 'wired.com', 'Nature': 'nature.com',
}
LANGUAGES = {'English': 'en', 'Hindi': 'hi', 'Tamil': 'ta', 'Telugu': 'te', 'Bengali': 'bn',
             'Marathi': 'mr', 'Malayalam': 'ml', 'Kannada': 'kn', 'Gujarati': 'gu',
             'French': 'fr', 'German': 'de', 'Spanish': 'es', 'Portuguese': 'pt',
             'Arabic': 'ar', 'Japanese': 'ja', 'Korean': 'ko', 'Chinese': 'zh-hans'}
_RATE_LOCK = threading.Lock()
_NEXT_REQUEST = 0.0


class DiscoveryError(Exception):
    pass


def phrases(raw, *, limit=8, length=70):
    values = [re.sub(r'\s+', ' ', value).strip() for value in re.split(r'[,;\n]+', raw or '')]
    values = list(dict.fromkeys(value for value in values if value))
    if len(values) > limit or any(len(value) > length for value in values):
        raise DiscoveryError(f'Use up to {limit} phrases, each at most {length} characters.')
    return values


def normalize_domain(value):
    value = value.strip().lower().removeprefix('www.').rstrip('.')
    if (not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', value)
            or value.endswith(('.local', '.localhost', '.internal', '.test', '.example'))):
        raise DiscoveryError('Use a public publisher domain such as thehindu.com, without a URL or path.')
    return value


def normalized_url(value):
    """Validate display URLs without making a request to each result's host."""
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or '').lower().rstrip('.')
        if parsed.scheme not in ('https', 'http') or parsed.username or parsed.password or not host:
            return None
        if parsed.port not in (None, 80, 443) or '.' not in host or host.endswith(('.local', '.localhost', '.internal')):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
                 if not key.lower().startswith(('utm_', 'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'msockid'))]
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or '/', urlencode(query), ''))
    except (ValueError, AttributeError):
        return None


@dataclass(frozen=True)
class SearchSpec:
    topics: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    keyword_mode: str = 'Highlight only'
    domains: tuple[str, ...] = ()
    language: str = 'English'
    start: date | None = None
    end: date | None = None
    target: int = 25
    sort: str = 'Best match'

    def validate(self):
        if not self.topics or len(self.topics) > 5 or any(not re.search(r'\w', item) or len(item) > 120 for item in self.topics):
            raise DiscoveryError('Enter one to five topics, separated by commas (up to 120 characters each).')
        if not isinstance(self.target, int) or isinstance(self.target, bool) or not 1 <= self.target <= 100:
            raise DiscoveryError('Choose between 1 and 100 results.')
        if self.language not in LANGUAGES or self.sort not in ('Best match', 'Newest first'):
            raise DiscoveryError('Choose a supported language and sort order.')
        if self.keyword_mode not in ('Highlight only', 'Match any', 'Match all') or len(self.keywords) > 8:
            raise DiscoveryError('Choose a supported keyword mode and up to eight keywords.')
        if any(not word.strip() or len(word) > 70 for word in self.keywords):
            raise DiscoveryError('Each priority keyword must contain 1–70 characters.')
        if len(self.domains) > 8:
            raise DiscoveryError('Choose up to eight publisher domains.')
        for domain in self.domains:
            normalize_domain(domain)
        if self.start and self.end and self.start > self.end:
            raise DiscoveryError('The start date must be on or before the end date.')
        if self.end and self.end > date.today():
            raise DiscoveryError('The end date cannot be in the future.')
        if self.start and self.start > date.today():
            raise DiscoveryError('The start date cannot be in the future.')


def _quote(value):
    # Topic text cannot inject provider operators; filters are built separately.
    cleaned = re.sub(r'[^\w\s\-’\']', ' ', value, flags=re.UNICODE)
    return '"' + re.sub(r'\s+', ' ', cleaned).strip() + '"'


def provider_query(spec):
    spec.validate()
    topics = [_quote(value) for value in spec.topics]
    query = '(' + ' OR '.join(topics) + ')' if len(topics) > 1 else topics[0]
    if spec.keywords and spec.keyword_mode != 'Highlight only':
        operator = ' OR ' if spec.keyword_mode == 'Match any' else ' AND '
        query += ' (' + operator.join(_quote(word) for word in spec.keywords) + ')'
    if spec.domains:
        query += ' (' + ' OR '.join('site:' + normalize_domain(domain) for domain in spec.domains) + ')'
    query += ' language:' + LANGUAGES[spec.language]
    if len(query) > 900:
        raise DiscoveryError('This search is too long. Use fewer topics, keywords, or publishers.')
    return query


def _plain(value):
    return re.sub(r'\s+', ' ', BeautifulSoup(value or '', 'html.parser').get_text(' ', strip=True)).strip()


def _keyword_pattern(words):
    parts = []
    for word in sorted(set(words), key=len, reverse=True):
        if word:
            parts.append((r'(?<!\w)' if re.match(r'\w', word[0]) else '') + re.escape(word)
                         + (r'(?!\w)' if re.match(r'\w', word[-1]) else ''))
    return re.compile('|'.join(parts), re.I) if parts else None


def parse_feed(body):
    if len(body) > MAX_RESPONSE_BYTES or re.search(br'<!\s*(DOCTYPE|ENTITY)\b', body, re.I):
        raise DiscoveryError('The news source returned an unsupported feed.')
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise DiscoveryError('The news source did not return a readable RSS feed. Try again later.') from exc
    if root.tag != 'rss' or root.find('channel') is None:
        raise DiscoveryError('The news source returned a page instead of RSS. No results were imported.')
    rows = []
    for item in root.findall('./channel/item')[:100]:
        link = item.findtext('link', '')
        try:
            parsed = urlsplit(link)
        except ValueError:
            continue
        if (parsed.hostname or '').lower() in ('www.bing.com', 'bing.com'):
            # Bing RSS exposes the publisher destination in the link's URL
            # parameter. Unwrap it locally; do not fetch a redirecting wrapper.
            link = parse_qs(parsed.query).get('url', [''])[0]
        url = normalized_url(link)
        title = _plain(item.findtext('title', ''))[:500]
        if not url or not title or re.search(r'\.(pdf|zip|mp4)(?:[?#]|$)', url, re.I):
            continue
        published = ''
        try:
            timestamp = parsedate_to_datetime(item.findtext('pubDate', ''))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            published = timestamp.astimezone().isoformat(timespec='seconds')
        except (ValueError, TypeError, OverflowError):
            pass
        source = next((_plain(child.text or '') for child in item if child.tag.rsplit('}', 1)[-1].lower() == 'source'), '')
        rows.append(dict(id=hashlib.sha256(url.encode()).hexdigest()[:16], url=url, title=title,
                         domain=(urlsplit(url).hostname or '').removeprefix('www.'),
                         source=source[:150], published=published, snippet=_plain(item.findtext('description', ''))[:1000]))
    return rows


def _fetch_page(params):
    global _NEXT_REQUEST
    with _RATE_LOCK:
        now = time.monotonic()
        ready = max(now, _NEXT_REQUEST)
        _NEXT_REQUEST = ready + 1.0
    if ready > now:
        time.sleep(ready - now)
    try:
        with requests.get(ENDPOINT, params=params, headers={'User-Agent': UA, 'Accept': 'application/rss+xml,application/xml'},
                          timeout=(5, 15), stream=True, allow_redirects=False) as response:
            if response.status_code == 429:
                raise DiscoveryError('The free news source is rate limited. Wait a minute before searching again.')
            if response.status_code in (401, 403):
                raise DiscoveryError('The free news source is blocking requests from this network. Try again later.')
            if response.status_code != 200:
                raise DiscoveryError(f'The free news source is unavailable (HTTP {response.status_code}). Try again later.')
            chunks, size, started = [], 0, time.monotonic()
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES or time.monotonic() - started > 25:
                    raise DiscoveryError('The search response exceeded its size or time limit.')
                chunks.append(chunk)
            return parse_feed(b''.join(chunks))
    except requests.RequestException as exc:
        # No provider URL/query exception text in the product or logs.
        raise DiscoveryError('The free news source could not be reached. Check the connection and try again.') from exc


def matches_filters(row, spec):
    if spec.domains and not any(row['domain'] == domain or row['domain'].endswith('.' + domain) for domain in spec.domains):
        return False
    if spec.start or spec.end:
        if not row['published']:
            return False
        published = date.fromisoformat(row['published'][:10])
        if spec.start and published < spec.start or spec.end and published > spec.end:
            return False
    if spec.keywords and spec.keyword_mode != 'Highlight only':
        preview = (row['title'] + '\n' + row['snippet']).casefold()
        matches = [bool(_keyword_pattern([word]).search(preview)) for word in spec.keywords]
        if not (all(matches) if spec.keyword_mode == 'Match all' else any(matches)):
            return False
    return True


def search_articles(spec, progress=None):
    query = provider_query(spec)
    started, seen, titles, rows, warnings = time.monotonic(), set(), set(), [], []
    pages, repeats, candidate_count = 0, 0, 0
    for page in range(MAX_PAGES):
        if page and time.monotonic() - started >= SEARCH_BUDGET_SECONDS:
            warnings.append('Search reached its time budget. Narrow the topic or search again for a different selection.')
            break
        params = dict(q=query, format='rss', mkt='en-IN', count=20, first=page * 10 + 1)
        if spec.sort == 'Newest first':
            params['qft'] = 'sortbydate="1"'
        try:
            candidates = _fetch_page(params)
        except DiscoveryError as exc:
            if not rows:
                raise
            warnings.append(str(exc))
            break
        pages += 1
        new_urls = 0
        for row in candidates:
            if row['url'] in seen:
                continue
            seen.add(row['url']); new_urls += 1; candidate_count += 1
            title_key = (row['domain'], unicodedata.normalize('NFKC', row['title']).casefold())
            if title_key in titles or not matches_filters(row, spec):
                continue
            titles.add(title_key); rows.append(row)
        if progress:
            progress(min(len(rows), spec.target), spec.target)
        if len(rows) >= spec.target or not candidates:
            break
        repeats = repeats + 1 if not new_urls else 0
        if repeats >= 2:
            break
    if spec.sort == 'Newest first':
        rows.sort(key=lambda row: row['published'] or '', reverse=True)
    rows = rows[:spec.target]
    if len(rows) < spec.target:
        warnings.append(f'Found {len(rows)} of the {spec.target} requested results. The free feed has limited coverage; broader filters may find more.')
    return dict(items=rows, requested=spec.target, provider='Bing News RSS', query=query,
                searched_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), pages_checked=pages,
                candidates_checked=candidate_count, warnings=warnings,
                date_note='Dates are reported by the news feed, not verified publisher metadata.',
                language_note='Language is requested from the search provider; previews may contain exceptions.')


def highlighted(text, keywords):
    """Escape every provider-controlled character before adding our own marks."""
    if not keywords:
        return escape(text)
    pattern = _keyword_pattern(keywords)
    if pattern is None:
        return escape(text)
    parts, position = [], 0
    for match in pattern.finditer(text):
        parts.extend((escape(text[position:match.start()]), '<mark>' + escape(match.group()) + '</mark>'))
        position = match.end()
    parts.append(escape(text[position:]))
    return ''.join(parts)
