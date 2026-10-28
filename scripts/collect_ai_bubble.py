"""Collect a diverse, audited set of public AI-bubble reading copies.

Candidates are discovered separately. This script never bypasses robots, logins,
paywalls, or site blocks, and never substitutes search snippets for article text.
"""
import argparse
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.extract import extract_article
from app.facets import readable_text
from app.reports import create_pdf
from app import storage

AI = re.compile(r'\b(AI|artificial intelligence|generative AI|OpenAI|ChatGPT|Nvidia|Anthropic)\b', re.I)
DEBATE = re.compile(r'\b(bubble\w*|overvalu\w*|valuation\w*|capex|capital expenditur\w*|circular financ\w*|overinvest\w*|monetiz\w*|monetis\w*|AI infrastructure)\b', re.I)


def normalize_url(url):
    parsed = urlsplit(url)
    tracking = ('utm_', 'fbclid', 'gclid', 'mc_cid', 'mc_eid')
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not any(key.lower().startswith(prefix) for prefix in tracking)]
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, urlencode(query), ''))


def _candidate_batches(candidates, seen, successes, per_domain, paused=None):
    groups = defaultdict(list)
    for candidate in candidates:
        url = normalize_url(candidate['url'])
        if url in seen:
            continue
        host = urlsplit(url).hostname or ''
        host = host.removeprefix('www.')
        if successes[host] < per_domain and host not in (paused or {}):
            groups[host].append(dict(candidate, url=url, host=host))
    rng = random.Random(20261027)
    hosts = sorted(groups)
    rng.shuffle(hosts)
    for host in hosts:
        rng.shuffle(groups[host])
    queues = {host: deque(groups[host]) for host in hosts}
    while queues:
        batch = []
        for host in list(queues):
            if successes[host] >= per_domain:
                del queues[host]
                continue
            batch.append(queues[host].popleft())
            if not queues[host]:
                del queues[host]
            if len(batch) == 4:
                break
        if batch:
            yield batch


def quality_rejection(article):
    title = article['title']
    path = urlsplit(article['url']).path.rstrip('/').lower()
    if (re.search(r'\bpage \d+ of \d+\b', title, re.I)
            or (urlsplit(article['url']).hostname or '').endswith('theguardian.com') and not re.search(r'/\d{4}/[a-z]{3}/\d{2}/', path)
            or re.search(r'^(a16z show|wiresift research|the AI economy|AI bubble (?:dashboard|tracker))\b', title, re.I)
            or path.split('/')[-1] in ('research', 'show', 'economy')
            or '/insights/topic/' in path
            or title.strip().casefold() in ('outlook 2026', 'emerging markets: going the distance')
            or re.search(r'investimento tematico|economics \+ technology sector', title, re.I)):
        return 'Category, directory, or tracker page rather than an individual article'
    if 'invesco.com' in (urlsplit(article['url']).hostname or '') and 'Leaving Invesco.com' in article['text']:
        return 'Extracted reading copy contains extensive site navigation and disclosure boilerplate'
    if re.search(r'existential.risk|value leakage|chinese whiz kids|out.talk humanity|new path to AGI', title, re.I):
        return 'Primary subject is not the AI investment/bubble debate'
    if title.lower().startswith('dot-com bubble explained'):
        return 'General historical guide rather than an AI-focused article'
    if article['word_count'] > 15000:
        return 'Long report/book-length page exceeds the article-collection scope'
    if len(readable_text(article['text']).split()) < 220:
        return 'Readable body is under 220 words after removing link destinations'
    return None


def _fetch(candidate):
    started = time.monotonic()
    url = candidate['url']
    if (re.search(r'\.(pdf|mp4|zip)(?:[?#]|$)', url, re.I)
            or any(host in candidate['host'] for host in ('youtube.com', 'youtu.be', 'wikipedia.org', 'reddit.com', 'facebook.com'))):
        return None, dict(candidate, status='unsupported', reason='Not a public HTML article candidate')
    try:
        article = extract_article(url)
        text = readable_text(article['text'])
        rejection = quality_rejection(article)
        if rejection:
            raise ValueError(rejection)
        if article['word_count'] < 220:
            raise ValueError('Body is under 220 words; possible excerpt, gate, or incomplete extraction')
        if not AI.search(article['title'] + '\n' + text) or not DEBATE.search(article['title'] + '\n' + text):
            raise ValueError('Extracted article did not pass the AI-bubble relevance check')
        if re.search(r'(subscribe to (?:continue|read)|sign in to continue|unlock this article|to continue reading,)', text[-1200:], re.I):
            raise ValueError('Possible subscription or sign-in gate in extracted text')
        return article, dict(candidate, status='extracted', final_url=article['url'],
                             word_count=article['word_count'], published=article['published'],
                             elapsed_seconds=round(time.monotonic() - started, 2))
    except Exception as exc:
        return None, dict(candidate, status='failed', reason=str(exc)[:500],
                          elapsed_seconds=round(time.monotonic() - started, 2))


