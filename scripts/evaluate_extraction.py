"""Frozen-source diagnostics and honest review accounting; never writes the library.

Publisher HTML is cached locally for paired replay, not a redistributable fixture.
Automated paragraph coverage is a diagnostic, never a human completeness score.
"""
import argparse
import csv
import hashlib
import json
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
            'release_gate_met': len(reviewed) >= 100 and len(hosts) >= 10 and rate >= .9}


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
    if not 1 <= len(cases) <= 100 or len({row['id'] for row in cases}) != len(cases):
        raise ValueError('Expected 1-100 unique manifest cases.')
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
    parse_document = extract_document
    if options.engine == 'frozen':
        engine_path = cache/'baseline-extract.py'
        original = json.loads((output/'initial-diagnostics.json').read_text(encoding='utf-8'))
        if options.phase != 'baseline' or digest(engine_path.read_bytes()) != original['extraction_sha256']:
            raise ValueError('Frozen engine must match the recorded original baseline source.')
        parse_document = runpy.run_path(str(engine_path))['extract_document']
    origin_path = output/'initial-diagnostics.json'
    original_failures = {row['id']: row for row in json.loads(origin_path.read_text(encoding='utf-8'))['results'] if row['status'] == 'failed'} if origin_path.exists() else {}
    report = dict(version=1, phase=options.phase, started_at=stamp(), mode=options.mode,
                  manifest_sha256=digest(manifest_bytes), extraction_sha256=digest(engine_path.read_bytes()),
                  diagnostics_sha256=digest((ROOT/'app/capture_quality.py').read_bytes()),
                  limitations=manifest['limitations'], results=[])
    if report_path.exists():
        if not options.resume:
            raise ValueError('Phase already exists; use --resume or a new phase name.')
        previous = json.loads(report_path.read_text(encoding='utf-8'))
        for key in ('manifest_sha256', 'extraction_sha256', 'diagnostics_sha256', 'mode'):
            if report[key] != previous[key]:
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
    parser.add_argument('--phase', choices=('baseline', 'improved'), default='baseline')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--mode', choices=('html', 'auto'), default='html')
    parser.add_argument('--engine', choices=('current', 'frozen'), default='current', help='Frozen replays the recorded baseline source after verifying its checksum.')
    options = parser.parse_args()
    try:
        evaluate(options)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
