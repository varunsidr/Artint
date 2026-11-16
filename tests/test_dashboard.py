from pathlib import Path
from datetime import date
from unittest.mock import patch

import pytest
import requests
from streamlit.testing.v1 import AppTest

from app import storage
from app.intelligence import IntelligenceError


def test_context_caption_ignores_invalid_optional_backup_metadata():
    from app.ai_dashboard import _show_generation_context
    with patch('app.ai_dashboard.st.caption') as caption:
        for metadata in (None, [], {}, {'context_window': '8192'}, {'context_window': True}):
            _show_generation_context({'generation': metadata})
        caption.assert_not_called()
        _show_generation_context({'generation': {'context_window': 16384, 'prompt_tokens': 'bad',
                                                'attempts': None}})
        caption.assert_called_once_with('16K context')


def test_compute_check_is_explicit_and_distinguishes_installed_from_loaded(dashboard):
    from app.model_health import inspect_ollama
    from app.ai_dashboard import _compute_table
    from unittest.mock import patch
    import requests
    with patch('app.model_health.requests.get', side_effect=requests.ConnectionError()):
        offline = inspect_ollama()
    with patch('app.ai_dashboard.inspect_ollama', return_value=offline) as inspect, \
            patch('app.ai_dashboard._compute_table', wraps=_compute_table) as table:
        app = dashboard
        app.button(key='nav_research').click().run()
        inspect.assert_not_called()
        app.button(key='research_check_compute').click().run()
        assert not app.exception and inspect.call_count == 1
        assert any('Cannot reach' in warning.value for warning in app.warning)
        assert table.call_args.args[0][0]['Installed'] == 'Unknown'
        assert table.call_args.args[0][0]['Loaded on'] == 'Unavailable'


def test_model_selection_change_discards_old_compute_snapshot(dashboard):
    app = dashboard
    app.button(key='nav_research').click().run()
    app.session_state['research_compute_status'] = {'scope': ('old-endpoint', 'old-model', 'old-search'), 'report': {}}
    app.run()
    assert not app.exception and 'research_compute_status' not in app.session_state


def test_loaded_model_status_shows_gpu_memory_and_refresh_discards_snapshot(dashboard):
    from app.ai_dashboard import _compute_table
    report = dict(runtime_version='0.40.11', checked_at='2026-11-02T07:00:00+00:00', errors=[], selected={
        'chat': dict(name='qwen3:8b', installed=True, loaded=True,
                     residency=dict(placement='gpu', context_tokens=8192, gpu_memory_percent=100.0)),
        'embedding': dict(name='qwen3-embedding:0.6b', installed=True, loaded=False, residency=None)})
    with patch('app.ai_dashboard.inspect_ollama', return_value=report), \
            patch('app.ai_dashboard._compute_table', wraps=_compute_table) as table:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.button(key='research_check_compute').click().run()
        assert not app.exception
        rows = table.call_args.args[0]
        assert rows[0]['Loaded on'] == 'GPU' and rows[0]['Model memory on GPU'] == '100%'
        assert rows[0]['Context tokens'] == '8,192'
        assert rows[1]['Loaded on'] == 'Not loaded' and rows[1]['Context tokens'] == '—'
        next(b for b in app.button if b.label == 'Refresh models').click().run()
        assert not app.exception and 'research_compute_status' not in app.session_state


def test_compute_table_escapes_model_markup_and_keeps_accessible_headings():
    from app.ai_dashboard import _compute_table
    row = dict(zip(('Role', 'Model', 'Installed', 'Loaded on', 'Context tokens', 'Model memory on GPU'),
                   ('Answer', '<img src="https://example.org/no">', 'Yes', 'GPU', '8,192', '100%')))
    rendered = _compute_table([row])
    assert '<img' not in rendered and '&lt;img' in rendered
    assert '<th scope="col">Model</th>' in rendered and 'tabindex="0"' in rendered


def test_research_answer_has_both_exports_without_another_model_call(dashboard):
    answer = dict(question='What is saved?', model='qwen3:8b', supported=True,
        claims=[dict(text='Saved evidence.', sources=['offline:P1'])],
        passages=[dict(id='offline:P1', article_id='offline', title='Offline research',
                       text='Saved evidence.', url='https://example.org/research')])
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.answer_question', return_value=answer) as generate:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('What is saved?')
        app.button(key='FormSubmitter:article_question-Research').click().run()
        assert not app.exception and generate.call_count == 1
        keys = {item.key for item in app.download_button}
        assert {'research_export_markdown', 'research_export_json'} <= keys
        app.run()
        assert not app.exception and generate.call_count == 1


