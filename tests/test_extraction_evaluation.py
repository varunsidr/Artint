import csv
import json
from types import SimpleNamespace

import pytest

from scripts import evaluate_extraction as evaluation
from tests.test_browser_extraction import FULL_HTML


def fixture(tmp_path):
    cases = []
    cache = tmp_path/'local-cache'
    cache.mkdir()
    for number in range(2):
        url = f'https://example.org/research-{number}'
        case = dict(id=evaluation.digest(url.encode())[:16], url=url, publisher='example.org',
                    source_kind='article', prior_title='Research')
        cases.append(case)
        (cache/(case['id']+'.json')).write_text(json.dumps(dict(requested_url=url, final_url=url, html=FULL_HTML)), encoding='utf-8')
    (tmp_path/'manifest.json').write_text(json.dumps(dict(cases=cases, limitations='Synthetic fixture, no reviewed benchmark.')), encoding='utf-8')
    return cases


def options(tmp_path, **kwargs):
    return SimpleNamespace(**dict(output=tmp_path, freeze=False, offline=True, mode='html', phase='baseline',
                                  resume=False, engine='current', audit=None, **kwargs))


def test_offline_replay_never_fetches_and_keeps_reading_copies_local(tmp_path, monkeypatch):
    cases = fixture(tmp_path)
    monkeypatch.setattr(evaluation, '_request_html', lambda _: pytest.fail('Offline replay must not fetch'))
    evaluation.evaluate(options(tmp_path))
    report = json.loads((tmp_path/'baseline.json').read_text())
    assert report['summary']['captured'] == 2
    assert report['summary']['independent_review']['pass_rate'] is None
    assert report['summary']['independent_review']['release_gate_met'] is False
    assert len(list((tmp_path/'local-cache').glob('*.txt'))) == 2
    assert all(row['transport'] == 'local_replay' for row in report['results'])
    # Public report carries diagnostics and hashes, not publisher article bodies.
    assert 'regional electricity systems' not in (tmp_path/'baseline.json').read_text()


def test_offline_auto_is_rejected_before_any_browser_can_start(tmp_path):
    args = options(tmp_path)
    args.mode = 'auto'
    with pytest.raises(ValueError, match='requires HTML'):
        evaluation.evaluate(args)


def test_manifest_ids_cannot_escape_the_cache_directory(tmp_path):
    fixture(tmp_path)
    path = tmp_path/'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['cases'][0]['id'] = '../../outside'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='URL hashes'):
        evaluation.evaluate(options(tmp_path))


def test_resume_rejects_an_engine_change_in_the_same_phase(tmp_path):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    path = tmp_path/'baseline.json'
    report = json.loads(path.read_text())
    report['extraction_sha256'] = 'different'
    path.write_text(json.dumps(report))
    args = options(tmp_path)
    args.resume = True
    with pytest.raises(ValueError, match='different source/code'):
        evaluation.evaluate(args)


def test_review_accounting_requires_explicit_eligibility_all_criteria_and_reviewer(tmp_path):
    cases = fixture(tmp_path)
    path = tmp_path/'review.csv'
    evaluation.make_checklist(path, cases)
    assert evaluation.review_totals(path, cases)['reviewed_eligible'] == 0
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    rows[0].update(eligibility='eligible', reviewer='Reviewer', **{criterion:'pass' for criterion in evaluation.CRITERIA})
    rows[1].update(eligibility='excluded', reviewer='Reviewer', **{criterion:'pass' for criterion in evaluation.CRITERIA})
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    result = evaluation.review_totals(path, cases)
    assert result['reviewed_eligible'] == 1 and result['passed'] == 1 and result['pass_rate'] == 1
    assert result['release_gate_met'] is False


def test_duplicate_review_rows_cannot_inflate_the_benchmark(tmp_path):
    cases = fixture(tmp_path)
    path = tmp_path/'review.csv'
    evaluation.make_checklist(path, cases)
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows([rows[0], rows[0]])
    with pytest.raises(ValueError, match='duplicate'):
        evaluation.review_totals(path, cases)


def test_comparison_requires_identical_response_hashes_for_paired_count(tmp_path):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    args = options(tmp_path)
    args.phase = 'improved'
    evaluation.evaluate(args)
    comparison = evaluation.compare(tmp_path)
    assert comparison['paired_html_cases'] == 2 and comparison['metadata_changes'] == []
    assert comparison['outcome_changes'] == []
    assert (tmp_path/'comparison.md').exists()
