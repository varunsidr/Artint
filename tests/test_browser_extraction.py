"""Offline policy regressions and opt-in real-browser rendering fixtures."""
import json
import asyncio
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.robotparser import RobotFileParser

import pytest

from app import browser_render, extract


def test_browser_launch_always_requests_the_os_sandbox(monkeypatch):
    monkeypatch.setenv('ARTICLE_BROWSER_CHANNEL', 'auto')
    calls = []
    class Chromium:
        async def launch(self, **options):
            calls.append(options)
            raise RuntimeError('Sandbox unavailable')
    class Playwright:
        chromium = Chromium()
    with pytest.raises(extract.ExtractionError, match='sandboxed browser'):
        asyncio.run(browser_render._launch(Playwright()))
    assert len(calls) == 3
    assert all(options['chromium_sandbox'] is True for options in calls)


URL = 'https://example.org/javascript-article'
PARAGRAPHS = [
    'Researchers are studying how artificial intelligence infrastructure changes local energy demand. '
    'Their latest report compares several regional electricity systems and describes the assumptions '
    'behind projected data centre growth. The researchers say that investment plans must account '
    'for both efficient computing equipment and the practical limits of new transmission projects.',
    'Companies interviewed for the study described different approaches to buying computing capacity. '
    'Some prefer long contracts while others rent additional machines only when customers need them. '
    'These choices affect operating costs and make headline spending figures difficult to compare. '
    'The report recommends publishing clearer measures of utilisation and customer demand.',
    'The authors also examined public planning documents and independent forecasts. They found '
    'considerable uncertainty about the speed of construction and the availability of skilled workers. '
    'Rather than choosing a single forecast, planners should examine several possible outcomes and '
    'update their assumptions as projects begin operating. Further research will track these changes.',
]
ARTICLE = '<article><h1>Public research on computing infrastructure</h1>' + ''.join(
    '<p>' + text + '</p>' for text in PARAGRAPHS) + '<a href="/evidence">Study evidence</a></article>'
FULL_HTML = '<html><head><title>Public research</title></head><body>' + ARTICLE + '</body></html>'
SHELL = '<html><head><title>Loading research</title></head><body><div id="root">Loading article</div><script src="/app.js"></script></body></html>'


@pytest.fixture
def no_browser(monkeypatch):
    def fail(*args):
        pytest.fail('The browser must not start for this response')
    monkeypatch.setattr(browser_render, 'render_article_html', fail)


def test_complete_html_keeps_the_fast_path(monkeypatch, no_browser):
    monkeypatch.setattr(extract, '_request_html', lambda _: (FULL_HTML, URL))
    article = extract.extract_article(URL)
    assert article['fetch_method'] == 'html' and article['word_count'] > 100
    assert 'regional electricity systems' in article['text']


def test_auto_renders_only_an_incomplete_javascript_page(monkeypatch):
    monkeypatch.setattr(extract, '_request_html', lambda _: (SHELL, URL))
    calls = []
    def render(url, html):
        calls.append((url, html))
        return FULL_HTML, URL
    monkeypatch.setattr(browser_render, 'render_article_html', render)
    article = extract.extract_article(URL)
    assert article['fetch_method'] == 'browser'
    assert calls == [(URL, SHELL)]


def test_html_only_never_starts_a_browser(monkeypatch, no_browser):
    monkeypatch.setattr(extract, '_request_html', lambda _: (SHELL, URL))
    with pytest.raises(extract.IncompleteArticle):
        extract.extract_article(URL, mode='html')


@pytest.mark.parametrize('message', ['robots.txt disallows fetching this URL', 'HTTP 403', 'HTTP 429',
                                      'Network error', 'HTML exceeds 5 MB size limit'])
def test_fetch_failures_do_not_trigger_browser_retry(monkeypatch, no_browser, message):
    def fail(_):
        raise extract.ExtractionError(message)
    monkeypatch.setattr(extract, '_request_html', fail)
    with pytest.raises(extract.ExtractionError, match=message):
        extract.extract_article(URL)


@pytest.mark.parametrize('html', [
    '<title>Just a moment</title><div id="root"></div><script src="/challenge"></script>',
    '<p>Subscribe to continue reading</p><script src="/app.js"></script>',
    '<script type="application/ld+json">{"isAccessibleForFree":false}</script>' + FULL_HTML,
])
def test_known_gates_do_not_trigger_browser_retry(monkeypatch, no_browser, html):
    monkeypatch.setattr(extract, '_request_html', lambda _: (html, URL))
    with pytest.raises(extract.ExtractionError, match='challenge|subscription'):
        extract.extract_article(URL)


