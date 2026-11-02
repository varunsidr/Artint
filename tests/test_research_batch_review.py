"""Batch proposals are not approvals; use only original fictional source fixtures."""
import copy
import json
import os
from pathlib import Path

import pytest

from scripts.evaluate_research import main
from scripts.research_eval.batch_review import prepare_batch_review, validate_suggestions
from scripts.research_eval.contracts import EvaluationError, digest, encoded, load_corpus, read_json, write_json
from scripts.research_eval.development import _gold_review


@pytest.fixture
def packet(tmp_path):
    corpus = load_corpus(Path(__file__).parent / 'fixtures/research/synthetic-v1.json')
    corpus = copy.deepcopy(corpus)
    corpus.update(kind='development', name='Original fictional batch-review test')
    corpus['cases'] = corpus['cases'][:3]
    for case in corpus['cases']:
        case.update(split='development', label=dict(kind='unreviewed', reviewer='pending', reviewed_at=''))
    corpus['cases'][0]['question'] += ' Literal </script><img src="https://example.org/unwanted">'
    rows = []
    for index, case in enumerate(corpus['cases']):
        edited = copy.deepcopy(case)
        if index == 1:
            edited['question'] += ' Please preserve the target qualifier.'
        rows.append(dict(case_id=case['id'], case_sha256=digest(encoded(case)), case=edited,
            suggested_action='check' if index == 2 else 'revise' if index == 1 else 'keep',
            priority='high' if index == 2 else 'normal', notes='AI suggestion only, no approval.'))
    suggestions = dict(schema_version=1, authoring_kind='ai_assisted', proposal_sha256=digest(encoded(corpus)), judgments=rows)
    cpath, spath = tmp_path / 'corpus.json', tmp_path / 'suggestions.json'
    write_json(cpath, corpus)
    write_json(spath, suggestions)
    return corpus, suggestions, cpath, spath


def test_prepare_batch_keeps_originals_and_all_decisions_pending(packet, tmp_path):
    corpus, suggestions, cpath, spath = packet
    before = cpath.read_bytes(), spath.read_bytes()
    out = tmp_path / 'batch'
    result = prepare_batch_review(cpath, spath, out)
    assert result['cases'] == 3 and result['human_labels_created'] == 0
    assert result['suggested_actions'] == {'keep': 1, 'revise': 1, 'check': 1}
    review = read_json(out / 'gold-review.json')
    assert review['review_kind'] == 'unreviewed' and review['reviewer'] == ''
    assert not review['source_grouping_reviewed']
    assert all(row['decision'] == 'pending' for row in review['judgments'])
    assert all(row['case'] == original for row, original in zip(review['judgments'], corpus['cases']))
    _gold_review(corpus, review, require_complete=False)
    assert (cpath.read_bytes(), spath.read_bytes()) == before
    page = (out / 'batch-review.html').read_text(encoding='utf-8')
    assert r'\u003c/script>' in page and 'Literal </script><img' not in page
    assert (out / 'review.html').exists()  # Existing detailed workflow remains available.


@pytest.mark.parametrize('change', ['corpus_hash', 'case_hash', 'duplicate', 'scope', 'label', 'bad_span', 'hidden_exclusion', 'unchanged_revise', 'changed_keep', 'unflagged_absence', 'human_suggestions'])
def test_invalid_suggestions_fail_before_creating_output(packet, tmp_path, change):
    corpus, suggestions, cpath, spath = packet
    bad = copy.deepcopy(suggestions)
    row = bad['judgments'][0]
    if change == 'corpus_hash':
        bad['proposal_sha256'] = 'a' * 64
    elif change == 'case_hash':
        row['case_sha256'] = 'a' * 64
    elif change == 'duplicate':
        bad['judgments'][-1] = copy.deepcopy(row)
    elif change == 'scope':
        row['case']['source_ids'].append('invented')
    elif change == 'label':
        row['case']['label'] = dict(kind='human', reviewer='Invented', reviewed_at='2026-01-01T00:00:00Z')
    elif change == 'bad_span':
        row['case']['evidence'][0]['quote'] = 'Not in the source.'
        row['suggested_action'] = 'revise'
    elif change == 'hidden_exclusion':
        row['case']['eligible'] = False
        row['case']['exclusion_reason'] = 'Hidden omission'
    elif change == 'unchanged_revise':
        row['suggested_action'] = 'revise'
    elif change == 'changed_keep':
        row['case']['question'] += ' Changed.'
    elif change == 'unflagged_absence':
        bad['judgments'][-1]['suggested_action'] = 'keep'
    else:
        bad['authoring_kind'] = 'human'
    spath = tmp_path / 'bad-suggestions.json'
    write_json(spath, bad)
    out = tmp_path / 'invalid-output'
    with pytest.raises(EvaluationError):
        prepare_batch_review(cpath, spath, out)
    assert not out.exists()


