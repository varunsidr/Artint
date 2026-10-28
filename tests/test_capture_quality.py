import json
import sqlite3
from contextlib import closing
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from app import extract, storage
from app.capture_quality import explicit_metadata, inspect_capture, saved_quality, tokens
from app.discovery_imports import batches, create_batch, process_next
from tests.test_browser_extraction import ARTICLE, FULL_HTML, PARAGRAPHS, URL
from tests.test_library_storage import article as stored_article, _insight


def test_short_excerpts_are_rejected_even_when_longer_than_eighty_characters(monkeypatch):
    html = '<article><h1>A public research excerpt</h1><p>' + PARAGRAPHS[0] + '</p></article>'
    monkeypatch.setattr(extract, '_request_html', lambda _: (html, URL))
    with pytest.raises(extract.IncompleteArticle) as caught:
        extract.extract_article(URL)
    assert caught.value.code == 'incomplete_body'


def test_missing_metadata_is_inspectable_and_not_a_human_quality_claim():
    result = extract._article_from_html(FULL_HTML, URL)
    quality = saved_quality(result)
    assert quality['status'] == 'needs_review' and quality['reviewed'] is False
    assert {'missing_author', 'missing_publication_date'} <= {finding['code'] for finding in quality['warnings']}


def test_list_and_table_content_is_counted_without_nested_double_counting():
    html = '<article><p>' + PARAGRAPHS[0] + '</p><ul><li><p>' + PARAGRAPHS[1] + '</p></li><li>' + PARAGRAPHS[2] + '</li></ul></article>'
    result = dict(stored_article(), text='\n'.join(PARAGRAPHS))
    quality = inspect_capture(result, html)
    assert quality['evidence']['reference_paragraphs'] == 3
    assert quality['evidence']['paragraph_coverage'] == 1
    assert not any(finding['code'] == 'possible_extra_content' for finding in quality['warnings'])


def test_partial_body_is_flagged_against_the_same_visible_dom_blocks():
    paragraphs = PARAGRAPHS + [text.replace('Researchers', 'Investigators').replace('report', 'publication') for text in PARAGRAPHS]
    html = '<article>' + ''.join('<p>' + text + '</p>' for text in paragraphs) + '</article>'
    result = dict(stored_article(), text=PARAGRAPHS[0])
    assert any(finding['code'] == 'possible_missing_content' for finding in inspect_capture(result, html)['warnings'])


def test_explicit_published_date_overrides_an_inferred_update_date(monkeypatch):
    html = FULL_HTML.replace('<head>', '<head><meta property="article:published_time" content="2026-10-02T09:00:00Z">')
    baseline = {'text': '\n'.join(PARAGRAPHS), 'date': '2026-10-28', 'title': 'Research'}
    monkeypatch.setattr(extract.trafilatura, 'extract', lambda *args, **kwargs: json.dumps(baseline))
    result = extract._article_from_html(html, URL)
    assert result['published'] == '2026-10-02'
    assert saved_quality(result)['metadata_sources']['published'] == 'html_meta'


def test_bounded_article_jsonld_fills_author_without_using_hidden_article_body():
    data = {'@graph': [{'@type': 'NewsArticle', 'headline': 'Public headline', 'author': [{'name': 'First Writer'}, {'name': 'Second Writer'}],
                        'datePublished': '2026-10-02T09:00:00Z', 'articleBody': 'HIDDEN CONTENT MUST NEVER BECOME THE BODY'}]}
    soup = BeautifulSoup('<script type="application/ld+json">' + json.dumps(data) + '</script>', 'html.parser')
    values, sources = explicit_metadata(soup)
    assert values == {'title': 'Public headline', 'author': 'First Writer, Second Writer', 'published': '2026-10-02'}
    assert sources['author'] == 'article_jsonld'


def test_malformed_jsonld_and_invalid_dates_do_not_crash_capture():
    soup = BeautifulSoup('<meta property="article:published_time" content="2026-99-99"><script type="application/ld+json">{broken</script>', 'html.parser')
    assert explicit_metadata(soup) == ({}, {})


def test_cjk_articles_do_not_fail_only_because_they_lack_spaces(monkeypatch):
    content = '\u4eba\u5de5\u77e5\u80fd\u7814\u7a76\u62a5\u544a\u516c\u5f00\u6570\u636e\u4e0e\u7535\u529b\u57fa\u7840\u8bbe\u65bd\u3002' * 12
    monkeypatch.setattr(extract.trafilatura, 'extract', lambda *args, **kwargs: json.dumps({'text': content, 'title': 'Research'}))
    result = extract._article_from_html('<article><p>' + content + '</p></article>', URL)
    assert result['word_count'] >= 80 and len(tokens(content)) >= 80


