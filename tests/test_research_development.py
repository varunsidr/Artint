"""Candidate gold authoring is read-only and never impersonates human review."""
import copy
import json
from pathlib import Path 
from unittest.mock import patch

import pytest

from app import storage
from app.intelligence import IntelligenceError
from scripts.evaluate_research import main
from scripts.research_eval.contracts import EvaluationError, load_corpus, read_json, write_json
from scripts.research_eval.development import (
    apply_gold_review, prepare_development, prepare_gold_review, snapshot_library, source_anchors,
)
from scripts.research_eval.runner import run


class DraftClient:
    def generate(self, model, prompt, schema):
        ids = schema['properties']['answerable_questions']['items']['properties']['evidence_anchors']['items']['enum']
        return dict(answerable_questions=[dict(question='What opening date does the saved station report give?',
            evidence_anchors=[ids[0]], required_facts=['The reported opening date.']),
            dict(question='Which capacity does the saved station report describe?',
                 evidence_anchors=[ids[-1]], required_facts=['The reported station capacity.'])],
            unanswerable_question=dict(question='What independently audited annual profit does the station report?',
                                      missing_information='A proposed absent quantity; a human must inspect the full source scope.'))


@pytest.fixture
def source_library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'personal.db')
    for key in ('station', 'garden', 'unassigned'):
        storage.upsert(dict(id=key, title='Original fictional ' + key, url='https://example.org/' + key,
            source='Fictional source', author='Original fixture author', published='2026-01-01',
            fetched_at='2026-10-30T00:00:00Z', text=(
                f'The fictional {key} project opened a new site in January 2026.\n'
                f'The published {key} project description reports capacity for forty visitors.\n'
                f'The {key} report explains the consultation method and its seasonal limitations.'),
            word_count=45, links_json='[]', images_json='[]', pdf_path=''))
    selection = dict(schema_version=1, name='Original proposed development cases', protocol='Purposive original test fixtures; no human quality claim.',
        groups=[dict(id='station', story_group='station-story', source_ids=['station'], distractor_ids=['garden']),
                dict(id='garden', story_group='garden-story', source_ids=['garden'], distractor_ids=['station'])])
    path = tmp_path / 'selection.json'
    write_json(path, selection)
    return storage.DB, path, selection


def prepared(source_library, tmp_path):
    database, selection, _ = source_library
    output = tmp_path / 'draft'
    prepare_development(database, selection, output, client=DraftClient())
    return output


def test_readonly_library_snapshot_and_unassigned_sources_do_not_leak_text(source_library):
    database, _, selection = source_library
    before = database.read_bytes()
    sources, unassigned, audit, revision = snapshot_library(database, selection)
    assert database.read_bytes() == before
    assert {source['id'] for source in sources} == {'station', 'garden'}
    assert len(unassigned) == 1 and 'text' not in unassigned[0]
    assert 'not cleared' in unassigned[0]['status']
    assert all(source['source_type'] == 'other' for source in sources)
    assert all(item['source_type_review'] == 'pending' for item in audit.values())


def test_anchor_sampling_keeps_full_range_and_exact_offsets(source_library):
    sources, *_ = snapshot_library(source_library[0], source_library[2])
    source = sources[0]
    anchors = source_anchors(source)
    assert len(anchors) == 3  # Fewer anchors must not lose the end of the source.
    assert all(source['text'][anchor['start']:anchor['end']] == anchor['quote'] for anchor in anchors)
    assert anchors[-1]['quote'].endswith('limitations.')


def test_drafting_is_provisional_and_uses_isolated_readonly_source_input(source_library, tmp_path):
    database, selection, _ = source_library
    before = database.read_bytes()
    with patch('requests.request', side_effect=AssertionError('Network forbidden')):
        summary = prepare_development(database, selection, tmp_path / 'draft', client=DraftClient())
    corpus = load_corpus(tmp_path / 'draft/corpus.json')
    assert summary['drafted_cases'] == 6 and summary['human_reviewed_cases'] == 0
    assert summary['proposed_answerable'] == 4 and summary['proposed_unanswerable'] == 2
    assert summary['heldout_independence_established'] is False
    assert all(case['label']['kind'] == 'unreviewed' for case in corpus['cases'])
    assert database.read_bytes() == before and storage.DB == database
    assert all(note['absence_verified'] is False for note in read_json(tmp_path / 'draft/proposal-notes.json'))
    report = run(tmp_path / 'draft/corpus.json', tmp_path / 'diagnostic')
    assert report['summary']['gold_label_kinds'] == {'unreviewed': 6}
    assert report['summary']['quality_gate'] == 'not_established'
    with pytest.raises(EvaluationError, match='already exists'):
        prepare_development(database, selection, tmp_path / 'draft', client=DraftClient())


def test_unavailable_model_does_not_leave_new_output_or_traceback(source_library, tmp_path, capsys):
    database, selection, _ = source_library
    with patch('scripts.research_eval.development.RecordedOllama.identity', side_effect=IntelligenceError('Cannot reach Ollama')):
        result = main(['prepare-development', '--database', str(database), '--selection', str(selection), '--output', str(tmp_path/'offline')])
    assert result == 2 and not (tmp_path/'offline').exists()
    assert 'Traceback' not in capsys.readouterr().err


def test_missing_database_and_invalid_selection_never_create_a_library(tmp_path):
    selection = dict(schema_version=1, name='Missing source', protocol='Test selection.',
        groups=[dict(id='one', story_group='one', source_ids=['missing'], distractor_ids=[])])
    with pytest.raises(EvaluationError, match='does not exist'):
        snapshot_library(tmp_path / 'missing.db', selection)
    assert not (tmp_path / 'missing.db').exists()
    selection['groups'][0]['distractor_ids'] = ['missing']
    with pytest.raises(EvaluationError, match='Distractors'):
        snapshot_library(tmp_path / 'missing.db', selection)


