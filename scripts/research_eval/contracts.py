"""Versioned corpus contracts and source-independent gold evidence spans."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator


class EvaluationError(ValueError):
    """Invalid evaluation input; safe to display without source contents."""


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def string(maximum=200):
    return dict(type='string', minLength=1, maxLength=maximum)


def obj(properties, required=None):
    return dict(type='object', additionalProperties=False, properties=properties,
                required=list(properties) if required is None else required)


def array(items, maximum, minimum=0):
    return dict(type='array', items=items, maxItems=maximum, minItems=minimum)


SHA = dict(type='string', pattern='^[a-f0-9]{64}$')
IDENTIFIER = dict(type='string', pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
LABEL = obj(dict(kind=dict(enum=['synthetic', 'human', 'unreviewed']), reviewer=string(100),
                 reviewed_at=dict(type='string', maxLength=40)))
SOURCE = obj(dict(id=IDENTIFIER, title=string(1000), url=string(2000), story_group=IDENTIFIER,
                  text=string(256000), text_sha256=SHA, captured_at=string(40),
                  source_type=dict(enum=['synthetic', 'article', 'analysis', 'opinion', 'abstract', 'transcript', 'other'])))
EVIDENCE = obj(dict(id=IDENTIFIER, source_id=IDENTIFIER, text_sha256=SHA,
                    start=dict(type='integer', minimum=0), end=dict(type='integer', minimum=1), quote=string(4000)))
CASE = obj(dict(id=IDENTIFIER, question=string(2000), story_group=IDENTIFIER,
                split=dict(enum=['smoke', 'development', 'heldout']),
                answerability=dict(enum=['answerable', 'unanswerable']),
                tags=array(string(80), 20), source_ids=array(IDENTIFIER, 100, 1),
                evidence=array(EVIDENCE, 60), acceptable_sets=array(array(IDENTIFIER, 60, 1), 20),
                required_facts=array(obj(dict(id=IDENTIFIER, text=string(1200))), 30),
                label=LABEL, eligible=dict(type='boolean'), exclusion_reason=dict(type='string', maxLength=1000)))
CORPUS_SCHEMA = obj(dict(schema_version=dict(const=1), name=string(200),
                        kind=dict(enum=['synthetic', 'development', 'heldout']),
                        provenance=string(2000), selection_protocol=string(4000),
                        sources=array(SOURCE, 256, 1), cases=array(CASE, 1000, 1)))
CORPUS_SCHEMA['$schema'] = 'https://json-schema.org/draft/2020-12/schema'


def read_json(path, limit=16 * 1024 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise EvaluationError('Expected a regular JSON file within the size limit.')
    try:
        def pairs(values):
            result = {}
            for key, value in values:
                if key in result:
                    raise EvaluationError('Duplicate JSON object keys are not allowed.')
                result[key] = value
            return result
        def constant(value):
            raise EvaluationError('Non-finite JSON values are not allowed.')
        return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except EvaluationError:
        raise
    except (UnicodeError, ValueError) as exc:
        raise EvaluationError('Invalid UTF-8 JSON.') from exc


def _unique(values, field, context):
    keys = [row[field] for row in values]
    if len(keys) != len(set(keys)):
        raise EvaluationError(f'Duplicate {context} IDs.')
    return {row[field]: row for row in values}


def valid_timestamp(value):
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.utcoffset() is not None
    except (ValueError, TypeError, AttributeError):
        return False


def validate_corpus(corpus):
    # Report paths, never text/quotes in schema errors (corpora may be private).
    errors = list(Draft202012Validator(CORPUS_SCHEMA).iter_errors(corpus))
    if errors:
        path = '.'.join(map(str, errors[0].absolute_path)) or 'root'
        raise EvaluationError(f'Corpus schema validation failed at {path}.')
    sources = _unique(corpus['sources'], 'id', 'source')
    cases = _unique(corpus['cases'], 'id', 'case')
    if sum(len(source['text'].encode('utf-8')) for source in sources.values()) > 8 * 1024 * 1024:
        raise EvaluationError('Corpus text exceeds 8 MiB.')
    body_families, splits = {}, {}
    for source in sources.values():
        if digest(source['text'].encode('utf-8')) != source['text_sha256']:
            raise EvaluationError(f"Source hash mismatch: {source['id']}.")
        if not valid_timestamp(source['captured_at']):
            raise EvaluationError('Source capture time must include a timezone.')
        family = body_families.setdefault(source['text_sha256'], source['story_group'])
        if family != source['story_group']:
            raise EvaluationError('Identical source copies must share a story family.')
        url = urlsplit(source['url'])
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
                or any(ord(char) < 32 for char in source['url'])):
            raise EvaluationError('Source provenance URLs must be HTTP(S); they are never fetched.')
    for case in cases.values():
        case_id = case['id']
        ids = case['source_ids']
        if len(ids) != len(set(ids)) or any(value not in sources for value in ids):
            raise EvaluationError(f'Invalid or duplicate source scope: {case_id}.')
        if not case['eligible'] and not case['exclusion_reason'].strip():
            raise EvaluationError('Excluded cases need a reason.')
        if case['eligible'] and case['exclusion_reason']:
            raise EvaluationError('Eligible cases cannot carry an exclusion reason.')
        label = case['label']
        if label['kind'] == 'human' and (not label['reviewer'].strip() or not valid_timestamp(label['reviewed_at'])):
            raise EvaluationError('Human gold labels need a reviewer and a timezone-aware timestamp.')
        if corpus['kind'] == 'synthetic' and label['kind'] != 'synthetic':
            raise EvaluationError('Synthetic cases must retain synthetic label provenance.')
        expected_split = 'smoke' if corpus['kind'] == 'synthetic' else corpus['kind']
        if case['split'] != expected_split:
            raise EvaluationError('Use separate synthetic, development and held-out corpus files.')
        evidence = _unique(case['evidence'], 'id', 'evidence')
        facts = _unique(case['required_facts'], 'id', 'required-fact')
        for unit in evidence.values():
            source = sources.get(unit['source_id'])
            if not source or source['id'] not in ids or source['story_group'] != case['story_group']:
                raise EvaluationError(f'Gold evidence is outside the target story/scope: {case_id}.')
            if (unit['text_sha256'] != source['text_sha256'] or not 0 <= unit['start'] < unit['end'] <= len(source['text'])
                    or source['text'][unit['start']:unit['end']] != unit['quote'] or not unit['quote'].strip()):
                raise EvaluationError(f'Gold span/hash/quote mismatch: {case_id}.')
        used = set()
        for accepted in case['acceptable_sets']:
            if len(accepted) != len(set(accepted)) or any(unit not in evidence for unit in accepted):
                raise EvaluationError(f'Invalid acceptable evidence set: {case_id}.')
            used.update(accepted)
        if case['answerability'] == 'answerable':
            if not evidence or not used or used != set(evidence) or not facts:
                raise EvaluationError('Answerable cases need facts and complete acceptable evidence sets.')
        elif evidence or used or facts:
            raise EvaluationError('Unanswerable cases cannot claim sufficient gold evidence/facts.')
        for family in {case['story_group'], *(sources[value]['story_group'] for value in ids)}:
            previous = splits.setdefault(family, case['split'])
            if previous != case['split']:
                raise EvaluationError('A story/source family crosses corpus splits.')
    return corpus


def load_corpus(path):
    return validate_corpus(read_json(path))


def check_disjoint(left, right):
    """Check separate development/held-out files; near-duplicates require human grouping."""
    validate_corpus(left)
    validate_corpus(right)
    if left['kind'] != 'development' or right['kind'] != 'heldout':
        raise EvaluationError('Split checking requires development and heldout corpus kinds in that order.')
    groups = lambda corpus: {row['story_group'] for row in corpus['sources'] + corpus['cases']}
    hashes = lambda corpus: {row['text_sha256'] for row in corpus['sources']}
    if groups(left) & groups(right) or hashes(left) & hashes(right):
        raise EvaluationError('Development/held-out corpora share story families or exact source text.')


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')
