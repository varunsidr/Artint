"""Versioned JSON/ZIP library backups. No SQL, pickle, archive extraction or network."""
import hashlib
import io
import json
import math
import os
import re
import stat
import tempfile
import uuid
import zipfile
import zlib
from pathlib import Path
from urllib.parse import urlparse

from app import reports, storage
from app.library_actions import FILE_LOCK, clean_tags, managed_pdf_path, portable_id, require_idle_imports, stamp, text_hash

FORMAT = 'article-intelligence-library'
VERSION = 1
MAX_ARCHIVE = 250 * 1024 * 1024
MAX_METADATA = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_PDF = 20 * 1024 * 1024
ARTICLE_FIELDS = ('id', 'url', 'title', 'source', 'author', 'published', 'fetched_at', 'text',
                  'word_count', 'links_json', 'images_json', 'fetch_method', 'quality_json')
TABLES = {
    'articles': (ARTICLE_FIELDS, 10_000),
    'research_collections': (('id', 'title', 'query', 'created_at'), 10_000),
    'collection_articles': (('collection_id', 'article_id'), 200_000),
    'article_notes': (('article_id', 'body', 'updated_at'), 10_000),
    'article_tags': (('article_id', 'tag_key', 'label'), 200_000),
    'article_highlights': (('id', 'article_id', 'text_hash', 'start_offset', 'end_offset', 'quote', 'note', 'created_at'), 200_000),
    'article_insights': (('article_id', 'model', 'content_hash', 'version', 'insight_json'), 100_000),
    'embeddings': (('model', 'text_hash', 'vector_json'), 200_000),
}


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Backup JSON contains duplicate keys.')
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON number.')))
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError('Backup metadata contains invalid JSON.') from exc


