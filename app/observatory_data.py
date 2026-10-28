"""Bounded, source-backed analytics queries for the research observatory."""
import json
import re
from datetime import date, timedelta
from pathlib import Path

from app import storage
from app.facets import ENTITIES, LENSES

PAGE_SIZE = 12
LENS_IDS = {lens['id'] for lens in LENSES}


def collections():
    with storage.connect() as con:
        rows = [dict(row) for row in con.execute('''SELECT c.id,c.title,c.query,COUNT(ca.article_id) AS articles
            FROM research_collections c LEFT JOIN collection_articles ca ON ca.collection_id=c.id
            GROUP BY c.id ORDER BY c.created_at DESC,c.id''')]
        total = con.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
    return [dict(id='', title='All articles', query='Your saved article library', articles=total)] + rows


def clean_filters(value, choices):
    value = value if isinstance(value, dict) else {}
    valid_collections = {row['id'] for row in choices}
    default = 'ai-bubble' if 'ai-bubble' in valid_collections else ''
    collection = str(value.get('collection', default))
    if collection not in valid_collections:
        collection = default
    period = value.get('period', 'all')
    try:
        page = max(1, min(100000, int(value.get('page', 1) or 1)))
    except (ValueError, TypeError, OverflowError):
        page = 1
    lens, entity = value.get('lens'), value.get('entity')
    return dict(collection=collection, query=str(value.get('query', ''))[:256],
                source=str(value.get('source', ''))[:250], period=period if period in ('all', '90d', '1y') else 'all',
                lens=lens if isinstance(lens, str) and lens in LENS_IDS else '',
                entity=entity if isinstance(entity, str) and entity in ENTITIES else '',
                month=value.get('month') if re.fullmatch(r'\d{4}-\d{2}', str(value.get('month', ''))) else '',
                page=page)


def _base_filters(filters, as_of):
    return dict(collection_id=filters['collection'] or None, query=filters['query'],
                sources=[filters['source']] if filters['source'] else None,
                lens=filters['lens'] or None, entity=filters['entity'] or None,
                start_date=(date.fromisoformat(as_of) - timedelta(days=90 if filters['period'] == '90d' else 365)).isoformat()
                if filters['period'] != 'all' else None,
                end_date=as_of, month=filters['month'] or None)


def collection_audit(collection_id):
    path = Path(__file__).resolve().parents[1] / 'output' / 'ai-bubble-collection.json'
    if collection_id != 'ai-bubble' or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return None
    return dict(summary=data.get('summary', {}), updated_at=data.get('updated_at', ''),
                as_of=data.get('as_of', '2026-10-27'), selection=data.get('selection', ''),
                quality=data.get('quality_policy', ''))


