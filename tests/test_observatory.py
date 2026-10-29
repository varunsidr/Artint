import csv
import io
import json
import sqlite3
from contextlib import closing

import pytest

from app import storage
from app.exports import metadata_csv
from app.facets import extract_facets
from app.observatory_data import clean_filters, collections, snapshot


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')
    monkeypatch.setattr('app.observatory_data.collection_audit', lambda _: None)


def article(index, **changes):
    return dict(dict(id=str(index), url=f'https://example.org/{index}', title=f'AI article {index}',
                     source='Example', author='', published='2025-01-10', fetched_at='2026-01-01',
                     text='OpenAI capex and circular financing. Revenue growth is real, but debt is unsustainable.',
                     word_count=16, links_json='[]', images_json='[]', pdf_path=''), **changes)


def filters(**changes):
    return clean_filters(changes, collections())


def test_facets_ignore_url_destinations_and_report_inspectable_passages():
    signals = extract_facets(article(1, text='A [plain link](https://nvidia.com/debt/valuation). OpenAI capex is rising.'))
    assert signals['entities'] == ['OpenAI']
    assert signals['lenses'] == ['spending']
    assert 'capex' in signals['evidence']['spending']
    assert not signals['concern']
    assert not signals['countercase']


def test_linked_filters_export_and_evidence_use_the_same_membership():
    storage.create_collection('example', 'Example collection', 'AI bubble')
    storage.upsert(article(1), collection_id='example')
    storage.upsert(article(2, source='Other', text='Nvidia valuations are overvalued.'), collection_id='example')
    storage.upsert(article(3))  # Excluded by collection membership.
    chosen = filters(mode='investment', collection='example', lens='credit', entity='OpenAI', source='Example', query='capex')
    view = snapshot(chosen)
    assert view['stats']['articles'] == 1
    assert [row['id'] for row in view['rows']] == ['1']
    assert all(row['id'] == '1' for group in view['evidence'].values() for row in group)
    assert next(lens['count'] for lens in view['lenses'] if lens['id'] == 'credit') == 1
    exported = list(csv.DictReader(io.StringIO(metadata_csv(**view['export_filters']).decode('utf-8-sig'))))
    assert [row['id'] for row in exported] == ['1']
    assert view['sources'] == ['Example', 'Other']


def test_bounded_pages_and_zero_months_prevent_misleading_timeline():
    storage.upsert_many(article(index, published='2025-03-01' if index % 2 else '2025-01-01') for index in range(27))
    view = snapshot(filters(page=999))
    assert view['stats']['articles'] == 27
    assert view['page'] == 3 and len(view['rows']) == 3
    assert view['timeline'] == [dict(month='2025-01', count=14), dict(month='2025-02', count=0), dict(month='2025-03', count=13)]
    assert all('text' not in row for row in view['rows'])
    empty = snapshot(filters(query='nonexistent'))
    assert empty['page'] == empty['pages'] == 1
    assert empty['rows'] == empty['timeline'] == []


def test_date_filters_and_missing_dates_are_consistent():
    storage.upsert(article(1, published='2025-01-01'))
    storage.upsert(article(2, published=''))
    storage.upsert(article(3, published='2099-01-01'))
    view = snapshot(filters())
    assert view['stats']['articles'] == 2 and view['stats']['undated'] == 1
    assert [row['id'] for row in snapshot(filters(month='2025-01'))['rows']] == ['1']
    assert snapshot(filters(period='90d'))['stats']['articles'] == 0


def test_cache_invalidation_updates_signals_and_cascades_deleted_membership():
    storage.create_collection('example', 'Example', '')
    storage.upsert(article(1), collection_id='example')
    before = storage.library_overview()['revision']
    storage.upsert(article(1, text='Nvidia valuation.'))
    assert storage.library_overview()['revision'] > before
    assert snapshot(filters(mode='investment', lens='credit'))['stats']['articles'] == 0
    assert snapshot(filters(mode='investment', entity='Nvidia'))['stats']['articles'] == 1
    with storage.connect() as con:
        con.execute('DELETE FROM articles WHERE id=?', ('1',))
    with storage.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM article_facets').fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM collection_articles').fetchone()[0] == 0


def test_v1_migration_preserves_articles_insights_and_fts_and_creates_backup():
    storage.upsert(article(1))
    # Recreate the previous schema by removing only the new v2 objects.
    with storage.connect() as con:
        con.execute('DROP TABLE collection_articles')
        con.execute('DROP TABLE article_facets')
        con.execute('DROP TABLE research_collections')
        con.execute('PRAGMA user_version=1')
    with storage.connect() as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == storage.SCHEMA_VERSION
        assert con.execute('SELECT COUNT(*) FROM article_facets').fetchone()[0] == 1
    assert storage.library_page(query='capex')['total'] == 1
    backup = next((storage.DB.parent / 'backups').glob(f'*before-v{storage.SCHEMA_VERSION}*.db'))
    with closing(sqlite3.connect(backup)) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 1
        assert con.execute('SELECT COUNT(*) FROM articles').fetchone()[0] == 1