@pytest.mark.parametrize('identity_state', ['stable', 'changed', 'unavailable'])
def test_new_research_observes_selected_models_and_reuse_save_reopen_make_no_observations(dashboard, identity_state):
    from tests.test_model_health import manifest, reply
    from app import research_sessions
    from app.research_export import research_exports
    import json
    before = [manifest('qwen3:8b'), manifest('qwen3-embedding:0.6b')]
    after = [manifest('qwen3:8b', digest='b' * 64 if identity_state == 'changed' else 'a' * 64),
             manifest('qwen3-embedding:0.6b')]
    metadata = [reply({'models': before}), reply({'models': after}) if identity_state != 'unavailable' else requests.Timeout()]
    answer = dict(question='What is saved?', model='qwen3:8b', supported=True,
        claims=[dict(text='Saved evidence.', sources=['offline:P1'])],
        passages=[dict(id='offline:P1', article_id='offline', title='Offline research',
                       text='Saved evidence.', url='https://example.org/research')])
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.answer_question', return_value=answer) as generate, \
            patch('app.model_health.requests.get', side_effect=metadata) as get:
        app = dashboard
        app.button(key='nav_research').click().run()
        get.assert_not_called()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        get.assert_not_called()
        app.text_area[0].set_value('What is saved?')
        app.button(key='FormSubmitter:article_question-Research').click().run()
        assert not app.exception and generate.call_count == 1 and get.call_count == 2
        result = app.session_state['ai_research']['result']
        observed = result['model_observation']
        assert observed['state'] == identity_state and 'model_observation' not in answer
        assert set(observed['before']['models']) == {'qwen3:8b', 'qwen3-embedding:0.6b'}
        if identity_state == 'changed':
            assert any('versions changed during this run' in warning.value for warning in app.warning)
        elif identity_state == 'unavailable':
            assert any('observations were incomplete' in caption.value for caption in app.caption)
        app.button(key='FormSubmitter:article_question-Research').click().run()
        assert not app.exception and get.call_count == 2 and generate.call_count == 1
        app.button(key='research_save_result').click().run()
        app.button(key='research_view_saved').click().run()
        assert not app.exception and get.call_count == 2 and generate.call_count == 1
    ident = research_sessions.sessions_page()['items'][0]['id']
    loaded = research_sessions.load_session(ident)['result']
    assert loaded['model_observation'] == observed
    exported = json.loads(research_exports(loaded)[1])
    assert exported['model_observation'] == observed


def test_fresh_result_reobserves_models_without_rewriting_the_previous_metadata(dashboard):
    import copy
    from tests.test_model_health import manifest, reply
    answer = dict(question='What is saved?', model='qwen3:8b', supported=False, claims=[],
        passages=[dict(id='offline:P1', article_id='offline', title='Offline research',
                       text='Saved evidence.', url='https://example.org/research')])
    inventories = [reply({'models': [manifest('qwen3:8b', digest=digest * 64),
                                     manifest('qwen3-embedding:0.6b')]}) for digest in ('a', 'a', 'b', 'b')]
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.answer_question', return_value=answer) as generate, \
            patch('app.model_health.requests.get', side_effect=inventories) as get:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('What is saved?')
        app.button(key='FormSubmitter:article_question-Research').click().run()
        previous = app.session_state['ai_research']['result']
        original = copy.deepcopy(previous)
        next(box for box in app.checkbox if box.label == 'Generate a fresh result').check()
        app.button(key='FormSubmitter:article_question-Research').click().run()
        assert not app.exception and get.call_count == 4 and generate.call_count == 2
        current = app.session_state['ai_research']['result']
        assert previous == original and current['model_observation']['state'] == 'stable'
        assert current['model_observation']['before']['models']['qwen3:8b']['digest'] == 'b' * 64
        assert previous['model_observation']['before']['models']['qwen3:8b']['digest'] == 'a' * 64


def test_passage_search_observes_only_the_embedding_model(dashboard):
    from tests.test_model_health import manifest, reply
    passage = dict(id='offline:P1', article_id='offline', title='Offline research',
                   text='Saved evidence.', url='https://example.org/research')
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.semantic_search', return_value=[passage]) as search, \
            patch('app.ai_dashboard.answer_question') as generate, \
            patch('app.model_health.requests.get', side_effect=[reply({'models': [manifest('qwen3-embedding:0.6b')]}),
                                                               reply({'models': [manifest('qwen3-embedding:0.6b')]})]) as get:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('Find evidence')
        next(radio for radio in app.radio if radio.label == 'Research mode').set_value('Search passages')
        app.button(key='FormSubmitter:article_question-Research').click().run()
        assert not app.exception and get.call_count == 2 and search.call_count == 1
        generate.assert_not_called()
        result = app.session_state['ai_research']['result']
        assert 'supported' not in result
        assert set(result['model_observation']['before']['models']) == {'qwen3-embedding:0.6b'}


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')
    storage.upsert(dict(
        id='offline', url='https://example.org/research', title='Offline research',
        source='Example', author='Writer', published='2026-10-27',
        fetched_at='2026-10-27T00:00:00Z', text='Saved research evidence. ' * 10,
        word_count=30, links_json='[]', images_json='[]', pdf_path='',
    ))
    storage.save_insight(storage.all_articles()[0], 'qwen3:8b', '1', {
        'summary': {'text': 'A saved research summary.', 'sources': ['offline:P1']},
        'key_points': [{'text': 'The evidence remains inspectable.', 'sources': ['offline:P1']}],
        'topics': ['Research'], 'partial': False, 'passages_analyzed': 1,
        'total_passages': 1, 'model': 'qwen3:8b',
    })
    from app.ai_dashboard import _model_status
    _model_status.clear()
    with patch('app.ai_dashboard.OllamaClient.models',
               side_effect=IntelligenceError('Ollama is offline for this test.')), \
            patch('app.model_health.requests.get', side_effect=requests.ConnectionError()):
        # Every functional navigation step gets the startup budget, including
        # cold component imports on fresh or busy hosts. Latency is not asserted here.
        yield AppTest.from_file(Path(__file__).resolve().parents[1] / 'app' / 'dashboard.py', default_timeout=20).run()


def test_library_and_research_remain_usable_when_ollama_is_offline(dashboard):
    app = dashboard
    assert not app.exception
    assert app.button(key='read_offline')
    # Model discovery is deferred until the user opens Research.
    assert not app.warning
    app.button(key='nav_research').click().run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ['Article summaries', 'Ask a question']
    assert any('Ollama is offline' in warning.value for warning in app.warning)
    assert app.download_button[0].label == 'Export analysis'


def test_library_search_and_reading_room(dashboard):
    app = dashboard
    app.text_input(key='library_search').set_value('not in this library').run()
    assert not any(button.key == 'read_offline' for button in app.button)
    assert not app.exception
    app.text_input(key='library_search').set_value('Offline research').run()
    app.button(key='read_offline').click().run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ['Article', 'Analysis', 'Notes & highlights', 'Source details']


