import json
import hashlib
import sqlite3
import re
import os
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.facets import FACET_VERSION, extract_facets

DB = Path(os.getenv('ARTICLE_LIBRARY_DB', str(Path(__file__).resolve().parents[1] / 'data' / 'articles.db')))

SCHEMA_VERSION = 6
SORTS = {
    'Newest saved': 'a.fetched_at DESC, a.id DESC',
    'Oldest saved': 'a.fetched_at ASC, a.id ASC',
    'Newest published': 'date(a.published) IS NULL, date(a.published) DESC, a.id DESC',
    'Oldest published': 'date(a.published) IS NULL, date(a.published) ASC, a.id ASC',
    'Title A–Z': 'a.title COLLATE NOCASE ASC, a.id ASC',
    'Longest read': 'a.word_count DESC, a.id DESC',
    'Shortest read': 'a.word_count ASC, a.id ASC',
}


def _publisher_key(article):
    return (article.get('source') or urlparse(article.get('url', '')).hostname or 'Unknown').removeprefix('www.')


def _migrate(con):
    """Transactional first migration, with a consistent backup of existing data."""
    con.execute('BEGIN IMMEDIATE')
    try:
        current_version = con.execute('PRAGMA user_version').fetchone()[0]
        if current_version >= SCHEMA_VERSION:
            con.commit()
            return
        existing = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'").fetchone()
        if existing:
            backups = DB.parent / 'backups'
            backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            # A separate reader can back up the last committed snapshot while this
            # connection holds the write reservation, before any schema changes.
            with closing(sqlite3.connect(DB)) as source, closing(sqlite3.connect(backups / f'{DB.stem}-before-v{SCHEMA_VERSION}-{stamp}.db')) as target:
                source.backup(target)
        if current_version == 0:
            _create_schema(con)
            columns = {row['name'] for row in con.execute('PRAGMA table_info(articles)')}
            if 'content_hash' not in columns:
                con.execute("ALTER TABLE articles ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
            if 'publisher_key' not in columns:
                con.execute("ALTER TABLE articles ADD COLUMN publisher_key TEXT NOT NULL DEFAULT 'Unknown'")
            cursor = con.execute('SELECT * FROM articles')
            while rows := cursor.fetchmany(100):
                con.executemany('UPDATE articles SET content_hash=?, publisher_key=? WHERE id=?',
                                [(article_fingerprint(dict(row)), _publisher_key(dict(row)), row['id']) for row in rows])
            con.execute('CREATE INDEX articles_saved_idx ON articles(fetched_at DESC, id DESC)')
            con.execute('CREATE INDEX articles_publisher_idx ON articles(publisher_key, fetched_at DESC, id DESC)')
            con.execute('CREATE INDEX articles_title_idx ON articles(title COLLATE NOCASE, id)')
            con.execute('CREATE INDEX articles_length_idx ON articles(word_count DESC, id DESC)')
            con.execute('CREATE TABLE library_state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL)')
            con.execute('INSERT INTO library_state VALUES(1, 1)')
            con.execute("""CREATE VIRTUAL TABLE articles_fts USING fts5(
                title, author, publisher_key, text, content='articles', content_rowid='rowid',
                tokenize='unicode61 remove_diacritics 2', prefix='2 3 4')""")
            con.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
            for operation in ('insert', 'delete', 'update'):
                delete = """INSERT INTO articles_fts(articles_fts,rowid,title,author,publisher_key,text)
                    VALUES('delete',old.rowid,old.title,old.author,old.publisher_key,old.text);""" if operation != 'insert' else ''
                insert = """INSERT INTO articles_fts(rowid,title,author,publisher_key,text)
                    VALUES(new.rowid,new.title,new.author,new.publisher_key,new.text);""" if operation != 'delete' else ''
                con.execute(f'''CREATE TRIGGER articles_fts_{operation} AFTER {operation.upper()} ON articles BEGIN
                    {delete} {insert} UPDATE library_state SET revision=revision+1 WHERE id=1; END''')
            for operation in ('INSERT', 'UPDATE', 'DELETE'):
                con.execute(f'''CREATE TRIGGER insights_revision_{operation.lower()} AFTER {operation} ON article_insights
                    BEGIN UPDATE library_state SET revision=revision+1 WHERE id=1; END''')
        if current_version < 2:
            _create_observatory_schema(con)
        _create_import_schema(con)
        for table, column, default in (('articles', 'fetch_method', 'html'),
                                       ('import_batches', 'fetch_mode', 'auto'),
                                       ('articles', 'quality_json', '{}'),
                                       ('import_batch_items', 'error_code', '')):
            columns = {row['name'] for row in con.execute(f'PRAGMA table_info({table})')}
            if column not in columns:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
        if current_version < 6:
            _create_personal_schema(con)
        con.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        con.commit()
    except Exception:
        con.rollback()
        raise


def _cache_facets(con, article):
    fingerprint = article.get('content_hash') or article_fingerprint(article)
    row = con.execute('SELECT content_hash,version FROM article_facets WHERE article_id=?', (article['id'],)).fetchone()
    if row and row['content_hash'] == fingerprint and row['version'] == FACET_VERSION:
        return
    con.execute('''INSERT INTO article_facets(article_id,content_hash,version,signals_json) VALUES(?,?,?,?)
        ON CONFLICT(article_id) DO UPDATE SET content_hash=excluded.content_hash,version=excluded.version,
        signals_json=excluded.signals_json''',
        (article['id'], fingerprint, FACET_VERSION, json.dumps(extract_facets(article), ensure_ascii=False)))


def _create_observatory_schema(con):
    con.execute('''CREATE TABLE research_collections(
        id TEXT PRIMARY KEY,title TEXT NOT NULL,query TEXT NOT NULL,created_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE collection_articles(collection_id TEXT NOT NULL,article_id TEXT NOT NULL,
        PRIMARY KEY(collection_id,article_id),
        FOREIGN KEY(collection_id) REFERENCES research_collections(id) ON DELETE CASCADE,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE)''')
    con.execute('CREATE INDEX collection_article_idx ON collection_articles(article_id)')
    con.execute('''CREATE TABLE article_facets(article_id TEXT PRIMARY KEY,content_hash TEXT NOT NULL,
        version TEXT NOT NULL,signals_json TEXT NOT NULL,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE)''')
    for table in ('collection_articles', 'article_facets', 'research_collections'):
        for operation in ('INSERT', 'UPDATE', 'DELETE'):
            con.execute(f'''CREATE TRIGGER {table}_revision_{operation.lower()} AFTER {operation} ON {table}
                BEGIN UPDATE library_state SET revision=revision+1 WHERE id=1; END''')
    cursor = con.execute('SELECT * FROM articles')
    while rows := cursor.fetchmany(50):
        for row in rows:
            _cache_facets(con, dict(row))


def _create_import_schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS import_batches(
        id TEXT PRIMARY KEY,title TEXT NOT NULL,query TEXT NOT NULL,collection_id TEXT NOT NULL,
        state TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
        cancel_requested INTEGER NOT NULL DEFAULT 0,owner TEXT NOT NULL DEFAULT '',
        lease_until REAL NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '')''')
    con.execute('''CREATE TABLE IF NOT EXISTS import_batch_items(
        batch_id TEXT NOT NULL,position INTEGER NOT NULL,url TEXT NOT NULL,state TEXT NOT NULL,
        article_id TEXT NOT NULL DEFAULT '',error TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(batch_id,position),UNIQUE(batch_id,url),
        FOREIGN KEY(batch_id) REFERENCES import_batches(id) ON DELETE CASCADE)''')
    con.execute('CREATE INDEX IF NOT EXISTS import_batch_state_idx ON import_batches(state,lease_until)')


def _create_personal_schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS article_notes(article_id TEXT PRIMARY KEY,body TEXT NOT NULL,
        updated_at TEXT NOT NULL,FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE)''')
    con.execute('''CREATE TABLE IF NOT EXISTS article_tags(article_id TEXT NOT NULL,tag_key TEXT NOT NULL,
        label TEXT NOT NULL,PRIMARY KEY(article_id,tag_key),
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE)''')
    con.execute('CREATE INDEX IF NOT EXISTS article_tag_idx ON article_tags(tag_key,article_id)')
    con.execute('''CREATE TABLE IF NOT EXISTS article_highlights(id TEXT PRIMARY KEY,article_id TEXT NOT NULL,
        text_hash TEXT NOT NULL,start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,quote TEXT NOT NULL,
        note TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(article_id,text_hash,start_offset,end_offset),
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE)''')
    con.execute('CREATE INDEX IF NOT EXISTS article_highlight_idx ON article_highlights(article_id,start_offset)')
    con.execute('''CREATE TABLE IF NOT EXISTS pending_pdf_deletions(id TEXT PRIMARY KEY,article_id TEXT NOT NULL,
        target_name TEXT NOT NULL,staged_name TEXT NOT NULL)''')
    for table in ('article_notes', 'article_tags', 'article_highlights'):
        for operation in ('INSERT', 'UPDATE', 'DELETE'):
            con.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_revision_{operation.lower()} AFTER {operation} ON {table}
                BEGIN UPDATE library_state SET revision=revision+1 WHERE id=1; END''')


def create_collection(collection_id, title, query):
    with connect() as con:
        con.execute('''INSERT INTO research_collections VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE
            SET title=excluded.title,query=excluded.query''',
            (collection_id, title, query, datetime.now(timezone.utc).isoformat(timespec='seconds')))


def _create_schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
        source TEXT, author TEXT, published TEXT, fetched_at TEXT NOT NULL,
        text TEXT NOT NULL, word_count INTEGER NOT NULL, links_json TEXT NOT NULL,
        images_json TEXT NOT NULL, pdf_path TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS article_insights (
        article_id TEXT NOT NULL, model TEXT NOT NULL, content_hash TEXT NOT NULL,
        version TEXT NOT NULL, insight_json TEXT NOT NULL,
        PRIMARY KEY (article_id, model)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS embeddings (
        model TEXT NOT NULL, text_hash TEXT NOT NULL, vector_json TEXT NOT NULL,
        PRIMARY KEY (model, text_hash)
    )""")


@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=15)
    con.execute('PRAGMA foreign_keys=ON')
    con.row_factory = sqlite3.Row
    try:
        version = con.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError('This library was created by a newer application version.')
        if version < SCHEMA_VERSION:
            _migrate(con)
        with con:
            yield con
    finally:
        con.close()

def upsert(article, *, collection_id=None):
    with connect() as con:
        _upsert(con, article)
        if collection_id:
            con.execute('INSERT OR IGNORE INTO collection_articles(collection_id,article_id) VALUES(?,?)', (collection_id,article['id']))


def upsert_many(articles):
    """Stream a batch through one transaction (also used by isolated load tests)."""
    count = 0
    with connect() as con:
        for article in articles:
            _upsert(con, article)
            count += 1
    return count


def _upsert(con, article):
    article = dict(article, content_hash=article_fingerprint(article), publisher_key=_publisher_key(article),
                   fetch_method=article.get('fetch_method', 'html'), quality_json=article.get('quality_json', '{}'))
    quality = json.loads(article['quality_json'])
    if not isinstance(quality, dict) or len(article['quality_json']) > 32_000:
        raise ValueError('Capture diagnostics must be a bounded JSON object.')
    con.execute("""INSERT INTO articles
            (id,url,title,source,author,published,fetched_at,text,word_count,links_json,images_json,pdf_path,content_hash,publisher_key,fetch_method,quality_json)
            VALUES (:id,:url,:title,:source,:author,:published,:fetched_at,:text,:word_count,:links_json,:images_json,:pdf_path,:content_hash,:publisher_key,:fetch_method,:quality_json)
            ON CONFLICT(url) DO UPDATE SET title=excluded.title,source=excluded.source,
            author=excluded.author,published=excluded.published,fetched_at=excluded.fetched_at,
            text=excluded.text,word_count=excluded.word_count,links_json=excluded.links_json,
            images_json=excluded.images_json,pdf_path=excluded.pdf_path,
            content_hash=excluded.content_hash,publisher_key=excluded.publisher_key,fetch_method=excluded.fetch_method,
            quality_json=excluded.quality_json""", article)
    _cache_facets(con, article)

def all_articles():
    with connect() as con:
        return [dict(row) for row in con.execute("SELECT * FROM articles ORDER BY fetched_at DESC")]


def get_article(article_id):
    with connect() as con:
        row = con.execute('SELECT * FROM articles WHERE id=?', (article_id,)).fetchone()
        return dict(row) if row else None


def load_articles(article_ids):
    ids = list(dict.fromkeys(article_ids))
    if len(ids) > 100:
        raise ValueError('Research up to 100 selected articles at a time.')
    if not ids:
        return []
    with connect() as con:
        rows = {row['id']: dict(row) for row in con.execute(
            f'SELECT * FROM articles WHERE id IN ({",".join("?" for _ in ids)})', ids)}
    return [rows[value] for value in ids if value in rows]


def _search_expression(query):
    if len(query) > 256:
        raise ValueError('Search must be 256 characters or fewer.')
    words = re.findall(r'[^\W_]+', query, flags=re.UNICODE)
    # Treat user input as literal word prefixes; never expose the FTS query language.
    return ' AND '.join('"' + word + '"*' for word in words[:32])


def _library_query(query='', sources=None, status='All articles', topics=None,
                   model='qwen3:8b', version='1', collection_id=None, lens=None, entity=None,
                   start_date=None, end_date=None, month=None, include_facets=False,
                   min_words=None, max_words=None, date_status=None, tags=None):
    if len(query) > 256:
        raise ValueError('Search must be 256 characters or fewer.')
    sql = '''FROM articles a LEFT JOIN article_insights s ON s.article_id=a.id
        AND s.model=? AND s.version=? AND s.content_hash=a.content_hash'''
    parameters = [model, version]
    if include_facets or lens or entity:
        sql += ''' LEFT JOIN article_facets f ON f.article_id=a.id
            AND f.content_hash=a.content_hash AND f.version=?'''
        parameters.append(FACET_VERSION)
    clauses = []
    for field, value, operator in (('word_count', min_words, '>='), ('word_count', max_words, '<=')):
        if value is not None:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError('Word-count bounds must be non-negative integers.')
            clauses.append(f'a.{field}{operator}?')
            parameters.append(value)
    if date_status == 'dated':
        clauses.append('date(a.published) IS NOT NULL')
    elif date_status == 'undated':
        clauses.append('date(a.published) IS NULL')
    elif date_status is not None:
        raise ValueError('Unknown publication-date filter.')
    if collection_id:
        clauses.append('a.id IN (SELECT article_id FROM collection_articles WHERE collection_id=?)')
        parameters.append(collection_id)
    for key, value in (('lenses', lens), ('entities', entity)):
        if value:
            clauses.append(f"EXISTS (SELECT 1 FROM json_each(f.signals_json,'$.{key}') WHERE value=?)")
            parameters.append(value)
    if start_date:
        clauses.append('date(a.published)>=date(?)')
        parameters.append(start_date)
    if end_date:
        clauses.append('(date(a.published) IS NULL OR date(a.published)<=date(?))')
        parameters.append(end_date)
    if month:
        clauses.append('substr(a.published,1,7)=?')
        parameters.append(month)
    if query.strip():
        expression = _search_expression(query)
        if expression:
            clauses.append('a.rowid IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?)')
            parameters.append(expression)
        else:
            clauses.append('0')
    if sources is not None:
        if sources:
            clauses.append('a.publisher_key IN (' + ','.join('?' for _ in sources) + ')')
            parameters.extend(sources)
        else:
            clauses.append('0')
    if status == 'Analyzed':
        clauses.append('s.article_id IS NOT NULL')
    elif status == 'Needs analysis':
        clauses.append('s.article_id IS NULL')
    elif status != 'All articles':
        raise ValueError('Unknown analysis filter.')
    if topics:
        clauses.append('EXISTS (SELECT 1 FROM json_each(s.insight_json, \'$.topics\') '
                       'WHERE value IN (' + ','.join('?' for _ in topics) + '))')
        parameters.extend(topics)
    if tags:
        if len(tags) > 20 or any(not isinstance(tag, str) or len(tag) > 160 for tag in tags):
            raise ValueError('Filter with up to 20 personal tags.')
        clauses.append('EXISTS (SELECT 1 FROM article_tags t WHERE t.article_id=a.id AND t.tag_key IN ('
                       + ','.join('?' for _ in tags) + '))')
        parameters.extend(tags)
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    return sql, parameters


def library_page(*, page=1, page_size=25, sort='Newest saved', **filters):
    if not 1 <= page_size <= 100:
        raise ValueError('Page size must be between 1 and 100.')
    if sort not in SORTS:
        raise ValueError('Unknown article sort.')
    sql, parameters = _library_query(**filters)
    with connect() as con:
        con.execute('BEGIN')
        total = con.execute('SELECT COUNT(*) ' + sql, parameters).fetchone()[0]
        pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(int(page), pages))
        rows = con.execute('''SELECT a.id,a.url,a.title,a.source,a.author,a.published,
            a.fetched_at,a.word_count,a.pdf_path,substr(a.text,1,240) AS excerpt,s.insight_json '''
            + sql + ' ORDER BY ' + SORTS[sort] + ' LIMIT ? OFFSET ?',
            parameters + [page_size, (page - 1) * page_size]).fetchall()
        items = []
        tag_labels = {}
        if rows:
            identifiers = [row['id'] for row in rows]
            for tagged in con.execute('SELECT article_id,label FROM article_tags WHERE article_id IN ('
                                      + ','.join('?' for _ in identifiers) + ') ORDER BY article_id,tag_key', identifiers):
                tag_labels.setdefault(tagged['article_id'], []).append(tagged['label'])
        for row in rows:
            item = dict(row)
            encoded = item.pop('insight_json')
            item['insight'] = json.loads(encoded) if encoded else None
            item['tags'] = tag_labels.get(item['id'], [])
            items.append(item)
    return dict(items=items, total=total, pages=pages, page=page, page_size=page_size)


def library_overview(model='qwen3:8b', version='1'):
    sql, parameters = _library_query(model=model, version=version)
    with connect() as con:
        con.execute('BEGIN')
        stats = dict(con.execute('''SELECT COUNT(*) AS total, COALESCE(SUM(a.word_count),0) AS words,
            COUNT(s.article_id) AS analyzed ''' + sql, parameters).fetchone())
        stats['publishers'] = [row[0] for row in con.execute('SELECT DISTINCT publisher_key FROM articles ORDER BY publisher_key')]
        stats['topics'] = [row[0] for row in con.execute('''SELECT j.value,COUNT(*) AS uses
            FROM articles a JOIN article_insights s ON a.id=s.article_id AND a.content_hash=s.content_hash,
            json_each(s.insight_json,'$.topics') j WHERE s.model=? AND s.version=?
            GROUP BY j.value ORDER BY uses DESC,j.value LIMIT 100''', (model, version))]
        stats['revision'] = con.execute('SELECT revision FROM library_state WHERE id=1').fetchone()[0]
        stats['tags'] = {row['tag_key']: row['label'] for row in con.execute('SELECT tag_key,MIN(label) AS label FROM article_tags GROUP BY tag_key ORDER BY tag_key')}
    return stats


def metadata_rows(*, sort='Newest saved', **filters):
    """Stream metadata only, for explicitly requested exports."""
    if sort not in SORTS:
        raise ValueError('Unknown article sort.')
    sql, parameters = _library_query(**filters)
    with connect() as con:
        cursor = con.execute('''SELECT a.id,a.url,a.title,a.source,a.author,a.published,
            a.fetched_at,a.word_count ''' + sql + ' ORDER BY ' + SORTS[sort], parameters)
        for row in cursor:
            yield dict(row)


def analytics_overview(sources=None):
    where = '' if sources is None else (' WHERE publisher_key IN (' + ','.join('?' for _ in sources) + ')' if sources else ' WHERE 0')
    parameters = list(sources or [])
    with connect() as con:
        con.execute('BEGIN')
        stats = dict(con.execute('''SELECT COUNT(*) AS total,COALESCE(SUM(word_count),0) AS words,
            COALESCE(AVG(word_count),0) AS average,COUNT(DISTINCT publisher_key) AS publishers FROM articles'''
            + where, parameters).fetchone())
        stats['sources'] = [dict(row) for row in con.execute('''SELECT publisher_key AS source,COUNT(*) AS articles
            FROM articles''' + where + ' GROUP BY publisher_key ORDER BY articles DESC,publisher_key LIMIT 20', parameters)]
        dated_where = where + (' AND ' if where else ' WHERE ') + 'date(published) IS NOT NULL'
        stats['timeline'] = [dict(row) for row in con.execute('''SELECT substr(published,1,7) AS month,COUNT(*) AS articles
            FROM articles''' + dated_where + ' GROUP BY month ORDER BY month DESC LIMIT 60', parameters)][::-1]
        bucket = '''CASE WHEN word_count<500 THEN 0 WHEN word_count<1000 THEN 1
            WHEN word_count<2000 THEN 2 WHEN word_count<4000 THEN 3 WHEN word_count<8000 THEN 4 ELSE 5 END'''
        stats['lengths'] = [dict(row) for row in con.execute('SELECT ' + bucket + ' AS bucket,COUNT(*) AS articles FROM articles'
                                                          + where + ' GROUP BY bucket ORDER BY bucket', parameters)]
    return stats


def recent_sample(sources=None, limit=250):
    if not 1 <= limit <= 250:
        raise ValueError('A text sample can include up to 250 articles.')
    sql, parameters = _library_query(sources=sources)
    with connect() as con:
        return [dict(row) for row in con.execute('SELECT a.id,a.text ' + sql
            + ' ORDER BY a.fetched_at DESC,a.id DESC LIMIT ?', parameters + [limit])]

def delete_all():
    with connect() as con:
        con.execute('DELETE FROM import_batch_items')
        con.execute('DELETE FROM import_batches')
        con.execute("DELETE FROM article_insights")
        con.execute("DELETE FROM embeddings")
        con.execute("DELETE FROM collection_articles")
        con.execute("DELETE FROM research_collections")
        con.execute("DELETE FROM article_facets")
        con.execute("DELETE FROM articles")


def article_fingerprint(article):
    values = {key: article.get(key, '') for key in ('id', 'title', 'url', 'text', 'source', 'published', 'author')}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode('utf-8')).hexdigest()


def load_insight(article, model, version):
    with connect() as con:
        row = con.execute("""SELECT insight_json FROM article_insights
            WHERE article_id=? AND model=? AND content_hash=? AND version=?""",
            (article['id'], model, article_fingerprint(article), version)).fetchone()
    return json.loads(row['insight_json']) if row else None


def save_insight(article, model, version, insight):
    result = dict(insight, generated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    with connect() as con:
        con.execute("""INSERT INTO article_insights (article_id,model,content_hash,version,insight_json)
            VALUES (?,?,?,?,?) ON CONFLICT(article_id,model) DO UPDATE SET
            content_hash=excluded.content_hash,version=excluded.version,insight_json=excluded.insight_json""",
            (article['id'], model, article_fingerprint(article), version, json.dumps(result)))
    return result


def _text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def cached_embeddings(model, texts):
    result = {}
    with connect() as con:
        for text in texts:
            row = con.execute('SELECT vector_json FROM embeddings WHERE model=? AND text_hash=?',
                              (model, _text_hash(text))).fetchone()
            if row:
                result[text] = json.loads(row['vector_json'])
    return result


def save_embeddings(model, vectors):
    with connect() as con:
        con.executemany("""INSERT INTO embeddings (model,text_hash,vector_json) VALUES (?,?,?)
            ON CONFLICT(model,text_hash) DO UPDATE SET vector_json=excluded.vector_json""",
            [(model, _text_hash(text), json.dumps(vector)) for text, vector in vectors.items()])
