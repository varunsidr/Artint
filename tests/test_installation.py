"""Meaningful clean-install and diagnostic regressions; no publisher/model calls."""
import sqlite3
import hashlib
import os
from urllib.parse import urlsplit

import pytest

from app import reports, storage
from scripts import check_install, smoke_install


def test_installation_smoke_preserves_the_configured_library(tmp_path, monkeypatch):
    database, pdfs = tmp_path / 'personal.db', tmp_path / 'personal-pdfs'
    monkeypatch.setattr(storage, 'DB', database)
    monkeypatch.setattr(reports, 'PDF_DIR', pdfs)
    # Even an existing unrelated file must not be opened by the default smoke.
    database.write_bytes(b'Personal sentinel')
    result = smoke_install.offline_smoke()
    assert result['backup_restore'] and result['search'] and result['restore_hardlinks']
    assert storage.DB == database and reports.PDF_DIR == pdfs
    assert database.read_bytes() == b'Personal sentinel' and not pdfs.exists()


@pytest.mark.parametrize('url', ['https://example.org/', 'http://192.168.1.1/', 'file:///tmp/local', 'http://name:secret@localhost/'])
def test_health_diagnostic_rejects_nonlocal_destinations(url):
    with pytest.raises(ValueError, match='local HTTP'):
        check_install.local_health(url)


def test_persistent_fixture_refuses_existing_library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')
    monkeypatch.setattr(reports, 'PDF_DIR', tmp_path / 'pdfs')
    from tests.test_library_storage import article
    storage.upsert(article())
    with pytest.raises(ValueError, match='empty isolated library'):
        smoke_install.prepare()
    with sqlite3.connect(storage.DB) as con:
        assert con.execute('SELECT COUNT(*) FROM articles').fetchone()[0] == 1
    assert not reports.PDF_DIR.exists()


@pytest.mark.skipif(not os.getenv('ARTINT_UI_SMOKE_URL'), reason='Opt-in: requires an isolated running synthetic app')
def test_running_installation_search_notes_and_pdf_download(tmp_path):
    from playwright.sync_api import expect, sync_playwright
    from pypdf import PdfReader

    url = os.environ['ARTINT_UI_SMOKE_URL']
    assert urlsplit(url).hostname in ('127.0.0.1', 'localhost', '::1')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel=os.getenv('ARTICLE_BROWSER_CHANNEL', 'chromium'), chromium_sandbox=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until='domcontentloaded')
            expect(page.get_by_role('heading', name='Article library', exact=True)).to_be_visible(timeout=30000)
            search = page.get_by_placeholder('Search your library')
            search.fill('infrastructure')
            search.press('Enter')
            expect(page.get_by_role('button', name='Read', exact=True)).to_have_count(1)
            page.get_by_role('button', name='Read', exact=True).click()
            with page.expect_download() as download:
                page.get_by_role('button', name='Download PDF', exact=True).click()
            target = tmp_path / 'reading.pdf'
            download.value.save_as(target)
            assert hashlib.sha256(target.read_bytes()).hexdigest() == os.environ['ARTINT_EXPECT_PDF_SHA']
            assert 'Synthetic demonstration article' in ''.join(p.extract_text() for p in PdfReader(target).pages)
            page.get_by_role('tab', name='Notes & highlights', exact=True).click()
            expect(page.get_by_label('Your notes', exact=True)).to_have_value('Synthetic installation note.')
            page.keyboard.press('Escape')
            search.fill('unfindable-installation-check')
            search.press('Enter')
            expect(page.get_by_role('button', name='Read', exact=True)).to_have_count(0)
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
        finally:
            browser.close()