def test_analytics_import_and_invalid_batch(dashboard):
    app = dashboard
    app.button(key='nav_analytics').click().run()
    assert not app.exception
    assert app.session_state['workspace_view'] == 'Analytics'
    app.button(key='nav_import_articles').click().run()
    assert not app.exception
    app.button(key='FormSubmitter:import_articles-Import articles').click().run()
    assert not app.exception
    assert any('Add at least one' in warning.value for warning in app.warning)


def test_reading_copy_preserves_currency_and_blocks_external_images():
    from app.library_view import _reading_html

    rendered = _reading_html('A $2tn market.\nThe budget is $5bn.\n\n![Reference](https://example.org/image.png)\n\n<script>unsafe()</script>')
    assert '$2tn' in rendered and '$5bn' in rendered
    assert '<br><br>' in rendered
    assert '<img' not in rendered
    assert '<script>' not in rendered
    assert '&lt;script&gt;' in rendered


def test_dark_mode_survives_navigation_and_can_be_switched_back(dashboard):
    app = dashboard
    app.toggle(key='dark_mode').set_value(True).run()
    assert not app.exception
    assert 'dark' in app.query_params['theme']
    app.button(key='nav_analytics').click().run()
    assert not app.exception
    assert app.toggle(key='dark_mode').value is True
    app.toggle(key='dark_mode').set_value(False).run()
    assert not app.exception
    assert 'light' in app.query_params['theme']


def test_dark_theme_link_restores_appearance_on_a_new_session(dashboard):
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app' / 'dashboard.py')
    app.query_params['theme'] = 'dark'
    app.run(timeout=20)
    assert not app.exception
    assert app.toggle(key='dark_mode').value is True
    app.button(key='read_offline').click().run()
    assert not app.exception


def test_library_paginates_and_resets_page_when_search_changes(dashboard):
    original = storage.all_articles()[0]
    storage.upsert_many(dict(original, id=f'large{index:04}', url=f'https://example.org/{index}',
                            title=f'Research article {index:04}') for index in range(60))
    with patch('app.storage.all_articles', side_effect=AssertionError('Unbounded UI read')):
        app = dashboard.run()
        assert not app.exception
        assert len([button for button in app.button if button.key and button.key.startswith('read_')]) == 25
        first_ids = {button.key for button in app.button if button.key and button.key.startswith('read_')}
        app.button(key='library_next').click().run()
        assert not app.exception
        next_ids = {button.key for button in app.button if button.key and button.key.startswith('read_')}
        assert len(next_ids) == 25 and not first_ids.intersection(next_ids)
        app.text_input(key='library_search').set_value('0001').run()
        assert not app.exception
        assert app.session_state['library_page'] == 1
        assert len([button for button in app.button if button.key and button.key.startswith('read_')]) == 1


def test_library_returns_from_analytics_without_losing_its_page(dashboard):
    original = storage.all_articles()[0]
    storage.upsert_many(dict(original, id=f'return{index:04}', url=f'https://example.org/return/{index}')
                        for index in range(60))
    app = dashboard.run()
    app.button(key='library_next').click().run()
    expected = {button.key for button in app.button if button.key and button.key.startswith('read_')}
    app.button(key='nav_analytics').click().run()
    app.button(key='nav_library').click().run()
    assert not app.exception
    assert app.session_state['library_page'] == 2
    assert {button.key for button in app.button if button.key and button.key.startswith('read_')} == expected
    app.number_input(key='library_page_input').set_value(3).run()
    app.button(key='nav_research').click().run()
    app.button(key='nav_library').click().run()
    assert not app.exception
    assert app.session_state['library_page'] == 3
    del app.session_state['library_page']
    app.run()
    assert not app.exception
    assert app.session_state['library_page'] == 1


def test_library_filter_values_survive_navigation_and_clear_together(dashboard):
    original = storage.all_articles()[0]
    storage.create_collection('bubble', 'Bubble collection', 'AI bubble')
    for index in range(30):
        storage.upsert(dict(original, id=f'filtered{index:03}', url=f'https://example.org/filtered/{index}',
                            title=f'Bubble article {index:03}', text='OpenAI capex and debt.', word_count=600),
                       collection_id='bubble')
    app = dashboard.run()
    app.text_input(key='library_search').set_value('Bubble').run()
    app.selectbox(key='library_collection').select('bubble').run()
    app.multiselect(key='library_publishers').select('Example').run()
    app.selectbox(key='library_status').select('Needs analysis').run()
    app.selectbox(key='library_length').select('Up to 5 min').run()
    app.selectbox(key='library_published').select('Custom dates').run()
    app.date_input(key='library_date_from').set_value(date(2026, 10, 1)).run()
    app.date_input(key='library_date_until').set_value(date(2026, 10, 27)).run()
    app.selectbox(key='library_page_size').select(50).run()
    app.selectbox(key='library_sort').select('Newest published').run()
    app.checkbox(key='library_ai_coverage').check().run()
    app.selectbox(key='library_lens').select('credit').run()
    app.selectbox(key='library_entity').select('OpenAI').run()
    assert not app.exception
    before = app.session_state['library_controls'].copy()
    app.button(key='nav_analytics').click().run()
    app.button(key='nav_library').click().run()
    assert not app.exception
    assert app.session_state['library_controls'] == before
    assert app.date_input(key='library_date_from').value == date(2026, 10, 1)
    assert len([button for button in app.button if button.key and button.key.startswith('read_')]) == 30
    app.button(key='clear_library_filters').click().run()
    assert not app.exception
    assert app.text_input(key='library_search').value == ''
    assert app.multiselect(key='library_publishers').value == []
    assert app.selectbox(key='library_collection').value == ''
    assert app.session_state['library_lens'] == ''
    assert not app.checkbox(key='library_ai_coverage').value
    assert app.selectbox(key='library_page_size').value == 50
    assert app.selectbox(key='library_sort').value == 'Newest published'


