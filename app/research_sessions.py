"""Explicitly saved immutable research evidence, with bounded storage and no inference."""
from datetime import datetime
import hashlib
import json
import math
import re
import uuid

from app import storage
from app.library_actions import portable_id, stamp
from app.research_export import research_exports

MAX_SESSION_BYTES = 256 * 1024
MAX_SESSIONS = 1000
MAX_TOTAL_BYTES = 64 * 1024 * 1024
FIELDS = ('id', 'snapshot_hash', 'question', 'created_at', 'result_json')


def _text(value, maximum, *, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError('Research contains a missing, invalid or oversized text field.')


def _ident(value):
    if not portable_id(value):
        raise ValueError('Research contains an invalid source identifier.')


def _timestamp(value):
    _text(value, 100, required=True)
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError
    except ValueError:
        raise ValueError('Research timestamps need an ISO date and timezone.') from None


def source_ids(result):
    ids = {passage['article_id'] for passage in result['passages']}
    scope = result.get('source_scope') or {}
    for key in ('selected_article_ids', 'searched_article_ids'):
        ids.update(scope.get(key, []))
    return ids


def validate_result(result):
    """Validate the portable snapshot contract before saving, importing or rendering."""
    if not isinstance(result, dict):
        raise ValueError('Research must be a complete result object.')
    _text(result.get('question'), 2000, required=True)
    try:
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(encoded.encode('utf-8')) > MAX_SESSION_BYTES:
            raise ValueError('Keep a saved research result within 256 KB.')
    except (TypeError, OverflowError, RecursionError) as exc:
        raise ValueError('Research contains invalid JSON metadata.') from exc
    passages, claims = result.get('passages'), result.get('claims', [])
    if not isinstance(passages, list) or len(passages) > 20 or not isinstance(claims, list) or len(claims) > 20:
        raise ValueError('Research has too many passages/claims or incomplete evidence.')
    for passage in passages:
        if not isinstance(passage, dict):
            raise ValueError('Research contains an invalid passage.')
        _ident(passage.get('article_id'))
        for key, maximum in (('id', 200), ('title', 2000), ('url', 8192), ('text', 10_000)):
            _text(passage.get(key), maximum, required=True)
        score = passage.get('score', 0)
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError('Research contains an invalid retrieval score.')
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get('sources'), list) or len(claim['sources']) > 20:
            raise ValueError('Research contains an invalid claim.')
        _text(claim.get('text'), 10_000, required=True)
    if 'model' in result:
        _text(result['model'], 256)
    if 'completed_at' in result:
        _timestamp(result['completed_at'])
    if 'elapsed_seconds' in result:
        elapsed = result['elapsed_seconds']
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('Research contains an invalid duration.')
    if 'retrieval' in result:
        trace = result['retrieval']
        if not isinstance(trace, dict):
            raise ValueError('Research contains invalid retrieval counts.')
        for key, value in trace.items():
            if key == 'retrieval_seconds':
                valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
            else:
                valid = type(value) is int and value >= 0
            if not valid:
                raise ValueError('Research contains invalid retrieval counts or timing.')
    scope = result.get('source_scope', {})
    if not isinstance(scope, dict):
        raise ValueError('Research contains invalid source-selection metadata.')
    for key in ('selected_article_ids', 'searched_article_ids'):
        values = scope.get(key, [])
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError('Research source selections are limited to 100 articles.')
        for ident in values:
            _ident(ident)
        if len(set(values)) != len(values):
            raise ValueError('Research contains duplicate selected sources.')
    fingerprints = scope.get('source_fingerprints', {})
    if not isinstance(fingerprints, dict) or len(fingerprints) > 100:
        raise ValueError('Research contains invalid source revisions.')
    for ident, digest in fingerprints.items():
        _ident(ident)
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Research contains an invalid source fingerprint.')
    if len(source_ids(result)) > 100 or set(fingerprints) - source_ids(result):
        raise ValueError('Research source revisions do not match its selection.')
    # Also checks citation identities, answer status and safe international URLs.
    research_exports(result)
    return encoded


def validate_record(row):
    if not isinstance(row, dict) or set(row) != set(FIELDS):
        raise ValueError('Saved research has an invalid record shape.')
    _ident(row['id']); _timestamp(row['created_at'])
    raw = row['result_json']
    _text(raw, MAX_SESSION_BYTES)
    try:
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('Research JSON contains duplicate keys.')
                value[key] = item
            return value
        result = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Saved research contains invalid JSON.') from exc
    encoded = validate_result(result)
    if row['question'] != result['question'] or row['snapshot_hash'] != hashlib.sha256(encoded.encode('utf-8')).hexdigest():
        raise ValueError('Saved research failed its snapshot integrity check.')
    return result, encoded