def test_scoped_article_fix_drops_outside_text_only_when_body_coverage_is_retained(monkeypatch):
    # Five substantial source paragraphs exceed the minimum diagnostic reference.
    body = '\n'.join(PARAGRAPHS + [PARAGRAPHS[0].replace('Researchers', 'Planners'), PARAGRAPHS[1].replace('Companies', 'Institutions')])
    html = '<article><h1>Research</h1>' + ''.join('<p>' + text + '</p>' for text in body.splitlines()) + '</article>'
    noise = '\nUnrelated directory listing and promotional navigation. ' * 70
    calls = []
    def parse(document, **kwargs):
        calls.append(kwargs)
        return json.dumps({'text': body if kwargs.get('favor_precision') else body + noise, 'title': 'Research'})
    monkeypatch.setattr(extract.trafilatura, 'extract', parse)
    result = extract._article_from_html(html, URL)
    assert result['text'] == body and len(calls) == 2
    assert saved_quality(result)['metadata_sources']['body'] == 'article_region'


def test_captcha_news_is_not_mistaken_for_a_challenge(monkeypatch):
    html = FULL_HTML.replace('<title>Public research</title>', '<title>CAPTCHA research and browser security</title>')
    monkeypatch.setattr(extract, '_request_html', lambda _: (html, URL))
    assert extract.extract_article(URL)['fetch_method'] == 'html'


@pytest.mark.parametrize('status,expected', [(401, 'http_blocked'), (403, 'http_blocked'), (429, 'rate_limited'), (404, 'http_unavailable')])
def test_http_failures_have_stable_codes(monkeypatch, status, expected):
    from tests.test_fetch_bounds import Response, policy
    import requests
    response = Response(status=status)
    response.raise_for_status = lambda: (_ for _ in ()).throw(requests.HTTPError('Publisher response', response=response))
    monkeypatch.setattr(extract, 'validate_public_url', lambda _: __import__('urllib.parse', fromlist=['urlparse']).urlparse(URL))
    monkeypatch.setattr(extract, '_robots', lambda _: policy())
    monkeypatch.setattr(extract, '_rate_limit', lambda *args: None)
    monkeypatch.setattr(extract.requests, 'get', lambda *args, **kwargs: response)
    with pytest.raises(extract.ExtractionError) as caught:
        extract._request_html(URL)
    assert caught.value.code == expected


def test_quality_upsert_preserves_valid_ai_cache_and_old_database_upgrade(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path/'library.db')
    original = stored_article()
    storage.upsert(original)
    storage.save_insight(original, 'qwen3:8b', '1', _insight())
    with storage.connect() as con:
        con.execute("INSERT INTO embeddings VALUES('model','hash','[0.1,0.2]')")
        con.execute('ALTER TABLE articles DROP COLUMN quality_json')
        con.execute('ALTER TABLE import_batch_items DROP COLUMN error_code')
        con.execute('PRAGMA user_version=4')
    assert saved_quality(storage.get_article(original['id']))['status'] == 'not_checked'
    annotated = dict(original, quality_json=json.dumps(inspect_capture(original)))
    storage.upsert(annotated)
    assert storage.library_overview()['analyzed'] == 1
    with storage.connect() as con:
        assert con.execute('SELECT vector_json FROM embeddings').fetchone()[0] == '[0.1,0.2]'
    backup = next((storage.DB.parent/'backups').glob(f'*before-v{storage.SCHEMA_VERSION}*.db'))
    with closing(sqlite3.connect(backup)) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 4


def test_import_batch_exposes_review_count_and_failure_category(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path/'library.db')
    create_batch(['https://example.org/one', 'https://example.org/blocked'], 'Quality batch', '')
    def fetch(url):
        if url.endswith('blocked'):
            raise extract.ExtractionError('Publisher rate limit', code='rate_limited')
        return dict(stored_article(word_count=100), url=url, quality_json=json.dumps({'version': '2', 'status': 'needs_review', 'warnings': []}))
    process_next(fetch=fetch, render=lambda _: 'fixture.pdf')
    job = batches()[0]
    assert job['needs_review'] == 1 and job['saved'] == job['failed'] == 1
    assert job['failures'][0]['error_code'] == 'rate_limited'