def test_library_rejects_reversed_custom_dates_without_crashing(dashboard):
    app = dashboard
    app.selectbox(key='library_published').select('Custom dates').run()
    app.date_input(key='library_date_from').set_value(date(2026, 10, 28)).run()
    app.date_input(key='library_date_until').set_value(date(2026, 10, 1)).run()
    assert not app.exception
    assert any('on or before' in warning.value for warning in app.warning)


def test_research_only_loads_one_saved_article_on_initial_render(dashboard):
    original = storage.all_articles()[0]
    storage.upsert_many(dict(original, id=f'research{index:04}', url=f'https://example.org/r/{index}') for index in range(101))
    with patch('app.ai_dashboard.get_article', wraps=storage.get_article) as load_one, \
            patch('app.storage.all_articles', side_effect=AssertionError('Unbounded UI read')):
        app = dashboard
        app.button(key='nav_research').click().run()
        assert not app.exception
        assert load_one.call_count == 1
        assert len(next(widget for widget in app.multiselect if widget.key == 'research_selected_ids').options) == 25


def test_reader_handoff_focuses_unanalyzed_article_and_preserves_filters(dashboard):
    original = storage.get_article('offline')
    storage.upsert(dict(original, id='new', title='New saved article', url='https://example.org/new'))
    app = dashboard
    app.button(key='nav_research').click().run()
    app.text_input(key='research_search').set_value('unrelated topic').run()
    app.button(key='nav_library').click().run()
    app.text_input(key='library_search').set_value('New saved article').run()
    app.button(key='read_new').click().run()
    app.button(key='research_article_new').click().run()
    assert not app.exception and app.session_state['workspace_view'] == 'Research'
    assert app.session_state['research_focus_article'] == 'new'
    assert app.button(key='focused_analyze_new').disabled  # Offline must remain actionable, not crash.
    assert not any(button.label == 'Analyze this page' for button in app.button)
    assert app.session_state['research_search'] == 'unrelated topic'
    next(button for button in app.button if button.label == 'Return to Library').click().run()
    assert not app.exception and app.text_input(key='library_search').value == 'New saved article'
    assert 'research_focus_article' not in app.session_state


def test_research_handoff_handles_deleted_article_without_analyzing_another(dashboard):
    app = dashboard
    app.session_state['research_focus_article'] = 'deleted'
    app.button(key='nav_research').click().run()
    assert not app.exception and any('no longer in the library' in item.value for item in app.warning)
    assert not any(button.label == 'Analyze this page' for button in app.button)
    next(button for button in app.button if button.label == 'Back to research library').click().run()
    assert not app.exception and app.multiselect(key='research_selected_ids')


def test_identical_research_reuses_last_answer_but_fresh_mode_and_changes_do_not(dashboard):
    from app.ai_dashboard import _model_status
    client_answer = dict(question='What is saved?', supported=True,
                         claims=[dict(text='Saved evidence.', sources=['offline:P1'])],
                         generation=dict(context_window=8192, prompt_tokens=350, attempts=[{}]),
                         passages=[dict(id='offline:P1', article_id='offline', title='Offline research',
                                        text='Saved evidence.', url='https://example.org/research')])
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.answer_question', return_value=client_answer.copy()) as answer:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('What is saved?')
        submit = 'FormSubmitter:article_question-Research'
        app.button(key=submit).click().run()
        assert not app.exception and answer.call_count == 1
        assert any('8K context' in item.value and '350 input tokens' in item.value for item in app.caption)
        app.button(key=submit).click().run()
        assert not app.exception and answer.call_count == 1
        assert any('Reused the previous result' in item.value for item in app.caption)
        next(box for box in app.checkbox if box.label == 'Generate a fresh result').check()
        app.button(key=submit).click().run()
        assert not app.exception and answer.call_count == 2
        next(box for box in app.checkbox if box.label == 'Generate a fresh result').uncheck()
        app.text_area[0].set_value('A changed question?')
        app.button(key=submit).click().run()
        assert not app.exception and answer.call_count == 3
        original = storage.get_article('offline')
        storage.upsert(dict(original, text=original['text'] + ' Changed source evidence.'))
        app.button(key=submit).click().run()
        assert not app.exception and answer.call_count == 4
    _model_status.clear()


def _completed_research_fixture():
    return dict(question='First question', model='qwen3:8b', supported=True,
        claims=[dict(text='Saved source evidence.', sources=['offline:P1'])],
        passages=[dict(id='offline:P1', article_id='offline', title='Offline research',
                       text='Saved source evidence.', url='https://example.org/research')])


def test_failed_new_research_preserves_completed_answer_and_can_be_cleared(dashboard):
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.answer_question', side_effect=[_completed_research_fixture(), IntelligenceError('Request timed out.')]) as generate:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('First question')
        submit = 'FormSubmitter:article_question-Research'
        app.button(key=submit).click().run()
        original = app.session_state['ai_research']['result']
        app.text_area[0].set_value('Second question')
        app.button(key=submit).click().run()
        assert not app.exception and generate.call_count == 2
        assert app.session_state['ai_research']['result'] == original
        assert any('Request timed out' in item.value for item in app.error)
        assert any('last completed result' in item.value for item in app.info)
        assert app.download_button(key='research_export_markdown')
        app.button(key='research_clear_result').click().run()
        assert not app.exception and 'ai_research' not in app.session_state and 'ai_research_error' not in app.session_state
        assert storage.library_overview()['total'] == 1


