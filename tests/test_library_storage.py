import sqlite3
from contextlib import closing
import json

import pytest

from app import storage


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')


def article(index=0, **changes):
    result = dict(id=f'article{index:04}', url=f'https://example.org/{index}', title=f'Article {index:04}',
                  source='www.example.org', author='Research Writer', published='2026-10-27',
                  fetched_at='2026-10-27T00:00:00Z', text='Evidence about astronomy and glass.',
                  word_count=6, links_json='[]', images_json='[]', pdf_path='')
    return dict(result, **changes)


def _insight():
    return {'summary': {'text': 'A summary.', 'sources': ['article0000:P1']},
            'key_points': [], 'topics': ['Science']}


def test_pagination_has_stable_ties_no_duplicates_and_bounded_payloads():
    storage.upsert_many(article(index, text='Evidence ' * 10000) for index in range(61))
    pages = [storage.library_page(page=page, page_size=25) for page in (1, 2, 3)]
    assert [len(page['items']) for page in pages] == [25, 25, 11]
    ids = [item['id'] for page in pages for item in page['items']]
    assert len(set(ids)) == 61
    assert ids == sorted(ids, reverse=True)
    assert all('text' not in item and len(item['excerpt']) <= 240 for page in pages for item in page['items'])
    assert storage.library_page(page=999)['page'] == 3
    assert len(storage.library_page(page_size=100)['items']) == 61


def test_fts_searches_title_author_publisher_body_and_unicode_prefixes():
    storage.upsert(article(title='Café findings', text='Astronomical evidence and glassmaking.'))
    for query in ('cafe', 'astro', 'glass', 'Research Writer', 'example org'):
        assert storage.library_page(query=query)['total'] == 1
    assert storage.library_page(query='astronomical impossible')['total'] == 0
    assert storage.library_page(query='--- " ***')['total'] == 0
    assert storage.library_page(query="x' OR 1=1 --")['total'] == 0
    assert storage.library_page(query='   ')['total'] == 1


def test_fts_updates_and_deletes_follow_article_mutations():
    original = article(text='Quasar evidence.')
    storage.upsert(original)
    assert storage.library_page(query='quasar')['total'] == 1
    storage.upsert(dict(original, text='Pulsar evidence.'))
    assert storage.library_page(query='quasar')['total'] == 0
    assert storage.library_page(query='pulsar')['total'] == 1
    storage.delete_all()
    assert storage.library_page(query='pulsar')['total'] == 0


def test_filters_and_analysis_counts_ignore_stale_or_other_model_insights():
    first, second = article(), article(1, source='Other publisher')
    storage.upsert_many([first, second])
    storage.save_insight(first, 'qwen3:8b', '1', _insight())
    assert storage.library_page(status='Analyzed')['total'] == 1
    assert storage.library_page(topics=['Science'])['total'] == 1
    assert storage.library_page(sources=['example.org'])['total'] == 1
    assert storage.library_page(sources=[])['total'] == 0
    assert storage.library_overview()['analyzed'] == 1
    assert storage.library_overview(model='different')['analyzed'] == 0
    assert storage.library_page(version='2', status='Analyzed')['total'] == 0
    storage.upsert(dict(first, text='Revised evidence.'))
    assert storage.library_overview()['analyzed'] == 0
    assert storage.library_page(topics=['Science'])['total'] == 0
    assert storage.library_page(status='Needs analysis')['total'] == 2


@pytest.mark.parametrize('arguments', [{'page_size': 0}, {'page_size': 101},
                                     {'sort': 'title; DROP TABLE articles'}, {'query': 'a' * 257}])
def test_query_limits_are_validated(arguments):
    with pytest.raises(ValueError):
        storage.library_page(**arguments)


def test_bulk_insert_is_atomic_on_failure():
    storage.upsert(article())
    with pytest.raises(sqlite3.ProgrammingError):
        storage.upsert_many([article(1), {'id': 'broken'}])
    assert storage.library_overview()['total'] == 1


