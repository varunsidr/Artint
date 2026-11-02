import copy
import json
from unittest.mock import Mock, patch

import pytest
import requests

from app import storage
from app.intelligence import (
    ANALYSIS_VERSION, MAX_ANALYSIS_CHARS, CONTEXT_MARGIN, OUTPUT_TOKENS,
    IntelligenceError, OllamaClient, analyze_article, answer_question,
    article_passages, context_budget, semantic_search,
)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'test.db')


@pytest.fixture
def article():
    return dict(id='science', title='Roman glass', url='https://example.org/glass',
                source='Example', author='Writer', published='2026-01-01',
                fetched_at='2026-10-27T00:00:00Z',
                text='Scientists recreated ancient glass. Gold nanoparticles change its colour.',
                word_count=10, links_json='[]', images_json='[]', pdf_path='')


def response(content):
    result = Mock(status_code=200)
    result.json.return_value = {'version': '0.40.11', 'done': True, 'message': {'content': json.dumps(content)}}
    return result


def analysis_result(article):
    claim = {'text': 'Scientists recreated colour-changing glass.',
             'sources': [article_passages(article)[0]['id']]}
    return {'summary': claim, 'key_points': [copy.deepcopy(claim)], 'topics': ['Archaeology']}


def test_analysis_is_saved_and_reused_without_another_model_call(article):
    with patch('app.intelligence.requests.request', return_value=response(analysis_result(article))) as request:
        first = analyze_article(article, 'local-model')
        second = analyze_article(article, 'local-model')
    assert first == second
    assert sum(call.args[1].endswith('/api/chat') for call in request.call_args_list) == 1
    assert first['partial'] is False


@pytest.mark.parametrize('change', ['text', 'title', 'model', 'version'])
def test_cached_insight_is_invalidated_when_inputs_change(article, change):
    storage.save_insight(article, 'model', ANALYSIS_VERSION, analysis_result(article))
    modified = dict(article)
    if change in ('text', 'title'):
        modified[change] += ' Changed.'
    assert storage.load_insight(modified, 'other' if change == 'model' else 'model',
                                'new' if change == 'version' else ANALYSIS_VERSION) is None


def test_invalid_citations_are_rejected_and_never_cached(article):
    invalid = analysis_result(article)
    invalid['summary']['sources'] = ['invented-article:P1']
    with patch('app.intelligence.requests.request', return_value=response(invalid)):
        with pytest.raises(IntelligenceError, match='invalid citations'):
            analyze_article(article, 'local-model')
    assert storage.load_insight(article, 'local-model', ANALYSIS_VERSION) is None


def test_truncated_analysis_is_labeled_and_only_cites_supplied_passages(article):
    article['text'] = '\n'.join(f'Paragraph {n}: ' + 'evidence ' * 110 for n in range(40))
    client = Mock()
    client.generate.return_value = analysis_result(article)
    result = analyze_article(article, 'local-model', client)
    assert result['partial'] is True
    assert result['passages_analyzed'] < result['total_passages']
    prompt = client.generate.call_args.args[1]
    sources = json.loads(prompt.split('Source passages:\n')[1])
    assert sum(len(p['text']) for p in sources) <= MAX_ANALYSIS_CHARS


def test_passage_splitting_preserves_words_and_stable_ids(article):
    article['text'] = 'A' * 3000 + '\n' + 'B' * 1500
    passages = article_passages(article)
    assert all(len(p['text']) <= 1200 for p in passages)
    assert ''.join(p['text'].replace('\n', '') for p in passages) == article['text'].replace('\n', '')
    assert passages == article_passages(article)


def test_semantic_search_ranks_by_meaning_and_reuses_embeddings(article):
    other = dict(article, id='birds', title='Migration', text='Wild geese fly south in winter.')
    client = Mock()
    # Query wording differs from the article wording; similarity comes from vectors.
    client.embed.return_value = [[1.0, 0.0], [0.0, 1.0], [0.95, 0.05]]
    first = semantic_search('How were antique vessels reproduced?', [article, other], 'embedding', client)
    second = semantic_search('How were antique vessels reproduced?', [article, other], 'embedding', client)
    assert first[0]['article_id'] == 'science'
    assert first == second
    assert client.embed.call_count == 1


