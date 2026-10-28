from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import pytest

from app import extract


class Response:
    def __init__(self, body=b'', status=200, headers=None):
        self.body, self.status_code = body, status
        self.headers = {'Content-Type': 'text/html; charset=utf-8', **(headers or {})}
        self.encoding = 'utf-8'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.body


@pytest.fixture(autouse=True)
def network(monkeypatch):
    extract._ROBOTS_CACHE.clear()
    monkeypatch.setattr(extract, 'validate_public_url', urlparse)
    monkeypatch.setattr(extract, '_rate_limit', lambda *args: None)


def policy(disallow=''):
    result = RobotFileParser()
    result.parse(['User-agent: *', f'Disallow: {disallow}'])
    return result


def test_robots_denial_prevents_article_request(monkeypatch):
    monkeypatch.setattr(extract, '_robots', lambda _: policy('/'))
    monkeypatch.setattr(extract.requests, 'get', lambda *args, **kwargs: pytest.fail('Article request must be blocked'))
    with pytest.raises(extract.ExtractionError, match='disallows'):
        extract._request_html('https://example.org/article')


def test_redirect_checks_destination_robots_before_request(monkeypatch):
    origins, requests = [], []
    def robots(root):
        origins.append(root)
        return policy('/' if root.endswith('other.org') else '')
    def request(url, **kwargs):
        requests.append(url)
        assert kwargs['allow_redirects'] is False
        return Response(status=302, headers={'Location': 'https://other.org/private'})
    monkeypatch.setattr(extract, '_robots', robots)
    monkeypatch.setattr(extract.requests, 'get', request)
    with pytest.raises(extract.ExtractionError, match='disallows'):
        extract._request_html('https://example.org/article')
    assert origins == ['https://example.org', 'https://other.org']
    assert len(requests) == 1


def test_stream_size_is_bounded_and_utf8_preserved(monkeypatch):
    monkeypatch.setattr(extract, '_robots', lambda _: policy())
    monkeypatch.setattr(extract.requests, 'get', lambda *args, **kwargs: Response('Caf\u00e9'.encode()))
    assert extract._request_html('https://example.org/article')[0] == 'Caf\u00e9'
    with pytest.raises(extract.ExtractionError, match='size limit'):
        extract._bounded_resource('https://example.org/article', 2)


def test_robots_status_policy_and_cache(monkeypatch):
    calls = []
    def request(url, **kwargs):
        calls.append(url)
        return Response(status=404)
    monkeypatch.setattr(extract.requests, 'get', request)
    assert extract._robots('https://example.org').can_fetch(extract.UA, 'https://example.org/article')
    extract._robots('https://example.org')
    assert len(calls) == 1
    monkeypatch.setattr(extract.requests, 'get', lambda *args, **kwargs: Response(status=403))
    assert not extract._robots('https://blocked.org').can_fetch(extract.UA, 'https://blocked.org/article')


def test_unverifiable_html_robots_and_long_crawl_delay_are_rejected(monkeypatch):
    monkeypatch.setattr(extract.requests, 'get', lambda *args, **kwargs: Response(b'<!doctype html><html>Login</html>'))
    with pytest.raises(extract.ExtractionError, match='Cannot verify'):
        extract._robots('https://example.org')
    delayed = RobotFileParser()
    delayed.parse(['User-agent: *', 'Crawl-delay: 60', 'Disallow:'])
    monkeypatch.setattr(extract, '_robots', lambda _: delayed)
    with pytest.raises(extract.ExtractionError, match='crawl delay'):
        extract._request_html('https://example.org/article')
