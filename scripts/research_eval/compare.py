"""Paired diagnostics from frozen evidence, independent of today's chunker."""
from pathlib import Path

from scripts.research_eval.contracts import EvaluationError, write_json
from scripts.research_eval.metrics import clustered_mean, retrieval_metrics
from scripts.research_eval.runner import load_run


def compare(baseline_directory, candidate_directory, output):
    corpus, baseline, baseline_hash = load_run(baseline_directory)
    _, candidate, candidate_hash = load_run(candidate_directory)
    if corpus['kind'] != candidate['corpus_kind'] or baseline['corpus_sha256'] != candidate['corpus_sha256']:
        raise EvaluationError('Paired comparison requires the exact same frozen corpus.')
    for field in ('mode', 'repeats', 'cache', 'selected_case_ids', 'retrieval_budget'):
        if baseline['config'][field] != candidate['config'][field]:
            raise EvaluationError(f'Paired comparison requires equal {field}.')
    if baseline.get('model_identity_changed') or candidate.get('model_identity_changed'):
        raise EvaluationError('Cannot compare runs with changed/unverifiable model identity.')
    cases = {case['id']: case for case in corpus['cases']}
    right = {(row['case_id'], row['repeat']): row for row in candidate['cases']}
    pairs, deltas = [], {}
    for left in baseline['cases']:
        key = (left['case_id'], left['repeat'])
        row, case = right[key], cases[key[0]]
        if not case['eligible']:
            continue
        budget = baseline['config']['retrieval_budget']
        score = lambda item: retrieval_metrics(case, item['passages'] if item['status'] == 'ok' else [], corpus['sources'], budget)
        before, after = score(left), score(row)
        delta = {name: after[name] - value for name, value in before.items() if value is not None and after[name] is not None}
        for name, value in delta.items():
            deltas.setdefault(name, []).append((case['story_group'], case['id'], value))
        latency = None
        if left['status'] == row['status'] == 'ok':
            latency = row['timing']['pipeline_seconds'] - left['timing']['pipeline_seconds']
            deltas.setdefault('pipeline_seconds', []).append((case['story_group'], case['id'], latency))
        pairs.append(dict(case_id=key[0], repeat=key[1], baseline_status=left['status'],
                          candidate_status=row['status'], metric_delta=delta, pipeline_seconds_delta=latency))
    report = dict(schema_version=1, baseline_sha256=baseline_hash, candidate_sha256=candidate_hash,
                  corpus_sha256=baseline['corpus_sha256'], corpus_kind=corpus['kind'],
                  baseline_config=baseline['config'], candidate_config=candidate['config'],
                  baseline_model_identity=baseline.get('model_identity_before'),
                  candidate_model_identity=candidate.get('model_identity_before'),
                  baseline_request_settings=baseline.get('request_settings'), candidate_request_settings=candidate.get('request_settings'),
                  pairs=pairs, deltas={name: clustered_mean(values) for name, values in deltas.items()},
                  baseline_failed_runs=sum(row['status'] == 'error' for row in baseline['cases']),
                  candidate_failed_runs=sum(row['status'] == 'error' for row in candidate['cases']),
                  quality_gate='not_established',
                  limitations=['Paired retrieval/latency diagnostics only. Human claim-support review is separate.',
                               'Failures retain zero applicable retrieval credit; paired successful latency excludes failures.',
                               'An interval or synthetic improvement does not establish real-world answer quality.'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'comparison.json', report)
    with (output / 'comparison.md').open('x', encoding='utf-8', newline='\n') as handle:
        handle.write('# Paired research diagnostics\n\nCandidate minus baseline; quality gate: **not established**.\n\n')
        handle.write('| Metric | Story-macro delta |\n| --- | --- |\n')
        for name, value in report['deltas'].items():
            handle.write(f"| {name} | {value['value']:.6f} |\n")
        handle.write('\nSee comparison.json for intervals, failures, paired cases and limitations.\n')
    return report