def test_changed_article_text_gets_new_embeddings(article):
    client = Mock()
    client.embed.return_value = [[1.0, 0.0], [1.0, 0.0]]
    semantic_search('glass', [article], 'embedding', client)
    modified = dict(article, text='A revised article about Roman craftsmanship.')
    client.embed.return_value = [[0.8, 0.2]]
    semantic_search('glass', [modified], 'embedding', client)
    assert len(client.embed.call_args.args[1]) == 1
    assert 'revised article' in client.embed.call_args.args[1][0]


def test_unanswerable_question_has_no_generated_claims(article):
    client = Mock()
    client.embed.return_value = [[1.0, 0.0], [0.0, 1.0]]
    client.generate.return_value = {'supported': False, 'claims': []}
    result = answer_question('Who won the football match?', [article], 'chat', 'embedding', client)
    assert result['supported'] is False
    assert result['claims'] == []
    assert result['passages']


def test_inconsistent_answer_is_rejected(article):
    client = Mock()
    client.embed.return_value = [[1.0, 0.0], [1.0, 0.0]]
    client.generate.return_value = {'supported': True, 'claims': []}
    with pytest.raises(IntelligenceError, match='inconsistent answer'):
        answer_question('What changed?', [article], 'chat', 'embedding', client)


@pytest.mark.parametrize('vectors', [[], [[]], [[float('nan')]], [[0.0]], [[True]], [[1.0], [1.0]]])
def test_invalid_embeddings_are_rejected(vectors):
    reply = Mock(status_code=200)
    reply.json.return_value = {'embeddings': vectors}
    with patch('app.intelligence.requests.request', return_value=reply):
        with pytest.raises(IntelligenceError):
            OllamaClient().embed('embedding', ['passage'])


@pytest.mark.parametrize('error,message', [
    (requests.ConnectionError(), 'Cannot reach Ollama'),
    (requests.Timeout(), 'timed out'),
])
def test_connection_failures_provide_actionable_errors(error, message):
    with patch('app.intelligence.requests.request', side_effect=error):
        with pytest.raises(IntelligenceError, match=message):
            OllamaClient().models()


def test_invalid_question_never_calls_model(article):
    client = Mock()
    for question in [' ', 'x' * 2001]:
        with pytest.raises(IntelligenceError):
            semantic_search(question, [article], 'embedding', client)
    client.embed.assert_not_called()


def test_multiple_embedding_batches_stay_warm_then_release_and_preserve_ranking(article):
    import math
    articles = [dict(article, id=str(index), text=f'Unique source {index}.') for index in range(36)]
    query = 'Instruct: Retrieve article passages relevant to the question.\nQuery: evidence'
    inputs = [item['title'] + '\n' + article_passages(item)[0]['text'] for item in articles] + [query]
    vectors = {text: [1.0, float(index + 1)] for index, text in enumerate(inputs)}
    client = Mock()
    client.embed.side_effect = lambda model, texts, **kwargs: [vectors[text] for text in texts]
    stats = {}
    result = semantic_search('evidence', articles, 'embedding', client, stats=stats)
    assert [call.kwargs['keep_alive'] for call in client.embed.call_args_list] == ['1m', '1m', 0]
    # Compare against the unchanged baseline formula, independently of cache batching.
    q = vectors[query]
    expected = sorted(zip(articles, inputs[:-1]), key=lambda pair: sum(a*b for a, b in zip(vectors[pair[1]], q))
                      / math.sqrt(sum(x*x for x in vectors[pair[1]]) * sum(x*x for x in q)), reverse=True)[:6]
    assert [p['article_id'] for p in result] == [item['id'] for item, _ in expected]
    assert stats['embeddings_created'] == 37 and stats['embedding_batches'] == 3
    assert stats['passages_searched'] == 36
    client.embed.reset_mock()
    warm = {}
    assert semantic_search('evidence', articles, 'embedding', client, stats=warm) == result
    client.embed.assert_not_called()
    assert warm['embeddings_reused'] == 37 and warm['embeddings_created'] == 0


