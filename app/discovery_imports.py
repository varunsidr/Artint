"""Durable, bounded local import batches. Workers never call Streamlit APIs."""
import threading
import time
import uuid
from datetime import datetime, timezone

from app import storage
from app.capture_quality import failure_details
from app.discovery import normalized_url
from app.extract import extract_article
from app.reports import create_pdf

LEASE_SECONDS = 300
_RUNNERS = {}
_RUNNERS_LOCK = threading.Lock()


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def saved_urls(urls):
    values = list(dict.fromkeys(urls))
    if len(values) > 100:
        raise ValueError('Check up to 100 result URLs at a time.')
    if not values:
        return {}
    with storage.connect() as con:
        return {row['url']: row['id'] for row in con.execute(
            'SELECT id,url FROM articles WHERE url IN (' + ','.join('?' for _ in values) + ')', values)}


def create_batch(urls, title, query, *, fetch_mode='auto'):
    if fetch_mode not in ('auto', 'html'):
        raise ValueError('Choose Auto or HTML-only extraction.')
    values = list(dict.fromkeys(urls))
    if not 1 <= len(values) <= 100 or any(normalized_url(url) != url for url in values):
        raise ValueError('Select 1–100 valid publisher article URLs.')
    title = title.strip()
    if not title or len(title) > 120:
        raise ValueError('Give the collection a name of 1–120 characters.')
    job_id = uuid.uuid4().hex
    collection_id = 'search-' + job_id[:16]
    now = _stamp()
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        existing = con.execute('SELECT id,query FROM research_collections WHERE title=? COLLATE NOCASE', (title,)).fetchone()
        if existing:
            if existing['query'].casefold() != query[:1000].casefold():
                raise ValueError('That name belongs to a different search. Choose another collection name.')
            collection_id = existing['id']
        else:
            con.execute('INSERT INTO research_collections VALUES(?,?,?,?)', (collection_id, title, query[:1000], now))
        con.execute('''INSERT INTO import_batches(id,title,query,collection_id,state,created_at,updated_at,fetch_mode)
            VALUES(?,?,?,?,?,?,?,?)''', (job_id, title[:120], query[:1000], collection_id, 'queued', now, now, fetch_mode))
        con.executemany('INSERT INTO import_batch_items(batch_id,position,url,state) VALUES(?,?,?,?)',
                        [(job_id, index, url, 'queued') for index, url in enumerate(values)])
    return job_id


def batches(limit=10):
    if not 1 <= limit <= 20:
        raise ValueError('Show up to 20 recent import batches.')
    with storage.connect() as con:
        jobs = [dict(row) for row in con.execute('''SELECT b.*,COUNT(i.position) AS total,
            SUM(i.state='saved') AS saved,SUM(i.state='existing') AS existing,
            SUM(i.state='failed') AS failed,SUM(i.state='cancelled') AS cancelled,
            SUM(i.state='running') AS running FROM import_batches b
            JOIN import_batch_items i ON i.batch_id=b.id GROUP BY b.id
            ORDER BY CASE b.state WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
            b.created_at DESC,b.id DESC LIMIT ?''', (limit,))]
        for job in jobs:
            job['needs_review'] = con.execute('''SELECT COUNT(*) FROM import_batch_items i JOIN articles a ON a.id=i.article_id
                WHERE i.batch_id=? AND i.state IN ('saved','existing') AND json_extract(a.quality_json,'$.status')='needs_review' ''', (job['id'],)).fetchone()[0]
            job['failures'] = [dict(row) for row in con.execute('''SELECT url,error,error_code FROM import_batch_items
                WHERE batch_id=? AND state='failed' ORDER BY position LIMIT 100''', (job['id'],))]
    return jobs


def cancel_batch(job_id):
    with storage.connect() as con:
        con.execute('UPDATE import_batches SET cancel_requested=1,updated_at=? WHERE id=? AND state IN (?,?)',
                    (_stamp(), job_id, 'queued', 'running'))
        con.execute("UPDATE import_batch_items SET state='cancelled' WHERE batch_id=? AND state='queued' AND EXISTS "
                    "(SELECT 1 FROM import_batches WHERE id=? AND state='queued')", (job_id, job_id))
        con.execute("UPDATE import_batches SET state='cancelled' WHERE id=? AND state='queued' AND cancel_requested=1", (job_id,))


def _claim(owner):
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute("""SELECT * FROM import_batches WHERE state='queued'
            OR (state='running' AND lease_until<?) ORDER BY created_at,id LIMIT 1""", (time.time(),)).fetchone()
        if not row:
            return None
        job = dict(row)
        con.execute("UPDATE import_batches SET state='running',owner=?,lease_until=?,updated_at=? WHERE id=?",
                    (owner, time.time() + LEASE_SECONDS, _stamp(), job['id']))
        con.execute("UPDATE import_batch_items SET state='queued' WHERE batch_id=? AND state='running'", (job['id'],))
        return job


