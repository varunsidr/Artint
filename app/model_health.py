"""Read-only Ollama inventory/runtime/residency checks; never load a model."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import re
from urllib.parse import urlsplit

import requests

from app.intelligence import MIN_CONTEXT_RUNTIME

MAX_METADATA_BYTES = 1024 * 1024
MAX_MODELS = 512


class ModelHealthError(Exception):
    """A bounded metadata check failed without exposing server response bodies."""


def _endpoint(value):
    value = (value or os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')).rstrip('/')
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or any(ord(c) < 32 for c in value)):
        raise ValueError('Use an HTTP(S) Ollama endpoint without credentials, query or fragment.')
    try:
        parsed.port
    except ValueError:
        raise ValueError('The Ollama endpoint has an invalid port.') from None
    return value


def _metadata(base_url, path):
    try:
        with requests.get(base_url + path, timeout=(3, 3), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise ModelHealthError(f'{path} returned HTTP {response.status_code}.')
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=16384):
                size += len(chunk)
                if size > MAX_METADATA_BYTES:
                    raise ModelHealthError(f'{path} metadata exceeded the size limit.')
                chunks.append(chunk)
            try:
                data = json.loads(b''.join(chunks))
            except (ValueError, UnicodeError, RecursionError):
                raise ModelHealthError(f'{path} did not return valid JSON metadata.') from None
            if not isinstance(data, dict) or data.get('error'):
                raise ModelHealthError(f'{path} returned invalid metadata.')
            return data
    except requests.RequestException:
        raise ModelHealthError('Cannot reach the Ollama metadata service. Check the endpoint and start Ollama if it is local.') from None


def _models(data):
    rows = data.get('models')
    if (not isinstance(rows, list) or len(rows) > MAX_MODELS
            or any(not isinstance(row, dict) or not isinstance(row.get('name'), str)
                   or not row['name'].strip() or len(row['name']) > 512 for row in rows)):
        raise ModelHealthError('Ollama returned an invalid or oversized model list.')
    return rows


def _nonnegative_int(value):
    return value if type(value) is int and value >= 0 else None


def residency(row):
    """Classify reported model-memory residency, not GPU utilization or speed."""
    total, gpu = _nonnegative_int(row.get('size')), _nonnegative_int(row.get('size_vram'))
    placement, percent = 'unknown', None
    if total and gpu is not None and gpu <= total:
        placement = 'gpu' if gpu == total else 'cpu' if gpu == 0 else 'mixed'
        percent = 100 * gpu / total
    context = _nonnegative_int(row.get('context_length'))
    return dict(placement=placement, gpu_memory_percent=percent, total_bytes=total,
                gpu_bytes=gpu if total and gpu is not None and gpu <= total else None,
                context_tokens=context if context else None)


def memory_share_label(memory):
    percent = memory.get('gpu_memory_percent')
    if type(percent) not in (int, float) or not 0 <= percent <= 100:
        return 'Unavailable'
    if memory.get('placement') == 'mixed':
        if percent > 99.9:
            return '>99.9%'
        if percent < 0.1:
            return '<0.1%'
    return f'{percent:.1f}'.rstrip('0').rstrip('.') + '%'


def observe_models(base_url, names):
    """Observe only selected installed manifests; never infer cached-vector identity."""
    if (not isinstance(names, (list, tuple)) or not 1 <= len(names) <= 2
            or any(not isinstance(name, str) or not name.strip() or len(name) > 512 for name in names)):
        raise ValueError('Observe one or two explicitly selected model names.')
    selected = dict.fromkeys(names)
    snapshot = dict(checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        state='unavailable', models={name: dict(installed=None, digest=None, details={}) for name in selected},
        error=None)
    try:
        rows = _models(_metadata(_endpoint(base_url), '/api/tags'))
        matches = [row for row in rows if row['name'] in selected]
        if len({row['name'] for row in matches}) != len(matches):
            raise ModelHealthError('Ollama returned duplicate selected model names.')
        by_name = {row['name']: row for row in matches}
        for name in selected:
            row = by_name.get(name)
            item = snapshot['models'][name]
            item['installed'] = row is not None
            if row is None:
                continue
            digest = row.get('digest')
            item['digest'] = digest if isinstance(digest, str) and re.fullmatch(r'[a-f0-9]{64}', digest) else None
            details = row.get('details')
            if isinstance(details, dict):
                item['details'] = {key: value for key in ('format', 'family', 'parameter_size', 'quantization_level')
                    if isinstance((value := details.get(key)), str) and 0 < len(value) <= 128}
        snapshot['state'] = 'complete' if all(item['digest'] for item in snapshot['models'].values()) else 'incomplete'
    except (ModelHealthError, ValueError) as exc:
        snapshot['error'] = str(exc)
    return snapshot


def model_observation(before, after):
    """Compare observed manifest digests, without certifying inference or cache weights."""
    left, right = before['models'], after['models']
    if set(left) != set(right):
        raise ValueError('Model observations need the same selected names.')
    changed = any((type(left[name]['installed']) is bool and type(right[name]['installed']) is bool
                   and left[name]['installed'] != right[name]['installed'])
                  or (left[name]['digest'] is not None and right[name]['digest'] is not None
                      and left[name]['digest'] != right[name]['digest']) for name in left)
    state = 'changed' if changed else 'stable' if before['state'] == after['state'] == 'complete' else 'unavailable'
    return dict(version='ollama-model-observation-v1', state=state,
        before=deepcopy(before), after=deepcopy(after),
        notice='Selected installed-manifest observations only; stable digests do not verify the weights '
               'used by inference, server defaults or reused embeddings. Embedding cache keys remain model tags.')


def inspect_ollama(base_url=None, *, chat_model='qwen3:8b', embedding_model='qwen3-embedding:0.6b'):
    base_url = _endpoint(base_url)
    for name in (chat_model, embedding_model):
        if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 512):
            raise ValueError('Choose a nonempty installed model name.')
    report = dict(endpoint=base_url, checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        connection='unavailable', runtime_version=None, generation_compatible=None,
        installed_models=None, loaded_models=None, errors=[], answer_ready=False, search_ready=False)
    installed = None
    try:
        installed = sorted({row['name'] for row in _models(_metadata(base_url, '/api/tags'))})
        report.update(connection='online', installed_models=installed)
    except ModelHealthError as exc:
        report['errors'].append(dict(check='inventory', message=str(exc)))
    if installed is not None:
        try:
            version = _metadata(base_url, '/api/version').get('version')
            report['runtime_version'] = version if isinstance(version, str) and len(version) <= 100 else None
            match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:\+[\w.-]+)?', report['runtime_version'] or '')
            report['generation_compatible'] = bool(match and tuple(map(int, match.groups())) >= MIN_CONTEXT_RUNTIME)
            if not report['generation_compatible']:
                report['errors'].append(dict(check='runtime', message='New answers require Ollama 0.40.11 or newer for checked context controls.'))
        except ModelHealthError as exc:
            report['errors'].append(dict(check='runtime', message=str(exc)))
        try:
            loaded = _models(_metadata(base_url, '/api/ps'))
            if len({m['name'] for m in loaded}) != len(loaded):
                raise ModelHealthError('Ollama returned duplicate running-model identities.')
            report['loaded_models'] = [dict(name=row['name'], **residency(row)) for row in loaded]
        except ModelHealthError as exc:
            report['errors'].append(dict(check='residency', message=str(exc)))
    selected = {}
    for role, name in (('chat', chat_model), ('embedding', embedding_model)):
        loaded = report['loaded_models']
        match = next((m for m in loaded or [] if m['name'] == name), None)
        selected[role] = dict(name=name, installed=(name in installed) if installed is not None else None,
            loaded=(match is not None) if loaded is not None else None,
            residency=match)
    report['selected'] = selected
    if installed is not None:
        if not selected['chat']['installed']:
            report['errors'].append(dict(check='selection', message='The selected answer model is not installed. Choose an installed model or install it in Ollama.'))
        if not selected['embedding']['installed']:
            report['errors'].append(dict(check='selection', message='The selected search model is not installed. Choose an installed embedding model or install it in Ollama.'))
    report['search_ready'] = bool(selected['embedding']['installed'])
    report['answer_ready'] = bool(selected['chat']['installed'] and report['generation_compatible'])
    return report
