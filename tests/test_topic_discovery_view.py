"""Discovery navigation is model-free; new runs are scoped and retain prior results."""
from unittest.mock import patch
from copy import deepcopy

import pytest

from app import storage
from app.intelligence import IntelligenceError
from app.topic_discovery_view import _sources
from tests.test_dashboard import dashboard
from tests.test_topic_discovery import articles, client, inventory, run


def open_topics(app):
    app.button(key='nav_analytics').click().run()
    app.radio(key='analytics_workspace').set_value('Topic discovery (experimental)').run()
    assert not app.exception
    return app


def test_opening_discovery_and_changing_scope_never_runs_a_model(dashboard):
    with patch('app.topic_discovery_view.discover_topics') as discover:
        app = open_topics(dashboard)
        app.number_input[0].set_value(2).run()
        assert not app.exception and app.button(key='FormSubmitter:topic_discovery_form-Discover topics')
        discover.assert_not_called()


def test_too_small_scope_and_missing_backend_show_actionable_errors(dashboard):
    app = open_topics(dashboard)
    app.button(key='FormSubmitter:topic_discovery_form-Discover topics').click().run()
    assert not app.exception and any('4' in error.value for error in app.error)
    with patch('app.topic_discovery_view.dependencies', side_effect=IntelligenceError('Install requirements-topics.txt')):
        app.button(key='FormSubmitter:topic_discovery_form-Discover topics').click().run()
    assert not app.exception and any('requirements' in error.value for error in app.error)


def test_scoped_reads_do_not_silently_take_first_page(dashboard):
    storage.create_collection('chosen', 'Chosen', '')
    for article in articles():
        storage.upsert(article, collection_id='chosen')
    assert {article['id'] for article in _sources('chosen')} == {article['id'] for article in articles()}
    template = articles()[0]
    for i in range(201):
        storage.upsert(dict(template, id=f'large{i}', url=f'https://example.org/large{i}'))
    with pytest.raises(IntelligenceError, match='no subset was analyzed'):
        _sources('')


def test_discovery_retains_original_result_after_failure_scope_or_source_change(dashboard, client):
    storage.create_collection('chosen', 'Chosen', '')
    values = articles()
    for article in values:
        storage.upsert(article, collection_id='chosen')
    with patch('app.topic_discovery.observe_models', side_effect=lambda *args: inventory()):
        result = run(values, client)
    with patch('app.topic_discovery_view.discover_topics', return_value=result) as discover:
        app = open_topics(dashboard)
        app.selectbox(key='topic_collection').select('chosen').run()
        app.text_input[0].set_value('embed')
        app.button(key='FormSubmitter:topic_discovery_form-Discover topics').click().run()
        assert not app.exception and discover.call_count == 1
        assert {article['id'] for article in discover.call_args.args[0]} == {article['id'] for article in values}
        assert app.session_state['topic_discovery_result']['result'] == result
        assert app.download_button(key='topic_export')
        discover.side_effect = IntelligenceError('Ollama offline')
        app.button(key='FormSubmitter:topic_discovery_form-Discover topics').click().run()
        assert not app.exception and app.session_state['topic_discovery_result']['result'] == result
        assert any('Ollama offline' in error.value for error in app.error)
        storage.upsert(dict(values[0], text='Changed saved article.'))
        app.run()
        assert not app.exception and any('last completed discovery' in message.value for message in app.info)
        app.selectbox(key='topic_collection').select('').run()
        assert app.session_state['topic_discovery_result']['result'] == result and discover.call_count == 2
        app.button(key='topic_clear').click().run()
        assert not app.exception and 'topic_discovery_result' not in app.session_state


def test_subtopic_browsing_filters_sources_without_discovery_or_inference(dashboard, client):
    values = articles()
    for article in values:
        storage.upsert(article)
    with patch('app.topic_discovery.observe_models', side_effect=lambda *args: inventory()):
        result = run(values, client)
    parent = result['topics'][0]
    parent['subtopics'] = [dict(id=f'child-{i}', parent_id=parent['id'], keywords=[f'aspect{i}'],
        article_ids=parent['article_ids'][i:i+1], representatives=parent['article_ids'][i:i+1], unique_articles=1)
        for i in range(2)]
    parent['subtopic_outlier_article_ids'] = parent['article_ids'][2:]
    parent['subtopic_status'] = 'split'
    original = deepcopy(result)
    with patch('app.topic_discovery_view.discover_topics', return_value=result) as discover:
        app = open_topics(dashboard)
        app.button(key='FormSubmitter:topic_discovery_form-Discover topics').click().run()
        key = 'topic_browse_' + parent['id']
        assert not app.exception
        app.selectbox(key=key).select('child-0').run()
        shown = {button.key.removeprefix('topic_read_') for button in app.button
                 if button.key and button.key.startswith('topic_read_')}
        assert parent['article_ids'][0] in shown
        assert not set(parent['article_ids'][1:]).intersection(shown)
        app.selectbox(key=key).select('remaining').run()
        shown = {button.key.removeprefix('topic_read_') for button in app.button
                 if button.key and button.key.startswith('topic_read_')}
        assert set(parent['article_ids'][2:]) <= shown
        assert not set(parent['article_ids'][:2]).intersection(shown)
        assert discover.call_count == 1 and result == original and not app.exception


def test_previous_v1_result_remains_readable_without_subtopic_fields(dashboard, client):
    with patch('app.topic_discovery.observe_models', side_effect=lambda *args: inventory()):
        result = run(articles(), client)
    result['version'] = 'density-topics-v1'
    for topic in result['topics']:
        for field in ('subtopics', 'subtopic_status', 'subtopic_outlier_article_ids'):
            topic.pop(field)
    with patch('app.topic_discovery_view.discover_topics', return_value=result):
        app = open_topics(dashboard)
        app.button(key='FormSubmitter:topic_discovery_form-Discover topics').click().run()
        assert not app.exception and app.download_button(key='topic_export')
