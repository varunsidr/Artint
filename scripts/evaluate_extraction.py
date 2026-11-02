"""Frozen-source diagnostics and honest review accounting; never writes the library.

Publisher HTML is cached locally for paired replay, not a redistributable fixture.
Automated paragraph coverage is a diagnostic, never a human completeness score.
"""
import argparse
import csv
import hashlib
import json
import math
import runpy
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.capture_quality import failure_details, inspect_capture
from app.extract import _request_html, extract_document

MAX_CACHE_BYTES = 128_000_000
CRITERIA = ('body_complete', 'title_correct', 'metadata_correct', 'no_boilerplate')
REVIEW_CRITERIA = (*CRITERIA, 'date_correct', 'publisher_correct', 'no_missing_sections', 'not_duplicate')
SOURCE_KINDS = ('article', 'analysis', 'opinion', 'abstract', 'transcript', 'other')


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def freeze(audit, output):
    target = output / 'manifest.json'
    if target.exists():
        raise ValueError('Manifest already exists. Use it unchanged or choose another evaluation directory.')
    saved = json.loads(audit.read_text(encoding='utf-8'))['saved']
    cases = [dict(id=digest(row['url'].encode())[:16], url=row['url'], publisher=urlsplit(row['url']).hostname,
                  source_kind=row.get('source_kind', 'unclassified'), prior_title=row['title'],
                  prior_article_id=row['article_id']) for row in saved[:100]]
    if len(cases) != 100 or len({row['url'] for row in cases}) != 100 or len({row['publisher'] for row in cases}) < 10:
        raise ValueError('The diagnostic cohort needs 100 unique URLs from at least 10 hosts.')
    atomic_json(target, dict(version=1, created_at=stamp(), selection='First 100 previously saved AI-bubble sources in the existing audit; convenience sample biased toward past successes.',
                            limitations='Includes known abstracts and heterogeneous pages. Eligibility and body/metadata correctness require independent review. This is not the M2 eligible benchmark.',
                            cache_policy='Local publisher HTML only, excluded from version control; no redistribution license is assumed.', cases=cases))
    return target


def freeze_candidates(candidates, protocol_path, output):
    """Freeze a declared candidate cohort before capture; no network or library IO."""
    if not protocol_path:
        raise ValueError('Provide --protocol with the candidate selection and eligibility rules.')
    if candidates.stat().st_size > 2_000_000 or protocol_path.stat().st_size > 16_000:
        raise ValueError('Candidate list or protocol exceeds its size budget.')
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    for key in ('name', 'selection_method', 'inclusion_criteria', 'exclusion_criteria'):
        if not isinstance(protocol.get(key), str) or not protocol[key].strip():
            raise ValueError(f'Protocol requires a nonempty {key}.')
    protocol = {key: protocol[key] for key in ('name', 'selection_method', 'inclusion_criteria', 'exclusion_criteria')}
    if any((output / name).exists() for name in ('manifest.json', 'baseline.json', 'improved.json')):
        raise ValueError('Use a new cohort directory; existing captures/manifests cannot be relabelled prospective.')
    with candidates.open(encoding='utf-8-sig', newline='') as stream:
        entries = list(csv.DictReader(stream))
    if not 1 <= len(entries) <= 500:
        raise ValueError('Declare 1-500 candidates; small development cohorts do not satisfy the release target.')
    cases, seen = [], set()
    for entry in entries:
        url, kind = entry.get('url', '').strip(), entry.get('source_kind', '').strip()
        parsed = urlsplit(url)
        if len(url) > 2048 or any(ord(character) < 32 for character in url) or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Candidate URLs must be complete HTTP(S) URLs without credentials.')
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError('Candidate URL port is invalid.') from exc
        if url in seen or kind not in SOURCE_KINDS:
            raise ValueError('Candidate URLs must be unique and source_kind must use a documented category.')
        seen.add(url)
        cases.append(dict(id=digest(url.encode())[:16], url=url, publisher=parsed.hostname.lower(), source_kind=kind))
    target = output / 'manifest.json'
    atomic_json(target, dict(version=2, created_at=stamp(), cohort_kind='prospective_candidates',
                            selection=protocol['selection_method'], protocol=protocol,
                            protocol_sha256=digest(protocol_bytes), cases=cases,
                            limitations='Declared candidate cohort. Eligibility, extraction completeness and metadata require human review. This is not a representative sample of the web.',
                            cache_policy='Publisher HTML/text stays local; no redistribution permission is assumed.'))
    return target


