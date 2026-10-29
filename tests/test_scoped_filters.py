"""Filter choices must come from current matching sources, never unrelated labels."""
import pytest

from app import library_actions, storage
from tests.test_library_storage import article


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')


def insight(item, topics, model='qwen3:8b', version='1'):
    storage.save_insight(item, model, version, {
        'summary': {'text': 'Synthetic research summary.', 'sources': [item['id'] + ':P1']},
        'key_points': [], 'topics': topics, 'model': model,
    })


def test_choices_follow_query_collection_date_and_current_analysis():
    layoffs = article(1, title='Layoffs in retail', text='Layoffs and job cuts in retail.', source='Jobs desk', published='2026-10-20')
    glass = article(2, title='Ancient Roman glass', text='An ancient glass study.', source='Science desk')
    stale = article(3, title='Layoffs in technology', text='Layoffs reported in a technology business.', published='2026-01-01')
    for item in (layoffs, glass, stale):
        storage.upsert(item)
    insight(layoffs, ['Layoffs', 'Retail employment'])
    insight(glass, ['Ancient Roman Glass'])
    insight(stale, ['Outdated topic'])
    storage.upsert(dict(stale, text=stale['text'] + ' An updated saved copy.'))
    storage.create_collection('jobs', 'Layoff research', 'layoffs')
    storage.upsert(layoffs, collection_id='jobs')
    library_actions.save_organization(layoffs['id'], note='', tags=['Follow up'], collection_ids=['jobs'])
    library_actions.save_organization(glass['id'], note='', tags=['History'], collection_ids=[])

    choices = storage.library_filter_options(query='layoff')
    assert choices['total'] == 2 and choices['analyzed'] == 1
    assert set(choices['topics']) == {'Layoffs', 'Retail employment'}
    assert choices['tags'] == {'follow up': 'Follow up'}
    assert storage.library_filter_options(query='layoff', collection_id='jobs')['total'] == 1
    assert storage.library_filter_options(query='layoff', start_date='2026-10-01')['total'] == 1
    assert storage.library_filter_options(query='layoff', status='Needs analysis')['topics'] == []
    assert storage.library_filter_options(query='no-such-source')['topics'] == []


def test_choices_cover_every_matching_page_and_honor_model_version():
    for index in range(35):
        item = article(index, title=f'Layoffs report {index}', text='Layoffs and workforce changes.')
        storage.upsert(item)
        insight(item, ['Regional layoffs' if index == 0 else 'Workforce'])
    choices = storage.library_filter_options(query='layoff')
    assert choices['total'] == 35
    assert len(storage.library_page(query='layoff')['items']) == 25
    assert set(choices['topics']) == {'Regional layoffs', 'Workforce'}
    assert storage.library_filter_options(query='layoff', model='another-model')['topics'] == []
    assert storage.library_filter_options(query='layoff', version='2')['topics'] == []


def test_optional_coverage_choices_include_only_current_matching_signals():
    spending = article(1, title='AI infrastructure', text='OpenAI capex on data centres.')
    layoffs = article(2, title='Layoffs report', text='Layoffs in local restaurants.')
    storage.upsert_many([spending, layoffs])
    assert storage.library_filter_options(query='layoff')['lenses'] == []
    assert storage.library_filter_options(query='layoff')['entities'] == []
    ai = storage.library_filter_options(query='infrastructure')
    assert ai['lenses'] == ['spending'] and ai['entities'] == ['OpenAI']


def test_bounded_choices_retain_valid_rare_selections_without_restoring_unrelated_values():
    for index in range(120):
        item = article(index, title='Layoffs report', text='Layoffs in a fictional business.')
        storage.upsert(item)
        label = 'Z rare topic' if index == 119 else f'Topic {index:03}'
        insight(item, [label])
    assert 'Z rare topic' not in storage.library_filter_options(query='layoff')['topics']
    choices = storage.library_filter_options(query='layoff', retain_topics=['Z rare topic', 'Ancient Roman Glass'])
    assert len(choices['topics']) == 100 and 'Z rare topic' in choices['topics']
    assert 'Ancient Roman Glass' not in choices['topics']
