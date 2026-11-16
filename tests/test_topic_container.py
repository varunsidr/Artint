"""Opt-in live container topic workflow; scripted vectors do not certify model quality."""
import json
import os
import re
from urllib.parse import urlsplit

import pytest

from scripts.topic_validation import COLLECTION, articles, embedding_service


@pytest.mark.skipif(not os.getenv('ARTINT_TOPIC_UI_SMOKE') or not os.getenv('ARTINT_UI_SMOKE_URL'),
                    reason='Opt-in: marked topic-enabled disposable runtime required')
def test_running_topic_installation_and_cached_reopen(tmp_path):
    from playwright.sync_api import expect, sync_playwright
    url = os.environ['ARTINT_UI_SMOKE_URL']
    assert urlsplit(url).hostname in ('127.0.0.1', 'localhost', '::1')
    expected = {article['id'] for article in articles()}
    warm = os.getenv('ARTINT_TOPIC_EXPECT_WARM') == '1'
    with embedding_service() as service, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel=os.getenv('ARTICLE_BROWSER_CHANNEL', 'chromium'), chromium_sandbox=True)
        try:
            page = browser.new_page(viewport=dict(width=1440, height=1100))
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url, wait_until='domcontentloaded')
            page.get_by_role('button', name='Analytics', exact=True).click()
            page.get_by_text('Topic discovery (experimental)', exact=True).click()
            page.get_by_label('Collection to discover', exact=True).click()
            page.get_by_role('option', name='Container topic check', exact=True).click()
            assert service['embedding_calls'] == 0
            page.get_by_role('button', name='Discover topics', exact=True).click()
            expect(page.get_by_role('heading', name='Discovered themes', exact=True)).to_be_visible(timeout=45000)
            if warm:
                expect(page.get_by_text(re.compile('12 embeddings reused / 0 created'))).to_be_visible()
            with page.expect_download() as download:
                page.get_by_role('button', name='Download topic discovery', exact=True).click()
            path = tmp_path / 'discovery.json'
            download.value.save_as(path)
            result = json.loads(path.read_text(encoding='utf-8'))
            assert result['counts']['articles'] == 13 and result['counts']['distinct_articles'] == 12
            assert result['counts']['exact_copies'] == 1 and len(result['topics']) == 3
            assert set(result['source_fingerprints']) == expected
            assert result['model_observation']['state'] == 'stable'
            assert result['model_observation']['after']['models'][result['embedding_model']]['details']['family'] == 'synthetic-container-fixture'
            assert result['counts']['embeddings_created'] == (0 if warm else 12)
            assert service['embedding_calls'] == (0 if warm else 1)
            calls = service['embedding_calls']
            point = page.locator('.scatterlayer .point').first
            point.scroll_into_view_if_needed()
            point.click(force=True)
            expect(page.locator('details[open]')).to_have_count(1)
            page.get_by_role('button', name='Discover topics', exact=True).click()
            expect(page.get_by_text(re.compile('12 embeddings reused / 0 created'))).to_be_visible(timeout=30000)
            assert service['embedding_calls'] == calls
            page.get_by_text('Dark mode', exact=True).click()
            page.set_viewport_size(dict(width=390, height=844))
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 2')
            assert not errors
        finally:
            browser.close()


def test_topic_preparation_refuses_unmarked_personal_library(tmp_path, monkeypatch):
    from app import storage
    from scripts.topic_validation import prepare
    personal = tmp_path / 'personal.db'
    personal.write_bytes(b'Personal sentinel')
    monkeypatch.setattr(storage, 'DB', personal)
    monkeypatch.delenv('ARTINT_INSTALL_SMOKE', raising=False)
    with pytest.raises(ValueError, match='explicit disposable'):
        prepare()
    monkeypatch.setenv('ARTINT_INSTALL_SMOKE', '1')
    with pytest.raises(ValueError, match='marked disposable'):
        prepare()
    assert personal.read_bytes() == b'Personal sentinel'