def _shingles(article):
    words = re.findall(r'\w+', readable_text(article['text']).casefold())
    return {' '.join(words[index:index + 5]) for index in range(max(0, len(words) - 4))}


def collect(options):
    storage.create_collection('ai-bubble', 'AI bubble', 'AI valuations, infrastructure spending, returns, and financing risks')
    report_path = ROOT / 'output' / 'ai-bubble-collection.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {
        'topic': 'AI bubble', 'collection_id': 'ai-bubble', 'target': options.target,
        'as_of': options.as_of, 'selection': 'Reproducibly shuffled publisher buckets, at most five articles per host; not a representative sentiment survey.',
        'quality_policy': 'Public HTML only, publisher robots respected, at least 220 extracted words, relevance and duplicate checks; completeness is not guaranteed.',
        'attempts': [], 'saved': [],
    }
    saved = report['saved']
    seen = {row['url'] for row in report['attempts']}
    successes = Counter(row['host'] for row in saved)
    fingerprints, known_shingles, known_titles = set(), [], set()
    paused = report.get('paused_hosts', {})
    for record in saved:
        article = storage.get_article(record['article_id'])
        if article:
            fingerprints.add(hashlib.sha256(readable_text(article['text']).encode()).hexdigest())
            known_shingles.append(_shingles(article))
            known_titles.add((record['host'], re.sub(r'\W+', ' ', article['title'].casefold()).strip()))

    def save_report():
        report['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        report['summary'] = dict(saved=len(saved), publishers=len(successes), attempted=len(report['attempts']),
                                 statuses=dict(Counter(row['status'] for row in report['attempts'])))
        report['paused_hosts'] = paused
        temporary = report_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(report_path)

    idle_since = None
    with ThreadPoolExecutor(max_workers=4) as executor:
        while len(saved) < options.target:
            candidates = json.loads(options.candidates.read_text(encoding='utf-8'))
            batches = list(_candidate_batches(candidates, seen, successes, options.per_domain, paused))
            if not batches:
                if idle_since is None:
                    idle_since = time.monotonic()
                    print(f'Waiting for more candidates: {len(saved)}/{options.target} saved.', flush=True)
                if time.monotonic() - idle_since >= options.wait_for_candidates:
                    break
                time.sleep(5)
                continue
            idle_since = None
            for batch in batches:
                eligible = [candidate for candidate in batch if candidate['url'] not in seen
                            and successes[candidate['host']] < options.per_domain and candidate['host'] not in paused]
                if not eligible:
                    continue
                futures = {executor.submit(_fetch, candidate): candidate for candidate in eligible}
                for future in as_completed(futures):
                    article, record = future.result()
                    seen.add(record['url'])
                    if record['status'] == 'failed' and re.search(r'\b(403|429) Client Error', record.get('reason', '')):
                        paused[record['host']] = record['reason'][:200]
                    if article and len(saved) < options.target:
                        fingerprint = hashlib.sha256(readable_text(article['text']).encode()).hexdigest()
                        shingles = _shingles(article)
                        title_key = (record['host'], re.sub(r'\W+', ' ', article['title'].casefold()).strip())
                        if article['published'] and article['published'][:10] > options.as_of:
                            record.update(status='rejected', reason='Publication date is after the declared collection cutoff')
                        elif title_key in known_titles or fingerprint in fingerprints or any(len(shingles & other) / max(1, len(shingles | other)) >= .85 for other in known_shingles):
                            record.update(status='duplicate', reason='Duplicate or near-duplicate extracted article text')
                        elif successes[record['host']] >= options.per_domain:
                            record.update(status='quota', reason='Publisher contribution limit reached')
                        else:
                            try:
                                article['pdf_path'] = str(create_pdf(article))
                                storage.upsert(article, collection_id='ai-bubble')
                                fingerprints.add(fingerprint)
                                known_shingles.append(shingles)
                                known_titles.add(title_key)
                                record.update(status='saved', article_id=article['id'], title=article['title'],
                                              text_sha256=fingerprint, date_missing=not bool(article['published']),
                                              source_kind='research_abstract' if '/abs/' in article['url'] or 'research.google/pubs/' in article['url'] else 'article')
                                successes[record['host']] += 1
                                saved.append(dict(record))
                            except Exception as exc:
                                record.update(status='failed', reason='Save/PDF failure: ' + str(exc)[:400])
                    elif article:
                        record.update(status='not_needed', reason='Collection target reached')
                    report['attempts'].append(record)
                    save_report()
                    print(json.dumps(dict(saved=len(saved), target=options.target, publishers=len(successes),
                                          status=record['status'], host=record['host'],
                                          reason=record.get('reason', '')[:130])), flush=True)
                if len(saved) >= options.target:
                    break
    save_report()
    print(json.dumps(report['summary']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', type=Path, default=ROOT / 'data' / 'ai-bubble-candidates.json')
    parser.add_argument('--target', type=int, default=100)
    parser.add_argument('--per-domain', type=int, default=5)
    parser.add_argument('--as-of', default='2026-10-27')
    parser.add_argument('--wait-for-candidates', type=int, default=300)
    options = parser.parse_args()
    collect(options)