def _text(value, limit, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('Backup contains a missing, oversized or invalid text field.')


def _ident(value):
    if not portable_id(value):
        raise ValueError('Backup contains an invalid record ID.')


def _url(value):
    _text(value, 8192)
    try:
        parsed = urlparse(value)
        port = parsed.port
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or any(ord(c) < 32 for c in value):
            raise ValueError
    except ValueError as exc:
        raise ValueError('Backup contains an unsafe source or reference URL.') from exc


def _valid_analysis(value):
    if not isinstance(value, dict) or not isinstance(value.get('topics'), list) or len(value['topics']) > 100:
        raise ValueError('Backup contains an invalid saved analysis.')
    for topic in value['topics']:
        _text(topic, 200)
    points = value.get('key_points')
    if not isinstance(points, list) or len(points) > 100:
        raise ValueError('Backup contains invalid analysis points.')
    for claim in [value.get('summary'), *points]:
        if not isinstance(claim, dict) or not isinstance(claim.get('sources'), list) or len(claim['sources']) > 1000:
            raise ValueError('Backup contains invalid analysis citations.')
        _text(claim.get('text'), 100_000)
        for source in claim['sources']:
            _text(source, 200)
    if 'partial' in value and type(value['partial']) is not bool:
        raise ValueError('Backup contains invalid analysis coverage.')
    if value.get('partial'):
        if any(type(value.get(key)) is not int or not 0 <= value[key] <= 1_000_000 for key in ('passages_analyzed', 'total_passages')):
            raise ValueError('Backup contains invalid analysis passage counts.')
    for key in ('model', 'generated_at'):
        if key in value:
            _text(value[key], 500)


def _validate(data):
    if not isinstance(data, dict) or data.get('format') != FORMAT or type(data.get('version')) is not int or data['version'] != VERSION:
        raise ValueError('Choose an Article Intelligence version-1 library backup.')
    if type(data.get('schema_version')) is not int or data['schema_version'] > storage.SCHEMA_VERSION:
        raise ValueError('This backup requires a newer application version.')
    records = data.get('tables')
    if not isinstance(records, dict) or set(records) != set(TABLES):
        raise ValueError('Backup is missing a required library section.')
    for table, (fields, maximum) in TABLES.items():
        rows = records[table]
        if not isinstance(rows, list) or len(rows) > maximum or any(not isinstance(row, dict) or set(row) != set(fields) for row in rows):
            raise ValueError(f'Backup contains an invalid or oversized {table} section.')
    articles = {}
    urls, portable_ids = set(), set()
    for row in records['articles']:
        _ident(row['id']); _url(row['url'])
        if row['id'].casefold() in portable_ids or row['url'] in urls:
            raise ValueError('Backup contains duplicate articles.')
        portable_ids.add(row['id'].casefold())
        articles[row['id']] = row
        urls.add(row['url'])
        for field, limit in [('title', 2000), ('text', 5_000_000), ('fetched_at', 100)]:
            _text(row[field], limit)
        for field in ('source', 'author', 'published'):
            _text(row[field], 2000, nullable=True)
        if type(row['word_count']) is not int or not 0 <= row['word_count'] <= 10_000_000 or row['fetch_method'] not in ('html', 'browser'):
            raise ValueError('Backup contains invalid capture metadata.')
        _text(row['quality_json'], 32_000)
        quality = _json(row['quality_json'])
        if not isinstance(quality, dict):
            raise ValueError('Backup contains invalid capture checks.')
        if quality and (not isinstance(quality.get('warnings'), list) or len(quality['warnings']) > 100
                        or any(not isinstance(w, dict) or not isinstance(w.get('message'), str) or w.get('severity') not in ('warning', 'info') for w in quality['warnings'])):
            raise ValueError('Backup contains malformed capture warnings.')
        evidence = quality.get('evidence', {})
        if not isinstance(evidence, dict):
            raise ValueError('Backup contains malformed capture evidence.')
        for warning in quality.get('warnings', []):
            _text(warning['message'], 2000)
        if evidence.get('reference_paragraphs'):
            if (type(evidence['reference_paragraphs']) is not int or type(evidence.get('matched_paragraphs')) is not int
                    or not 0 <= evidence['matched_paragraphs'] <= evidence['reference_paragraphs'] <= 2000):
                raise ValueError('Backup contains invalid capture-block counts.')
        for field, maximum in (('links_json', 200), ('images_json', 100)):
            _text(row[field], 2_000_000)
            values = _json(row[field])
            if not isinstance(values, list) or len(values) > maximum:
                raise ValueError('Backup contains invalid article references.')
            for value in values:
                _url(value)
    collections = set()
    for row in records['research_collections']:
        _ident(row['id'])
        if row['id'] in collections:
            raise ValueError('Backup contains duplicate collections.')
        collections.add(row['id'])
        _text(row['title'], 120); _text(row['query'], 1000); _text(row['created_at'], 100)
    seen = {table: set() for table in TABLES}
    highlight_counts, tag_counts = {}, {}
    for table in ('collection_articles', 'article_notes', 'article_tags', 'article_highlights', 'article_insights'):
        for row in records[table]:
            if row['article_id'] not in articles:
                raise ValueError('Backup annotations refer to a missing article.')
            article = articles[row['article_id']]
            key = row['article_id']
            if table == 'collection_articles':
                if row['collection_id'] not in collections:
                    raise ValueError('Backup membership refers to a missing collection.')
                key = (row['collection_id'], key)
            elif table == 'article_notes':
                _text(row['body'], 20_000); _text(row['updated_at'], 100)
            elif table == 'article_tags':
                _text(row['label'], 40); _text(row['tag_key'], 160)
                if clean_tags([row['label']]) != {row['tag_key']: row['label']}:
                    raise ValueError('Backup tag keys do not match their labels.')
                key = (key, row['tag_key'])
                tag_counts[row['article_id']] = tag_counts.get(row['article_id'], 0) + 1
                if tag_counts[row['article_id']] > 20:
                    raise ValueError('Backup exceeds 20 tags per article.')
            elif table == 'article_highlights':
                _ident(row['id']); _text(row['quote'], 5000); _text(row['note'], 5000); _text(row['created_at'], 100)
                if not re.fullmatch(r'[0-9a-f]{64}', str(row['text_hash'])):
                    raise ValueError('Backup contains invalid highlight revisions.')
                start, end = row['start_offset'], row['end_offset']
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= 5_000_000 or end-start != len(row['quote']):
                    raise ValueError('Backup contains an invalid highlight location.')
                if row['text_hash'] == text_hash(article['text']) and article['text'][start:end] != row['quote']:
                    raise ValueError('Backup highlight does not match its saved source.')
                key = row['id']
                location = (row['article_id'], row['text_hash'], start, end)
                if location in seen['articles']:
                    raise ValueError('Backup contains duplicate highlight locations.')
                seen['articles'].add(location)
                highlight_counts[row['article_id']] = highlight_counts.get(row['article_id'], 0) + 1
                if highlight_counts[row['article_id']] > 200:
                    raise ValueError('Backup exceeds 200 highlights per article.')
            else:
                for field in ('model', 'version'):
                    _text(row[field], 256)
                if not re.fullmatch(r'[0-9a-f]{64}', str(row['content_hash'])):
                    raise ValueError('Backup contains an invalid analysis fingerprint.')
                _text(row['insight_json'], 2_000_000)
                _valid_analysis(_json(row['insight_json']))
                key = (key, row['model'])
            if key in seen[table]:
                raise ValueError('Backup contains duplicate annotation records.')
            seen[table].add(key)
    for row in records['embeddings']:
        _text(row['model'], 256); _text(row['vector_json'], 2_000_000)
        if not re.fullmatch(r'[0-9a-f]{64}', str(row['text_hash'])):
            raise ValueError('Backup contains an invalid embedding fingerprint.')
        vector = _json(row['vector_json'])
        if (not isinstance(vector, list) or not 1 <= len(vector) <= 16_384 or not any(vector)
                or any(type(number) not in (int, float) or not math.isfinite(number) for number in vector)):
            raise ValueError('Backup contains invalid cached vectors.')
        key = (row['model'], row['text_hash'])
        if key in seen['embeddings']:
            raise ValueError('Backup contains duplicate vectors.')
        seen['embeddings'].add(key)
    pdfs = data.get('pdfs')
    if not isinstance(pdfs, list) or len(pdfs) > len(articles):
        raise ValueError('Backup contains an invalid PDF manifest.')
    names = set()
    for row in pdfs:
        if not isinstance(row, dict) or set(row) != {'article_id', 'name', 'size', 'sha256'}:
            raise ValueError('Backup contains an invalid PDF entry.')
        if row['article_id'] not in articles or row['name'] != 'pdfs/' + row['article_id'] + '.pdf' or row['name'] in names:
            raise ValueError('Backup contains an unsafe or duplicate PDF path.')
        if type(row['size']) is not int or not 5 <= row['size'] <= MAX_PDF or not re.fullmatch(r'[0-9a-f]{64}', str(row['sha256'])):
            raise ValueError('Backup contains invalid PDF integrity metadata.')
        names.add(row['name'])
    return data


def create_backup():
    output = io.BytesIO()
    with FILE_LOCK:
        with storage.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            require_idle_imports(con)
            data = dict(format=FORMAT, version=VERSION, schema_version=storage.SCHEMA_VERSION, created_at=stamp(), tables={}, pdfs=[], missing_pdfs=[])
            estimated = 0
            for table, (fields, maximum) in TABLES.items():
                if con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] > maximum:
                    raise ValueError(f'This backup exceeds the supported {table} record limit.')
                data['tables'][table] = []
                for row in con.execute('SELECT ' + ','.join(fields) + ' FROM ' + table):
                    item = dict(row)
                    estimated += len(json.dumps(item, ensure_ascii=False).encode())
                    if estimated > MAX_METADATA:
                        raise ValueError('Library metadata exceeds the 128 MB backup limit.')
                    data['tables'][table].append(item)
            paths = {row['id']: managed_pdf_path(dict(row)) for row in con.execute('SELECT id,pdf_path FROM articles')}
            expanded = 0
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
                for article_id, path in paths.items():
                    if not path or not path.is_file():
                        data['missing_pdfs'].append(article_id); continue
                    if path.stat().st_size > MAX_PDF:
                        raise ValueError('A PDF exceeds the 20 MB per-file backup limit.')
                    with path.open('rb') as check:
                        if check.read(5) != b'%PDF-':
                            data['missing_pdfs'].append(article_id); continue
                    name, checksum, size = 'pdfs/' + article_id + '.pdf', hashlib.sha256(), 0
                    with path.open('rb') as source, archive.open(name, 'w') as destination:
                        while chunk := source.read(64 * 1024):
                            size += len(chunk); expanded += len(chunk)
                            if size > MAX_PDF or expanded > MAX_EXPANDED or output.tell() > MAX_ARCHIVE:
                                raise ValueError('Library exceeds the bounded backup size limits.')
                            checksum.update(chunk); destination.write(chunk)
                    data['pdfs'].append(dict(article_id=article_id, name=name, size=size, sha256=checksum.hexdigest()))
                encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
                if len(encoded) > MAX_METADATA or expanded + len(encoded) > MAX_EXPANDED:
                    raise ValueError('Library exceeds the backup metadata or expanded size limit.')
                _validate(data)
                archive.writestr('library.json', encoded)
                if output.tell() > MAX_ARCHIVE:
                    raise ValueError('Backup exceeds the 250 MB download limit.')
    if output.tell() > MAX_ARCHIVE:
        raise ValueError('Backup exceeds the 250 MB download limit.')
    return output.getvalue(), dict(articles=len(data['tables']['articles']), pdfs=len(data['pdfs']), missing_pdfs=len(data['missing_pdfs']))