def _review_context(output, phase):
    if phase not in ('baseline', 'improved'):
        raise ValueError('Choose a known evaluation phase.')
    manifest_path, report_path = output / 'manifest.json', output / (phase + '.json')
    if manifest_path.stat().st_size > 1_000_000 or report_path.stat().st_size > 8_000_000:
        raise ValueError('Review input exceeds its metadata budget.')
    manifest_bytes = manifest_path.read_bytes()
    manifest, report = json.loads(manifest_bytes), json.loads(report_path.read_text(encoding='utf-8'))
    if report['phase'] != phase or report['manifest_sha256'] != digest(manifest_bytes):
        raise ValueError('Phase and frozen manifest fingerprints do not match.')
    cases = manifest['cases']
    rows = {row['id']: row for row in report['results']}
    if len(rows) != len(report['results']) or set(rows) != {case['id'] for case in cases}:
        raise ValueError('Finish the complete phase before preparing or scoring a review.')
    expected = {}
    for case in cases:
        row = rows[case['id']]
        if not re.fullmatch(r'[0-9a-f]{16}', case['id']) or case['id'] != digest(case['url'].encode())[:16]:
            raise ValueError('Review case IDs must match their URL hashes.')
        evidence = {key: row.get(key) for key in ('id', 'status', 'html_sha256', 'text_sha256', 'title', 'published', 'author', 'failure')}
        reading_hash = None
        if row['status'] == 'captured' and row.get('local_reading_copy'):
            relative = f'local-cache/{case["id"]}.{phase}.txt'
            if row['local_reading_copy'] != relative:
                raise ValueError('Unexpected reading-copy path in phase metadata.')
            reading, cache = output / relative, output / 'local-cache'
            if reading.is_symlink() or cache.is_symlink():
                raise ValueError('Review reading copies must not be symbolic links.')
            if reading.exists():
                if reading.stat().st_size > 8_000_000:
                    raise ValueError('Reading copy exceeds the review size budget.')
                body = reading.read_bytes()
                prefix = (row['title'] + '\n' + row.get('final_url', case['url']) + '\n\n').encode()
                if not body.startswith(prefix) or digest(body[len(prefix):]) != row['text_sha256']:
                    raise ValueError('Local reading copy is stale or modified relative to the captured phase.')
                reading_hash = digest(body)
        evidence['reading_sha256'] = reading_hash
        evidence.update(extraction_sha256=report['extraction_sha256'], diagnostics_sha256=report['diagnostics_sha256'], mode=report['mode'])
        if 'cleanup_sha256' in report:
            evidence['cleanup_sha256'] = report['cleanup_sha256']
        expected[case['id']] = dict(case, status=row['status'], reading_available=reading_hash is not None,
                                    evidence_sha256=digest(json.dumps(evidence, sort_keys=True).encode()))
    return manifest, report, expected


def prepare_phase_review(output, phase):
    manifest, report, expected = _review_context(output, phase)
    path = output / f'review-{phase}-v2.csv'
    fields = ['id', 'url', 'source_kind', 'capture_status', 'phase', 'manifest_sha256', 'evidence_sha256',
              'eligibility', 'exclusion_reason', *REVIEW_CRITERIA, 'review_kind', 'reviewer', 'reviewed_at', 'notes']
    # Exclusive creation preserves completed labels and all legacy review files.
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in expected.values():
            writer.writerow(dict(id=case['id'], url=case['url'], source_kind=case['source_kind'],
                                  capture_status=case['status'], phase=phase, manifest_sha256=report['manifest_sha256'],
                                  evidence_sha256=case['evidence_sha256'], eligibility='pending',
                                  **{criterion: 'not_reviewed' for criterion in REVIEW_CRITERIA}))
    return path