def test_batch_accepts_suggestions_in_any_order_and_refuses_overwrite(packet, tmp_path):
    corpus, suggestions, cpath, spath = packet
    suggestions['judgments'].reverse()
    spath = tmp_path / 'reordered-suggestions.json'
    write_json(spath, suggestions)
    out = tmp_path / 'batch'
    prepare_batch_review(cpath, spath, out)
    assert [r['case_id'] for r in read_json(out / 'suggestions.json')['judgments']] == [c['id'] for c in corpus['cases']]
    original = (out / 'gold-review.json').read_bytes()
    with pytest.raises(FileExistsError):
        prepare_batch_review(cpath, spath, out)
    assert (out / 'gold-review.json').read_bytes() == original


def test_batch_cli_writes_pending_packet(packet, tmp_path, capsys):
    _, _, cpath, spath = packet
    out = tmp_path / 'cli-batch'
    assert main(['prepare-batch-review', '--corpus', str(cpath), '--suggestions', str(spath), '--output', str(out)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['human_labels_created'] == 0 and result['quality_gate'] == 'not_established'


@pytest.mark.skipif(os.getenv('RUN_BROWSER_TESTS') != '1', reason='Opt-in actual browser workflow')
def test_batch_browser_preserves_pending_edits_and_exports_compatible_decisions(packet, tmp_path):
    import asyncio
    from playwright.async_api import async_playwright
    from app.browser_render import _launch

    corpus, _, cpath, spath = packet
    out = tmp_path / 'browser'
    prepare_batch_review(cpath, spath, out)

    async def exercise():
        errors, remote = [], []
        async with async_playwright() as playwright:
            browser = await _launch(playwright)
            try:
                page = await browser.new_page(accept_downloads=True)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda request: remote.append(request.url) if request.url.startswith(('http:', 'https:')) else None)
                await page.goto((out / 'batch-review.html').as_uri())
                assert await page.locator('#progress').inner_text() == '0 / 3'
                assert await page.locator('img').count() == 0
                case_id = corpus['cases'][1]['id']
                row = page.locator(f'tr[data-case-id="{case_id}"]')
                await row.get_by_text('Edit proposed case', exact=True).click()
                edited = json.loads(await row.locator('.case-editor').input_value())
                edited['question'] += ' Saved pending edit.'
                await row.locator('.case-editor').fill(json.dumps(edited))
                await row.get_by_text('Use my edited case', exact=True).click()
                assert await page.locator('#progress').inner_text() == '0 / 3'
                async with page.expect_download() as pending:
                    await page.locator('#export').click()
                saved = tmp_path / 'pending-edits.json'
                await (await pending.value).save_as(saved)
                assert read_json(saved)['review_kind'] == 'unreviewed'
                assert read_json(saved)['judgments'][1]['case']['question'] == edited['question']
                await page.reload()
                await page.locator('#import-file').set_input_files(saved)
                await page.wait_for_function("document.getElementById('message').textContent.startsWith('Saved review loaded')")
                assert 'Saved pending edit.' in await page.locator(f'tr[data-case-id="{case_id}"] .case-editor').input_value()
                await page.locator('#select-visible').check()
                await page.locator('#approve').click()
                assert await page.locator('#progress').inner_text() == '0 / 3'
                await page.locator('#reviewer').fill('Automated fictional browser fixture')
                await page.locator('#approve').click()
                assert 'full-source' in await page.locator('#message').inner_text()
                assert await page.locator('#progress').inner_text() == '0 / 3'
                await page.locator('#scope-confirm').check()
                await page.locator('#approve').click()
                assert await page.locator('#progress').inner_text() == '3 / 3'
                assert not await page.locator('#family-confirm').is_checked()
                await page.locator('#family-confirm').check()
                async with page.expect_download() as completed:
                    await page.locator('#export').click()
                final = tmp_path / 'completed-fictional-review.json'
                await (await completed.value).save_as(final)
                accepted = _gold_review(corpus, read_json(final), require_complete=True)
                assert accepted['cases'][1]['question'] == edited['question']
                assert all(c['label']['kind'] == 'human' for c in accepted['cases'])
                # This is declared fictional test data, never a real human review.
                assert errors == [] and remote == []
            finally:
                await browser.close()

    asyncio.run(exercise())