def inspect_backup(blob):
    if not isinstance(blob, bytes) or len(blob) > MAX_ARCHIVE:
        raise ValueError('Choose a library backup ZIP of at most 250 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if (len(entries) > 10_001 or len(set(names)) != len(names) or 'library.json' not in names
                    or sum(entry.file_size for entry in entries) > MAX_EXPANDED
                    or any(entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16) for entry in entries)):
                raise ValueError('Backup contains duplicate, encrypted, linked or oversized entries.')
            metadata = archive.getinfo('library.json')
            if metadata.file_size > MAX_METADATA:
                raise ValueError('Backup metadata exceeds 128 MB.')
            with archive.open(metadata) as stream:
                raw = stream.read(MAX_METADATA + 1)
            if len(raw) > MAX_METADATA:
                raise ValueError('Backup metadata exceeds 128 MB.')
            data = _validate(_json(raw))
            if set(names) != {'library.json', *[row['name'] for row in data['pdfs']]}:
                raise ValueError('Backup contains unexpected files or unsafe archive paths.')
            for row in data['pdfs']:
                info = archive.getinfo(row['name'])
                if info.file_size != row['size'] or info.file_size > MAX_PDF:
                    raise ValueError('A PDF size does not match the backup manifest.')
                checksum, first = hashlib.sha256(), b''
                with archive.open(info) as stream:
                    while chunk := stream.read(64 * 1024):
                        if not first:
                            first = chunk[:5]
                        checksum.update(chunk)
                if first != b'%PDF-' or checksum.hexdigest() != row['sha256']:
                    raise ValueError('A PDF failed its format or checksum check.')
    except (zipfile.BadZipFile, RuntimeError, EOFError, NotImplementedError, KeyError, TypeError, OverflowError, zlib.error) as exc:
        raise ValueError('This file is not a supported, intact library backup.') from exc
    return data


