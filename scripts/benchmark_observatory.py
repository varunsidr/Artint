"""Measure the linked analytics queries using disposable, dense synthetic coverage."""
import json
import platform
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import storage
from app.observatory_data import clean_filters, collections, snapshot
from scripts.benchmark_library import measure, synthetic_articles


def run():
    report = dict(evaluated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  environment=dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                                   os=platform.platform(), processor=platform.processor()),
                  dataset='Synthetic 400-1200 word articles, 20 publishers. Every article matches all six lenses and three companies.',
                  limitations=['Warm SQL and Python serialization preparation only; excludes browser paint, network, PDF generation, inference, and concurrency.',
                               'Separate from the real 100-source AI-bubble collection.'], results=[])
    original = storage.DB
    try:
        for count in (1000, 10000):
            with tempfile.TemporaryDirectory(prefix='article-observatory-load-') as directory:
                storage.DB = Path(directory) / 'synthetic.db'
                def articles():
                    for article in synthetic_articles(count):
                        article['text'] += '\nOpenAI Nvidia Microsoft capex valuation revenue debt power supply dot-com. Overinvestment is unsustainable; revenue growth is real.'
                        yield article
                storage.upsert_many(articles())
                choices = collections()
                full = clean_filters({}, choices)
                focused = clean_filters(dict(lens='credit', entity='OpenAI', page=400), choices)
                view = snapshot(full)
                assert view['stats']['articles'] > count * .9
                assert len(view['rows']) == 12 and len(view['timeline']) <= 60
                report['results'].append(dict(articles=count, matching_articles=view['stats']['articles'],
                    snapshot=measure(lambda: snapshot(full), 15),
                    filtered_page=measure(lambda: snapshot(focused), 15),
                    rows=len(view['rows']), payload_bytes=len(json.dumps(view).encode())))
                print(json.dumps(report['results'][-1]), flush=True)
    finally:
        storage.DB = original
    (ROOT / 'output' / 'observatory-benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    run()
