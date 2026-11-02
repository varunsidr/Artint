"""Frozen, isolated baseline runs around the existing Artint RAG functions."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
import platform
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from time import perf_counter
from urllib.parse import urlsplit

from jsonschema import validate

from app import storage
from app.intelligence import IntelligenceError, OllamaClient, answer_question, semantic_search
from scripts.research_eval.contracts import EvaluationError, digest, encoded, load_corpus, read_json, validate_corpus, write_json
from scripts.research_eval.metrics import passage_locations, summarize

ROOT = Path(__file__).resolve().parents[2]
HARNESS_VERSION = 'research-eval-1'


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class FixtureClient:
    """Deterministic plumbing diagnostic, deliberately not a semantic/LLM benchmark.

    Hashed word-count embeddings and a matching-passage first-sentence echo use
    no gold labels, expected facts or answerability fields.
    """
    metadata = dict(provider='fixture', model_digest=None, runtime='scripted diagnostic; no LLM')
    stop = set('a an the and or of in on to for is are was were be by it its as at from what which how who when did does do with this that their has have much many'.split())

    @classmethod
    def words(cls, text):
        return [word for word in re.findall(r'[^\W_]+', text.lower()) if word not in cls.stop]

    def embed(self, model, texts, **kwargs):
        result = []
        for text in texts:
            if text.startswith('Instruct:'):
                text = text.split('\nQuery: ', 1)[-1]
            vector = [0.0] * 128
            for word, count in Counter(self.words(text)).items():
                vector[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 128] += count
            if not any(vector):
                vector[0] = 1.0
            result.append(vector)
        return result

    def generate(self, model, prompt, schema):
        question_text, source_text = prompt.split('\nQuestion (data):\n', 1)[1].split('\nSource passages:\n', 1)
        question, passages = json.loads(question_text), json.loads(source_text)
        words = set(self.words(question))
        matching = [passage for passage in passages if len(words & set(self.words(passage['text']))) >= 2]
        claims = []
        if matching:
            passage = matching[0]
            first = re.split(r'(?<=[.!?])\s+', passage['text'], maxsplit=1)[0]
            claims.append(dict(text=first, sources=[passage['id']]))
        result = dict(supported=bool(claims), claims=claims)
        validate(result, schema)
        return result


class RecordedOllama(OllamaClient):
    def __init__(self, base_url, timeout):
        super().__init__(base_url, timeout)
        self.request_settings = {}

    def _request(self, method, path, **kwargs):
        body = kwargs.get('json', {})
        if path == '/api/chat':
            self.request_settings['chat'] = dict(model=body.get('model'), options=body.get('options'),
                think=body.get('think'), stream=body.get('stream'), keep_alive=body.get('keep_alive'),
                truncate=body.get('truncate'), shift=body.get('shift'),
                schema_sha256=digest(encoded(body.get('format'))))
        elif path == '/api/embed':
            self.request_settings['embedding'] = dict(model=body.get('model'), truncate=body.get('truncate'))
        return super()._request(method, path, **kwargs)

    def identity(self, names):
        data = self._request('GET', '/api/tags', read_timeout=5)
        models = data.get('models')
        if not isinstance(models, list):
            raise IntelligenceError('Ollama returned an invalid model inventory.')
        selected = {row['name']: dict(name=row['name'], digest=row.get('digest'), details=row.get('details'))
                    for row in models if isinstance(row, dict) and row.get('name') in names}
        if set(selected) != set(names):
            raise IntelligenceError('An evaluation model is not installed; check the exact model names.')
        if any(not re.fullmatch(r'[a-f0-9]{64}', str(row['digest'])) for row in selected.values()):
            raise IntelligenceError('The model inventory did not provide immutable digests.')
        try:
            version = self._request('GET', '/api/version', read_timeout=5).get('version')
        except IntelligenceError:
            version = None
        return dict(models=selected, runtime_version=version)


class ObservedClient:
    def __init__(self, delegate):
        self.delegate = delegate
        self.generation_seconds = None
        self.embedding_seconds = 0.0
        self.embedding_calls = 0
        self.dimensions = set()
        self.generation_metadata = {}

    @property
    def last_generation(self):
        return self.generation_metadata

    def embed(self, *args, **kwargs):
        started = perf_counter()
        try:
            self.embedding_calls += 1
            vectors = self.delegate.embed(*args, **kwargs)
            self.dimensions.update(len(vector) for vector in vectors)
            return vectors
        finally:
            self.embedding_seconds += perf_counter() - started

    def generate(self, *args, **kwargs):
        started = perf_counter()
        try:
            return self.delegate.generate(*args, **kwargs)
        finally:
            self.generation_seconds = perf_counter() - started
            metadata = getattr(self.delegate, 'last_generation', {})
            if isinstance(metadata, dict):
                self.generation_metadata = json.loads(json.dumps(metadata))


def source_snapshot(destination):
    paths = [ROOT / 'app' / name for name in ('intelligence.py', 'storage.py', 'facets.py', 'text_preview.py')]
    paths += [ROOT / 'scripts/evaluate_research.py', *sorted(Path(__file__).parent.glob('*.py'))]
    result = {}
    for source in paths:
        relative = source.relative_to(ROOT)
        target = destination / 'engine-snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        target.write_bytes(content)
        result[relative.as_posix()] = digest(content)
    return result


def git_identity():
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, stderr=subprocess.DEVNULL))
        return dict(revision=revision, dirty=dirty)
    except (OSError, subprocess.CalledProcessError):
        return dict(revision=None, dirty=None)


def freeze(corpus_path, output):
    corpus = load_corpus(corpus_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'corpus.json', corpus)
    write_json(output / 'freeze.json', dict(schema_version=1, frozen_at=timestamp(),
        corpus_sha256=digest(encoded(corpus)), source=git_identity(), cases=len(corpus['cases']),
        notice='Frozen source bodies remain local unless redistribution is authorized. No URL is fetched.'))
    return output


def markdown_report(report):
    summary = report['summary']
    lines = ['# Research evaluation', '', f"Engine: {report['config']['engine']}; mode: {report['config']['mode']}.",
             '', f"Corpus kind: **{report['corpus_kind']}**. Quality gate: **not established**.", '',
             f"Selected cases: {summary['cases']}; eligible: {summary['eligible_cases']}; excluded: {summary['excluded_cases']}; failed runs: {summary['failed_runs']}.",
             '', 'Values below are story-macro diagnostics. Synthetic or provisional labels establish no model-quality claim.',
             '', '| Metric | Value | Story clusters |', '| --- | --- | --- |']
    for name, metric in summary['metrics'].items():
        value = metric['value']
        lines.append(f"| {name} | {value:.4f} | {metric['story_clusters']} |" if value is not None else f'| {name} | Not measured | 0 |')
    lines += ['', 'Claim support and useful answer coverage require a separate human review. Valid citation IDs are not a support score.',
              '', 'Retrieval runs measure top-10. Answer runs keep the application\'s six-passage context; @10 is not measured there.', '',
              'Case failures remain in applicable metric denominators; timing summaries cover successful runs only.', '',
              'See report.json for intervals, case results, source offsets, cache counts, model identity and timing boundaries.', '']
    return '\n'.join(lines)


def run(corpus_path, output, *, engine='fixture', mode='retrieval', model='qwen3:8b',
        embedding_model='qwen3-embedding:0.6b', base_url='http://127.0.0.1:11434',
        timeout=120, repeats=1, cache='cold', case_ids=None, client=None):
    corpus = load_corpus(corpus_path)
    frozen_manifest = Path(corpus_path).parent / 'freeze.json'
    if frozen_manifest.exists() and read_json(frozen_manifest).get('corpus_sha256') != digest(encoded(corpus)):
        raise EvaluationError('Frozen corpus changed after its manifest was created.')
    if engine not in ('fixture', 'ollama') or mode not in ('retrieval', 'answers') or cache not in ('cold', 'shared'):
        raise EvaluationError('Invalid engine, mode or cache regime.')
    if type(repeats) is not int or not 1 <= repeats <= 5 or not 1 <= timeout <= 300:
        raise EvaluationError('Use 1–5 repeats and a timeout of 1–300 seconds.')
    parsed = urlsplit(base_url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise EvaluationError('Use an HTTP(S) model endpoint without credentials, query or fragment.')
    chosen = set(case_ids or [case['id'] for case in corpus['cases']])
    cases = [case for case in corpus['cases'] if case['id'] in chosen]
    if len(cases) != len(chosen):
        raise EvaluationError('Unknown selected case ID.')
    if len(cases) * repeats > 1000:
        raise EvaluationError('Limit one run to 1,000 case/repeat observations.')
    locations = passage_locations(corpus['sources'])
    source_by_id = {source['id']: source for source in corpus['sources']}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'corpus.json', corpus)
    config = dict(harness_version=HARNESS_VERSION, engine=engine, mode=mode,
                  model=model if engine == 'ollama' else 'fixture-chat-v1',
                  embedding_model=embedding_model if engine == 'ollama' else 'fixture-embedding-v1',
                  endpoint=base_url if engine == 'ollama' else None, repeats=repeats, cache=cache,
                  selected_case_ids=[case['id'] for case in cases], retrieval_budget=10 if mode == 'retrieval' else 6,
                  timeout_seconds=timeout, source=git_identity(), source_files=source_snapshot(output),
                  environment=dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                                   os=platform.platform(), machine=platform.machine(), processor=platform.processor()),
                  dependency_versions={name: version(name) for name in ('requests', 'jsonschema')},
                  memory_measurement=None, cache_note='Cold means a new SQLite embedding cache per case/repeat; it does not clear OS caches or unload a resident model.')
    write_json(output / 'config.json', config)
    delegate = client or (FixtureClient() if engine == 'fixture' else RecordedOllama(base_url, timeout))
    names = [config['embedding_model']] + ([config['model']] if mode == 'answers' else [])
    identity_before, identity_after, setup_error = None, None, None
    if engine == 'ollama' and client is None:
        try:
            identity_before = delegate.identity(names)
        except IntelligenceError as exc:
            setup_error = dict(type=type(exc).__name__, message=str(exc)[:300])
    else:
        identity_before = dict(provider='fixture' if engine == 'fixture' else 'injected-test-client', digest=None)
    rows = []
    original_db = storage.DB
    try:
        # Every embedding write occurs inside this disposable cache, even when
        # the shell has configured the user's normal ARTICLE_LIBRARY_DB.
        with tempfile.TemporaryDirectory(prefix='artint-research-eval-') as temporary, (output / 'results.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            def record(row):
                rows.append(row)
                journal.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                journal.flush()
            for repeat in range(1, repeats + 1):
                for index, case in enumerate(cases):
                    row = dict(case_id=case['id'], repeat=repeat, status='excluded' if not case['eligible'] else 'ok',
                               exclusion_reason=case['exclusion_reason'], passages=[])
                    if not case['eligible']:
                        record(row)
                        continue
                    storage.DB = Path(temporary) / ('shared.db' if cache == 'shared' else f'case-{index}-{repeat}.db')
                    observed = ObservedClient(delegate)
                    started = perf_counter()
                    try:
                        if setup_error:
                            raise IntelligenceError('Model setup failed.')
                        sources = [source_by_id[source_id] for source_id in case['source_ids']]
                        stats = {}
                        if mode == 'answers':
                            answer = answer_question(case['question'], sources, config['model'], config['embedding_model'], observed)
                            retrieved = answer.pop('passages')
                            stats = answer.pop('retrieval')
                            row['answer'] = answer
                        else:
                            retrieved = semantic_search(case['question'], sources, config['embedding_model'], observed, limit=10, stats=stats)
                        row['timing'] = dict(pipeline_seconds=perf_counter()-started,
                            retrieval_seconds=stats.get('retrieval_seconds'), generation_seconds=observed.generation_seconds,
                            embedding_seconds=observed.embedding_seconds)
                        row['cache'] = stats
                        row['embedding_calls'] = observed.embedding_calls
                        row['embedding_dimensions_created'] = sorted(observed.dimensions)
                        row['request_settings'] = json.loads(json.dumps(getattr(delegate, 'request_settings', {})))
                        for passage in retrieved:
                            location = locations.get(passage['id'])
                            if not location or passage['text'] != location['text'] or location['source_id'] not in case['source_ids']:
                                raise EvaluationError('Retrieved passage identity/text is outside the frozen scope.')
                            row['passages'].append(dict(id=passage['id'], **location, score=passage['score']))
                        from scripts.research_eval.metrics import retrieval_metrics
                        row['retrieval_metrics'] = retrieval_metrics(case, row['passages'], sources, config['retrieval_budget'])
                    except (IntelligenceError, EvaluationError) as exc:
                        row.update(status='error', error_type=type(exc).__name__, passages=[],
                                   timing=dict(pipeline_seconds=perf_counter()-started), retrieval_metrics={})
                    if observed.last_generation:
                        row['generation'] = observed.last_generation
                    record(row)
                    if cache == 'cold':
                        cache_path = storage.DB.resolve()
                        if cache_path.parent != Path(temporary).resolve():
                            raise EvaluationError('Refusing to remove a cache outside this disposable run.')
                        for suffix in ('', '-wal', '-shm'):
                            Path(str(cache_path) + suffix).unlink(missing_ok=True)
    finally:
        storage.DB = original_db
    if engine == 'ollama' and client is None and not setup_error:
        try:
            identity_after = delegate.identity(names)
        except IntelligenceError:
            identity_after = None
    selected = dict(corpus, cases=cases)
    identity_changed = engine == 'ollama' and client is None and not setup_error and identity_before != identity_after
    report = dict(schema_version=1, created_at=timestamp(), corpus_sha256=digest(encoded(corpus)),
                  corpus_kind=corpus['kind'], corpus_name=corpus['name'], config=config,
                  model_identity_before=identity_before, model_identity_after=identity_after,
                  model_identity_changed=identity_changed, setup_error=setup_error,
                  request_settings=getattr(delegate, 'request_settings', {}),
                  status='invalid' if identity_changed else 'failed' if any(row['status'] == 'error' for row in rows) else 'complete',
                  summary=summarize(selected, rows, mode, config['retrieval_budget']), cases=rows)
    write_json(output / 'report.json', report)
    with (output / 'report.md').open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(markdown_report(report))
    return report


def load_run(directory):
    directory = Path(directory)
    report = read_json(directory / 'report.json', 128 * 1024 * 1024)
    corpus = load_corpus(directory / 'corpus.json')
    if report.get('schema_version') != 1 or report.get('corpus_sha256') != digest(encoded(corpus)):
        raise EvaluationError('Run/corpus integrity mismatch.')
    if read_json(directory / 'config.json') != report.get('config'):
        raise EvaluationError('Run configuration changed after capture.')
    for relative, expected in report['config']['source_files'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
            raise EvaluationError('Invalid engine snapshot path.')
        snapshot = directory / 'engine-snapshot' / path
        if (snapshot.is_symlink() or not snapshot.is_file() or snapshot.stat().st_size > 1024 * 1024
                or not snapshot.resolve().is_relative_to(directory.resolve()) or digest(snapshot.read_bytes()) != expected):
            raise EvaluationError('Engine snapshot changed after capture.')
    cases = {case['id']: case for case in corpus['cases']}
    expected_rows = {(case_id, repeat) for case_id in report['config']['selected_case_ids']
                     for repeat in range(1, report['config']['repeats'] + 1)}
    actual = [(row['case_id'], row['repeat']) for row in report['cases']]
    if len(actual) != len(set(actual)) or set(actual) != expected_rows or any(case_id not in cases for case_id, _ in actual):
        raise EvaluationError('Run has missing, duplicate or unexpected cases.')
    source_by_id = {source['id']: source for source in corpus['sources']}
    for row in report['cases']:
        case = cases[row['case_id']]
        if row['status'] not in ('ok', 'error', 'excluded') or (row['status'] == 'excluded') != (not case['eligible']):
            raise EvaluationError('Run eligibility/status mismatch.')
        seen = set()
        for passage in row['passages']:
            source = source_by_id.get(passage.get('source_id'))
            start, end = passage.get('start'), passage.get('end')
            if (not source or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source['text'])
                    or passage.get('text_sha256') != source['text_sha256'] or not isinstance(passage.get('text'), str)
                    or any(passage.get(key) != source[key] for key in ('title', 'url', 'captured_at'))
                    or ''.join(passage['text'].split()) != ''.join(source['text'][start:end].split())
                    or passage['source_id'] not in case['source_ids'] or passage['id'] in seen
                    or not isinstance(passage.get('score'), (float, int)) or not math.isfinite(passage['score'])):
                raise EvaluationError('Run contains changed, duplicate or out-of-scope evidence.')
            seen.add(passage['id'])
        answer = row.get('answer')
        if answer and (type(answer.get('supported')) is not bool or answer['supported'] != bool(answer.get('claims'))
                       or answer.get('question') != case['question'].strip()
                       or any(not claim.get('text') or not claim.get('sources') or not set(claim['sources']) <= seen for claim in answer['claims'])):
            raise EvaluationError('Run answer/citations do not match the recorded evidence.')
    return corpus, report, digest(encoded(report))
