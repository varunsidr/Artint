from dataclasses import replace
from datetime import date
from urllib.parse import quote

import pytest

from app import discovery
from app.discovery import DiscoveryError, SearchSpec, highlighted, matches_filters, normalized_url, parse_feed, provider_query, search_articles


def candidate(index, **changes):
    return dict(dict(id=str(index), url=f'https://example.org/articles/{index}', title=f'AI debt story {index}',
                     domain='example.org', source='Example', published='2026-10-20T12:00:00+05:30',
                     snippet='Nvidia capex and debt are discussed.'), **changes)


def test_feed_unwraps_publisher_links_and_strips_active_markup():
    url = 'https://www.thehindu.com/news/article123.ece?utm_source=feed'
    rss = f'''<rss><channel><item><title>&lt;b&gt;AI bubble&lt;/b&gt;</title>
        <link>https://www.bing.com/news/apiclick.aspx?url={quote(url, safe='')}</link>
        <description>&lt;img src="https://tracker.test/x"&gt;Nvidia debt</description>
        <pubDate>Tue, 20 Oct 2026 12:00:00 GMT</pubDate></item>
        <item><title>Blocked</title><link>http://127.0.0.1/private</link></item></channel></rss>'''.encode()
    rows = parse_feed(rss)
    assert len(rows) == 1
    assert rows[0]['url'] == 'https://www.thehindu.com/news/article123.ece'
    assert rows[0]['title'] == 'AI bubble' and rows[0]['snippet'] == 'Nvidia debt'
    assert rows[0]['domain'] == 'thehindu.com'
    assert date.fromisoformat(rows[0]['published'][:10]) == date(2026, 10, 20)


@pytest.mark.parametrize('body', [b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss/>', b'<html>Not RSS</html>', b'<rss'])
def test_bad_feeds_are_actionable_errors(body):
    with pytest.raises(DiscoveryError):
        parse_feed(body)


def test_query_escapes_input_and_has_explicit_publisher_and_language_filters():
    spec = SearchSpec(('AI bubble', 'data centers'), keywords=('Nvidia', 'debt'), keyword_mode='Match all',
                      domains=('theguardian.com', 'thehindu.com'), language='Hindi', target=100)
    query = provider_query(spec)
    assert query.startswith('("AI bubble" OR "data centers")')
    assert '("Nvidia" AND "debt")' in query
    assert '(site:theguardian.com OR site:thehindu.com)' in query
    assert query.endswith('language:hi')
    assert 'site:evil.com' not in provider_query(SearchSpec(('AI site:evil.com',)))


def test_pagination_deduplicates_and_reports_a_real_shortfall(monkeypatch):
    calls = []
    def fetch(params):
        calls.append(params['first'])
        return [candidate(index) for index in range(15)]
    monkeypatch.setattr(discovery, '_fetch_page', fetch)
    result = search_articles(SearchSpec(('AI bubble',), target=25))
    assert len(result['items']) == 15 and calls == [1, 11, 21]
    assert any('15 of the 25' in value for value in result['warnings'])
    assert len({row['url'] for row in result['items']}) == 15


def test_partial_provider_failure_preserves_previews_without_inventing_results(monkeypatch):
    responses = iter([[candidate(index) for index in range(10)], DiscoveryError('Rate limited')])
    def fetch(params):
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(discovery, '_fetch_page', fetch)
    result = search_articles(SearchSpec(('AI',), target=25))
    assert len(result['items']) == 10 and 'Rate limited' in result['warnings']


def test_filter_predicates_dates_publishers_keywords_and_word_boundaries():
    spec = SearchSpec(('AI',), domains=('example.org',), keywords=('AI', 'debt'), keyword_mode='Match all',
                      start=date(2026, 10, 1), end=date(2026, 10, 27))
    assert matches_filters(candidate(1), spec)
    assert not matches_filters(candidate(1, domain='example.org.evil.com'), spec)
    assert not matches_filters(candidate(1, published=''), spec)
    assert not matches_filters(candidate(1, published='2026-09-30T12:00:00Z'), spec)
    assert not matches_filters(candidate(1, title='They said debt', snippet='Only debt'), spec)
    assert matches_filters(candidate(1, title='Only debt'), replace(spec, keyword_mode='Match any'))


def test_highlighting_is_safe_and_does_not_highlight_ai_inside_said():
    html = highlighted('They said AI <script>alert(1)</script> & debt.', ['AI', 'debt'])
    assert 'said' in html and 's<mark>' not in html
    assert '<mark>AI</mark>' in html and '<mark>debt</mark>' in html
    assert '<script>' not in html and '&lt;script&gt;' in html and '&amp;' in html


@pytest.mark.parametrize('spec', [SearchSpec((), target=5), SearchSpec(('AI',), target=101),
                                  SearchSpec(('AI',), domains=('https://thehindu.com/path',)),
                                  SearchSpec(('AI',), start=date(2026, 10, 20), end=date(2026, 10, 1))])
def test_invalid_searches_are_rejected_before_network(spec, monkeypatch):
    monkeypatch.setattr(discovery, '_fetch_page', lambda _: pytest.fail('Invalid query made a network request'))
    with pytest.raises(DiscoveryError):
        search_articles(spec)


@pytest.mark.parametrize('url', ['file:///tmp/x', 'http://user:pass@publisher.com/x', 'http://127.0.0.1/',
                                 'http://localhost/a', 'https://publisher.com:9000/x'])
def test_unsafe_result_urls_are_not_rendered(url):
    assert normalized_url(url) is None