def process_next(owner=None, *, fetch=None, render=None):
    """Claim and process one batch; injectable I/O keeps recovery tests offline."""
    owner = owner or uuid.uuid4().hex
    job = _claim(owner)
    if not job:
        return False
    fetch = fetch or (lambda url: extract_article(url, mode=job['fetch_mode']))
    render = render or create_pdf
    try:
        while True:
            with storage.connect() as con:
                con.execute('BEGIN IMMEDIATE')
                current = con.execute('SELECT * FROM import_batches WHERE id=? AND owner=?', (job['id'], owner)).fetchone()
                if not current:
                    return True
                if current['cancel_requested']:
                    con.execute("UPDATE import_batch_items SET state='cancelled' WHERE batch_id=? AND state='queued'", (job['id'],))
                    con.execute("UPDATE import_batches SET state='cancelled',owner='',lease_until=0,updated_at=? WHERE id=?", (_stamp(), job['id']))
                    return True
                item = con.execute("SELECT * FROM import_batch_items WHERE batch_id=? AND state='queued' ORDER BY position LIMIT 1", (job['id'],)).fetchone()
                if not item:
                    con.execute("UPDATE import_batches SET state='completed',owner='',lease_until=0,updated_at=? WHERE id=?", (_stamp(), job['id']))
                    return True
                item = dict(item)
                con.execute("UPDATE import_batch_items SET state='running' WHERE batch_id=? AND position=?", (job['id'], item['position']))
                con.execute('UPDATE import_batches SET lease_until=?,updated_at=? WHERE id=?', (time.time() + LEASE_SECONDS, _stamp(), job['id']))
                existing = con.execute('SELECT id FROM articles WHERE url=?', (item['url'],)).fetchone()
                if existing:
                    con.execute('INSERT OR IGNORE INTO collection_articles VALUES(?,?)', (job['collection_id'], existing['id']))
                    con.execute("UPDATE import_batch_items SET state='existing',article_id=? WHERE batch_id=? AND position=?", (existing['id'], job['id'], item['position']))
                    continue
            try:
                article = fetch(item['url'])
                if not 80 <= article['word_count'] <= 30000:
                    raise ValueError('Reading text must contain 80–30,000 words; the page may be a short excerpt or a long report.')
                article['pdf_path'] = str(render(article))
                with storage.connect() as con:
                    con.execute('BEGIN IMMEDIATE')
                    owned = con.execute("SELECT 1 FROM import_batches WHERE id=? AND owner=? AND state='running'", (job['id'], owner)).fetchone()
                    if not owned:
                        return True
                    # Commit article, collection membership, and item completion
                    # together. A crash cannot mark an unsaved article complete.
                    storage._upsert(con, article)
                    con.execute('INSERT OR IGNORE INTO collection_articles VALUES(?,?)', (job['collection_id'], article['id']))
                    con.execute("UPDATE import_batch_items SET state='saved',article_id=? WHERE batch_id=? AND position=?", (article['id'], job['id'], item['position']))
                    con.execute('UPDATE import_batches SET lease_until=?,updated_at=? WHERE id=?', (time.time() + LEASE_SECONDS, _stamp(), job['id']))
            except Exception as exc:
                failure = failure_details(exc)
                if isinstance(exc, OSError):
                    failure['code'] = 'pdf_failed'
                with storage.connect() as con:
                    con.execute("UPDATE import_batch_items SET state='failed',error=?,error_code=? WHERE batch_id=? AND position=? AND EXISTS "
                                '(SELECT 1 FROM import_batches WHERE id=? AND owner=?)',
                                (failure['message'], failure['code'], job['id'], item['position'], job['id'], owner))
    except Exception:
        with storage.connect() as con:
            con.execute("UPDATE import_batches SET state='failed',error=?,owner='',lease_until=0,updated_at=? WHERE id=? AND owner=?",
                        ('The import worker stopped unexpectedly. Saved articles remain in the collection.', _stamp(), job['id'], owner))
        raise


def ensure_worker():
    """Resume eligible batches after restart and keep one worker per local DB."""
    key = str(storage.DB.resolve())
    with _RUNNERS_LOCK:
        existing = _RUNNERS.get(key)
        if existing and existing.is_alive():
            return
        with storage.connect() as con:
            ready = con.execute("SELECT 1 FROM import_batches WHERE state IN ('queued','running') LIMIT 1").fetchone()
        if not ready:
            return
        def run():
            try:
                owner = uuid.uuid4().hex
                while True:
                    if process_next(owner):
                        continue
                    # A restarted process may encounter a lease that has not
                    # expired yet. Keep waiting off the UI thread so recovery
                    # does not depend on another click or an open search page.
                    with storage.connect() as con:
                        next_lease = con.execute("SELECT MIN(lease_until) FROM import_batches WHERE state IN ('queued','running')").fetchone()[0]
                    if next_lease is None:
                        break
                    time.sleep(min(5.0, max(.1, next_lease - time.time())))
            finally:
                with _RUNNERS_LOCK:
                    if _RUNNERS.get(key) is threading.current_thread():
                        del _RUNNERS[key]
        thread = threading.Thread(target=run, name='article-discovery-import', daemon=True)
        _RUNNERS[key] = thread
        thread.start()
