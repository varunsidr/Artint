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


@pytest.mark.parametrize('field', ['extraction_sha256', 'cleanup_sha256'])
def test_resume_rejects_an_engine_change_in_the_same_phase(tmp_path, field):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    path = tmp_path/'baseline.json'
    report = json.loads(path.read_text())
    report[field] = 'different'
    path.write_text(json.dumps(report))
    args = options(tmp_path)
    args.resume = True
    with pytest.raises(ValueError, match='different source/code'):
        evaluation.evaluate(args)


def test_frozen_extraction_refuses_a_changed_cleanup_dependency(tmp_path):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    report = json.loads((tmp_path/'baseline.json').read_text())
    report['cleanup_sha256'] = 'different'
    (tmp_path/'initial-diagnostics.json').write_text(json.dumps(report))
    (tmp_path/'local-cache/baseline-extract.py').write_bytes((evaluation.ROOT/'app/extract.py').read_bytes())
    args = options(tmp_path)
    args.engine = 'frozen'
    args.resume = True
    with pytest.raises(ValueError, match='cleanup dependency'):
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


def labelled_rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def write_labels(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def human_label(row, eligibility='eligible'):
    row.update(eligibility=eligibility, review_kind='human', reviewer='Synthetic test reviewer',
               reviewed_at=evaluation.stamp(), **{criterion: 'pass' for criterion in evaluation.REVIEW_CRITERIA})


def test_phase_review_is_offline_hash_bound_and_does_not_overwrite_labels(tmp_path, monkeypatch):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    snapshot = (tmp_path / 'baseline.json').read_bytes()
    legacy = (tmp_path / 'review.csv').read_bytes()
    monkeypatch.setattr(evaluation, '_request_html', lambda _: pytest.fail('Review cannot fetch'))
    path = evaluation.prepare_phase_review(tmp_path, 'baseline')
    result = evaluation.summarize_phase_review(tmp_path, 'baseline')
    assert result['pending'] == 2 and result['pass_rate'] is None and not result['release_gate_met']
    assert (tmp_path / 'baseline.json').read_bytes() == snapshot
    assert (tmp_path / 'review.csv').read_bytes() == legacy
    assert 'regional electricity systems' not in path.read_text(encoding='utf-8')
    with pytest.raises(FileExistsError):
        evaluation.prepare_phase_review(tmp_path, 'baseline')


def test_stale_source_or_wrong_phase_cannot_reuse_human_labels(tmp_path):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    path = evaluation.prepare_phase_review(tmp_path, 'baseline')
    fields, rows = labelled_rows(path)
    human_label(rows[0])
    write_labels(path, fields, rows)
    result = evaluation.summarize_phase_review(tmp_path, 'baseline')
    assert result['reviewed_eligible'] == result['passed'] == 1
    args = options(tmp_path)
    args.phase = 'improved'
    evaluation.evaluate(args)
    with pytest.raises(ValueError, match='stale'):
        evaluation.summarize_phase_review(tmp_path, 'improved', path)
    report_path = tmp_path / 'baseline.json'
    report = json.loads(report_path.read_text())
    report['results'][0]['text_sha256'] = 'changed-copy'
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='stale'):
        evaluation.summarize_phase_review(tmp_path, 'baseline')


@pytest.mark.parametrize('change', ['missing', 'duplicate'])
def test_phase_review_keeps_every_frozen_case(tmp_path, change):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    path = evaluation.prepare_phase_review(tmp_path, 'baseline')
    fields, rows = labelled_rows(path)
    write_labels(path, fields, rows[:1] if change == 'missing' else [rows[0], rows[0]])
    with pytest.raises(ValueError, match='missing|duplicate'):
        evaluation.summarize_phase_review(tmp_path, 'baseline')