def test_embedding_cache_reads_are_bounded_and_keep_model_isolation(monkeypatch):
    from contextlib import contextmanager
    values = {f'passage {index}': [float(index), 1.0] for index in range(700)}
    storage.save_embeddings('primary', values)
    storage.save_embeddings('other', {'passage 0': [-1.0, 9.0]})
    statements = []
    original = storage.connect
    @contextmanager
    def traced():
        with original() as con:
            con.set_trace_callback(statements.append)
            yield con
    monkeypatch.setattr(storage, 'connect', traced)
    assert storage.cached_embeddings('primary', [*values, 'missing', 'passage 0']) == values
    reads = [sql for sql in statements if 'FROM embeddings' in sql]
    assert len(reads) == 3
    assert storage.cached_embeddings('other', ['passage 0']) == {'passage 0': [-1.0, 9.0]}
    statements.clear()
    assert storage.cached_embeddings('primary', []) == {} and not statements


def test_intermediate_embedding_failure_does_not_cache_missing_vectors(article):
    articles = [dict(article, id=str(index), text=f'Unique source {index}.') for index in range(32)]
    client = Mock()
    client.embed.side_effect = [ [[1.0, 1.0]] * 16, IntelligenceError('interrupted') ]
    with pytest.raises(IntelligenceError, match='interrupted'):
        semantic_search('evidence', articles, 'embedding', client)
    # Resume completes only missing batches and retains the same ranking inputs.
    client.embed.reset_mock(side_effect=True)
    client.embed.side_effect = lambda model, texts, **kwargs: [[1.0, 1.0]] * len(texts)
    stats = {}
    semantic_search('evidence', articles, 'embedding', client, stats=stats)
    assert stats['embeddings_reused'] == 16 and stats['embeddings_created'] == 17
    assert client.embed.call_args_list[-1].kwargs['keep_alive'] == 0


def test_context_budget_boundary_and_schema_unicode_bytes():
    available = 8192 - OUTPUT_TOKENS - CONTEXT_MARGIN
    assert context_budget([{'content': 'x' * (available * 3)}])['context_window'] == 8192
    assert context_budget([{'content': 'x' * (available * 3 + 1)}])['context_window'] == 16384
    assert context_budget([{'content': '界' * 7000}])['context_window'] == 16384


SIMPLE_SCHEMA = dict(type='object', properties={'value': {'type': 'integer'}}, required=['value'])


def runtime_response(version='0.40.11'):
    reply = Mock(status_code=200)
    reply.json.return_value = {'version': version}
    return reply


def context_error_reply(status=400):
    reply = Mock(status_code=status)
    reply.json.return_value = {'error': 'request (9000 tokens) exceeds the available context size (8192 tokens), try increasing it'}
    return reply


def test_small_request_uses_8k_with_output_reserve_and_no_truncation():
    client = OllamaClient()
    with patch('app.intelligence.requests.request', side_effect=[runtime_response(), response({'value': 42}),
                                                              response({'value': 43})]) as request:
        assert client.generate('qwen3:8b', 'Small question', SIMPLE_SCHEMA) == {'value': 42}
        assert client.generate('qwen3:8b', 'Another question', SIMPLE_SCHEMA) == {'value': 43}
    assert request.call_count == 3  # Runtime capability floor checked once per client.
    payload = request.call_args.kwargs['json']
    assert payload['options'] == dict(temperature=0, num_ctx=8192, num_predict=1600)
    assert payload['truncate'] is False and payload['shift'] is False and payload['think'] is False
    assert client.last_generation['context_window'] == 8192


def test_large_schema_is_counted_even_for_a_short_question():
    schema = dict(type='object', properties={'value': {'type': 'string', 'enum': ['x' * 24000]}}, required=['value'])
    with patch('app.intelligence.requests.request', side_effect=[runtime_response(), response({'value': 'x' * 24000})]) as request:
        OllamaClient().generate('chat', 'Small question', schema)
    assert request.call_args.kwargs['json']['options']['num_ctx'] == 16384


