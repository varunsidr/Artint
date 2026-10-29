"""Measure the linked analytics queries using disposable, dense synthetic coverage."""
import json
import argparse
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


def run(output=None):
    report = dict(evaluated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  environment=dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                                   os=platform.platform(), processor=platform.processor()),
                  dataset='Synthetic 400-1200 word articles, 20 publishers. Every article matches all six lenses and three companies, with three hand-authored saved topic labels for general analytics.',
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
                # Dense saved-label fixture: metadata only, no model call or
                # claim that these synthetic labels measure analysis quality.
                with storage.connect() as con:
                    con.execute('''INSERT INTO article_insights(article_id,model,content_hash,version,insight_json)
                        SELECT id,'qwen3:8b',content_hash,'1',? FROM articles''',
                        (json.dumps(dict(topics=['Synthetic research', 'Enterprise software', 'Cloud services'])),))
                choices = collections()
                general = clean_filters({}, choices)
                full = clean_filters(dict(mode='investment'), choices)
                focused = clean_filters(dict(mode='investment', lens='credit', entity='OpenAI', page=400), choices)
                view = snapshot(full)
                assert view['stats']['articles'] > count * .9
                assert len(view['rows']) == 12 and len(view['timeline']) <= 60
                report['results'].append(dict(articles=count, matching_articles=view['stats']['articles'],
                    snapshot=measure(lambda: snapshot(full), 15),
                    general_snapshot=measure(lambda: snapshot(general), 15),
                    filtered_page=measure(lambda: snapshot(focused), 15),
                    rows=len(view['rows']), payload_bytes=len(json.dumps(view).encode())))
                print(json.dumps(report['results'][-1]), flush=True)
    finally:
        storage.DB = original
    output = output or ROOT / 'output' / 'observatory-benchmark.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional report destination; use a new filename to preserve earlier runs.')
    run(parser.parse_args().output)
