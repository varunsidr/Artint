"""Publishing fixtures must not overwrite a user's files or connect to services."""
import hashlib
import sqlite3

import pytest

from app import reports, storage
from scripts.seed_demo import seed_demo


def test_offline_demo_is_isolated_and_rejects_overwrite(tmp_path, monkeypatch):
    import requests

    def no_network(*args, **kwargs):
        pytest.fail('The public demo must not call publishers or Ollama')

    monkeypatch.setattr(requests.sessions.Session, 'request', no_network)
    original_db, original_pdfs = storage.DB, reports.PDF_DIR
    destination = tmp_path / 'demo'
    manifest = seed_demo(destination)
    assert storage.DB == original_db and reports.PDF_DIR == original_pdfs
    assert manifest['synthetic'] and manifest['articles'] == 36
    with sqlite3.connect(destination / 'library.db') as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert con.execute('PRAGMA foreign_key_check').fetchall() == []
        assert con.execute('SELECT COUNT(*) FROM articles').fetchone()[0] == 36
        assert con.execute('SELECT COUNT(*) FROM article_insights').fetchone()[0] == 12
        assert all(row[0].startswith('https://') and '.example/demo/' in row[0]
                   for row in con.execute('SELECT url FROM articles'))
        assert con.execute('SELECT COUNT(*) FROM article_highlights').fetchone()[0] == 1
    pdfs = list((destination / 'pdfs').glob('*.pdf'))
    assert len(pdfs) == 36 and all(pdf.read_bytes().startswith(b'%PDF-') for pdf in pdfs)
    before = hashlib.sha256((destination / 'library.db').read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='new or empty'):
        seed_demo(destination)
    assert hashlib.sha256((destination / 'library.db').read_bytes()).hexdigest() == before


def test_demo_refuses_a_directory_with_unrelated_files(tmp_path):
    sentinel = tmp_path / 'personal.txt'
    sentinel.write_text('Keep this file', encoding='utf-8')
    with pytest.raises(ValueError, match='new or empty'):
        seed_demo(tmp_path)
    assert sentinel.read_text(encoding='utf-8') == 'Keep this file'
    assert not (tmp_path / 'library.db').exists()