def test_offline_models_and_empty_filters_keep_last_result_exportable(dashboard):
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)) as models, \
            patch('app.ai_dashboard.answer_question', return_value=_completed_research_fixture()) as generate:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('First question')
        app.button(key='FormSubmitter:article_question-Research').click().run()
        original = app.session_state['ai_research']['result']
        models.return_value = ([], 'Ollama is unavailable.')
        app.run()
        assert not app.exception and generate.call_count == 1
        assert app.download_button(key='research_export_json')
        assert app.session_state['ai_research']['result'] == original
        assert any('last completed result' in item.value for item in app.info)
        app.text_input(key='research_search').set_value('No saved source can match this string').run()
        assert not app.exception and generate.call_count == 1
        assert app.download_button(key='research_export_json')
        app.button(key='research_clear_result').click().run()
        assert 'ai_research' not in app.session_state


def test_completed_research_captures_loaded_source_fingerprints_and_survives_revisions(dashboard):
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.answer_question', return_value=_completed_research_fixture()) as generate:
        original = storage.get_article('offline')
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('First question')
        app.button(key='FormSubmitter:article_question-Research').click().run()
        result = app.session_state['ai_research']['result']
        assert result['source_scope']['selected_article_ids'] == ['offline']
        assert result['source_scope']['searched_article_ids'] == ['offline']
        assert result['source_scope']['source_fingerprints']['offline'] == storage.article_fingerprint(original)
        assert result['source_scope']['embedding_model'] == 'qwen3-embedding:0.6b'
        assert result['completed_at'].endswith('+00:00')
        storage.upsert(dict(original, text='The saved source has been revised since the answer.'))
        app.run()
        assert not app.exception and generate.call_count == 1
        assert app.session_state['ai_research']['result'] == result
        assert any('last completed result' in item.value for item in app.info)


def test_passage_search_records_the_embedding_model_and_source_scope(dashboard):
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.semantic_search', return_value=_completed_research_fixture()['passages']) as search:
        app = dashboard
        app.button(key='nav_research').click().run()
        app.multiselect(key='research_selected_ids').set_value(['offline']).run()
        app.text_area[0].set_value('Find original saved evidence')
        app.radio[0].set_value('Search passages')
        app.button(key='FormSubmitter:article_question-Research').click().run()
        assert not app.exception and search.call_count == 1
        result = app.session_state['ai_research']['result']
        assert result['model'] == 'qwen3-embedding:0.6b'
        assert result['source_scope']['context_policy'] is None and 'supported' not in result


def test_research_collection_excludes_unrelated_articles_and_allows_scoped_questions(dashboard):
    original = storage.all_articles()[0]
    storage.create_collection('ai-bubble', 'AI bubble', 'AI investment debate')
    for index in range(30):
        storage.upsert(dict(original, id=f'bubble{index:03}', url=f'https://example.org/bubble/{index}',
                            title=f'Bubble article {index:03}'), collection_id='ai-bubble')
    app = dashboard
    app.button(key='nav_research').click().run()
    app.selectbox(key='research_collection').select('ai-bubble').run()
    assert not app.exception
    options = next(widget for widget in app.multiselect if widget.key == 'research_selected_ids').options
    assert len(options) == 25 and all(title.startswith('Bubble article') for title in options)
    assert not app.checkbox(key='research_all_matches').disabled
    app.checkbox(key='research_all_matches').check().run()
    assert any('search 30 articles' in caption.value for caption in app.caption)


def _add_filter_context_articles():
    from tests.test_scoped_filters import insight
    original = storage.all_articles()[0]
    for identifier, title, topics in [('layoffs', 'Layoffs in retail', ['Layoffs', 'Retail employment']),
                                       ('glass', 'Ancient Roman glass', ['Ancient Roman Glass'])]:
        item = dict(original, id=identifier, url='https://example.org/' + identifier,
                    title=title, text=title + '. Synthetic source evidence. ' * 20)
        storage.upsert(item)
        insight(item, topics)


def test_research_topics_follow_search_and_clear_incompatible_selections(dashboard):
    _add_filter_context_articles()
    app = dashboard
    app.button(key='nav_research').click().run()
    app.text_input(key='research_search').set_value('layoff').run()
    assert not app.exception
    assert set(app.multiselect(key='research_topics').options) == {'Layoffs', 'Retail employment'}
    app.multiselect(key='research_topics').select('Layoffs').run()
    app.button(key='nav_analytics').click().run()
    app.button(key='nav_research').click().run()
    assert app.text_input(key='research_search').value == 'layoff'
    assert app.multiselect(key='research_topics').value == ['Layoffs']
    app.text_input(key='research_search').set_value('glass').run()
    assert not app.exception
    assert app.multiselect(key='research_topics').value == []
    assert app.multiselect(key='research_topics').options == ['Ancient Roman Glass']
    assert any('search 0 articles' in caption.value for caption in app.caption)
    app.multiselect(key='research_selected_ids').set_value(['glass']).run()
    assert any('search 1 article' in caption.value for caption in app.caption)
    app.text_input(key='research_search').set_value('missing-source').run()
    assert not app.exception
    assert app.multiselect(key='research_topics').options == []
    assert app.multiselect(key='research_topics').disabled


def test_library_topics_are_scoped_and_ai_filters_require_opt_in(dashboard):
    _add_filter_context_articles()
    app = dashboard.run()
    app.multiselect(key='library_topics').select('Ancient Roman Glass').run()
    app.text_input(key='library_search').set_value('layoff').run()
    assert not app.exception
    assert app.multiselect(key='library_topics').value == []
    assert set(app.multiselect(key='library_topics').options) == {'Layoffs', 'Retail employment'}
    assert not app.session_state['library_ai_coverage']
    assert not any(widget.key == 'library_ai_coverage' for widget in app.checkbox)
    assert not any(widget.key in ('library_lens', 'library_entity') for widget in app.selectbox)
    assert len([button for button in app.button if button.key and button.key.startswith('read_')]) == 1


