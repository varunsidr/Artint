"""Original container fixtures and a loopback-only scripted embedding service."""
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading

MODEL = 'qwen3-embedding:0.6b'
PORT = 11499
COLLECTION = 'container-topic-check'


def articles():
    """Three deliberately distinct vector families; no publisher material."""
    result = []
    for family, words in enumerate(('astronomy telescope galaxy stars', 'marine coral ocean reef', 'banking credit lending finance')):
        for index in range(4):
            ident = f'container-topic-{family}-{index}'
            result.append(dict(id=ident, title=f'{words} item {index}',
                text=f'Original fictional container topic fixture. {words}. Detailed observation {index} in family {family}.',
                url=f'https://example.org/container-topics/{ident}', source=f'Fictional publisher {index}',
                author='Original fixture', published='2026-11-10', fetched_at='2026-11-12T00:00:00+00:00',
                word_count=18, links_json='[]', images_json='[]', pdf_path=''))
    result.append(dict(result[0], id='container-topic-copy', source='Fictional syndication',
                       url='https://example.org/container-topics/copy'))
    return result


def prepare():
    """Seed only a marked, verified installation-smoke library with one article."""
    from app import storage
    from scripts.smoke_install import verify
    if os.getenv('ARTINT_INSTALL_SMOKE') != '1':
        raise ValueError('Topic preparation requires the explicit disposable installation-smoke flag.')
    marker = storage.DB.parent / '.artint-install-smoke.json'
    if not marker.is_file() or marker.is_symlink():
        raise ValueError('Topic preparation requires a marked disposable smoke library.')
    verify()
    if storage.library_overview()['total'] != 1:
        raise ValueError('Topic preparation requires the original one-article installation fixture.')
    storage.create_collection(COLLECTION, 'Container topic check', 'Original scripted topic-discovery fixture')
    values = articles()
    for article in values:
        storage.upsert(article, collection_id=COLLECTION)
    verify()  # Existing PDF, notes and saved research still match their marker.
    return dict(articles=len(values), collection=COLLECTION, original_fixture_preserved=True)


@contextmanager
def embedding_service(port=PORT):
    state = dict(embedding_calls=0, inputs=[])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, value, status=200):
            body = json.dumps(value).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/api/tags':
                self.respond(dict(models=[dict(name=MODEL, digest='f' * 64,
                    details=dict(family='synthetic-container-fixture', quantization_level='scripted-five-dimensional'))]))
            elif self.path == '/api/version':
                self.respond(dict(version='0.40.15'))
            else:
                self.respond(dict(error='Not a fixture endpoint'), 404)

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.path != '/api/embed' or not 0 < length <= 256 * 1024:
                    raise ValueError
                payload = json.loads(self.rfile.read(length))
                values = payload.get('input')
                if payload.get('model') != MODEL or not isinstance(values, list) or not 1 <= len(values) <= 16:
                    raise ValueError
                vectors = []
                for text in values:
                    if not isinstance(text, str) or not text.startswith(('astronomy ', 'marine ', 'banking ')):
                        raise ValueError
                    family = next(i for i, word in enumerate(('astronomy', 'marine', 'banking')) if text.startswith(word))
                    match = re.search(r'item (\d+)\n', text)
                    if not match or not 0 <= int(match[1]) <= 3:
                        raise ValueError
                    index = int(match[1])
                    vector = [0.0] * 5
                    vector[family] = 1.0
                    vector[3], vector[4] = .01 * (index + 1), .005 * (index ** 2 + family)
                    vectors.append(vector)
                state['embedding_calls'] += 1
                state['inputs'].extend(values)
                self.respond(dict(embeddings=vectors))
            except (ValueError, TypeError, KeyError):
                self.respond(dict(error='Only original fixture inputs are accepted'), 400)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == '__main__':
    # Only the validator invokes this inside its owned disposable container.
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    print(json.dumps(prepare()))