def test_failed_drafts_are_visible_and_cannot_be_mistaken_for_sixty_cases(source_library, tmp_path):
    class Broken(DraftClient):
        def generate(self, *args):
            raise IntelligenceError('Test failure')
    summary = prepare_development(source_library[0], source_library[1], tmp_path/'broken', client=Broken())
    assert summary['status'] == 'incomplete' and summary['drafted_cases'] == 0
    assert len(summary['failures']) == 2 and not (tmp_path/'broken/corpus.json').exists()
    assert len((tmp_path/'broken/drafts.jsonl').read_text().splitlines()) == 2


def test_gold_review_starts_pending_and_browser_payload_escapes_markup(source_library, tmp_path):
    draft = prepared(source_library, tmp_path)
    corpus = read_json(draft/'corpus.json')
    corpus['cases'][0]['question'] = '</script><script>globalThis.injected=true</script>'
    path = tmp_path/'unsafe-question.json'
    write_json(path, corpus)
    prepare_gold_review(path, tmp_path/'review')
    review = read_json(tmp_path/'review/gold-review.json')
    assert review['review_kind'] == 'unreviewed' and not review['reviewer']
    assert all(row['decision'] == 'pending' for row in review['judgments'])
    html = (tmp_path/'review/review.html').read_text(encoding='utf-8')
    assert '\\u003c/script>' in html and 'fetch(' not in html
    with pytest.raises(EvaluationError, match='Review every case'):
        apply_gold_review(path, tmp_path/'review/gold-review.json', tmp_path/'should-not-exist')
    assert not (tmp_path/'should-not-exist').exists()


def human_decisions(review, *, reviewer='Test fixture reviewer'):
    result = copy.deepcopy(review)
    result.update(review_kind='human', reviewer=reviewer, reviewed_at='2026-10-30T12:00:00Z', source_grouping_reviewed=True)
    for row in result['judgments']:
        row['decision'] = 'accept'
    return result


def test_applying_gold_requires_complete_human_declarations_and_preserves_exclusions(source_library, tmp_path):
    draft = prepared(source_library, tmp_path)
    corpus_path = draft/'corpus.json'
    prepare_gold_review(corpus_path, tmp_path/'review')
    primary = human_decisions(read_json(tmp_path/'review/gold-review.json'))
    primary['judgments'][0].update(decision='exclude', notes='Test-only source/case exclusion.')
    primary['judgments'][1]['decision'] = 'revise'
    primary['judgments'][1]['case']['question'] = 'Which visitor capacity is reported for this fictional site?'
    path = tmp_path/'filled.json'
    write_json(path, primary)
    summary = apply_gold_review(corpus_path, path, tmp_path/'reviewed')
    result = load_corpus(tmp_path/'reviewed/corpus.json')
    assert summary['eligible_cases'] == 5 and summary['excluded_cases'] == 1
    assert all(case['label']['kind'] == 'human' for case in result['cases'])
    assert all('gold_review_pending' not in case['tags'] for case in result['cases'])
    assert result['cases'][0]['eligible'] is False
    assert summary['count_targets_met'] is False and summary['quality_gate'] == 'not_established'
    assert all(case['label']['kind']=='unreviewed' for case in load_corpus(corpus_path)['cases'])


@pytest.mark.parametrize('damage',['stale','drop','missing_person','missing_time','model','no_group_ack','silent_edit','scope_change','bad_span'])
def test_invalid_gold_approval_is_rejected_before_writing(source_library, tmp_path, damage):
    draft = prepared(source_library, tmp_path)
    prepare_gold_review(draft/'corpus.json', tmp_path/'review')
    review = human_decisions(read_json(tmp_path/'review/gold-review.json'))
    if damage=='stale': review['proposal_sha256']='0'*64
    elif damage=='drop': review['judgments'].pop()
    elif damage=='missing_person': review['reviewer']=''
    elif damage=='missing_time': review['reviewed_at']=''
    elif damage=='model': review['review_kind']='model'
    elif damage=='no_group_ack': review['source_grouping_reviewed']=False
    elif damage=='silent_edit': review['judgments'][0]['case']['question']='Silently changed question?'
    elif damage=='scope_change': review['judgments'][0]['case']['source_ids']=['unassigned']
    else:
        review['judgments'][0]['decision']='revise'
        review['judgments'][0]['case']['evidence'][0]['start']=99999
    write_json(tmp_path/'bad-review.json',review)
    with pytest.raises(EvaluationError):
        apply_gold_review(draft/'corpus.json',tmp_path/'bad-review.json',tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_double_gold_review_rejects_same_reviewer_and_disagreements(source_library, tmp_path):
    draft = prepared(source_library,tmp_path)
    prepare_gold_review(draft/'corpus.json',tmp_path/'review')
    template=read_json(tmp_path/'review/gold-review.json')
    a=human_decisions(template,reviewer='Reviewer A')
    b=human_decisions(template,reviewer='Reviewer B')
    write_json(tmp_path/'a.json',a);write_json(tmp_path/'b.json',b)
    result=apply_gold_review(draft/'corpus.json',tmp_path/'a.json',tmp_path/'both',second_review=tmp_path/'b.json')
    assert result['double_reviewed_cases']==6
    b['judgments'][0]['decision']='exclude';b['judgments'][0]['notes']='Different eligibility judgment.'
    (tmp_path/'b.json').write_text(json.dumps(b),encoding='utf-8')
    with pytest.raises(EvaluationError,match='disagree'):
        apply_gold_review(draft/'corpus.json',tmp_path/'a.json',tmp_path/'disagree',second_review=tmp_path/'b.json')
    assert not (tmp_path/'disagree').exists()