def test_research_requires_explicit_sources_and_only_sends_the_selected_article(dashboard):
    original = storage.get_article('offline')
    storage.upsert(dict(original, id='sap', url='https://example.org/sap', title='SAP cloud collaboration',
                        text='SAP reports a cloud collaboration.'))
    storage.upsert(dict(original, id='spacex', url='https://example.org/spacex', title='SpaceX satellite launch',
                        text='SpaceX reports a satellite launch.'))
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b', 'qwen3-embedding:0.6b'], None)), \
            patch('app.ai_dashboard.answer_question', return_value=_completed_research_fixture()) as generate:
        app = dashboard
        app.button(key='nav_research').click().run()
        submit = 'FormSubmitter:article_question-Research'
        assert not app.exception and app.button(key=submit).disabled
        assert app.multiselect(key='research_selected_ids').value == []
        assert app.expander[-1].label == 'Research settings'
        assert [tab.label for tab in app.tabs] == ['Article summaries', 'Ask a question']
        generate.assert_not_called()
        app.multiselect(key='research_selected_ids').set_value(['sap']).run()
        assert not app.button(key=submit).disabled
        summary_article = next(widget for widget in app.selectbox if widget.label == 'Article')
        assert summary_article.options == ['SAP cloud collaboration']
        app.text_area[0].set_value('What did SAP announce?')
        app.button(key=submit).click().run()
        assert not app.exception and generate.call_count == 1
        assert [article['id'] for article in generate.call_args.args[1]] == ['sap']
        assert app.session_state['ai_research']['result']['source_scope']['selected_article_ids'] == ['sap']
        app.multiselect(key='research_selected_ids').set_value([]).run()
        assert app.button(key=submit).disabled and generate.call_count == 1
        assert app.download_button(key='research_export_json')  # Original result remains inspectable.


def test_research_source_context_change_revokes_include_all_and_selected_sources(dashboard):
    _add_filter_context_articles()
    app = dashboard
    app.button(key='nav_research').click().run()
    app.checkbox(key='research_all_matches').check().run()
    assert app.multiselect(key='research_selected_ids').disabled
    assert any('search 3 articles' in item.value for item in app.caption)
    app.text_input(key='research_search').set_value('layoff').run()
    assert not app.exception
    assert not app.checkbox(key='research_all_matches').value
    assert not app.multiselect(key='research_selected_ids').disabled
    assert app.multiselect(key='research_selected_ids').value == []
    app.multiselect(key='research_selected_ids').set_value(['layoffs']).run()
    app.text_input(key='research_search').set_value('glass').run()
    assert not app.exception and app.multiselect(key='research_selected_ids').value == []
    assert any('search 0 articles' in item.value for item in app.caption)


def test_article_summary_needs_only_chat_and_batch_uses_only_selected_sources(dashboard):
    original = storage.get_article('offline')
    storage.upsert(dict(original, id='sap', url='https://example.org/sap', title='SAP cloud collaboration'))
    with patch('app.ai_dashboard._model_status', return_value=(['qwen3:8b'], None)), \
            patch('app.ai_dashboard.analyze_article') as summarize, \
            patch('app.ai_dashboard.semantic_search', side_effect=AssertionError('Summaries need no embeddings')):
        app = dashboard
        app.button(key='nav_research').click().run()
        assert app.button(key='research_summarize_selected').disabled
        app.multiselect(key='research_selected_ids').set_value(['sap']).run()
        assert app.button(key='FormSubmitter:article_question-Research').disabled
        assert not app.button(key='research_summarize_selected').disabled
        app.button(key='research_summarize_selected').click().run()
        assert not app.exception and summarize.call_count == 1
        assert summarize.call_args.args[0]['id'] == 'sap'


def test_research_unanalyzed_scope_has_no_unrelated_topic_fallback(dashboard):
    original = storage.all_articles()[0]
    storage.upsert(dict(original, id='layoffs', url='https://example.org/layoffs', title='Layoffs in retail'))
    app = dashboard
    app.button(key='nav_research').click().run()
    app.text_input(key='research_search').set_value('layoff').run()
    assert not app.exception
    assert app.multiselect(key='research_topics').options == []
    assert app.multiselect(key='research_topics').disabled
    assert any('No saved analysis topics in this selection' in caption.value for caption in app.caption)
    assert len(app.multiselect(key='research_selected_ids').options) == 1


def test_library_scoped_selection_is_not_limited_by_global_top_topics(dashboard):
    from tests.test_scoped_filters import insight
    original = storage.all_articles()[0]
    for index in range(105):
        item = dict(original, id=f'other{index}', url=f'https://example.org/other/{index}', title='Unrelated science report')
        storage.upsert(item)
        insight(item, [f'Other topic {index:03}'])
    rare = dict(original, id='rare-layoff', url='https://example.org/rare-layoff', title='Layoffs in retail')
    storage.upsert(rare)
    insight(rare, ['Z rare workforce topic'])
    assert 'Z rare workforce topic' not in storage.library_overview()['topics']
    app = dashboard.run()
    app.text_input(key='library_search').set_value('layoff').run()
    assert app.multiselect(key='library_topics').options == ['Z rare workforce topic']
    app.multiselect(key='library_topics').select('Z rare workforce topic').run()
    assert not app.exception
    assert app.multiselect(key='library_topics').value == ['Z rare workforce topic']