def test_newsletter_captcha_does_not_block_a_complete_public_article(monkeypatch, no_browser):
    monkeypatch.setattr(extract, '_request_html', lambda _: (FULL_HTML + '<div class="g-recaptcha"></div>', URL))
    assert extract.extract_article(URL)['fetch_method'] == 'html'


def test_browser_gate_is_reported_instead_of_saved(monkeypatch):
    monkeypatch.setattr(extract, '_request_html', lambda _: (SHELL, URL))
    monkeypatch.setattr(browser_render, 'render_article_html', lambda *args: ('<title>Access denied</title>', URL))
    with pytest.raises(extract.ExtractionError, match='challenge'):
        extract.extract_article(URL)


def test_missing_browser_dependency_has_an_actionable_error(monkeypatch):
    monkeypatch.setattr(browser_render, 'installed', lambda: False)
    with pytest.raises(extract.ExtractionError, match='Install project requirements'):
        browser_render.render_article_html(URL, SHELL)


def test_browser_resource_rejects_private_redirect_before_following(monkeypatch):
    calls = []
    def dns(host, port):
        address = '127.0.0.1' if host == '127.0.0.1' else '93.184.216.34'
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, port))]
    class Response:
        status_code = 302
        headers = {'Location': 'http://127.0.0.1/private'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): pytest.fail('A private redirect must be rejected before reading')
    def get(url, **kwargs):
        calls.append(url)
        assert kwargs['allow_redirects'] is False
        return Response()
    monkeypatch.setattr(extract.socket, 'getaddrinfo', dns)
    monkeypatch.setattr(browser_render.requests, 'get', get)
    with pytest.raises(extract.ExtractionError, match='private'):
        browser_render._read_resource(URL, {}, 1000, 2)
    assert calls == [URL]


@pytest.mark.skipif(os.getenv('RUN_BROWSER_TESTS') != '1', reason='Opt-in: requires an installed Chrome/Edge/Chromium')
def test_real_chrome_renders_visible_content_and_blocks_private_requests(monkeypatch):
    """Real Chromium, deterministic public-origin fixture, no live publisher traffic."""
    policy = RobotFileParser()
    policy.parse(['User-agent: *', 'Disallow:'])
    monkeypatch.setattr(extract, '_robots', lambda _: policy)
    monkeypatch.setattr(extract, '_rate_limit', lambda *args: None)
    def dns(host, port):
        address = '93.184.216.34' if host == 'example.org' else '127.0.0.1'
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, port))]
    monkeypatch.setattr(extract.socket, 'getaddrinfo', dns)
    initial = SHELL.replace('</head>', '<link rel="stylesheet" href="/article.css"></head>')
    monkeypatch.setattr(extract, '_request_html', lambda _: (initial, URL))
    calls = []
    def resource(url, headers, maximum, remaining):
        calls.append(url)
        assert url.startswith('https://example.org/'), 'Private resources must never reach the transport'
        if url.endswith('/app.js'):
            return 200, {'Content-Type': 'text/javascript'}, b"""
                fetch('http://127.0.0.1/private').catch(() => {});
                fetch('/redirect.json').then(r => r.json()).then(data => {
                    document.title = 'Rendered public research';
                    document.querySelector('#root').innerHTML = data.body;
                });"""
        if url.endswith('/article.css'):
            return 200, {'Content-Type': 'text/css'}, b'.hidden-copy {display:none}'
        if url.endswith('/redirect.json'):
            return 302, {'Location': '/article.json'}, b''
        if url.endswith('/article.json'):
            body = ARTICLE.replace('</article>', '<p class="hidden-copy">SECRET_HIDDEN_PAYLOAD</p></article>')
            return 200, {'Content-Type': 'application/json'}, json.dumps({'body': body}).encode()
        pytest.fail('Unexpected resource: ' + url)
    monkeypatch.setattr(browser_render, '_read_resource', resource)
    # Import workers run in a background thread, including on Windows.
    with ThreadPoolExecutor(max_workers=1) as pool:
        article = pool.submit(extract.extract_article, URL).result(timeout=60)
    assert article['fetch_method'] == 'browser' and article['word_count'] > 100
    assert 'regional electricity systems' in article['text']
    assert 'SECRET_HIDDEN_PAYLOAD' not in article['text']
    assert json.loads(article['links_json']) == ['https://example.org/evidence']
    assert len(calls) == 4