def test_untrusted_filter_state_is_normalized():
    clean = filters(page={'bad': 1}, lens=['credit'], entity='imaginary', period='unlimited', collection='missing')
    assert clean['page'] == 1 and clean['lens'] == clean['entity'] == clean['collection'] == ''
    assert clean['period'] == 'all'


def save_topics(item, topics, model='qwen3:8b', version='1'):
    storage.save_insight(item, model, version, dict(topics=topics))


def test_general_analytics_is_default_even_with_an_ai_bubble_collection():
    storage.create_collection('ai-bubble', 'AI bubble', 'AI bubble')
    storage.upsert(article(1), collection_id='ai-bubble')
    storage.create_collection('layoffs', 'Layoffs', 'layoffs')
    item = article(2, title='Layoffs in retail', text='Workers face job cuts.', word_count=2000)
    storage.upsert(item, collection_id='layoffs')
    save_topics(item, ['Employment', 'Retail'])
    assert filters()['collection'] == ''
    chosen = filters(collection='layoffs', lens='credit', entity='OpenAI')
    view = snapshot(chosen)
    assert view['mode'] == 'general' and chosen['lens'] == chosen['entity'] == ''
    assert view['lenses'] == view['matrix'] == view['entities'] == [] and view['evidence'] == {}
    assert view['topics'] == [dict(name='Employment', count=1), dict(name='Retail', count=1)]
    assert view['stats']['analyzed'] == 1 and view['stats']['words'] == 2000
    assert view['stats']['medium_reads'] == 1


def test_topic_status_and_daily_filters_share_export_membership():
    storage.create_collection('sap', 'SAP collaboration', 'sap')
    for index in range(1, 5):
        item = article(index, published=f'2026-10-{24 + index:02}', text='SAP collaboration.',
                       source='Second' if index > 2 else 'First')
        storage.upsert(item, collection_id='sap')
        if index < 3:
            save_topics(item, ['Enterprise software', 'Cloud'])
    chosen = filters(collection='sap', topic='Cloud', status='Analyzed', day='2026-10-26')
    view = snapshot(chosen)
    assert view['stats']['articles'] == view['stats']['analyzed'] == 1
    assert [row['id'] for row in view['rows']] == ['2']
    assert view['timeline'] == [dict(day='2026-10-26', count=1)]
    exported = list(csv.DictReader(io.StringIO(metadata_csv(**view['export_filters']).decode('utf-8-sig'))))
    assert [row['id'] for row in exported] == ['2']
    assert snapshot(filters(collection='sap', status='Needs analysis'))['stats']['articles'] == 2
    # No current analysis means no fabricated topic labels.
    assert snapshot(filters(collection='sap', status='Needs analysis'))['topics'] == []
    assert snapshot(filters(collection='sap', topic='Roman glass'))['stats']['articles'] == 0


def test_only_current_model_version_and_content_contribute_topics_across_pages():
    for index in range(18):
        item = article(index)
        storage.upsert(item)
        save_topics(item, ['Shared', 'Shared'])  # Count each source once per label.
    save_topics(article(0), ['Old version'], version='old')
    save_topics(article(1), ['Other model'], model='other')
    storage.upsert(article(2, text='Changed saved content.'))
    view = snapshot(filters())
    assert view['stats']['analyzed'] == 16  # Other-model analysis doesn't replace the default model.
    assert view['topics'] == [dict(name='Shared', count=16)]
    assert len(view['rows']) == 12


def test_short_ranges_use_daily_bins_including_days_without_articles():
    storage.upsert(article(1, published='2026-10-25'))
    storage.upsert(article(2, published='2026-10-27'))
    view = snapshot(filters())
    assert view['timeline_granularity'] == 'day'
    assert view['timeline'] == [dict(day='2026-10-25', count=1), dict(day='2026-10-26', count=0), dict(day='2026-10-27', count=1)]
    assert filters(day='2026-02-30')['day'] == ''
    assert snapshot(filters(day='2026-10-25', period='90d'))['stats']['articles'] == 1


def test_previews_remove_image_destinations_and_preserve_unicode_prose():
    from app.text_preview import plain_excerpt
    value = plain_excerpt('# Story title\n\n![見出し画像](https://example.org/photo.png)\n\n'
                          'NTT と SAP collaborate on **cloud**. [Details](https://example.org/source). '
                          '<script>unsafe()</script>', title='Story title')
    assert 'NTT と SAP collaborate on cloud.' in value and 'Details' in value
    assert all(part not in value for part in ['https://', '見出し画像', 'script', 'unsafe', '**'])
    assert len(plain_excerpt('word ' * 2000)) <= 240
    original = '# Story title\n\n![見出し画像](https://example.org/photo.png)\n\nNTT と SAP discuss cloud services.'
    storage.upsert(article(1, title='Story title', text=original))
    assert storage.library_page()['items'][0]['excerpt'] == 'NTT と SAP discuss cloud services.'
    assert storage.get_article('1')['text'] == original