def test_eligible_capture_failures_stay_in_the_human_denominator(tmp_path):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    report_path = tmp_path / 'baseline.json'
    report = json.loads(report_path.read_text())
    report['results'][1].update(status='failed', failure={'code': 'http_blocked'})
    report_path.write_text(json.dumps(report))
    path = evaluation.prepare_phase_review(tmp_path, 'baseline')
    fields, rows = labelled_rows(path)
    for row in rows:
        human_label(row)
    write_labels(path, fields, rows)
    result = evaluation.summarize_phase_review(tmp_path, 'baseline')
    assert result['reviewed_eligible'] == 2 and result['passed'] == result['failed'] == 1
    assert result['pass_rate'] == .5 and result['wilson_95_interval'][0] < .5
    assert result['by_source_kind']['article']['reviewed'] == 2
    assert not result['release_gate_met'] and not result['prospective_cohort']


def test_exclusions_and_second_review_require_real_decisions_and_distinct_names(tmp_path):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    path = evaluation.prepare_phase_review(tmp_path, 'baseline')
    fields, rows = labelled_rows(path)
    human_label(rows[0], eligibility='excluded')
    write_labels(path, fields, rows)
    with pytest.raises(ValueError, match='exclusion requires'):
        evaluation.summarize_phase_review(tmp_path, 'baseline')
    human_label(rows[0])
    write_labels(path, fields, rows)
    with pytest.raises(ValueError, match='different human'):
        evaluation.summarize_phase_review(tmp_path, 'baseline', second_review_path=path)


def test_prospective_freeze_requires_a_protocol_and_never_fetches(tmp_path, monkeypatch):
    candidates, protocol = tmp_path / 'candidates.csv', tmp_path / 'protocol.json'
    candidates.write_text('url,source_kind\nhttps://example.org/one,article\nhttps://example.net/two,opinion\n')
    protocol.write_text(json.dumps(dict(name='Original synthetic fixture', selection_method='Predeclared test cases',
                                       inclusion_criteria='Individual synthetic HTML articles', exclusion_criteria='Listing and file pages')))
    monkeypatch.setattr(evaluation, '_request_html', lambda _: pytest.fail('Freeze cannot fetch'))
    with pytest.raises(ValueError, match='protocol'):
        evaluation.freeze_candidates(candidates, None, tmp_path / 'cohort')
    manifest = evaluation.freeze_candidates(candidates, protocol, tmp_path / 'cohort')
    result = json.loads(manifest.read_text())
    assert result['cohort_kind'] == 'prospective_candidates' and len(result['cases']) == 2
    assert result['protocol_sha256'] == evaluation.digest(protocol.read_bytes())
    with pytest.raises(ValueError, match='new cohort'):
        evaluation.freeze_candidates(candidates, protocol, tmp_path / 'cohort')


def test_modified_local_reading_cannot_be_certified_by_unchanged_report_hashes(tmp_path):
    cases = fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    evaluation.prepare_phase_review(tmp_path, 'baseline')
    reading = tmp_path / 'local-cache' / (cases[0]['id'] + '.baseline.txt')
    reading.write_text(reading.read_text(encoding='utf-8') + '\nChanged evidence.', encoding='utf-8')
    with pytest.raises(ValueError, match='stale or modified'):
        evaluation.summarize_phase_review(tmp_path, 'baseline')


def test_second_reviewer_eligibility_disagreement_is_not_dropped(tmp_path):
    fixture(tmp_path)
    evaluation.evaluate(options(tmp_path))
    path = evaluation.prepare_phase_review(tmp_path, 'baseline')
    fields, rows = labelled_rows(path)
    human_label(rows[0])
    write_labels(path, fields, rows)
    rows[0].update(eligibility='excluded', exclusion_reason='Synthetic reviewer disagrees on source type.', reviewer='Second synthetic reviewer')
    second = tmp_path / 'second-review.csv'
    write_labels(second, fields, rows)
    result = evaluation.summarize_phase_review(tmp_path, 'baseline', second_review_path=second)
    assert result['disagreements'] == [rows[0]['id']]
    assert result['double_reviewed'] == 1 and not result['release_gate_met']
