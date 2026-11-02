"""Inspectable retrieval measurements and story-clustered uncertainty."""
from collections import defaultdict
from collections import Counter
import math
import random
import statistics

from app.intelligence import article_passages
from scripts.research_eval.contracts import EvaluationError


def passage_locations(sources):
    """Align the unchanged whitespace-normalizing chunker to original offsets.

    Fail closed if a later chunker adds/removes non-whitespace content. Gold spans
    are never rewritten to match current chunk IDs or approximated by fuzzy text.
    """
    result = {}
    for source in sources:
        positions = [index for index, char in enumerate(source['text']) if not char.isspace()]
        compact = ''.join(source['text'][index] for index in positions)
        cursor = 0
        for passage in article_passages(source):
            needle = ''.join(char for char in passage['text'] if not char.isspace())
            if not needle or not compact.startswith(needle, cursor):
                raise EvaluationError('Current passages cannot be aligned exactly to frozen source offsets.')
            result[passage['id']] = dict(source_id=source['id'], text_sha256=source['text_sha256'],
                start=positions[cursor], end=positions[cursor + len(needle) - 1] + 1, text=passage['text'],
                title=source['title'], url=source['url'], captured_at=source['captured_at'])
            cursor += len(needle)
        if cursor != len(compact):
            raise EvaluationError('Current passages omit frozen non-whitespace source text.')
    return result


def retrieval_metrics(case, ranked, sources, budget):
    if case['answerability'] != 'answerable':
        return {}
    by_id = {source['id']: source for source in sources}
    gold = {unit['id']: unit for unit in case['evidence']}

    def covered(units):
        hits = set()
        for unit_id, unit in gold.items():
            spans = [(row['start'], row['end']) for row in units if row['source_id'] == unit['source_id']]
            text = by_id[unit['source_id']]['text']
            if all(any(start <= index < end for start, end in spans)
                   for index in range(unit['start'], unit['end']) if not text[index].isspace()):
                hits.add(unit_id)
        return hits

    measured = {}
    for k in (5, 6, 10):
        if k > budget:
            measured[f'recall_at_{k}'] = measured[f'sufficient_at_{k}'] = None
            continue
        hits = covered(ranked[:k])
        # Alternatives are sufficient evidence sets, not extra mandatory spans.
        measured[f'recall_at_{k}'] = max(len(hits & set(group)) / len(group) for group in case['acceptable_sets'])
        measured[f'sufficient_at_{k}'] = float(any(set(group) <= hits for group in case['acceptable_sets']))
    measured['mrr_at_10'] = None
    if budget >= 10:
        measured['mrr_at_10'] = 0.0
        for rank, row in enumerate(ranked[:10], 1):
            relevant = any(row['source_id'] == unit['source_id']
                           and any(not by_id[unit['source_id']]['text'][index].isspace()
                                   for index in range(max(row['start'], unit['start']), min(row['end'], unit['end'])))
                           for unit in gold.values())
            if relevant:
                measured['mrr_at_10'] = 1 / rank
                break
    return measured


def interval(groups, *, ratio=False, samples=1000):
    """Resample whole story families; repeated claims/questions aren't IID."""
    groups = list(groups)
    count = len(groups)
    if not count:
        return dict(value=None, ci95=None, story_clusters=0)
    def score(values):
        if ratio:
            numerator = sum(item[0] for item in values)
            denominator = sum(item[1] for item in values)
            return numerator / denominator if denominator else None
        return statistics.mean(values)
    value = score(groups)
    result = dict(value=value, ci95=None, story_clusters=count,
                  method='percentile story-cluster bootstrap; seed 1729; 1000 resamples')
    if count < 2 or value is None:
        result['limitation'] = 'At least two independent story clusters are needed for this interval.'
        return result
    rng = random.Random(1729)
    draws = sorted(value for _ in range(samples)
                   if (value := score([groups[rng.randrange(count)] for _ in range(count)])) is not None)
    if draws:
        result['ci95'] = [draws[max(0, math.floor(.025 * len(draws)))], draws[min(len(draws)-1, math.ceil(.975 * len(draws))-1)]]
        result['limitation'] = ('Descriptive bootstrap conditional on these stories; homogeneous labels can produce a degenerate interval. '
                                'It does not establish a release target or account for annotation/sample-selection bias.')
    return result