def test_discovery_previews_require_explicit_import_and_selection_survives_navigation(dashboard):
    from tests.test_discovery import candidate
    def result(spec, **kwargs):
        return dict(items=[candidate(index) for index in range(spec.target)], requested=spec.target,
                    provider='Synthetic offline feed', query='AI bubble', searched_at='2026-10-28T00:00:00Z',
                    pages_checked=1, candidates_checked=spec.target, warnings=[], date_note='Reported dates.',
                    language_note='Requested language.')
    with patch('app.discovery_view._search', side_effect=result) as search, \
            patch('app.discovery_view.ensure_worker'), patch('app.discovery_imports.ensure_worker'):
        app = dashboard
        app.button(key='nav_search_articles').click().run()
        assert not app.exception
        app.text_input(key='discover_topics').set_value('AI bubble')
        search.assert_not_called()
        app.button(key='FormSubmitter:discover_articles-Search articles').click().run()
        assert not app.exception
        assert storage.library_overview()['total'] == 1
        keys = [widget.key for widget in app.checkbox if widget.key and widget.key.startswith('discovery_select_')]
        assert len(keys) == 10, [error.value for error in app.error]
        app.checkbox(key=keys[0]).check().run()
        assert len(app.session_state['discovery_selected']) == 1
        app.selectbox(key='discovery_fetch_mode').select('html').run()
        app.button(key='nav_library').click().run()
        app.button(key='nav_search_articles').click().run()
        assert not app.exception
        assert app.checkbox(key=keys[0]).value is True
        assert app.selectbox(key='discovery_fetch_mode').value == 'html'
        next(button for button in app.button if button.label == 'Select all 25').click().run()
        assert len(app.session_state['discovery_selected']) == 25
        next(button for button in app.button if button.label == 'Import selected (25)').click().run()
        assert not app.exception
        assert storage.library_overview()['total'] == 1
        from app.discovery_imports import batches
        assert batches()[0]['total'] == 25 and batches()[0]['state'] == 'queued'
        assert batches()[0]['fetch_mode'] == 'html'


def test_manual_import_uses_capture_choice_and_retains_it_across_views(dashboard):
    app = dashboard
    app.button(key='nav_import_articles').click().run()
    assert app.selectbox(key='import_fetch_mode').value == 'auto'
    app.selectbox(key='import_fetch_mode').select('html')
    app.text_area[0].set_value('https://example.org/research')
    with patch('app.ingest_view.extract_article', return_value=storage.get_article('offline')) as fetch, \
            patch('app.ingest_view.create_pdf', return_value=''):
        app.button(key='FormSubmitter:import_articles-Import articles').click().run()
        assert not app.exception
        fetch.assert_called_once_with('https://example.org/research', mode='html')
    app.button(key='nav_library').click().run()
    app.button(key='nav_import_articles').click().run()
    assert app.selectbox(key='import_fetch_mode').value == 'html'


def test_capture_findings_are_visible_in_import_and_reading_room(dashboard):
    from app.extract import _article_from_html
    from tests.test_browser_extraction import FULL_HTML, URL
    captured = _article_from_html(FULL_HTML, URL)
    app = dashboard
    app.button(key='nav_import_articles').click().run()
    app.text_area[0].set_value(URL)
    with patch('app.ingest_view.extract_article', return_value=captured), patch('app.ingest_view.create_pdf', return_value=''):
        app.button(key='FormSubmitter:import_articles-Import articles').click().run()
    assert not app.exception
    assert any('Saved with capture warnings' in warning.value for warning in app.warning)
    app.button(key='nav_library').click().run()
    app.button(key='read_' + captured['id']).click().run()
    assert not app.exception
    assert any('Publication date is unavailable' in warning.value for warning in app.warning)
    assert any('not verify completeness' in caption.value for caption in app.caption)


def test_manual_import_explains_access_failures_without_saving(dashboard):
    from app.extract import ExtractionError
    app = dashboard
    app.button(key='nav_import_articles').click().run()
    app.text_area[0].set_value('https://example.org/blocked')
    with patch('app.ingest_view.extract_article', side_effect=ExtractionError('Publisher response', code='rate_limited')):
        app.button(key='FormSubmitter:import_articles-Import articles').click().run()
    assert not app.exception
    assert any('Wait before trying again' in caption.value for caption in app.caption)
    assert storage.library_overview()['total'] == 1


def test_reader_saves_notes_tags_and_projects_and_filters_them_after_navigation(dashboard):
    from app.library_actions import annotation_state
    app = dashboard
    app.button(key='read_offline').click().run()
    app.text_area(key='reader_note_offline').set_value('Follow up this evidence.')
    app.text_input(key='reader_tags_offline').set_value('Follow up, Research')
    app.text_input(key='reader_new_collection_offline').set_value('My project')
    next(button for button in app.button if button.label == 'Save notes & organization').click().run()
    assert not app.exception
    state = annotation_state('offline')
    assert state['note'] == 'Follow up this evidence.' and state['tags'] == ['Follow up','Research']
    assert len(state['collections']) == 1
    app.button(key='nav_analytics').click().run()
    app.button(key='nav_library').click().run()
    app.multiselect(key='library_tags').select('follow up').run()
    assert not app.exception and app.button(key='read_offline')
    app.button(key='read_offline').click().run()
    assert app.text_area(key='reader_note_offline').value == 'Follow up this evidence.'


