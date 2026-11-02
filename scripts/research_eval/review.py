"""Human review packets bound to a frozen run; never uses a model as judge."""
from collections import defaultdict
from pathlib import Path
from jsonschema import Draft202012Validator

from scripts.research_eval.contracts import EvaluationError, IDENTIFIER, SHA, array, obj, string, digest, encoded, read_json, valid_timestamp, write_json
from scripts.research_eval.metrics import interval
from scripts.research_eval.runner import load_run

SUPPORT = {'pending', 'supported', 'partial', 'unsupported', 'contradicted', 'unverifiable', 'non_factual'}
CITATION = {'pending', 'supported', 'partial', 'unsupported', 'missing', 'not_applicable'}
DECISIONS = {'pending', 'complete', 'partial', 'incorrect', 'uncertain', 'correct_abstention', 'incorrect_answer', 'pipeline_error'}
REVIEW_SCHEMA = obj(dict(schema_version=dict(const=1), report_sha256=SHA, corpus_sha256=SHA,
    review_kind=dict(enum=['unreviewed', 'human']), reviewer=dict(type='string', maxLength=100),
    reviewed_at=dict(type='string', maxLength=40), judgments=array(obj(dict(
        case_id=IDENTIFIER, repeat=dict(type='integer', minimum=1, maximum=5),
        decision=dict(enum=sorted(DECISIONS)), covered_facts=array(IDENTIFIER, 30), atomic_complete=dict(type='boolean'),
        notes=dict(type='string', maxLength=4000), claims=array(obj(dict(
            claim_index=dict(type='integer', minimum=0, maximum=4), claim_sha256=SHA,
            units=array(obj(dict(id=dict(type='integer', minimum=1), text=string(1200),
                                 support=dict(enum=sorted(SUPPORT)), citation=dict(enum=sorted(CITATION)))), 20, 1))), 5))), 5000)))


def prepare_review(run_directory, output):
    corpus, report, fingerprint = load_run(run_directory)
    if report['config']['mode'] != 'answers':
        raise EvaluationError('Human answer review requires an answer run.')
    cases = {case['id']: case for case in corpus['cases']}
    judgments, packet = [], []
    for row in report['cases']:
        if row['status'] == 'excluded':
            continue
        answer = row.get('answer', {})
        claims = []
        for index, claim in enumerate(answer.get('claims', [])):
            claims.append(dict(claim_index=index, claim_sha256=digest(encoded(claim)),
                units=[dict(id=1, text=claim['text'], support='pending', citation='pending')]))
        judgments.append(dict(case_id=row['case_id'], repeat=row['repeat'], decision='pending',
                              covered_facts=[], atomic_complete=False, claims=claims, notes=''))
        case = cases[row['case_id']]
        packet.append(dict(case_id=row['case_id'], repeat=row['repeat'], question=case['question'],
            answerability=case['answerability'], gold_label=case['label'], required_facts=case['required_facts'],
            gold_evidence=case['evidence'], pipeline_status=row['status'], claims=answer.get('claims', []),
            supported=answer.get('supported'), passages=row['passages']))
    template = dict(schema_version=1, report_sha256=fingerprint, corpus_sha256=report['corpus_sha256'],
                    review_kind='unreviewed', reviewer='', reviewed_at='', judgments=judgments)
    output = Path(output)
    packet_path = output.with_name(output.stem + '.packet.json')
    if output.exists() or packet_path.exists():
        raise EvaluationError('Review or packet already exists; never overwrite completed labels.')
    output.parent.mkdir(parents=True, exist_ok=True)
    # The separate packet hides model names, but this is practical blinding,
    # not authenticated anonymity; reviewers can still open the run directory.
    write_json(output, template)
    write_json(packet_path, dict(schema_version=1, report_sha256=fingerprint,
        rubric='Split compound claims into atomic units. Judge only cited frozen passages. Mark all factual units and required facts; attest atomic_complete only after checking omissions.',
        cases=packet))
    return template


