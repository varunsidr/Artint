import csv
import io
from unittest.mock import patch

import pytest

from app import exports, storage


def test_metadata_export_is_filtered_and_excludes_full_text(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')
    storage.upsert(dict(id='one', url='https://example.org/a', title='=UNTRUSTED()', source='Example',
                        author='Author', published='', fetched_at='2026-10-27T00:00:00Z',
                        text='Private long article text.', word_count=4, links_json='[]', images_json='[]', pdf_path=''))
    data = exports.metadata_csv(query='Private')
    rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
    assert len(rows) == 1
    assert rows[0]['title'] == "'=UNTRUSTED()"
    assert 'text' not in rows[0]
    assert len(list(csv.DictReader(io.StringIO(exports.metadata_csv(query='missing').decode('utf-8-sig'))))) == 0
    with patch('app.exports.MAX_CSV_BYTES', 1):
        with pytest.raises(ValueError, match='25 MB'):
            exports.metadata_csv()


def test_pdf_zip_is_bounded_and_reports_missing_files(tmp_path):
    pdf = tmp_path / 'article.pdf'
    pdf.write_bytes(b'%PDF- sample')
    items = [{'id': 'one', 'title': 'Article', 'pdf_path': str(pdf)},
             {'id': 'two', 'title': 'Missing', 'pdf_path': ''}]
    data, count = exports.page_pdf_zip(items)
    assert data.startswith(b'PK') and count == 1
    with patch('app.exports.MAX_ZIP_INPUT_BYTES', 1):
        with pytest.raises(ValueError, match='50 MB'):
            exports.page_pdf_zip(items)
    with pytest.raises(ValueError, match='100'):
        exports.page_pdf_zip(items * 51)
    with pytest.raises(ValueError, match='No saved PDFs'):
        exports.page_pdf_zip([])