def insert_record(con, row, mapping):
    """Insert within the caller's write transaction; never replace saved evidence."""
    result, encoded = validate_record(row)
    if set(mapping) != source_ids(result):
        raise ValueError('Saved research source links do not match its original selection.')
    for value in mapping.values():
        _ident(value)
    if mapping:
        existing_sources = {r[0] for r in con.execute('SELECT id FROM articles WHERE id IN ('
            + ','.join('?' for _ in mapping) + ')', list(mapping.values()))}
        if set(mapping.values()) != existing_sources:
            raise ValueError('Some source articles were removed. This result cannot be saved.')
    found = con.execute('SELECT id FROM research_sessions WHERE snapshot_hash=?', (row['snapshot_hash'],)).fetchone()
    if found:
        return found['id'], False
    used = con.execute('SELECT COUNT(*),COALESCE(SUM(length(CAST(result_json AS BLOB))),0) FROM research_sessions').fetchone()
    if used[0] >= MAX_SESSIONS or used[1] + len(encoded.encode('utf-8')) > MAX_TOTAL_BYTES:
        raise ValueError('Saved research limit reached (1,000 results / 64 MB). Export and delete older results first.')
    ident = row['id']
    if con.execute('SELECT 1 FROM research_sessions WHERE id=?', (ident,)).fetchone():
        ident = uuid.uuid4().hex
    con.execute('INSERT INTO research_sessions VALUES(?,?,?,?,?)',
                (ident, row['snapshot_hash'], row['question'], row['created_at'], encoded))
    con.executemany('INSERT INTO research_session_sources VALUES(?,?,?)',
                    [(ident, source, target) for source, target in sorted(mapping.items())])
    return ident, True


def save_result(result):
    encoded = validate_result(result)
    row = dict(id=uuid.uuid4().hex, snapshot_hash=hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
               question=result['question'], created_at=stamp(), result_json=encoded)
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        ident, _ = insert_record(con, row, {source: source for source in source_ids(result)})
    return ident


def revision():
    with storage.connect() as con:
        return con.execute('SELECT revision FROM research_state WHERE id=1').fetchone()[0]


def sessions_page(query='', page=1, page_size=20):
    _text(query, 256)
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 50:
        raise ValueError('Choose a valid saved-research page.')
    escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    where = " WHERE question LIKE ? ESCAPE '\\'" if query else ''
    parameters = ['%' + escaped + '%'] if query else []
    with storage.connect() as con:
        con.execute('BEGIN')
        total = con.execute('SELECT COUNT(*) FROM research_sessions' + where, parameters).fetchone()[0]
        pages = max(1, (total + page_size - 1) // page_size); page = min(page, pages)
        rows = [dict(row) for row in con.execute('SELECT id,question,created_at FROM research_sessions'
            + where + ' ORDER BY created_at DESC,id LIMIT ? OFFSET ?', parameters + [page_size, (page-1)*page_size])]
    return dict(items=rows, total=total, page=page, pages=pages)


def load_session(ident):
    _ident(ident)
    with storage.connect() as con:
        con.execute('BEGIN')
        row = con.execute('SELECT * FROM research_sessions WHERE id=?', (ident,)).fetchone()
        if not row:
            return None
        result, _ = validate_record(dict(row))
        expected = result.get('source_scope', {}).get('source_fingerprints', {})
        sources = [dict(row) for row in con.execute('''SELECT r.source_id,r.article_id,a.content_hash
            FROM research_session_sources r JOIN articles a ON a.id=r.article_id WHERE session_id=?''', (ident,))]
        if {source['source_id'] for source in sources} != source_ids(result):
            raise ValueError('Saved research has missing or invalid source links.')
    changed = sum(source['source_id'] == source['article_id'] and source['source_id'] in expected
                  and source['content_hash'] != expected[source['source_id']] for source in sources)
    unknown = sum(source['source_id'] not in expected or source['source_id'] != source['article_id'] for source in sources)
    return dict(id=ident, created_at=row['created_at'], result=result, changed_sources=changed, unverified_sources=unknown)


def delete_session(ident):
    _ident(ident)
    with storage.connect() as con:
        con.execute('DELETE FROM research_sessions WHERE id=?', (ident,))


def article_session_count(article_id):
    with storage.connect() as con:
        return con.execute('SELECT COUNT(DISTINCT session_id) FROM research_session_sources WHERE article_id=?', (article_id,)).fetchone()[0]
