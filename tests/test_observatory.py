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
    chosen = filters(collection='example', lens='credit', entity='OpenAI', source='Example', query='capex')
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
    assert snapshot(filters(lens='credit'))['stats']['articles'] == 0
    assert snapshot(filters(entity='Nvidia'))['stats']['articles'] == 1
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
