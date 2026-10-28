"""Personal annotations and managed, recoverable single-article deletion."""
import hashlib
import os
import re
import unicodedata
import uuid
import threading
from functools import wraps
from datetime import datetime, timezone
from pathlib import Path

from app import reports, storage

MAX_NOTES = 20_000
MAX_HIGHLIGHTS = 200
FILE_LOCK = threading.RLock()
RESERVED_FILE_IDS = {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(number) for number in range(1, 10)),
                     *('LPT' + str(number) for number in range(1, 10))}


def portable_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value)) and value.upper() not in RESERVED_FILE_IDS


def serialized_files(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with FILE_LOCK:
            return function(*args, **kwargs)
    return wrapped


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def clean_tags(value):
    labels = value.split(',') if isinstance(value, str) else list(value)
    result = {}
    for label in labels:
        label = ' '.join(unicodedata.normalize('NFKC', str(label)).split())
        if not label:
            continue
        if len(label) > 40 or any(ord(char) < 32 for char in label):
            raise ValueError('Use tags of at most 40 characters.')
        if ',' in label:
            raise ValueError('Use commas to separate tags, rather than inside a tag.')
        result.setdefault(label.casefold(), label)
    if len(result) > 20:
        raise ValueError('Use up to 20 tags per article.')
    return result


def annotation_state(article_id):
    with storage.connect() as con:
        article = con.execute('SELECT text FROM articles WHERE id=?', (article_id,)).fetchone()
        if not article:
            raise ValueError('This article is no longer in the library.')
        note = con.execute('SELECT body FROM article_notes WHERE article_id=?', (article_id,)).fetchone()
        tags = [row['label'] for row in con.execute('SELECT label FROM article_tags WHERE article_id=? ORDER BY tag_key', (article_id,))]
        members = [row[0] for row in con.execute('SELECT collection_id FROM collection_articles WHERE article_id=?', (article_id,))]
        highlights = [dict(row) for row in con.execute('SELECT * FROM article_highlights WHERE article_id=? ORDER BY start_offset,created_at', (article_id,))]
    current_hash = text_hash(article['text'])
    for item in highlights:
        item['current'] = item['text_hash'] == current_hash and article['text'][item['start_offset']:item['end_offset']] == item['quote']
    return dict(note=note['body'] if note else '', tags=tags, collections=members, highlights=highlights)


def save_organization(article_id, *, note, tags, collection_ids, new_collection=''):
    if not isinstance(note, str) or len(note) > MAX_NOTES:
        raise ValueError('Keep article notes within 20,000 characters.')
    normalized = clean_tags(tags)
    members = list(dict.fromkeys(collection_ids))
    if len(members) > 100:
        raise ValueError('Use up to 100 collections per article.')
    title = new_collection.strip()
    if len(title) > 120:
        raise ValueError('Collection names can contain up to 120 characters.')
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if not con.execute('SELECT 1 FROM articles WHERE id=?', (article_id,)).fetchone():
            raise ValueError('This article is no longer in the library.')
        known = {row[0] for row in con.execute('SELECT id FROM research_collections')}
        if any(member not in known for member in members):
            raise ValueError('A collection changed. Reopen the article and try again.')
        if title:
            existing = next((row for row in con.execute('SELECT id,title FROM research_collections') if row['title'].casefold() == title.casefold()), None)
            collection_id = existing['id'] if existing else 'project-' + uuid.uuid4().hex
            if not existing:
                con.execute('INSERT INTO research_collections VALUES(?,?,?,?)', (collection_id, title, '', stamp()))
            if collection_id not in members:
                members.append(collection_id)
        if len(members) > 100:
            raise ValueError('Use up to 100 collections per article.')
        con.execute('''INSERT INTO article_notes VALUES(?,?,?) ON CONFLICT(article_id) DO UPDATE
            SET body=excluded.body,updated_at=excluded.updated_at''', (article_id, note, stamp()))
        con.execute('DELETE FROM article_tags WHERE article_id=?', (article_id,))
        con.executemany('INSERT INTO article_tags VALUES(?,?,?)', [(article_id, key, label) for key, label in normalized.items()])
        con.execute('DELETE FROM collection_articles WHERE article_id=?', (article_id,))
        con.executemany('INSERT INTO collection_articles VALUES(?,?)', [(member, article_id) for member in members])


def add_highlight(article_id, quote, *, note='', occurrence=0, expected_text_hash=None):
    if not isinstance(quote, str) or not 3 <= len(quote) <= 5000 or not quote.strip():
        raise ValueError('Choose a passage of 3–5,000 characters from the saved article.')
    if not isinstance(note, str) or len(note) > 5000:
        raise ValueError('Keep highlight notes within 5,000 characters.')
    if not isinstance(occurrence, int) or isinstance(occurrence, bool) or not 0 <= occurrence < 200:
        raise ValueError('Choose a valid occurrence of the passage.')
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT text FROM articles WHERE id=?', (article_id,)).fetchone()
        if not row:
            raise ValueError('This article is no longer in the library.')
        content = row['text']
        fingerprint = text_hash(content)
        if expected_text_hash and fingerprint != expected_text_hash:
            raise ValueError('The saved text changed. Reopen the article before highlighting.')
        start, cursor = -1, 0
        for _ in range(occurrence + 1):
            start = content.find(quote, cursor)
            if start < 0:
                raise ValueError('The passage must match the saved text exactly. Try selecting a shorter phrase.')
            cursor = start + 1
        existing = con.execute('SELECT id FROM article_highlights WHERE article_id=? AND text_hash=? AND start_offset=? AND end_offset=?',
                               (article_id, fingerprint, start, start + len(quote))).fetchone()
        if existing:
            con.execute('UPDATE article_highlights SET note=? WHERE id=?', (note, existing['id']))
            return existing['id']
        if con.execute('SELECT COUNT(*) FROM article_highlights WHERE article_id=?', (article_id,)).fetchone()[0] >= MAX_HIGHLIGHTS:
            raise ValueError('This article already has 200 highlights. Remove one before adding another.')
        highlight_id = uuid.uuid4().hex
        con.execute('INSERT INTO article_highlights VALUES(?,?,?,?,?,?,?,?)',
                    (highlight_id, article_id, fingerprint, start, start + len(quote), quote, note, stamp()))
        return highlight_id


def remove_highlight(article_id, highlight_id):
    with storage.connect() as con:
        con.execute('DELETE FROM article_highlights WHERE article_id=? AND id=?', (article_id, highlight_id))


def update_highlight_note(article_id, highlight_id, note):
    if not isinstance(note, str) or len(note) > 5000:
        raise ValueError('Keep highlight notes within 5,000 characters.')
    with storage.connect() as con:
        if not con.execute('UPDATE article_highlights SET note=? WHERE article_id=? AND id=?', (note, article_id, highlight_id)).rowcount:
            raise ValueError('This highlight is no longer available.')


def managed_pdf_path(article):
    """Only the exact managed <id>.pdf may be read, restored or deleted."""
    if not portable_id(article.get('id', '')) or not article.get('pdf_path'):
        return None
    root = reports.PDF_DIR.resolve()
    candidate = Path(article['pdf_path'])
    if candidate.is_symlink():
        return None
    candidate = candidate.resolve()
    return candidate if candidate.parent == root and candidate.name == article['id'] + '.pdf' else None


def require_idle_imports(con):
    if con.execute("SELECT 1 FROM import_batches WHERE state IN ('queued','running') LIMIT 1").fetchone():
        raise ValueError('Finish or stop active imports before deleting or restoring library data.')


@serialized_files
def recover_pending_deletions():
    """Recover only files recorded by our deletion journal; never scan unrelated files."""
    pending = 0
    with storage.connect() as con:
        operations = [dict(row) for row in con.execute('SELECT * FROM pending_pdf_deletions LIMIT 50')]
    for operation in operations:
        ident, article_id = operation['id'], operation['article_id']
        if not re.fullmatch(r'[a-f0-9]{32}', ident) or not portable_id(article_id):
            pending += 1; continue
        target = reports.PDF_DIR.resolve() / (article_id + '.pdf')
        stage = target.parent / ('.delete-' + ident + '-' + article_id + '.pdf')
        if operation['target_name'] != target.name or operation['staged_name'] != stage.name or target.is_symlink() or stage.is_symlink():
            pending += 1; continue
        try:
            with storage.connect() as con:
                con.execute('BEGIN IMMEDIATE')
                exists = con.execute('SELECT 1 FROM articles WHERE id=?', (article_id,)).fetchone()
                if exists and stage.exists():
                    if target.exists():
                        pending += 1; continue
                    os.link(stage, target)  # Exclusive creation; no existing target is overwritten.
                    stage.unlink()
                elif not exists:
                    stage.unlink(missing_ok=True)
                con.execute('DELETE FROM pending_pdf_deletions WHERE id=?', (ident,))
        except OSError:
            pending += 1
    return pending


@serialized_files
def delete_article(article_id):
    recover_pending_deletions()
    operation_id, target, stage = None, None, None
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        require_idle_imports(con)
        row = con.execute('SELECT * FROM articles WHERE id=?', (article_id,)).fetchone()
        if not row:
            raise ValueError('This article is no longer in the library.')
        original = dict(row)
        target = managed_pdf_path(original)
        if target and con.execute("SELECT 1 FROM articles WHERE id<>? AND replace(pdf_path,char(92),'/')=? COLLATE NOCASE LIMIT 1",
                                  (article_id, target.as_posix())).fetchone():
            target = None  # A legacy/shared reference must keep its PDF.
        if target and target.is_file():
            operation_id = uuid.uuid4().hex
            stage = target.parent / ('.delete-' + operation_id + '-' + article_id + '.pdf')
            con.execute('INSERT INTO pending_pdf_deletions VALUES(?,?,?,?)', (operation_id, article_id, target.name, stage.name))
    try:
        with storage.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            require_idle_imports(con)
            current = con.execute('SELECT * FROM articles WHERE id=?', (article_id,)).fetchone()
            if not current or dict(current) != original:
                raise ValueError('This article changed. Reopen it before deleting.')
            if stage:
                if stage.exists() or stage.is_symlink():
                    raise ValueError('PDF deletion staging conflict. Try again after recovery.')
                target.rename(stage)
            con.execute('DELETE FROM article_insights WHERE article_id=?', (article_id,))
            con.execute('DELETE FROM articles WHERE id=?', (article_id,))
    except Exception:
        recover_pending_deletions()
        raise
    pending = recover_pending_deletions()
    return {'deleted': article_id, 'pdf_removed': bool(stage), 'cleanup_pending': pending}