def _validate_review(corpus, report, fingerprint, review):
    if list(Draft202012Validator(REVIEW_SCHEMA).iter_errors(review)):
        raise EvaluationError('Review schema validation failed; check keys, types and allowed verdicts.')
    if (review.get('schema_version') != 1 or review.get('report_sha256') != fingerprint
            or review.get('corpus_sha256') != report['corpus_sha256']):
        raise EvaluationError('Review is stale or belongs to another run/corpus.')
    rows = {(row['case_id'], row['repeat']): row for row in report['cases'] if row['status'] != 'excluded'}
    cases = {case['id']: case for case in corpus['cases']}
    judgments = review.get('judgments')
    if not isinstance(judgments, list) or len(judgments) != len(rows):
        raise EvaluationError('Review must retain every eligible case/repeat, including pending/errors.')
    seen, graded = set(), False
    for judgment in judgments:
        key = (judgment.get('case_id'), judgment.get('repeat'))
        if key not in rows or key in seen:
            raise EvaluationError('Review contains duplicate or unexpected cases.')
        seen.add(key)
        row, case = rows[key], cases[key[0]]
        decision = judgment.get('decision')
        if decision not in DECISIONS or type(judgment.get('atomic_complete')) is not bool:
            raise EvaluationError('Invalid case decision or atomic-completeness attestation.')
        if not isinstance(judgment.get('notes'), str) or len(judgment['notes']) > 4000:
            raise EvaluationError('Review notes must be bounded text.')
        facts = judgment.get('covered_facts')
        allowed = {fact['id'] for fact in case['required_facts']}
        if not isinstance(facts, list) or any(not isinstance(fact, str) for fact in facts) or len(facts) != len(set(facts)) or not set(facts) <= allowed:
            raise EvaluationError('Covered facts must reference the frozen case facts.')
        answer = row.get('answer', {})
        if row['status'] == 'error' and decision not in ('pending', 'pipeline_error'):
            raise EvaluationError('A pipeline failure cannot be relabeled as a successful answer or abstention.')
        if row['status'] == 'ok' and decision == 'pipeline_error':
            raise EvaluationError('A successful run cannot be relabeled as a pipeline error.')
        if case['answerability'] == 'answerable':
            if decision not in ('pending', 'complete', 'partial', 'incorrect', 'uncertain', 'pipeline_error'):
                raise EvaluationError('Invalid answerable-case judgment.')
            if decision == 'complete' and (set(facts) != allowed or not answer.get('supported')):
                raise EvaluationError('A complete answer must return claims and cover every required fact.')
        elif decision not in ('pending', 'correct_abstention', 'incorrect_answer', 'uncertain', 'pipeline_error'):
            raise EvaluationError('Invalid unanswerable-case judgment.')
        elif decision == 'correct_abstention' and answer.get('supported') is not False:
            raise EvaluationError('An answer is not a correct abstention.')
        originals = answer.get('claims', [])
        claims = judgment.get('claims')
        if not isinstance(claims, list) or len(claims) != len(originals):
            raise EvaluationError('Review must retain all generated claims.')
        for index, (claim, original) in enumerate(zip(claims, originals)):
            if claim.get('claim_index') != index or claim.get('claim_sha256') != digest(encoded(original)):
                raise EvaluationError('Generated claim identity changed in review.')
            units = claim.get('units')
            if (not isinstance(units, list) or not 1 <= len(units) <= 20
                    or [unit.get('id') for unit in units] != list(range(1, len(units) + 1))):
                raise EvaluationError('Atomic units must have consecutive IDs, at most 20 per claim.')
            texts = set()
            for unit in units:
                text = unit.get('text')
                if not isinstance(text, str) or not text.strip() or len(text) > 1200 or text in texts:
                    raise EvaluationError('Atomic units need unique bounded text.')
                texts.add(text)
                support, citation = unit.get('support'), unit.get('citation')
                if support not in SUPPORT or citation not in CITATION:
                    raise EvaluationError('Invalid atomic-support or citation verdict.')
                if support == 'non_factual' and citation not in ('pending', 'not_applicable'):
                    raise EvaluationError('Non-factual units have no factual citation score.')
                if support not in ('pending', 'non_factual') and citation == 'not_applicable':
                    raise EvaluationError('Factual units need a citation-support verdict.')
                graded |= support != 'pending' or citation != 'pending'
        all_units = [unit for claim in claims for unit in claim['units']]
        if (decision == 'complete' and judgment['atomic_complete']
                and any(unit['support'] != 'pending' and unit['citation'] != 'pending'
                        and unit['support'] != 'non_factual'
                        and (unit['support'] != 'supported' or unit['citation'] != 'supported') for unit in all_units)):
            raise EvaluationError('A complete answer cannot include reviewed unsupported factual units.')
        graded |= decision != 'pending' or bool(facts) or judgment['atomic_complete']
    if review.get('review_kind') not in ('unreviewed', 'human'):
        raise EvaluationError('Only declared human review can establish support labels.')
    if graded and (review.get('review_kind') != 'human' or not str(review.get('reviewer', '')).strip()
                   or not valid_timestamp(review.get('reviewed_at'))):
        raise EvaluationError('Graded labels need declared human provenance, reviewer and timezone-aware time.')
    return {(judgment['case_id'], judgment['repeat']): judgment for judgment in judgments}