def _legacy_database():
    # Independent copy of the original on-disk contract.
    con = sqlite3.connect(storage.DB)
    con.execute('''CREATE TABLE articles (
        id TEXT PRIMARY KEY,url TEXT NOT NULL UNIQUE,title TEXT NOT NULL,source TEXT,author TEXT,
        published TEXT,fetched_at TEXT NOT NULL,text TEXT NOT NULL,word_count INTEGER NOT NULL,
        links_json TEXT NOT NULL,images_json TEXT NOT NULL,pdf_path TEXT)''')
    item = article(text='Legacy quasar evidence.')
    con.execute('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', tuple(item.values()))
    con.commit()
    con.close()
    return item


def test_legacy_migration_preserves_text_and_keeps_a_recoverable_backup(tmp_path):
    original = _legacy_database()
    assert storage.library_page(query='quasar')['total'] == 1
    assert storage.get_article(original['id'])['text'] == original['text']
    with storage.connect() as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == storage.SCHEMA_VERSION
    backups = list((tmp_path / 'backups').glob('*.db'))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 0
        assert con.execute('SELECT text FROM articles').fetchone()[0] == original['text']
        assert 'content_hash' not in {row[1] for row in con.execute('PRAGMA table_info(articles)')}
    storage.library_overview()
    assert len(list((tmp_path / 'backups').glob('*.db'))) == 1


def test_failed_migration_rolls_back_schema_and_data():
    original = _legacy_database()

    class BrokenFTS(sqlite3.Connection):
        def execute(self, sql, *args):
            if 'CREATE VIRTUAL TABLE articles_fts' in sql:
                raise sqlite3.OperationalError('Simulated missing FTS extension')
            return super().execute(sql, *args)

    with closing(sqlite3.connect(storage.DB, factory=BrokenFTS)) as con:
        con.row_factory = sqlite3.Row
        with pytest.raises(sqlite3.OperationalError):
            storage._migrate(con)
    with closing(sqlite3.connect(storage.DB)) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 0
        assert con.execute('SELECT text FROM articles').fetchone()[0] == original['text']
        assert 'content_hash' not in {row[1] for row in con.execute('PRAGMA table_info(articles)')}


def test_migration_preserves_saved_insights_and_embeddings():
    original = _legacy_database()
    insight = _insight()
    with closing(sqlite3.connect(storage.DB)) as con:
        con.execute('''CREATE TABLE article_insights(article_id TEXT,model TEXT,content_hash TEXT,
            version TEXT,insight_json TEXT,PRIMARY KEY(article_id,model))''')
        con.execute('INSERT INTO article_insights VALUES(?,?,?,?,?)',
                    (original['id'], 'qwen3:8b', storage.article_fingerprint(original), '1', json.dumps(insight)))
        con.execute('CREATE TABLE embeddings(model TEXT,text_hash TEXT,vector_json TEXT,PRIMARY KEY(model,text_hash))')
        con.execute('INSERT INTO embeddings VALUES(?,?,?)', ('embedding', storage._text_hash('original text'), '[1,0]'))
        con.commit()
    assert storage.library_overview()['analyzed'] == 1
    assert storage.load_insight(original, 'qwen3:8b', '1') == insight
    assert storage.cached_embeddings('embedding', ['original text']) == {'original text': [1, 0]}


def test_analytics_are_bounded_aggregates_and_samples():
    storage.upsert_many(article(index, word_count=100 + index * 300, source=f'Source {index % 25}') for index in range(301))
    result = storage.analytics_overview()
    assert result['total'] == 301
    assert len(result['sources']) == 20
    assert len(result['timeline']) <= 60
    assert sum(row['articles'] for row in result['lengths']) == 301
    assert len(storage.recent_sample()) == 250
    assert storage.analytics_overview([])['total'] == 0
    assert len(storage.load_articles(['article0001', 'article0002'])) == 2
    with pytest.raises(ValueError):
        storage.load_articles([str(index) for index in range(101)])