def test_reader_highlight_and_delete_require_concrete_user_actions(dashboard):
    from app.library_actions import annotation_state
    def reader_page():
        from app import storage
        from app.library_view import reading_room, render_library
        article = storage.get_article('offline')
        if article:
            reading_room(article, storage.load_insight(article, 'qwen3:8b', '1'))
        else:
            render_library(storage.library_overview())
    app = AppTest.from_function(reader_page).run()
    app.text_area(key='reader_quote_offline').set_value('Saved research evidence.')
    app.text_area(key='reader_quote_note_offline').set_value('A retained source passage')
    next(button for button in app.button if button.label == 'Save highlight').click().run()
    assert not app.exception and len(annotation_state('offline')['highlights']) == 1
    assert app.button(key='delete_article_offline').disabled
    app.checkbox(key='delete_confirm_offline').check().run()
    app.button(key='delete_article_offline').click().run()
    assert not app.exception and storage.get_article('offline') is None
    assert any(button.label == 'Restore a library backup' for button in app.button)


def test_full_backup_is_prepared_only_when_requested(dashboard):
    def backup_page():
        from app.backup_view import backup_dialog
        backup_dialog()
    app = AppTest.from_function(backup_page).run()
    assert 'portable_backup' not in app.session_state
    next(button for button in app.button if button.label == 'Prepare full backup').click().run()
    assert not app.exception
    assert app.session_state['portable_backup']['stats']['articles'] == 1
    assert any(button.label == 'Download full library backup' for button in app.download_button)


def test_discovery_validates_empty_query_and_preserves_previous_results_on_provider_error(dashboard):
    from app.discovery import DiscoveryError
    with patch('app.discovery_view._search', side_effect=DiscoveryError('The free source is unavailable.')) as search:
        app = dashboard
        app.button(key='nav_search_articles').click().run()
        app.button(key='FormSubmitter:discover_articles-Search articles').click().run()
        assert not app.exception
        search.assert_not_called()
        assert any('Enter one to five' in error.value for error in app.error)
        app.text_input(key='discover_topics').set_value('AI bubble')
        app.button(key='FormSubmitter:discover_articles-Search articles').click().run()
        assert not app.exception
        assert any('unavailable' in error.value for error in app.error), [error.value for error in app.error]


def test_completed_discovery_batch_opens_its_exact_collection(dashboard):
    from app.discovery_imports import batches, create_batch, process_next
    job_id = create_batch(['https://example.org/research'], 'Saved source collection', 'Research')
    process_next(fetch=lambda _: pytest.fail('Existing article must not be fetched again'))
    collection_id = batches()[0]['collection_id']
    app = dashboard
    app.button(key='nav_search_articles').click().run()
    app.button(key='open_import_' + job_id).click().run()
    assert not app.exception
    assert app.session_state['workspace_view'] == 'Library'
    assert app.selectbox(key='library_collection').value == collection_id
    assert app.button(key='read_offline')


def test_saved_research_reopens_in_a_new_offline_app_without_model_calls_and_can_be_deleted(dashboard):
    from app import research_sessions
    app = dashboard
    app.button(key='nav_research').click().run()
    answer = _completed_research_fixture()
    app.session_state['ai_research'] = dict(scope=None, result=answer, action='Answer with citations')
    app.run()
    app.button(key='research_save_result').click().run()
    assert not app.exception and research_sessions.sessions_page()['total'] == 1
    ident = research_sessions.sessions_page()['items'][0]['id']
    app.button(key='research_clear_result').click().run()
    assert research_sessions.sessions_page()['total'] == 1
    fresh = AppTest.from_file(Path(__file__).resolve().parents[1]/'app/dashboard.py', default_timeout=20)
    fresh.session_state['workspace_view'] = 'Research'
    fresh.session_state['research_workspace_view'] = 'saved'
    with patch('app.ai_dashboard._model_status', side_effect=AssertionError('Saved research must stay offline')) as model_status:
        fresh.run()
        assert not fresh.exception
        model_status.assert_not_called()
        assert fresh.download_button(key='saved_' + ident + '_export_json')
        assert research_sessions.load_session(ident)['result'] == answer
        fresh.checkbox(key='research_delete_confirm_' + ident).check().run()
        fresh.button(key='research_delete_saved').click().run()
        assert not fresh.exception and research_sessions.sessions_page()['total'] == 0
    assert storage.library_overview()['total'] == 1


def test_prepared_library_backup_is_invalidated_when_research_is_saved(dashboard):
    from app import research_sessions
    def backup_page():
        from app.backup_view import backup_dialog
        backup_dialog()
    app = AppTest.from_function(backup_page, default_timeout=20).run()
    next(button for button in app.button if button.label == 'Prepare full backup').click().run()
    assert app.session_state['portable_backup']['stats']['research_sessions'] == 0
    before = storage.library_overview()['revision']
    research_sessions.save_result(_completed_research_fixture())
    assert storage.library_overview()['revision'] == before
    app.run()
    assert not any(button.label == 'Download full library backup' for button in app.download_button)
    next(button for button in app.button if button.label == 'Prepare full backup').click().run()
    assert not app.exception and app.session_state['portable_backup']['stats']['research_sessions'] == 1


def test_article_deletion_explains_and_purges_linked_saved_research_and_active_answer(dashboard):
    from app import research_sessions
    answer = _completed_research_fixture()
    ident = research_sessions.save_result(answer)
    def reader_page():
        from app import storage
        from app.library_view import reading_room
        item = storage.get_article('offline')
        if item:
            reading_room(item, storage.load_insight(item, 'qwen3:8b', '1'))
    app = AppTest.from_function(reader_page, default_timeout=20)
    app.session_state['ai_research'] = dict(scope=None, result=answer, action='Answer with citations')
    app.run()
    assert any('1 saved research result' in message.value for message in app.warning)
    app.checkbox(key='delete_confirm_offline').check().run()
    app.button(key='delete_article_offline').click().run()
    assert not app.exception and research_sessions.load_session(ident) is None
    assert 'ai_research' not in app.session_state
