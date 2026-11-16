"""Export an existing research result without inference or storage writes."""
from datetime import datetime, timezone
import html
import json
import re
from urllib.parse import quote, urlsplit, urlunsplit


def _literal(value):
    text = html.escape(str(value), quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+.!|$~>-])', r'\\\1', text)


def _source_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise ValueError('A source link is missing or invalid.')
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('A source link is missing or invalid.')
    port = parsed.port
    try:
        host = ('[' + parsed.hostname + ']') if ':' in parsed.hostname else parsed.hostname.encode('idna').decode('ascii')
    except UnicodeError:
        raise ValueError('A source link has an invalid international domain.') from None
    netloc = host + (':' + str(port) if port is not None else '')
    normalized = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    return quote(normalized, safe=":/?#[]@!$&'*+,;=%-._~")


def research_exports(result):
    """Return readable Markdown and a versioned complete JSON snapshot.

    Only validated existing citations become generated links. All model/source
    text is literal Markdown, so saved image/HTML syntax cannot fetch assets.
    """
    if not isinstance(result, dict) or not isinstance(result.get('question'), str):
        raise ValueError('This research result is incomplete.')
    passages = result.get('passages')
    claims = result.get('claims', [])
    if not isinstance(passages, list) or not isinstance(claims, list):
        raise ValueError('This research result has invalid evidence.')
    by_id = {}
    for index, passage in enumerate(passages, 1):
        if (not isinstance(passage, dict) or not isinstance(passage.get('id'), str)
                or not passage['id'] or passage['id'] in by_id
                or not isinstance(passage.get('text'), str) or not isinstance(passage.get('title'), str)):
            raise ValueError('This research result has invalid evidence.')
        by_id[passage['id']] = (index, passage, _source_url(passage.get('url')))
    cited = set()
    for claim in claims:
        if (not isinstance(claim, dict) or not isinstance(claim.get('text'), str)
                or not isinstance(claim.get('sources'), list) or not claim['sources']
                or any(not isinstance(source, str) or source not in by_id for source in claim['sources'])):
            raise ValueError('A claim has a missing or invalid citation; inspect the result before exporting.')
        cited.update(claim['sources'])
    if 'supported' in result and (type(result['supported']) is not bool or result['supported'] != bool(claims)):
        raise ValueError('This research result has an inconsistent answer status.')
    if 'supported' not in result and claims:
        raise ValueError('This research result is missing its answer status.')
    exported_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    lines = ['# Research brief' if 'supported' in result else '# Passage search', '',
             '## Question', '', _literal(result['question']), '',
             'Model: ' + _literal(result.get('model', 'Not recorded')), '']
    if isinstance(result.get('source_scope'), dict):
        source_scope = result['source_scope']
        ids = source_scope.get('searched_article_ids')
        if isinstance(ids, list):
            lines += [f'Scope: {len(ids)} saved articles searched; {len(passages)} passages retrieved.', '']
        if isinstance(source_scope.get('embedding_model'), str):
            lines += ['Search model: ' + _literal(source_scope['embedding_model']), '']
    if isinstance(result.get('completed_at'), str):
        lines += ['Result completed: ' + _literal(result['completed_at']), '']
    observation = result.get('model_observation')
    if isinstance(observation, dict) and observation.get('version') == 'ollama-model-observation-v1':
        if observation.get('state') == 'changed':
            lines += ['Run note: Installed model versions changed during this run. Inspect the evidence and generate '
                      'a fresh result before comparing runs. Cached search vectors remain unverified.', '']
        elif observation.get('state') == 'unavailable':
            lines += ['Run note: Model-version observations were incomplete for this result. '
                      'The saved passages remain available for inspection.', '']
    lines += ['## Findings', '']
    if result.get('supported') is False:
        lines += ['The retrieved saved passages did not provide enough evidence to answer this question.', '']
    elif claims:
        for number, claim in enumerate(claims, 1):
            links = ', '.join(f'[Source {by_id[source][0]:02}](#source-{by_id[source][0]})'
                              for source in dict.fromkeys(claim['sources']))
            lines += [f'{number}. {_literal(claim["text"])} ({links})', '']
    else:
        lines += ['Retrieved passages are provided below; no answer was generated.', '']
    lines += ['## Cited evidence' if cited else '## Retrieved evidence', '']
    for source_id, (index, passage, url) in by_id.items():
        if cited and source_id not in cited:
            continue
        lines += [f'<a id="source-{index}"></a>', f'### Source {index:02}: {_literal(passage["title"])}', '',
                  f'[Original source](<{url}>)', '', 'Saved passage: ' + _literal(source_id), '']
        lines += ['> ' + _literal(line) for line in passage['text'].splitlines()]
        lines.append('')
    lines += ['---', '', 'Based on saved article passages. Check citations and original sources before relying on a claim.',
              '', 'Exported: ' + exported_at, '']
    snapshot = dict(result, export_version=1, exported_at=exported_at,
                    export_notice='Saved-passage evidence; citation identifiers do not establish claim faithfulness or independent truth.')
    return '\n'.join(lines), json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False)
