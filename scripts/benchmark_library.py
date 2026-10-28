"""Measure synthetic libraries in disposable databases, never the user's library.

Run: python scripts/benchmark_library.py --counts 1000 10000
Optional --preview-db output/benchmarks/library-10000.db retains an isolated QA copy.
"""
import argparse
import json
import math
import platform
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import storage
from app.exports import metadata_csv


def synthetic_articles(count):
    vocabulary = ('research climate energy markets policy technology science materials '
                  'satellites orbit tracking evidence discovery university innovation '
                  'analysis public sources information context development observation').split()
    beginning = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for index in range(count):
        length = 400 + index % 9 * 100
        words = [vocabulary[(position + index) % len(vocabulary)] for position in range(length)]
        text = f'case{index:08} ' + ' '.join(words)
        yield dict(id=f'benchmark{index:08}', url=f'https://publisher{index % 20}.example/article/{index}',
                   title=f'Synthetic research article {index:08}', source=f'Publisher {index % 20:02}',
                   author=f'Writer {index % 50}', published=f'{2024 + index % 3}-{1 + index % 12:02}-{1 + index % 27:02}',
                   fetched_at=(beginning + timedelta(seconds=index)).isoformat(), text=text,
                   word_count=len(words) + 1, links_json='[]', images_json='[]', pdf_path='')


def seed(count):
    storage.upsert_many(synthetic_articles(count))
    with storage.connect() as con:
        for index, row in enumerate(con.execute('SELECT id,content_hash FROM articles ORDER BY id')):
            if index % 2:
                continue
            insight = dict(summary=dict(text='Synthetic cached summary for a load test.', sources=[row['id'] + ':P1']),
                           topics=[f'Topic {index % 20:02}'], key_points=[], partial=False,
                           passages_analyzed=1, total_passages=1, model='qwen3:8b', generated_at='2026-10-27T00:00:00Z')
            con.execute('INSERT INTO article_insights VALUES(?,?,?,?,?)',
                        (row['id'], 'qwen3:8b', row['content_hash'], '1', json.dumps(insight)))


def measure(operation, rounds):
    operation()  # Warm SQLite and application caches; cold startup is separate.
    timings = []
    for _ in range(rounds):
        started = time.perf_counter()
        operation()
        timings.append((time.perf_counter() - started) * 1000)
    ordered = sorted(timings)
    return dict(median_ms=round(median(timings), 2),
                p95_ms=round(ordered[math.ceil(.95 * len(ordered)) - 1], 2), rounds=rounds)


def benchmark(count, rounds, preview_path=None):
    original = storage.DB
    prefix = 'article-library-load-'
    with tempfile.TemporaryDirectory(prefix=prefix) as directory:
        directory = Path(directory).resolve()
        assert directory.parent == Path(tempfile.gettempdir()).resolve() and directory.name.startswith(prefix)
        storage.DB = directory / 'synthetic.db'
        try:
            started = time.perf_counter()
            seed(count)
            seed_seconds = time.perf_counter() - started
            overview = storage.library_overview()
            assert overview['total'] == count and overview['analyzed'] == (count + 1) // 2

            def first_page():
                storage.library_overview()
                return storage.library_page()

            result = dict(
                articles=count, cached_analyses=overview['analyzed'], synthetic=True,
                seed_seconds=round(seed_seconds, 2),
                database_mb=round(storage.DB.stat().st_size / 1024 ** 2, 2),
                browse_data=measure(first_page, rounds),
                selective_search=measure(lambda: storage.library_page(query=f'case{count // 2:08}'), rounds),
                broad_search=measure(lambda: storage.library_page(query='climate energy'), rounds),
                last_page=measure(lambda: storage.library_page(page=math.ceil(count / 25)), rounds),
                analytics_aggregates=measure(storage.analytics_overview, rounds),
            )
            page = storage.library_page()
            result['first_page_articles'] = len(page['items'])
            result['first_page_payload_bytes'] = len(json.dumps(page).encode('utf-8'))
            assert len(page['items']) == min(25, count) and all('text' not in row for row in page['items'])
            assert storage.library_page(query=f'case{count // 2:08}')['total'] == 1
            result['metadata_csv_bytes'] = len(metadata_csv())

            from streamlit.testing.v1 import AppTest
            started = time.perf_counter()
            app = AppTest.from_file(ROOT / 'app' / 'dashboard.py').run(timeout=30)
            result['initial_apptest_ms'] = round((time.perf_counter() - started) * 1000, 2)
            assert not app.exception, [str(error.value) for error in app.exception]
            assert len([button for button in app.button if button.key and button.key.startswith('read_')]) == min(25, count)

            def render():
                app.run(timeout=30)
                assert not app.exception

            result['warm_apptest'] = measure(render, min(rounds, 10))
            if preview_path:
                if preview_path.exists():
                    raise FileExistsError(f'Refusing to overwrite the QA fixture: {preview_path}')
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                with storage.connect() as con, closing(sqlite3.connect(preview_path)) as target:
                    con.backup(target)
            return result
        finally:
            storage.DB = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts', type=int, nargs='+', default=[1000, 10000])
    parser.add_argument('--rounds', type=int, default=30)
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'library-benchmark.json')
    parser.add_argument('--preview-db', type=Path)
    options = parser.parse_args()
    if any(count < 1 or count > 100000 for count in options.counts) or options.rounds < 1:
        parser.error('Use positive counts up to 100,000 and at least one measurement round.')
    preview = options.preview_db.resolve() if options.preview_db else None
    if preview and not preview.is_relative_to(ROOT / 'output'):
        parser.error('The disposable preview database must be under this project’s output directory.')
    report = dict(
        evaluated_on='2026-10-27', dataset='Synthetic article text, metadata, and cached summaries; 20 publishers.',
        environment=dict(os=platform.platform(), processor=platform.processor(),
                         python=platform.python_version(), sqlite=sqlite3.sqlite_version),
        limitations=['Warm local measurements; not a concurrency or production deployment test.',
                     'AppTest measures script execution, not browser paint or network transfer.',
                     'Excludes publisher fetching, PDF generation, live model inference, and semantic index construction.'],
        results=[],
    )
    for position, count in enumerate(options.counts):
        result = benchmark(count, options.rounds, preview if position == len(options.counts) - 1 else None)
        report['results'].append(result)
        print(json.dumps(result), flush=True)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Report: {options.output}')


if __name__ == '__main__':
    main()