def _labelled_review(path, phase, report, expected):
    if path.stat().st_size > 2_000_000:
        raise ValueError('Review checklist exceeds its size budget.')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        entries = list(csv.DictReader(stream))
    seen, finalized, decisions, excluded = set(), {}, {}, 0
    for row in entries:
        identifier = row.get('id')
        if identifier not in expected or identifier in seen:
            raise ValueError('Review has an unknown or duplicate case.')
        seen.add(identifier)
        case = expected[identifier]
        if any(row.get(key) != value for key, value in dict(phase=phase, manifest_sha256=report['manifest_sha256'],
                evidence_sha256=case['evidence_sha256'], url=case['url'], capture_status=case['status'], source_kind=case['source_kind']).items()):
            raise ValueError('Review contains stale or modified source/phase fingerprints; prepare a review for the correct snapshot.')
        eligibility = row.get('eligibility')
        if eligibility not in ('pending', 'eligible', 'excluded'):
            raise ValueError('Eligibility must be pending, eligible or excluded.')
        if eligibility == 'pending':
            continue
        if row.get('review_kind') != 'human' or not row.get('reviewer', '').strip():
            raise ValueError('Final labels require an identified, declared human reviewer.')
        try:
            reviewed_at = datetime.fromisoformat(row.get('reviewed_at', '').replace('Z', '+00:00'))
            if reviewed_at.tzinfo is None:
                raise ValueError()
        except ValueError as exc:
            raise ValueError('Final labels require reviewed_at with a timezone.') from exc
        if eligibility == 'excluded':
            if not row.get('exclusion_reason', '').strip():
                raise ValueError('Every exclusion requires a reason; do not remove failed captures.')
            excluded += 1
            decisions[identifier] = dict(decision='excluded', reviewer=row['reviewer'].strip())
            continue
        if case['status'] == 'captured' and any(row.get(key) not in ('pass', 'fail') for key in REVIEW_CRITERIA):
            raise ValueError('Captured eligible sources require every review criterion.')
        if case['status'] == 'captured' and not case['reading_available'] and all(row.get(key) == 'pass' for key in REVIEW_CRITERIA):
            raise ValueError('An unavailable reading copy cannot receive an acceptable-body judgement.')
        finalized[identifier] = dict(case, reviewer=row['reviewer'].strip(),
                                      passed=case['status'] == 'captured' and all(row.get(key) == 'pass' for key in REVIEW_CRITERIA))
        decisions[identifier] = dict(decision='pass' if finalized[identifier]['passed'] else 'fail', reviewer=row['reviewer'].strip())
    if seen != set(expected):
        raise ValueError('Review is missing frozen cases; retain every row, including exclusions and failures.')
    return finalized, excluded, len(expected) - len(finalized) - excluded, decisions


def _wilson(passed, total):
    """Descriptive binomial interval; does not model publisher dependence."""
    if not total:
        return None
    z, rate = 1.959963984540054, passed / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0., centre - margin), 4), round(min(1., centre + margin), 4)]