@pytest.mark.parametrize('status', [200, 400, 413, 500])
def test_underestimated_request_retries_complete_prompt_once_at_16k(status):
    client = OllamaClient()
    with patch('app.intelligence.requests.request', side_effect=[runtime_response(), context_error_reply(status),
                                                              response({'value': 42})]) as request:
        assert client.generate('chat', 'Original evidence: 日本語 😀', SIMPLE_SCHEMA) == {'value': 42}
    first, second = [call.kwargs['json'] for call in request.call_args_list[1:]]
    assert [first['options']['num_ctx'], second['options']['num_ctx']] == [8192, 16384]
    assert first['messages'] == second['messages'] and first['format'] == second['format']
    assert first['messages'][1]['content'].startswith('Original evidence: 日本語 😀')
    assert client.last_generation['attempts'][0]['status'] == 'context_exceeded'
    assert client.last_generation['context_window'] == 16384


def test_actual_token_count_can_expand_context_to_preserve_answer_space():
    reply = response({'value': 42})
    reply.json.return_value.update(prompt_eval_count=7000, eval_count=5)
    client = OllamaClient()
    with patch('app.intelligence.requests.request', side_effect=[runtime_response(), reply, reply]):
        assert client.generate('chat', 'Underestimated input', SIMPLE_SCHEMA) == {'value': 42}
    assert client.last_generation['context_window'] == 16384
    assert client.last_generation['prompt_tokens'] == 7000
    assert client.last_generation['attempts'][0]['status'] == 'insufficient_output_room'


@pytest.mark.parametrize('overflow', [True, False])
def test_16k_limit_fails_without_saving_or_dropping_sources(article, overflow):
    reply = context_error_reply() if overflow else response(analysis_result(article))
    if not overflow:
        reply.json.return_value.update(prompt_eval_count=15500)
    with patch('app.intelligence.requests.request', side_effect=[runtime_response(), reply, reply]) as request:
        with pytest.raises(IntelligenceError, match='16K'):
            analyze_article(article, 'chat')
    assert request.call_count == 3
    assert storage.load_insight(article, 'chat', ANALYSIS_VERSION) is None


@pytest.mark.parametrize('kind', ['network', 'invalid_citation', 'output_limit', 'server'])
def test_non_context_failures_are_not_retried_at_a_larger_context(article, kind):
    reply = response(analysis_result(article))
    if kind == 'network':
        reply = requests.Timeout()
    elif kind == 'invalid_citation':
        invalid = analysis_result(article)
        invalid['summary']['sources'] = ['invented:P1']
        reply = response(invalid)
    elif kind == 'output_limit':
        reply.json.return_value.update(done_reason='length')
    else:
        reply.status_code = 500
        reply.json.return_value = {'error': 'model load failed: insufficient memory'}
    with patch('app.intelligence.requests.request', side_effect=[runtime_response(), reply]) as request:
        with pytest.raises(IntelligenceError):
            analyze_article(article, 'chat')
    assert request.call_count == 2
    assert storage.load_insight(article, 'chat', ANALYSIS_VERSION) is None


@pytest.mark.parametrize('version', ['0.40.10', '0.12.0', 'unknown', None])
def test_unverified_runtime_does_not_silently_ignore_context_controls(version):
    with patch('app.intelligence.requests.request', return_value=runtime_response(version)) as request:
        with pytest.raises(IntelligenceError, match='0.40.11'):
            OllamaClient().generate('chat', 'question', SIMPLE_SCHEMA)
    assert request.call_count == 1


def test_saved_analysis_and_research_trace_include_actual_context(article):
    reply = response(analysis_result(article))
    reply.json.return_value.update(prompt_eval_count=240, eval_count=60)
    client = OllamaClient()
    with patch('app.intelligence.requests.request', side_effect=[runtime_response(), reply]):
        saved = analyze_article(article, 'chat', client)
    assert saved['generation']['context_window'] == 8192
    assert saved['generation']['prompt_tokens'] == 240
    client.embed = Mock(return_value=[[1., 1.], [1., 1.]])
    claim = {'text': 'Reported glass research.', 'sources': [article_passages(article)[0]['id']]}
    reply = response({'supported': True, 'claims': [claim]})
    reply.json.return_value.update(prompt_eval_count=350, eval_count=35)
    with patch('app.intelligence.requests.request', return_value=reply):
        answer = answer_question('What is reported?', [article], 'chat', 'embed', client)
    assert answer['generation']['prompt_tokens'] == 350
    assert answer['generation']['context_window'] == 8192
