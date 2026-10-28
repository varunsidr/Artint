import sqlite3
import time
from contextlib import closing

import pytest

from app import storage
from app.discovery_imports import _claim, batches, cancel_batch, create_batch, ensure_worker, process_next


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')


def article(url, **kwargs):
    return dict(id=url.rsplit('/', 1)[-1], url=url, title='Saved discovery article', source='Example',
                author='', published='2026-10-20', fetched_at='2026-10-28T00:00:00Z', text='Evidence. ' * 100,
                word_count=100, links_json='[]', images_json='[]', pdf_path='')


def test_batch_commits_articles_membership_and_visible_outcomes_atomically():
    existing = article('https://example.org/existing')
    storage.upsert(existing)
    job = create_batch(['https://example.org/existing', 'https://example.org/new', 'https://example.org/blocked'], 'AI sources', 'AI bubble')
    fetched = []
    def fetch(url):
        fetched.append(url)
        if url.endswith('blocked'):
            raise ValueError('Publisher access denied')
        return article(url)
    assert process_next(fetch=fetch, render=lambda _: 'test.pdf')
    result = batches()[0]
    assert result['id'] == job and result['state'] == 'completed'
    assert (result['saved'], result['existing'], result['failed']) == (1, 1, 1)
    assert 'https://example.org/existing' not in fetched
    assert storage.library_page(collection_id=result['collection_id'])['total'] == 2
    assert not process_next(fetch=fetch, render=lambda _: 'test.pdf')


def test_lease_excludes_other_workers_and_recovers_an_interrupted_item():
    job = create_batch(['https://example.org/recover'], 'Recover', 'AI')
    assert _claim('first')['id'] == job
    assert _claim('second') is None
    with storage.connect() as con:
        con.execute("UPDATE import_batches SET lease_until=0 WHERE id=?", (job,))
        con.execute("UPDATE import_batch_items SET state='running' WHERE batch_id=?", (job,))
    process_next('second', fetch=article, render=lambda _: 'test.pdf')
    assert batches()[0]['saved'] == 1
    assert storage.library_overview()['total'] == 1


def test_worker_waits_for_an_old_lease_and_recovers_without_ui_polling(monkeypatch):
    from app import discovery_imports
    job = create_batch(['https://example.org/restart'], 'Restart recovery', 'AI')
    _claim('previous-process')
    with storage.connect() as con:
        con.execute('UPDATE import_batches SET lease_until=? WHERE id=?', (time.time() + .15, job))
        con.execute("UPDATE import_batch_items SET state='running' WHERE batch_id=?", (job,))
    monkeypatch.setattr(discovery_imports, 'extract_article', article)
    monkeypatch.setattr(discovery_imports, 'create_pdf', lambda _: 'test.pdf')
    ensure_worker()
    with discovery_imports._RUNNERS_LOCK:
        worker = discovery_imports._RUNNERS[str(storage.DB.resolve())]
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert batches()[0]['state'] == 'completed' and batches()[0]['saved'] == 1


def test_cancel_queued_and_stop_running_after_current_article():
    queued = create_batch(['https://example.org/queued'], 'Cancel queued', '')
    cancel_batch(queued)
    assert not process_next(fetch=lambda _: pytest.fail('Cancelled job fetched a page'))
    assert batches()[0]['cancelled'] == 1
    running = create_batch(['https://example.org/one', 'https://example.org/two'], 'Cancel running', '')
    def fetch(url):
        cancel_batch(running)
        return article(url)
    process_next(fetch=fetch, render=lambda _: 'test.pdf')
    result = next(row for row in batches() if row['id'] == running)
    assert result['state'] == 'cancelled' and result['saved'] == result['cancelled'] == 1


def test_pdf_failure_does_not_save_an_article_or_mark_it_complete():
    create_batch(['https://example.org/fail'], 'Failure', '')
    def render(_):
        raise OSError('Disk unavailable')
    process_next(fetch=article, render=render)
    assert batches()[0]['failed'] == 1 and batches()[0]['saved'] == 0
    assert storage.library_overview()['total'] == 0


def test_later_batches_extend_the_same_search_collection_but_do_not_overwrite_other_searches():
    create_batch(['https://example.org/one'], 'My research', 'AI')
    process_next(fetch=article, render=lambda _: 'test.pdf')
    collection = batches()[0]['collection_id']
    create_batch(['https://example.org/two'], 'My research', 'AI')
    process_next(fetch=article, render=lambda _: 'test.pdf')
    assert {row['collection_id'] for row in batches()} == {collection}
    assert storage.library_page(collection_id=collection)['total'] == 2
    with pytest.raises(ValueError, match='different search'):
        create_batch(['https://example.org/other'], 'My research', 'Climate')


def test_v2_migration_preserves_library_and_creates_recovery_backup():
    storage.upsert(article('https://example.org/original'))
    with storage.connect() as con:
        con.execute('DROP TABLE import_batch_items')
        con.execute('DROP TABLE import_batches')
        con.execute('PRAGMA user_version=2')
    assert storage.library_page(query='Evidence')['total'] == 1
    assert batches() == []
    backup = next((storage.DB.parent / 'backups').glob(f'*before-v{storage.SCHEMA_VERSION}*.db'))
    with closing(sqlite3.connect(backup)) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 2
        assert con.execute('SELECT COUNT(*) FROM articles').fetchone()[0] == 1


@pytest.mark.parametrize('mode', ['html', 'auto'])
def test_worker_uses_the_persisted_capture_mode(monkeypatch, mode):
    from app import discovery_imports
    create_batch(['https://example.org/mode'], 'Capture choice', 'AI', fetch_mode=mode)
    calls = []
    def fetch(url, *, mode):
        calls.append(mode)
        return dict(article(url), fetch_method='browser' if mode == 'auto' else 'html')
    monkeypatch.setattr(discovery_imports, 'extract_article', fetch)
    process_next(render=lambda _: 'test.pdf')
    assert calls == [mode] and batches()[0]['fetch_mode'] == mode
    assert storage.get_article('mode')['fetch_method'] == ('browser' if mode == 'auto' else 'html')


def test_v3_migration_preserves_content_and_defaults_queued_capture_modes():
    original = article('https://example.org/legacy')
    storage.upsert(original)
    create_batch(['https://example.org/queued'], 'Before upgrade', 'AI')
    with storage.connect() as con:
        fingerprint = con.execute('SELECT content_hash FROM articles').fetchone()[0]
        con.execute('ALTER TABLE articles DROP COLUMN fetch_method')
        con.execute('ALTER TABLE import_batches DROP COLUMN fetch_mode')
        con.execute('PRAGMA user_version=3')
    assert storage.get_article('legacy')['fetch_method'] == 'html'
    assert storage.get_article('legacy')['content_hash'] == fingerprint
    assert batches()[0]['fetch_mode'] == 'auto' and batches()[0]['state'] == 'queued'
    backup = next((storage.DB.parent / 'backups').glob(f'*before-v{storage.SCHEMA_VERSION}*.db'))
    with closing(sqlite3.connect(backup)) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 3
        assert con.execute('SELECT text FROM articles').fetchone()[0] == original['text']