def summarize_phase_review(output, phase, review_path=None, second_review_path=None):
    manifest, report, expected = _review_context(output, phase)
    path = review_path or output / f'review-{phase}-v2.csv'
    finalized, excluded, pending, decisions = _labelled_review(path, phase, report, expected)
    passed, count = sum(row['passed'] for row in finalized.values()), len(finalized)
    hosts = {row['publisher'] for row in finalized.values()}
    strata = {}
    for key in ('publisher', 'source_kind'):
        groups = defaultdict(list)
        for row in finalized.values():
            groups[row[key]].append(row['passed'])
        strata[key] = {name: dict(reviewed=len(values), passed=sum(values), pass_rate=round(sum(values) / len(values), 4)) for name, values in sorted(groups.items())}
    double_reviewed, disagreements = 0, []
    if second_review_path:
        _, _, _, second = _labelled_review(second_review_path, phase, report, expected)
        for identifier in decisions.keys() & second.keys():
            if decisions[identifier]['reviewer'].casefold() == second[identifier]['reviewer'].casefold():
                raise ValueError('Second review must identify a different human reviewer.')
            double_reviewed += int(identifier in finalized)
            if decisions[identifier]['decision'] != second[identifier]['decision']:
                disagreements.append(identifier)
    interval = _wilson(passed, count)
    prospective = manifest.get('cohort_kind') == 'prospective_candidates' and bool(manifest.get('protocol_sha256'))
    observed_target = bool(count >= 100 and len(hosts) >= 10 and not pending and passed / count >= .9)
    result = dict(version=2, phase=phase, created_at=stamp(), manifest_sha256=report['manifest_sha256'],
                  review_sha256=digest(path.read_bytes()), total_cases=len(expected), reviewed_eligible=count,
                  cohort_by_publisher=dict(Counter(case['publisher'] for case in expected.values())),
                  cohort_by_source_kind=dict(Counter(case['source_kind'] for case in expected.values())),
                  reviewed_hosts=len(hosts), passed=passed, failed=count-passed, excluded=excluded, pending=pending,
                  pass_rate=round(passed / count, 4) if count else None, wilson_95_interval=interval,
                  by_publisher=strata['publisher'], by_source_kind=strata['source_kind'],
                  double_reviewed=double_reviewed, disagreements=disagreements, prospective_cohort=prospective,
                  observed_target_met=observed_target,
                  release_gate_met=bool(observed_target and prospective and double_reviewed >= math.ceil(count * .2) and not disagreements),
                  limitations='Human labels are declarations, not independently authenticated identities. Wilson intervals assume independent cases and do not account for publisher/story dependence. The release gate concerns the declared cohort only, not a general-web success rate; do not present this interval as population or cluster-aware evidence.')
    if second_review_path:
        result['second_review_sha256'] = digest(second_review_path.read_bytes())
    atomic_json(output / f'review-{phase}-summary.json', result)
    rate = 'Not established (no reviewed eligible cases)' if result['pass_rate'] is None else f"{passed}/{count} ({100 * passed / count:.1f}%)"
    lines = ['# Human extraction review', '', f'Phase: {phase}', '',
             f'- Frozen cases: {len(expected)}; eligible reviewed: {count}; excluded: {excluded}; pending: {pending}.',
             f'- Reviewed pass rate: {rate}.', f'- Double-reviewed: {double_reviewed}; disagreements: {len(disagreements)}.',
             f'- Declared cohort gate met: {result["release_gate_met"]}.', '', result['limitations'], '',
             'A convenience sample cannot become a prospective benchmark by filling in labels. No publisher bodies are included in this report.', '']
    (output / f'review-{phase}-summary.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


def review_totals(path, cases):
    if not path.exists():
        return {'reviewed_eligible': 0, 'reviewed_publishers': 0, 'passed': 0, 'pass_rate': None, 'release_gate_met': False}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        entries = list(csv.DictReader(stream))
    expected = {case['id']: case for case in cases}
    seen, reviewed = set(), []
    for row in entries:
        if row.get('id') not in expected or row['id'] in seen:
            raise ValueError('Review checklist contains an unknown or duplicate case.')
        seen.add(row['id'])
        if row.get('eligibility') != 'eligible':
            continue
        if row.get('reviewer', '').strip() and all(row.get(key) in ('pass', 'fail') for key in CRITERIA):
            reviewed.append(row)
    passed = sum(all(row[key] == 'pass' for key in CRITERIA) for row in reviewed)
    hosts = {expected[row['id']]['publisher'] for row in reviewed}
    rate = passed / len(reviewed) if reviewed else None
    return {'reviewed_eligible': len(reviewed), 'reviewed_publishers': len(hosts), 'passed': passed,
            'pass_rate': round(rate, 4) if rate is not None else None,
            'release_gate_met': False, 'review_schema': 'legacy-unbound',
            'limitations': 'Legacy review counts are not phase/hash-bound and cannot establish the release gate. Use the v2 phase review commands.'}


def make_checklist(path, cases):
    if path.exists():
        return
    fields = ['id', 'url', 'source_kind', 'eligibility', 'exclusion_reason', *CRITERIA, 'reviewer', 'notes']
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in cases:
            writer.writerow(dict(id=case['id'], url=case['url'], source_kind=case['source_kind'], eligibility='pending',
                                 **{key: 'not_reviewed' for key in CRITERIA}))


def summary(rows, cases, reviews):
    captured = [row for row in rows if row['status'] == 'captured']
    return dict(total_cases=len(cases), completed=len(rows), publisher_hosts=len({case['publisher'] for case in cases}),
                captured=len(captured), failed=sum(row['status'] == 'failed' for row in rows),
                skipped=sum(row['status'] == 'skipped' for row in rows),
                needs_review=sum(row.get('quality', {}).get('status') == 'needs_review' for row in rows),
                checks_passed=sum(row.get('quality', {}).get('status') == 'checks_passed' for row in rows),
                warning_counts=dict(Counter(w['code'] for row in captured for w in row['quality']['warnings'])),
                failure_counts=dict(Counter(row['failure']['code'] for row in rows if row.get('failure'))),
                independent_review=reviews)


def write_markdown(path, report):
    stats = report['summary']
    lines = ['# Extraction diagnostic report', '', f"Phase: **{report['phase']}** · Updated {report['updated_at']}", '',
             report['limitations'], '',
             f"- {stats['completed']}/{stats['total_cases']} cases processed across {stats['publisher_hosts']} hosts.",
             f"- {stats['captured']} captured; {stats['failed']} failed; {stats['skipped']} skipped.",
             f"- {stats['needs_review']} captures need review; {stats['checks_passed']} passed automated checks.",
             f"- Independently reviewed eligible sources: {stats['independent_review']['reviewed_eligible']}. No reviewed success rate is claimed until review exists.", '',
             'Paragraph coverage compares extraction with detected HTML paragraphs. It can include related content or miss non-paragraph content; it is not proof of completeness.', '',
             '| Result | Count |', '| --- | ---: |']
    lines += [f'| {code} | {count} |' for code, count in sorted({**stats['warning_counts'], **stats['failure_counts']}.items())]
    lines += ['', 'Review checklist: `review.csv`. Open each original, compare the reading copy/body and metadata, assign eligibility, enter pass/fail for every criterion, and identify the reviewer. Do not change the frozen cohort to remove failures.', '',
              '| Source | Outcome | Findings |', '| --- | --- | --- |']
    for row in report['results']:
        notes = ', '.join(w['code'] for w in row.get('quality', {}).get('warnings', [])) or row.get('failure', {}).get('code', 'none')
        lines.append(f"| [{row['publisher']}]({row['url']}) | {row['status']} | {notes} |")
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def compare(output):
    before = json.loads((output/'baseline.json').read_text(encoding='utf-8'))
    after = json.loads((output/'improved.json').read_text(encoding='utf-8'))
    if before['manifest_sha256'] != after['manifest_sha256']:
        raise ValueError('Comparison requires exactly the same frozen cohort.')
    original = {row['id']: row for row in before['results']}
    metadata_changes, body_changes, outcome_changes, paired = [], [], [], []
    for row in after['results']:
        old = original[row['id']]
        if row.get('html_sha256') and row['html_sha256'] == old.get('html_sha256'):
            paired.append(row['id'])
        if row['status'] != old['status']:
            outcome_changes.append(dict(id=row['id'], url=row['url'], before=old['status'], after=row['status']))
        if row['status'] == old['status'] == 'captured':
            for field in ('title', 'author', 'published'):
                if old[field] != row[field]:
                    metadata_changes.append(dict(id=row['id'], url=row['url'], field=field, before=old[field], after=row[field]))
            if old['text_sha256'] != row['text_sha256']:
                body_changes.append(dict(id=row['id'], url=row['url'],
                                         before_units=old['quality']['evidence']['readable_units'],
                                         after_units=row['quality']['evidence']['readable_units'],
                                         before_coverage=old['quality']['evidence'].get('paragraph_coverage'),
                                         after_coverage=row['quality']['evidence'].get('paragraph_coverage')))
    report = dict(updated_at=stamp(), manifest_sha256=before['manifest_sha256'], paired_html_cases=len(paired),
                  cases_without_replay=len(after['results'])-len(paired), metadata_changes=metadata_changes,
                  body_changes=body_changes, outcome_changes=outcome_changes,
                  before=before['summary'], after=after['summary'],
                  limitations='Same cached HTTP responses; no claim that automated checks establish complete bodies or correct metadata. Original network failures are retained without replay. Independent source-by-source review remains pending.')
    atomic_json(output/'comparison.json', report)
    lines = ['# Extraction reliability: paired diagnostic results', '', report['limitations'], '',
             f"Frozen cohort: {after['summary']['total_cases']} sources across {after['summary']['publisher_hosts']} hosts. {len(paired)} identical cached HTML responses were compared; {report['cases_without_replay']} original network failures had no response to replay.", '',
             '| Measure | Baseline | Improved |', '| --- | ---: | ---: |']
    for field, label in [('captured','Captured'),('failed','Failed'),('needs_review','Flagged for review'),('checks_passed','No warning-level automated findings')]:
        lines.append(f"| {label} | {before['summary'][field]} | {after['summary'][field]} |")
    lines += ['', f"Metadata changes: {len(metadata_changes)}. Body changes: {len(body_changes)}. Capture-outcome changes: {len(outcome_changes)}.", '',
              '## Metadata changes', '', '| Source | Field | Previous | Current |', '| --- | --- | --- | --- |']
    for change in metadata_changes:
        clean = lambda value: str(value).replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| [{urlsplit(change['url']).hostname}]({change['url']}) | {change['field']} | {clean(change['before']) or 'Unavailable'} | {clean(change['after'])} |")
    lines += ['', 'Explicit published-date metadata takes precedence over inferred dates. Time-zone boundaries can also change calendar dates; these changes still require source review.', '',
              '## Body changes', '']
    for change in body_changes:
        lines.append(f"- [{urlsplit(change['url']).hostname}]({change['url']}): {change['before_units']} → {change['after_units']} readable units; detected source-block coverage {change['before_coverage']} → {change['after_coverage']}.")
    lines += ['', '## Remaining work', '',
              'Inspect flagged pages and complete `review.csv` against originals and the phase-specific reading copies under `local-cache/`. The convenience cohort includes abstracts and other heterogeneous source types. Declare eligible sources before claiming the M2 target; at least 100 reviewed eligible sources across 10 publishers are still required. Publisher HTML and reading text are local-only and excluded from version control.', '']
    (output/'comparison.md').write_text('\n'.join(lines), encoding='utf-8')
    return report


def evaluate(options):
    if options.offline and options.mode != 'html':
        raise ValueError('Offline replay requires HTML mode so JavaScript cannot make network requests.')
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = freeze(options.audit, output) if options.freeze else output / 'manifest.json'
    if manifest_path.stat().st_size > 1_000_000:
        raise ValueError('Evaluation manifest exceeds the 1 MB limit.')
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    cases = manifest['cases']
    if not 1 <= len(cases) <= 500 or len({row['id'] for row in cases}) != len(cases):
        raise ValueError('Expected 1-500 unique manifest cases.')
    for case in cases:
        if not re.fullmatch(r'[0-9a-f]{16}', case['id']) or case['id'] != digest(case['url'].encode())[:16]:
            raise ValueError('Manifest case IDs must match their URL hashes.')
        parsed = urlsplit(case['url'])
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Manifest contains an invalid publisher URL.')
    make_checklist(output / 'review.csv', cases)
    cache = output / 'local-cache'
    cache.mkdir(exist_ok=True)
    cache_bytes = sum(path.stat().st_size for path in cache.iterdir() if path.is_file())
    cache_lock, host_locks, paused = threading.Lock(), defaultdict(threading.Lock), {}
    report_path = output / (options.phase + '.json')
    engine_path = ROOT/'app/extract.py'
    cleanup_sha256 = digest((ROOT/'app/article_cleanup.py').read_bytes())
    parse_document = extract_document
    if options.engine == 'frozen':
        engine_path = cache/'baseline-extract.py'
        original = json.loads((output/'initial-diagnostics.json').read_text(encoding='utf-8'))
        if options.phase != 'baseline' or digest(engine_path.read_bytes()) != original['extraction_sha256']:
            raise ValueError('Frozen engine must match the recorded original baseline source.')
        if b'from app.article_cleanup import' in engine_path.read_bytes() and original.get('cleanup_sha256') != cleanup_sha256:
            raise ValueError('Frozen engine cleanup dependency differs from its recorded baseline.')
        parse_document = runpy.run_path(str(engine_path))['extract_document']
    origin_path = output/'initial-diagnostics.json'
    original_failures = {row['id']: row for row in json.loads(origin_path.read_text(encoding='utf-8'))['results'] if row['status'] == 'failed'} if origin_path.exists() else {}
    report = dict(version=1, phase=options.phase, started_at=stamp(), mode=options.mode,
                  manifest_sha256=digest(manifest_bytes), extraction_sha256=digest(engine_path.read_bytes()),
                  diagnostics_sha256=digest((ROOT/'app/capture_quality.py').read_bytes()),
                  cleanup_sha256=cleanup_sha256,
                  limitations=manifest['limitations'], results=[])
    if report_path.exists():
        if not options.resume:
            raise ValueError('Phase already exists; use --resume or a new phase name.')
        previous = json.loads(report_path.read_text(encoding='utf-8'))
        for key in ('manifest_sha256', 'extraction_sha256', 'diagnostics_sha256', 'cleanup_sha256', 'mode'):
            if report[key] != previous.get(key):
                raise ValueError('Cannot mix different source/code versions in one phase.')
        report = previous
    completed = {row['id'] for row in report['results']}

    def run(case):
        nonlocal cache_bytes
        began = time.monotonic()
        row = dict(case, status='failed', transport='live')
        with host_locks[case['publisher']]:
            try:
                path = cache / (case['id'] + '.json')
                if path.exists():
                    if path.stat().st_size > 10_100_000:
                        raise ValueError('Cached HTML exceeded the local replay size limit.')
                    cached = json.loads(path.read_text(encoding='utf-8'))
                    if cached['requested_url'] != case['url']:
                        raise ValueError('Cached URL does not match the frozen case.')
                    html, final_url = cached['html'], cached['final_url']
                    row['transport'] = 'local_replay'
                elif options.offline:
                    if case['id'] in original_failures:
                        row.update(status='failed', transport='live_failure_not_replayed', failure=original_failures[case['id']]['failure'])
                        return row
                    raise ValueError('No cached HTML exists for this case; offline replay cannot fetch it.')
                elif case['publisher'] in paused:
                    row.update(status='skipped', failure=paused[case['publisher']])
                    return row
                else:
                    html, final_url = _request_html(case['url'])
                    payload = json.dumps(dict(requested_url=case['url'], final_url=final_url, html=html), ensure_ascii=False).encode()
                    with cache_lock:
                        if cache_bytes + len(payload) <= MAX_CACHE_BYTES:
                            path.write_bytes(payload)
                            cache_bytes += len(payload)
                        else:
                            row['cache_warning'] = 'Local cache reached its 128 MB limit; this case cannot be replayed.'
                row['html_sha256'] = digest(html.encode())
                row['final_url'] = final_url
                article = parse_document(html, final_url, mode=options.mode)
                row.update(status='captured', title=article['title'], published=article['published'], author=article['author'],
                           word_count=article['word_count'], text_sha256=digest(article['text'].encode()),
                           fetch_method=article['fetch_method'], quality=json.loads(article['quality_json']) if article.get('quality_json') else inspect_capture(article, html))
                reading = cache/(case['id'] + '.' + options.phase + '.txt')
                reading_body = (article['title'] + '\n' + article['url'] + '\n\n' + article['text']).encode()
                with cache_lock:
                    previous_size = reading.stat().st_size if reading.exists() else 0
                    if cache_bytes - previous_size + len(reading_body) <= MAX_CACHE_BYTES:
                        reading.write_bytes(reading_body)
                        cache_bytes += len(reading_body) - previous_size
                        row['local_reading_copy'] = 'local-cache/' + reading.name
            except Exception as exc:
                row['failure'] = failure_details(exc)
                if row['failure']['code'] in ('http_blocked', 'rate_limited', 'robots_denied'):
                    paused[case['publisher']] = row['failure']
            finally:
                row['elapsed_seconds'] = round(time.monotonic() - began, 3)
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run, case) for case in cases if case['id'] not in completed]
        for future in as_completed(futures):
            row = future.result()
            report['results'].append(row)
            report['results'].sort(key=lambda row: next(index for index, case in enumerate(cases) if case['id'] == row['id']))
            report['updated_at'] = stamp()
            report['summary'] = summary(report['results'], cases, review_totals(output / 'review.csv', cases))
            atomic_json(report_path, report)
            write_markdown(output / (options.phase + '.md'), report)
            print(f"{len(report['results']):3}/{len(cases)} {row['status']:8} {row['publisher']}", flush=True)
    report['updated_at'] = stamp()
    report['summary'] = summary(report['results'], cases, review_totals(output / 'review.csv', cases))
    atomic_json(report_path, report)
    write_markdown(output / (options.phase + '.md'), report)
    print(json.dumps(report['summary'], indent=2))
    if options.phase == 'improved' and (output/'baseline.json').exists():
        compare(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'output/evaluations/ai-bubble-20261028')
    parser.add_argument('--audit', type=Path, default=ROOT/'output/ai-bubble-collection.json')
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--freeze-candidates', type=Path, help='Freeze a declared candidate CSV and protocol without fetching.')
    parser.add_argument('--protocol', type=Path, help='JSON selection/inclusion/exclusion protocol for a new candidate cohort.')
    parser.add_argument('--prepare-review', action='store_true', help='Create a new phase/hash-bound human review CSV; never overwrite labels.')
    parser.add_argument('--review-summary', action='store_true', help='Validate phase-bound human labels and summarize without network or capture changes.')
    parser.add_argument('--review-file', type=Path)
    parser.add_argument('--second-review-file', type=Path)
    parser.add_argument('--phase', choices=('baseline', 'improved'), default='baseline')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--mode', choices=('html', 'auto'), default='html')
    parser.add_argument('--engine', choices=('current', 'frozen'), default='current', help='Frozen replays the recorded baseline source after verifying its checksum.')
    options = parser.parse_args()
    try:
        if sum((options.freeze, bool(options.freeze_candidates), options.prepare_review, options.review_summary)) > 1:
            raise ValueError('Choose one freeze/review action at a time.')
        if (options.review_file or options.second_review_file) and not options.review_summary:
            raise ValueError('Review files require --review-summary; no capture was started.')
        if options.protocol and not options.freeze_candidates:
            raise ValueError('--protocol requires --freeze-candidates; no capture was started.')
        if options.freeze_candidates:
            print(freeze_candidates(options.freeze_candidates, options.protocol, options.output.resolve()))
        elif options.prepare_review:
            print(prepare_phase_review(options.output.resolve(), options.phase))
        elif options.review_summary:
            print(json.dumps(summarize_phase_review(options.output.resolve(), options.phase, options.review_file, options.second_review_file), indent=2))
        else:
            evaluate(options)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
