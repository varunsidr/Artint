"""Offline installation/restore smoke; persistent mode is for isolated CI volumes only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    from app import library_actions, reports, storage
    from scripts.seed_demo import QUOTE, demo_articles

    marker = storage.DB.parent / '.artint-install-smoke.json'
    if marker.exists() or storage.library_overview()['total']:
        raise ValueError('Persistence smoke requires an empty isolated library; existing data was kept.')
    article = next(demo_articles())
    if (reports.PDF_DIR / (article['id'] + '.pdf')).exists():
        raise ValueError('Persistence smoke refuses to overwrite an existing PDF.')
    article['pdf_path'] = str(reports.create_pdf(article))
    storage.upsert(article)
    library_actions.save_organization(article['id'], note='Synthetic installation note.', tags=['Install check'], collection_ids=[])
    library_actions.add_highlight(article['id'], QUOTE, note='Synthetic highlight.')
    record = dict(id=article['id'], pdf_sha256=digest(article['pdf_path']), text_sha256=hashlib.sha256(article['text'].encode()).hexdigest())
    marker.write_text(json.dumps(record), encoding='utf-8')
    return verify()


def verify():
    from app import library_actions, storage

    record = json.loads((storage.DB.parent / '.artint-install-smoke.json').read_text(encoding='utf-8'))
    article = storage.get_article(record['id'])
    if not article or storage.library_page(query='infrastructure')['total'] != 1:
        raise RuntimeError('Synthetic library/search persistence failed.')
    if digest(article['pdf_path']) != record['pdf_sha256'] or hashlib.sha256(article['text'].encode()).hexdigest() != record['text_sha256']:
        raise RuntimeError('Saved article or PDF changed.')
    state = library_actions.annotation_state(article['id'])
    if state['note'] != 'Synthetic installation note.' or len(state['highlights']) != 1:
        raise RuntimeError('Annotation persistence failed.')
    return dict(articles=1, search=True, annotations=True, pdf_sha256=record['pdf_sha256'])


def offline_smoke():
    from app import exports, library_actions, library_backup, reports, storage

    original_db, original_pdfs = storage.DB, reports.PDF_DIR
    try:
        with tempfile.TemporaryDirectory(prefix='artint install caf\u00e9 ') as temporary:
            root = Path(temporary)
            storage.DB, reports.PDF_DIR = root / 'source/library.db', root / 'source/pdfs'
            result = prepare()
            article = storage.all_articles()[0]
            if not exports.metadata_csv(query='infrastructure'):
                raise RuntimeError('Metadata export failed.')
            blob, stats = library_backup.create_backup()
            if stats['pdfs'] != 1:
                raise RuntimeError('PDF backup failed.')
            storage.DB, reports.PDF_DIR = root / 'restored/library.db', root / 'restored/pdfs'
            restored = library_backup.restore_backup(blob)
            copy = storage.get_article(article['id'])
            if restored['articles'] != 1 or digest(copy['pdf_path']) != result['pdf_sha256']:
                raise RuntimeError('Portable restore changed the reading PDF.')
            if library_actions.annotation_state(copy['id'])['note'] != 'Synthetic installation note.':
                raise RuntimeError('Portable restore changed notes.')
            if library_backup.restore_backup(blob)['articles'] != 0:
                raise RuntimeError('Repeated restore duplicated the article.')
            return dict(result, metadata_export=True, backup_restore=True, restore_hardlinks=True, isolated=True)
    finally:
        storage.DB, reports.PDF_DIR = original_db, original_pdfs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--persistent', choices=('prepare', 'verify'), help='Isolated CI volumes only; requires ARTINT_INSTALL_SMOKE=1.')
    args = parser.parse_args()
    try:
        if args.persistent:
            if os.getenv('ARTINT_INSTALL_SMOKE') != '1':
                raise ValueError('Persistent smoke is restricted to explicitly isolated validation volumes.')
            result = prepare() if args.persistent == 'prepare' else verify()
        else:
            result = offline_smoke()
        print(json.dumps(dict(ok=True, **result), indent=2))
    except Exception as exc:
        print(json.dumps(dict(ok=False, error=str(exc))), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