def review_summary(run_directory, review_path, second_review=None):
    corpus, report, fingerprint = load_run(run_directory)
    if report['config']['mode'] != 'answers':
        raise EvaluationError('Human answer review requires an answer run.')
    primary = read_json(review_path, 64 * 1024 * 1024)
    judgments = _validate_review(corpus, report, fingerprint, primary)
    cases = {case['id']: case for case in corpus['cases']}
    support_groups, citation_groups = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    response_groups = defaultdict(lambda: [0, 0])
    complete, pending_units, reviewed_units, nonfactual = 0, 0, 0, 0
    for key, judgment in judgments.items():
        case = cases[key[0]]
        story = case['story_group']
        units = [unit for claim in judgment['claims'] for unit in claim['units']]
        units_complete = all(unit['support'] != 'pending' and unit['citation'] != 'pending' for unit in units)
        finished = judgment['decision'] != 'pending' and judgment['atomic_complete'] and units_complete
        complete += bool(finished)
        if finished and case['answerability'] == 'answerable':
            response_groups[story][0] += judgment['decision'] == 'complete'
            response_groups[story][1] += 1
        for unit in units:
            if unit['support'] == 'pending' or unit['citation'] == 'pending':
                pending_units += 1
                continue
            if unit['support'] == 'non_factual':
                nonfactual += 1
                continue
            reviewed_units += 1
            support_groups[story][0] += unit['support'] == unit['citation'] == 'supported'
            support_groups[story][1] += 1
            citation_groups[story][0] += unit['citation'] == 'supported'
            citation_groups[story][1] += 1
    disagreement, double_reviewed = [], 0
    if second_review:
        secondary = read_json(second_review, 64 * 1024 * 1024)
        second = _validate_review(corpus, report, fingerprint, secondary)
        if (primary.get('review_kind') != secondary.get('review_kind') or primary.get('review_kind') != 'human'
                or not str(secondary.get('reviewer', '')).strip()
                or primary['reviewer'].strip().casefold() == secondary['reviewer'].strip().casefold()):
            raise EvaluationError('Double review requires distinct declared human reviewers.')
        for key, left in judgments.items():
            right = second[key]
            def finished(judgment):
                return (judgment['decision'] != 'pending' and judgment['atomic_complete']
                        and all(unit['support'] != 'pending' and unit['citation'] != 'pending'
                                for claim in judgment['claims'] for unit in claim['units']))
            if not finished(left) or not finished(right):
                continue
            double_reviewed += 1
            fields = ('decision', 'covered_facts', 'atomic_complete', 'claims')
            if any(left[field] != right[field] for field in fields):
                disagreement.append(dict(case_id=key[0], repeat=key[1]))
    return dict(schema_version=1, report_sha256=fingerprint, corpus_sha256=report['corpus_sha256'],
                corpus_kind=corpus['kind'], review_kind=primary['review_kind'],
                judgments=len(judgments), complete_case_runs=complete, pending_case_runs=len(judgments)-complete,
                reviewed_atomic_claims=reviewed_units, pending_atomic_claims=pending_units, non_factual_units=nonfactual,
                supported_atomic_claims=sum(group[0] for group in support_groups.values()),
                claim_support=interval(support_groups.values(), ratio=True),
                citation_support=interval(citation_groups.values(), ratio=True),
                useful_answer_coverage_reviewed=interval(response_groups.values(), ratio=True),
                double_reviewed_case_runs=double_reviewed, disagreements=disagreement,
                quality_gate='not_established',
                limitations=['Reviewer identities/timestamps are declarations, not authenticated proof of independent review.',
                             'Atomic decomposition completeness is a human attestation; automated tooling cannot prove it.',
                             'Rates describe only reviewed units/cases. Pending labels and selection bias remain explicit.',
                             'Synthetic or unreviewed gold cannot establish real-world model quality; no release threshold is certified.'])