def _merge_plan(con, data):
    current = {row['id']: dict(row) for row in con.execute('SELECT id,url,text,pdf_path FROM articles')}
    by_url = {row['url']: row for row in current.values()}
    portable_ids = {ident.casefold() for ident in current}
    mapping, new, compatible, changed = {}, [], set(), 0
    for row in data['tables']['articles']:
        existing = by_url.get(row['url'])
        if existing:
            mapping[row['id']] = existing['id']
            if existing['text'] == row['text']:
                compatible.add(row['id'])
            else:
                changed += 1
        elif row['id'].casefold() in portable_ids:
            raise ValueError('A backup article ID belongs to a different existing URL. Restore into a separate empty library.')
        else:
            mapping[row['id']] = row['id']; compatible.add(row['id']); new.append(row)
    return mapping, new, compatible, changed, current


def restore_preview(data):
    with storage.connect() as con:
        require_idle_imports(con)
        mapping, new, compatible, changed, current = _merge_plan(con, data)
    return dict(articles=len(mapping), new=len(new), existing=len(mapping)-len(new), changed_text=changed,
                notes=len(data['tables']['article_notes']), highlights=len(data['tables']['article_highlights']),
                pdfs=len(data['pdfs']))


def restore_backup(blob):
    data = inspect_backup(blob)  # Always verify again at execution, including PDF integrity.
    root = reports.PDF_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    staged, created = [], []
    result = dict(articles=0, notes=0, highlights=0, tags=0, pdfs=0, collections=0, changed_text_skipped=0, annotation_limit_skips=0)
    try:
        with FILE_LOCK, zipfile.ZipFile(io.BytesIO(blob)) as archive, storage.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            require_idle_imports(con)
            mapping, new, compatible, changed, current = _merge_plan(con, data)
            result['changed_text_skipped'] = changed
            new_ids = {row['id'] for row in new}
            pdf_paths = {}
            for pdf in data['pdfs']:
                source_id, target_id = pdf['article_id'], mapping[pdf['article_id']]
                if source_id not in compatible:
                    continue
                target = root/(target_id+'.pdf')
                if target.is_symlink():
                    raise ValueError('A PDF destination is a link; restore was cancelled.')
                existing = current.get(target_id)
                if existing and existing['pdf_path'] and managed_pdf_path(existing) != target:
                    continue  # Never touch an external/custom PDF location.
                if target.exists():
                    if existing and existing['pdf_path']:
                        continue
                    if target.stat().st_size != pdf['size'] or _hash(target.read_bytes()) != pdf['sha256']:
                        raise ValueError('A different file already occupies a PDF destination. Existing files were kept.')
                    pdf_paths[target_id] = str(target)
                    continue
                with tempfile.NamedTemporaryFile(dir=root, prefix='.restore-', suffix='.tmp', delete=False) as stream:
                    path = Path(stream.name); staged.append(path)
                    with archive.open(pdf['name']) as source:
                        while chunk := source.read(64 * 1024):
                            stream.write(chunk)
                    stream.flush(); os.fsync(stream.fileno())
                os.link(path, target)  # No overwrite, even if another process creates the target.
                created.append(target); pdf_paths[target_id] = str(target); result['pdfs'] += 1
            for row in new:
                storage._upsert(con, dict(row, pdf_path=pdf_paths.get(row['id'], '')))
                result['articles'] += 1
            for article_id, path in pdf_paths.items():
                if article_id not in new_ids:
                    con.execute('UPDATE articles SET pdf_path=? WHERE id=?', (path, article_id))
            collection_map = {}
            for row in data['tables']['research_collections']:
                existing = con.execute('SELECT * FROM research_collections WHERE id=?', (row['id'],)).fetchone()
                target_id = row['id']
                if existing and any(existing[field] != row[field] for field in ('title', 'query')):
                    target_id = 'restored-' + _hash(json.dumps([row['id'], row['title'], row['query']]).encode())[:24]
                    existing = con.execute('SELECT * FROM research_collections WHERE id=?', (target_id,)).fetchone()
                    if existing and any(existing[field] != row[field] for field in ('title', 'query')):
                        raise ValueError('A restored collection conflicts with another collection.')
                collection_map[row['id']] = target_id
                if not existing:
                    con.execute('INSERT INTO research_collections VALUES(?,?,?,?)', (target_id, row['title'], row['query'], row['created_at']))
                    result['collections'] += 1
            for row in data['tables']['collection_articles']:
                con.execute('INSERT OR IGNORE INTO collection_articles VALUES(?,?)', (collection_map[row['collection_id']], mapping[row['article_id']]))
            for table in ('article_notes', 'article_tags', 'article_highlights', 'article_insights'):
                fields = TABLES[table][0]
                for original in data['tables'][table]:
                    if original['article_id'] not in compatible:
                        continue
                    row = dict(original, article_id=mapping[original['article_id']])
                    if table == 'article_insights' and row['article_id'] != original['article_id']:
                        continue  # Passage IDs cannot be silently rebased.
                    if table == 'article_notes':
                        existing = con.execute('SELECT body FROM article_notes WHERE article_id=?', (row['article_id'],)).fetchone()
                        if existing and (existing['body'] or not row['body']):
                            continue
                        if existing:
                            con.execute('DELETE FROM article_notes WHERE article_id=?', (row['article_id'],))
                    elif table == 'article_tags':
                        if con.execute('SELECT COUNT(*) FROM article_tags WHERE article_id=?', (row['article_id'],)).fetchone()[0] >= 20:
                            if not con.execute('SELECT 1 FROM article_tags WHERE article_id=? AND tag_key=?', (row['article_id'],row['tag_key'])).fetchone():
                                result['annotation_limit_skips'] += 1
                            continue
                    elif table == 'article_highlights':
                        if con.execute('SELECT COUNT(*) FROM article_highlights WHERE article_id=?', (row['article_id'],)).fetchone()[0] >= 200:
                            if not con.execute('SELECT 1 FROM article_highlights WHERE article_id=? AND text_hash=? AND start_offset=? AND end_offset=?',
                                               (row['article_id'],row['text_hash'],row['start_offset'],row['end_offset'])).fetchone():
                                result['annotation_limit_skips'] += 1
                            continue
                        if con.execute('SELECT 1 FROM article_highlights WHERE id=?', (row['id'],)).fetchone():
                            row['id'] = uuid.uuid4().hex
                    cursor = con.execute('INSERT OR IGNORE INTO ' + table + '('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')', [row[field] for field in fields])
                    key = {'article_notes':'notes','article_tags':'tags','article_highlights':'highlights'}.get(table)
                    if key:
                        result[key] += cursor.rowcount
            for row in data['tables']['embeddings']:
                con.execute('INSERT OR IGNORE INTO embeddings VALUES(?,?,?)', (row['model'], row['text_hash'], row['vector_json']))
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    finally:
        for path in staged:
            path.unlink(missing_ok=True)
    return result
