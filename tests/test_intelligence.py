import copy
import json
from unittest.mock import Mock, patch

import pytest
import requests

from app import storage
from app.intelligence import (
    ANALYSIS_VERSION, MAX_ANALYSIS_CHARS, IntelligenceError, OllamaClient,
    analyze_article, answer_question, article_passages, semantic_search,
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
    result.json.return_value = {'done': True, 'message': {'content': json.dumps(content)}}
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
    assert request.call_count == 1
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