def clustered_mean(values):
    # First average repetitions within a case, then cases within a story. Each
    # story receives equal weight in the reported macro mean and bootstrap.
    cases = defaultdict(list)
    for story, case_id, value in values:
        if value is not None:
            cases[(story, case_id)].append(value)
    stories = defaultdict(list)
    for (story, _), repeats in cases.items():
        stories[story].append(statistics.mean(repeats))
    return interval([statistics.mean(cases) for cases in stories.values()])


def summarize(corpus, rows, mode, budget):
    cases = {case['id']: case for case in corpus['cases']}
    eligible = [case for case in cases.values() if case['eligible']]
    metrics = {}
    for name in ('recall_at_5', 'recall_at_6', 'recall_at_10', 'sufficient_at_5', 'sufficient_at_6', 'sufficient_at_10', 'mrr_at_10'):
        values = []
        for row in rows:
            case = cases[row['case_id']]
            if not case['eligible'] or case['answerability'] != 'answerable':
                continue
            measurable = int(name.rsplit('_', 1)[-1]) <= budget
            value = row.get('retrieval_metrics', {}).get(name) if row['status'] == 'ok' else 0.0 if measurable else None
            values.append((case['story_group'], case['id'], value))
        metrics[name] = clustered_mean(values)
    for answerability, name in [('answerable', 'answerable_response_rate'), ('unanswerable', 'correct_abstention_rate')]:
        values = []
        if mode == 'answers':
            for row in rows:
                case = cases[row['case_id']]
                if case['eligible'] and case['answerability'] == answerability:
                    answer = row.get('answer', {})
                    correct = row['status'] == 'ok' and answer.get('supported') is (answerability == 'answerable')
                    values.append((case['story_group'], case['id'], float(correct)))
        metrics[name] = clustered_mean(values)
    timings = {}
    for name in ('pipeline_seconds', 'retrieval_seconds', 'generation_seconds'):
        values = [row['timing'][name] for row in rows if row['status'] == 'ok' and row.get('timing', {}).get(name) is not None]
        timings[name] = dict(observations=len(values), median=statistics.median(values) if values else None,
                             p95=sorted(values)[math.ceil(.95 * len(values))-1] if values else None)
    scoped = {source_id for case in eligible for source_id in case['source_ids']}
    return dict(cases=len(cases), eligible_cases=len(eligible), excluded_cases=len(cases)-len(eligible),
                story_families=len({case['story_group'] for case in eligible}),
                gold_label_kinds=dict(Counter(case['label']['kind'] for case in eligible)),
                case_tags=dict(Counter(tag for case in eligible for tag in case['tags'])),
                source_types=dict(Counter(source['source_type'] for source in corpus['sources'] if source['id'] in scoped)),
                answerable_cases=sum(case['answerability'] == 'answerable' for case in eligible),
                unanswerable_cases=sum(case['answerability'] == 'unanswerable' for case in eligible),
                case_runs=sum(row['status'] != 'excluded' for row in rows),
                failed_runs=sum(row['status'] == 'error' for row in rows), metrics=metrics, timing=timings,
                claim_support=None, useful_answer_coverage=None,
                quality_gate='not_established',
                limitations=['Synthetic/provisional gold is diagnostic, not human-reviewed quality evidence.',
                             'Answerable response rate measures returning claims, not their correctness or usefulness.',
                             'Failed eligible runs remain in applicable quality denominators as failures; successful timing summaries exclude them.',
                             'Gold-span coverage requires all non-whitespace characters; human review must assess relevance and factual support.',
                             'Memory/GPU utilization is not measured. Model/runtime latency depends on hardware and cache state.'])
