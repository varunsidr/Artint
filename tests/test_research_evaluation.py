"""Research harness regressions; no publisher traffic or real-model quality claims."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app import storage
from app.intelligence import IntelligenceError
from scripts.evaluate_research import main
from scripts.research_eval.compare import compare
from scripts.research_eval.contracts import EvaluationError, check_disjoint, digest, load_corpus, read_json, validate_corpus, write_json
from scripts.research_eval.metrics import clustered_mean, passage_locations, retrieval_metrics
from scripts.research_eval.review import prepare_review, review_summary
from scripts.research_eval.runner import FixtureClient, ObservedClient, freeze, load_run, run

FIXTURE = Path(__file__).parent / 'fixtures/research/synthetic-v1.json'


@pytest.mark.parametrize('failure', [True, False])
def test_observer_preserves_context_attempts_for_success_and_failure(failure):
    from unittest.mock import Mock
    delegate = Mock()
    delegate.last_generation = dict(context_window=16384,
        attempts=[dict(context_window=8192, status='context_exceeded')])
    delegate.generate.return_value = {'supported': False, 'claims': []}
    if failure:
        delegate.generate.side_effect = IntelligenceError('16K context exceeded')
    observed = ObservedClient(delegate)
    assert observed.last_generation == {}  # No previous case's generation metadata.
    if failure:
        with pytest.raises(IntelligenceError):
            observed.generate('model', 'prompt', {})
    else:
        observed.generate('model', 'prompt', {})
    delegate.last_generation['attempts'].clear()
    assert observed.last_generation['context_window'] == 16384
    assert observed.last_generation['attempts'][0]['status'] == 'context_exceeded'


@pytest.fixture
def corpus():
    return load_corpus(FIXTURE)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def small_corpus(corpus, path, *, count=1):
    result = copy.deepcopy(corpus)
    result['cases'] = result['cases'][:count]
    write_json(path, result)
    return path


def test_original_fixture_contract_and_scope(corpus):
    assert len(corpus['cases']) == 24 and len(corpus['sources']) == 16
    assert sum(case['answerability'] == 'unanswerable' for case in corpus['cases']) == 8
    assert len({case['story_group'] for case in corpus['cases']}) == 8
    assert all(case['label']['kind'] == 'synthetic' for case in corpus['cases'])
    long = next(case for case in corpus['cases'] if case['id'] == 'larch-1')
    assert len(long['acceptable_sets']) == 2 and long['evidence'][0]['start'] > 18000


@pytest.mark.parametrize('damage', ['duplicate_case', 'source_hash', 'quote', 'stale_evidence', 'scope',
                                  'missing_fact', 'missing_gold', 'false_exclusion', 'silent_exclusion', 'false_human'])
def test_invalid_gold_and_provenance_are_rejected(corpus, damage):
    case = corpus['cases'][0]
    if damage == 'duplicate_case':
        corpus['cases'].append(copy.deepcopy(case))
    elif damage == 'source_hash':
        corpus['sources'][0]['text'] += ' Changed.'
    elif damage == 'quote':
        case['evidence'][0]['quote'] = 'Invented gold statement.'
    elif damage == 'stale_evidence':
        case['evidence'][0]['text_sha256'] = '0' * 64
    elif damage == 'scope':
        case['source_ids'] = ['missing-source']
    elif damage == 'missing_fact':
        case['required_facts'] = []
    elif damage == 'missing_gold':
        case['acceptable_sets'] = []
    elif damage == 'false_exclusion':
        case['exclusion_reason'] = 'Hide this failure.'
    elif damage == 'silent_exclusion':
        case['eligible'] = False
    else:
        case['label']['kind'] = 'human'
    with pytest.raises(EvaluationError):
        validate_corpus(corpus)


def test_separate_corpora_reject_story_or_exact_source_leakage(corpus):
    with pytest.raises(EvaluationError, match='corpus kinds'):
        check_disjoint(corpus, corpus)
    corpus['kind'] = 'development'
    for case in corpus['cases']:
        case['split'] = 'development'
    other = copy.deepcopy(corpus)
    other['kind'] = 'heldout'
    for case in other['cases']:
        case['split'] = 'heldout'
    with pytest.raises(EvaluationError, match='share story families'):
        check_disjoint(corpus, other)
    for source in other['sources']:
        source['story_group'] += '-renamed'
    for case in other['cases']:
        case['story_group'] += '-renamed'
    # Renaming stories does not hide exact syndicated source copies.
    with pytest.raises(EvaluationError, match='exact source text'):
        check_disjoint(corpus, other)


def test_span_alignment_preserves_original_unicode_whitespace_and_repeated_text(corpus):
    source = dict(corpus['sources'][0], text=('\t日本語  repeated\n\n' + 'A' * 3000 + '\n repeated\ttext '))
    source['text_sha256'] = digest(source['text'].encode())
    locations = list(passage_locations([source]).values())
    assert len(locations) > 2
    assert locations[0]['start'] == 1 and locations[-1]['end'] < len(source['text'])
    assert all(''.join(row['text'].split()) == ''.join(source['text'][row['start']:row['end']].split()) for row in locations)
    assert all(left['end'] <= right['start'] for left, right in zip(locations, locations[1:]))
    with patch('scripts.research_eval.metrics.article_passages', return_value=[dict(id='invented', text='not source text')]):
        with pytest.raises(EvaluationError, match='aligned exactly'):
            passage_locations([source])


def test_recall_mrr_and_alternative_sets_have_known_denominators(corpus):
    source = dict(corpus['sources'][0], text='Noise here. First target. Second target.')
    source['text_sha256'] = digest(source['text'].encode())
    def span(text):
        start = source['text'].index(text)
        return dict(source_id=source['id'], start=start, end=start+len(text))
    evidence = [dict(id='first', **span('First target.')), dict(id='second', **span('Second target.'))]
    case = dict(corpus['cases'][0], evidence=evidence, acceptable_sets=[['first', 'second']])
    ranked = [span('Noise here.'), span('First target.')]
    measured = retrieval_metrics(case, ranked, [source], 10)
    assert measured['recall_at_5'] == .5 and measured['sufficient_at_5'] == 0
    assert measured['mrr_at_10'] == .5
    case['acceptable_sets'] = [['first'], ['second']]
    alternative = retrieval_metrics(case, ranked, [source], 10)
    assert alternative['recall_at_5'] == alternative['sufficient_at_5'] == 1
    answer_budget = retrieval_metrics(case, ranked, [source], 6)
    assert answer_budget['recall_at_10'] is answer_budget['mrr_at_10'] is None


def test_cross_chunk_gold_requires_both_passages(corpus):
    source = dict(corpus['sources'][0], text='A' * 2500)
    source['text_sha256'] = digest(source['text'].encode())
    passages = list(passage_locations([source]).values())
    case = dict(corpus['cases'][0], evidence=[dict(id='cross', source_id=source['id'], start=950, end=1050)], acceptable_sets=[['cross']])
    assert retrieval_metrics(case, passages[:1], [source], 10)['recall_at_5'] == 0
    assert retrieval_metrics(case, passages[:2], [source], 10)['recall_at_5'] == 1


def test_story_bootstrap_does_not_count_repeats_as_independent_cases():
    first = clustered_mean([('story-a', 'a', 0), ('story-b', 'b', 1)])
    repeated = clustered_mean([('story-a', 'a', 0)] * 100 + [('story-b', 'b', 1)])
    assert first == repeated and first['value'] == .5 and first['story_clusters'] == 2
    assert clustered_mean([('one-story', 'a', 1)])['ci95'] is None


def test_freeze_is_offline_exclusive_and_bound_to_its_manifest(tmp_path):
    frozen = tmp_path / 'frozen'
    with patch('requests.request', side_effect=AssertionError('Network forbidden')):
        freeze(FIXTURE, frozen)
    with pytest.raises(FileExistsError):
        freeze(FIXTURE, frozen)
    changed = load_corpus(frozen / 'corpus.json')
    changed['name'] += ' changed'
    save(frozen / 'corpus.json', changed)
    with pytest.raises(EvaluationError, match='Frozen corpus changed'):
        run(frozen / 'corpus.json', tmp_path / 'should-not-exist')
    assert not (tmp_path / 'should-not-exist').exists()


def test_full_fixture_run_is_offline_and_never_opens_personal_storage(tmp_path, monkeypatch):
    personal = tmp_path / 'personal.db'
    personal.write_bytes(b'Private database sentinel; not valid SQLite')
    pdf = tmp_path / 'private.pdf'
    pdf.write_bytes(b'Private PDF sentinel')
    monkeypatch.setattr(storage, 'DB', personal)
    with patch('app.intelligence.requests.request', side_effect=AssertionError('Network forbidden')):
        report = run(FIXTURE, tmp_path / 'run')
    assert report['status'] == 'complete' and report['summary']['eligible_cases'] == 24
    assert report['summary']['gold_label_kinds'] == {'synthetic': 24}
    assert storage.DB == personal and personal.read_bytes().startswith(b'Private database sentinel')
    assert pdf.read_bytes() == b'Private PDF sentinel'
    assert not list((tmp_path / 'run').rglob('*.db'))
    assert report['summary']['claim_support'] is None and report['summary']['quality_gate'] == 'not_established'
    with pytest.raises(FileExistsError):
        run(FIXTURE, tmp_path / 'run')


def test_shared_cache_reuses_vectors_and_failures_stay_in_denominators(tmp_path, corpus, monkeypatch):
    path = small_corpus(corpus, tmp_path / 'corpus.json')
    report = run(path, tmp_path / 'shared', cache='shared', repeats=2)
    assert report['cases'][0]['cache']['embeddings_created'] > 0
    assert report['cases'][1]['cache']['embeddings_created'] == 0
    broken = FixtureClient()
    broken.embed = lambda *args, **kwargs: (_ for _ in ()).throw(IntelligenceError('Test failure'))
    personal = storage.DB
    failed = run(path, tmp_path / 'failed', client=broken)
    assert storage.DB == personal and failed['status'] == 'failed'
    assert failed['summary']['failed_runs'] == failed['summary']['case_runs'] == 1
    assert failed['summary']['metrics']['recall_at_5']['value'] == 0
    assert failed['summary']['timing']['pipeline_seconds']['observations'] == 0


def test_exclusions_are_explicit_and_answer_budget_is_six(tmp_path, corpus):
    corpus['cases'] = corpus['cases'][:2]
    corpus['cases'][1].update(eligible=False, exclusion_reason='Test-only excluded fixture')
    write_json(tmp_path / 'corpus.json', corpus)
    report = run(tmp_path / 'corpus.json', tmp_path / 'answers', mode='answers')
    assert report['summary']['excluded_cases'] == report['summary']['case_runs'] == 1
    assert report['cases'][1]['status'] == 'excluded'
    assert len(report['cases'][0]['passages']) == 6
    assert report['summary']['metrics']['recall_at_10']['value'] is None


@pytest.fixture
def answer_run(tmp_path, corpus):
    path = small_corpus(corpus, tmp_path / 'corpus.json')
    directory = tmp_path / 'answers'
    run(path, directory, mode='answers')
    return directory


def test_pending_review_does_not_fabricate_quality_and_cannot_overwrite(answer_run, tmp_path):
    path = tmp_path / 'review.json'
    template = prepare_review(answer_run, path)
    assert template['review_kind'] == 'unreviewed'
    summary = review_summary(answer_run, path)
    assert summary['reviewed_atomic_claims'] == summary['complete_case_runs'] == 0
    assert summary['claim_support']['value'] is summary['useful_answer_coverage_reviewed']['value'] is None
    with pytest.raises(EvaluationError, match='already exists'):
        prepare_review(answer_run, path)


def fill_review(answer_run, path, reviewer='Test-only reviewer'):
    review = prepare_review(answer_run, path)
    review.update(review_kind='human', reviewer=reviewer, reviewed_at='2026-10-30T01:00:00Z')
    judgment = review['judgments'][0]
    judgment.update(decision='partial', atomic_complete=True, covered_facts=['f1'])
    for claim in judgment['claims']:
        for unit in claim['units']:
            unit.update(support='supported', citation='supported')
    return review


def test_atomic_claim_denominator_and_declared_human_provenance(answer_run, tmp_path):
    path = tmp_path / 'review.json'
    review = fill_review(answer_run, path)
    claim = review['judgments'][0]['claims'][0]
    claim['units'] = [dict(id=1, text='One test atomic assertion.', support='supported', citation='supported'),
                      dict(id=2, text='Another test atomic assertion.', support='partial', citation='partial')]
    save(path, review)
    summary = review_summary(answer_run, path)
    assert summary['reviewed_atomic_claims'] == 2 and summary['claim_support']['value'] == .5
    assert summary['quality_gate'] == 'not_established' and summary['corpus_kind'] == 'synthetic'
    review['review_kind'] = 'model'
    save(path, review)
    with pytest.raises(EvaluationError):
        review_summary(answer_run, path)


def test_second_review_requires_distinct_people_and_reports_disagreement(answer_run, tmp_path):
    first, second = tmp_path / 'a.json', tmp_path / 'b.json'
    a = fill_review(answer_run, first, 'Reviewer A')
    b = fill_review(answer_run, second, 'Reviewer B')
    b['judgments'][0]['claims'][0]['units'][0].update(support='unsupported', citation='unsupported')
    save(first, a); save(second, b)
    report = review_summary(answer_run, first, second)
    assert report['double_reviewed_case_runs'] == 1 and len(report['disagreements']) == 1
    b['reviewer'] = 'reviewer a'
    save(second, b)
    with pytest.raises(EvaluationError, match='distinct'):
        review_summary(answer_run, first, second)


@pytest.mark.parametrize('damage', ['drop_case', 'duplicate_case', 'claim_hash', 'missing_reviewer', 'missing_time', 'complete_without_facts'])
def test_incomplete_stale_or_misattributed_reviews_are_rejected(answer_run, tmp_path, damage):
    path = tmp_path / 'review.json'
    review = fill_review(answer_run, path)
    if damage == 'drop_case':
        review['judgments'] = []
    elif damage == 'duplicate_case':
        review['judgments'] *= 2
    elif damage == 'claim_hash':
        review['judgments'][0]['claims'][0]['claim_sha256'] = '0' * 64
    elif damage == 'missing_reviewer':
        review['reviewer'] = ''
    elif damage == 'missing_time':
        review['reviewed_at'] = ''
    else:
        review['judgments'][0].update(decision='complete', covered_facts=[])
    save(path, review)
    with pytest.raises(EvaluationError):
        review_summary(answer_run, path)


def test_changed_run_invalidates_review_and_changed_evidence_is_rejected(answer_run, tmp_path):
    review_path = tmp_path / 'review.json'
    prepare_review(answer_run, review_path)
    report_path = answer_run / 'report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    report['created_at'] = '2026-10-30T12:00:00Z'
    save(report_path, report)
    with pytest.raises(EvaluationError, match='stale'):
        review_summary(answer_run, review_path)
    report['cases'][0]['passages'][0]['text'] += ' Injected.'
    save(report_path, report)
    with pytest.raises(EvaluationError, match='changed'):
        load_run(answer_run)


def test_engine_snapshot_integrity_and_independence_from_current_chunker(answer_run, tmp_path):
    with patch('scripts.research_eval.metrics.article_passages', side_effect=AssertionError('Current chunker must not validate old evidence')):
        load_run(answer_run)
        result = compare(answer_run, answer_run, tmp_path / 'comparison')
    assert all(metric['value'] == 0 for metric in result['deltas'].values())
    snapshot = answer_run / 'engine-snapshot/app/intelligence.py'
    snapshot.write_text('changed', encoding='utf-8')
    with pytest.raises(EvaluationError, match='Engine snapshot changed'):
        load_run(answer_run)


def test_cli_runs_and_rejects_mismatched_comparisons(tmp_path, corpus, capsys):
    path = small_corpus(corpus, tmp_path / 'corpus.json')
    assert main(['validate', '--corpus', str(path)]) == 0
    assert main(['run', '--corpus', str(path), '--output', str(tmp_path / 'baseline')]) == 0
    assert main(['run', '--corpus', str(path), '--output', str(tmp_path / 'candidate'), '--cache', 'shared']) == 0
    assert main(['compare', '--baseline', str(tmp_path / 'baseline'), '--candidate', str(tmp_path / 'candidate'),
                 '--output', str(tmp_path / 'comparison')]) == 2
    assert not (tmp_path / 'comparison').exists()
    assert main(['run', '--corpus', str(path), '--output', str(tmp_path / 'baseline')]) == 2


@pytest.mark.parametrize('text', ['{"duplicate":1,"duplicate":2}', '{"nonfinite":NaN}', '{"nonfinite":Infinity}'])
def test_nonstandard_or_ambiguous_json_is_rejected(tmp_path, text):
    path = tmp_path / 'bad.json'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(EvaluationError):
        read_json(path)


def test_partial_run_journal_survives_interrupt_and_restores_storage(tmp_path, corpus):
    path = small_corpus(corpus, tmp_path / 'corpus.json', count=2)
    client = FixtureClient()
    # Raising at the second semantic_search invocation leaves exactly one row.
    from app.intelligence import semantic_search as actual_search
    requests = 0
    def search(*args, **kwargs):
        nonlocal requests
        requests += 1
        if requests == 2:
            raise KeyboardInterrupt()
        return actual_search(*args, **kwargs)
    original_db = storage.DB
    with patch('scripts.research_eval.runner.semantic_search', side_effect=search):
        with pytest.raises(KeyboardInterrupt):
            run(path, tmp_path / 'interrupted', client=client)
    assert storage.DB == original_db
    journal = (tmp_path / 'interrupted/results.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(journal) == 1 and json.loads(journal[0])['status'] == 'ok'
    assert not (tmp_path / 'interrupted/report.json').exists()


def test_live_model_identity_change_invalidates_a_run(tmp_path, corpus):
    path = small_corpus(corpus, tmp_path / 'corpus.json')
    client = FixtureClient()
    client.request_settings = {}
    from unittest.mock import Mock
    client.identity = Mock(side_effect=[dict(models={'embedding': {'digest': 'a'*64}}, runtime_version='test'),
                                       dict(models={'embedding': {'digest': 'b'*64}}, runtime_version='test')])
    with patch('scripts.research_eval.runner.RecordedOllama', return_value=client):
        report = run(path, tmp_path / 'changed', engine='ollama')
    assert report['status'] == 'invalid' and report['model_identity_changed']
    with pytest.raises(EvaluationError, match='model identity'):
        compare(tmp_path / 'changed', tmp_path / 'changed', tmp_path / 'comparison')