def snapshot(filters):
    audit = collection_audit(filters['collection'])
    as_of = audit['as_of'] if audit else date.today().isoformat()
    base = _base_filters(filters, as_of)
    sql, parameters = storage._library_query(**base, include_facets=True)
    before_where, separator, after_where = sql.partition(' WHERE ')
    where = separator + after_where if separator else ''
    with storage.connect() as con:
        con.execute('BEGIN')
        stats = dict(con.execute('''SELECT COUNT(*) AS articles,COUNT(DISTINCT a.publisher_key) AS publishers,
            COUNT(f.article_id) AS indexed,MIN(date(a.published)) AS earliest,MAX(date(a.published)) AS latest,
            SUM(CASE WHEN date(a.published) IS NULL THEN 1 ELSE 0 END) AS undated,
            SUM(CASE WHEN json_extract(f.signals_json,'$.bubble')=1 THEN 1 ELSE 0 END) AS bubble '''
            + sql, parameters).fetchone())
        stats['bubble'] = stats['bubble'] or 0
        stats['undated'] = stats['undated'] or 0
        lens_counts = {row[0]: row[1] for row in con.execute('SELECT j.value,COUNT(*) '
            + before_where + " JOIN json_each(f.signals_json,'$.lenses') j" + where + ' GROUP BY j.value', parameters)}
        entity_counts = [dict(name=row[0], count=row[1]) for row in con.execute('SELECT j.value,COUNT(*) '
            + before_where + " JOIN json_each(f.signals_json,'$.entities') j" + where
            + ' GROUP BY j.value ORDER BY COUNT(*) DESC,j.value', parameters)]
        matrix = [dict(entity=row[0], lens=row[1], count=row[2]) for row in con.execute('SELECT e.value,l.value,COUNT(*) '
            + before_where + " JOIN json_each(f.signals_json,'$.entities') e JOIN json_each(f.signals_json,'$.lenses') l"
            + where + ' GROUP BY e.value,l.value', parameters)]
        publishers = [dict(name=row[0], count=row[1]) for row in con.execute('SELECT a.publisher_key,COUNT(*) '
            + sql + ' GROUP BY a.publisher_key ORDER BY COUNT(*) DESC,a.publisher_key LIMIT 8', parameters)]
        dated_counts = [dict(month=row[0], count=row[1]) for row in con.execute('SELECT substr(a.published,1,7),COUNT(*) '
            + sql + (' AND ' if where else ' WHERE ') + 'date(a.published) IS NOT NULL'
            + ' GROUP BY substr(a.published,1,7) ORDER BY substr(a.published,1,7) DESC LIMIT 60', parameters)][::-1]
        timeline = []
        if dated_counts:
            counts_by_month = {row['month']: row['count'] for row in dated_counts}
            first = date.fromisoformat(dated_counts[0]['month'] + '-01')
            last = date.fromisoformat(dated_counts[-1]['month'] + '-01')
            final_index = last.year * 12 + last.month - 1
            first_index = max(first.year * 12 + first.month - 1, final_index - 59)
            for index in range(first_index, final_index + 1):
                month = f'{index // 12:04}-{index % 12 + 1:02}'
                timeline.append(dict(month=month, count=counts_by_month.get(month, 0)))
        pages = max(1, (stats['articles'] + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(filters['page'], pages)
        order = ''' ORDER BY CASE WHEN date(a.published) IS NULL THEN 1 ELSE 0 END,
            date(a.published) DESC,a.fetched_at DESC,a.id DESC'''
        rows = []
        for row in con.execute('''SELECT a.id,a.title,a.url,a.publisher_key AS source,a.published,a.word_count,
            substr(a.text,1,200) AS excerpt,f.signals_json ''' + sql + order + ' LIMIT ? OFFSET ?',
            parameters + [PAGE_SIZE, (page - 1) * PAGE_SIZE]):
            item = dict(row)
            facets = json.loads(item.pop('signals_json') or '{}')
            item['lenses'] = facets.get('lenses', [])
            item['entities'] = facets.get('entities', [])
            item['excerpt'] = (facets.get('evidence', {}).get(filters['lens']) if filters['lens'] else '') or item['excerpt']
            rows.append(item)
        evidence = {}
        for kind in ('concern', 'countercase'):
            extra = (' AND ' if where else ' WHERE ') + f"length(json_extract(f.signals_json,'$.{kind}'))>0"
            evidence[kind] = [dict(row) for row in con.execute(f'''SELECT a.id,a.title,a.url,
                a.publisher_key AS source,a.published,json_extract(f.signals_json,'$.{kind}') AS excerpt '''
                + sql + extra + order + ' LIMIT 2', parameters)]
        # Control choices stay available while a particular publisher is focused.
        controls_sql, controls_parameters = storage._library_query(collection_id=filters['collection'] or None)
        sources = [row[0] for row in con.execute('SELECT DISTINCT a.publisher_key ' + controls_sql
                                                + ' ORDER BY a.publisher_key', controls_parameters)]
    return dict(stats=stats, lenses=[dict(id=lens['id'], label=lens['label'], short=lens['short'],
                                         count=lens_counts.get(lens['id'], 0)) for lens in LENSES],
                entities=entity_counts, matrix=matrix, publishers=publishers, timeline=timeline,
                rows=rows, evidence=evidence, page=page, pages=pages, page_size=PAGE_SIZE,
                sources=sources, audit=audit, as_of=as_of, export_filters=base)
