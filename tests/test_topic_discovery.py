"""Discovery must cluster corpus vectors without touching labels or retrieval policy."""
from copy import deepcopy
from datetime import date
import json
from unittest.mock import Mock

import pytest

from app import storage
from app.intelligence import IntelligenceError
from app.topic_discovery import discover_topics, documents, _trends, MAX_ARTICLES, fingerprint


def articles():
    result = []
    for topic, words in enumerate(('astronomy telescope galaxy stars', 'marine coral ocean reef', 'banking credit lending finance')):
        for index in range(4):
            result.append(dict(id=f't{topic}-{index}', title=words + f' study {index}',
                text=f'{words}. Independent detailed findings number {index} in group {topic}.',
                url=f'https://example.org/t{topic}-{index}', source=f'Publisher {index}',
                published='2026-11-10', author='', fetched_at='2026-11-11T00:00:00Z',
                word_count=15, links_json='[]', images_json='[]', pdf_path=''))
    return result


def inventory(digest='a' * 64):
    return dict(checked_at='2026-11-11T00:00:00+00:00', state='complete', error=None,
                models={'embed': dict(installed=True, digest=digest, details={})})


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'topics.db')
    monkeypatch.setattr('app.topic_discovery.observe_models', lambda *args: inventory())


@pytest.fixture
def client():
    def embed(model, texts, **kwargs):
        result = []
        for text in texts:
            topic = next(i for i, word in enumerate(('astronomy', 'marine', 'banking')) if word in text)
            # Independent small perturbations avoid zero-distance degeneracy.
            index = int(text.split('study ')[1].split('\n')[0])
            vector = [0.0] * 5
            vector[topic] = 1.0
            vector[3] = .01 * (index + 1)
            vector[4] = .005 * (index ** 2 + topic)
            result.append(vector)
        return result
    return Mock(base_url='http://127.0.0.1:11434', embed=Mock(side_effect=embed))


def run(values, client, **kwargs):
    return discover_topics(values, 'embed', client=client, min_cluster_size=3, as_of='2026-11-11', **kwargs)


def test_discovers_separate_themes_and_representatives_from_vectors_without_saved_labels(client):
    values = articles()
    result = run(values, client)
    assert len(result['topics']) == 3
    assert sorted(topic['unique_articles'] for topic in result['topics']) == [4, 4, 4]
    assert {tuple(sorted(topic['article_ids'])) for topic in result['topics']} == {
        tuple(f't{topic}-{index}' for index in range(4)) for topic in range(3)}
    assert all(set(topic['representatives']) <= set(topic['article_ids']) and topic['keywords'] for topic in result['topics'])
    assert result['counts']['embeddings_created'] == 12 and result['counts']['partial_articles'] == 0
    assert len(result['projection']['points']) == 12
    assert 0 <= result['projection']['explained_variance'] <= 1
    client.generate.assert_not_called()
    assert all('topics' not in article for article in values)


def test_exact_copies_do_not_inflate_group_sizes_or_publication_denominators(client):
    values = articles()
    duplicate = dict(values[0], id='duplicate', source='Syndicated publisher', published='2026-11-11',
                     text='  ' + values[0]['text'].upper().replace(' ', '  ') + '\n')
    result = run(values + [duplicate], client)
    assert result['counts']['exact_copies'] == 1 and result['counts']['distinct_articles'] == 12
    assert result['time_windows']['7']['current_total'] == 12
    group = next(topic for topic in result['topics'] if 'duplicate' in topic['article_ids'])
    assert group['unique_articles'] == 4 and len(group['article_ids']) == 5
    assert set(group['publishers']) == {'Publisher 0', 'Publisher 1', 'Publisher 2', 'Publisher 3', 'Syndicated publisher'}


def test_digest_cache_is_reused_but_legacy_retrieval_vectors_are_not(client, monkeypatch):
    values = articles()
    raw = values[0]['title'] + '\n' + values[0]['text']
    storage.save_embeddings('embed', {raw: [-9.0, 2.0]})
    first = run(values, client)
    client.embed.reset_mock()
    warm = run(list(reversed(values)), client)
    client.embed.assert_not_called()
    assert warm['topics'] == first['topics'] and warm['counts']['embeddings_created'] == 0
    assert storage.cached_embeddings('embed', [raw]) == {raw: [-9.0, 2.0]}
    monkeypatch.setattr('app.topic_discovery.observe_models', lambda *args: inventory('b' * 64))
    changed = run(values, client)
    assert client.embed.called and changed['counts']['embeddings_created'] == 12
    assert changed['corpus_fingerprint'] == first['corpus_fingerprint']


def test_model_drift_does_not_commit_new_vectors(client, monkeypatch):
    observations = iter([inventory(), inventory('b' * 64)])
    monkeypatch.setattr('app.topic_discovery.observe_models', lambda *args: next(observations))
    with pytest.raises(IntelligenceError, match='No new topic embeddings'):
        run(articles(), client)
    with storage.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0] == 0


def test_unavailable_identity_or_missing_backend_makes_no_embedding_call(client, monkeypatch):
    monkeypatch.setattr('app.topic_discovery.observe_models', lambda *args: dict(state='unavailable'))
    with pytest.raises(IntelligenceError, match='manifest digest'):
        run(articles(), client)
    client.embed.assert_not_called()
    def missing():
        raise IntelligenceError('Install the optional topic backend')
    monkeypatch.setattr('app.topic_discovery.dependencies', missing)
    with pytest.raises(IntelligenceError, match='optional topic backend'):
        run(articles(), client)
    client.embed.assert_not_called()


@pytest.mark.parametrize('vectors', [[[True]], [[0.0]], [[float('nan')]], [[1.0], [1.0, 2.0]], []])
def test_invalid_vectors_are_rejected_without_cache_commits(client, vectors):
    client.embed.side_effect = None
    client.embed.return_value = vectors
    with pytest.raises(IntelligenceError, match='vectors|norms'):
        run(articles(), client)
    with storage.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0] == 0


def test_changed_body_gets_new_embeddings_and_input_snapshot(client):
    values = articles()
    first = run(values, client)
    values[0]['text'] += ' A newly captured observation.'
    second = run(values, client)
    assert second['counts']['embeddings_created'] == 1
    assert second['corpus_fingerprint'] != first['corpus_fingerprint']
    assert second['source_fingerprints'][values[0]['id']] != first['source_fingerprints'][values[0]['id']]


def test_long_article_sampling_includes_tail_and_discloses_partial_coverage(client):
    values = articles()
    values[0]['text'] = '\n'.join('astronomy finding ' + 'galaxy ' * 170 for _ in range(16)) + '\nTAIL DISCOVERY EVIDENCE.'
    result = run(values, client)
    sample = next(row for row in result['sampling'] if row['article_id'] == values[0]['id'])
    assert sample['used'] == 6 and sample['total'] > 6
    assert 'TAIL DISCOVERY EVIDENCE.' in sample['excerpts'][-1]
    assert result['counts']['partial_articles'] == 1


def test_same_corpus_order_produces_same_memberships_and_inputs(client):
    values = articles()
    original = deepcopy(values)
    first = run(values, client)
    second = run(list(reversed(values)), client)
    assert first['topics'] == second['topics'] and values == original
    json.dumps(second, ensure_ascii=False, allow_nan=False)


@pytest.mark.parametrize('change', ['few', 'many', 'duplicate_ids', 'copies_only', 'empty', 'oversized'])
def test_invalid_corpus_is_rejected_before_model_calls(client, change):
    values = articles()
    if change == 'few':
        values = values[:3]
    elif change == 'many':
        values = [dict(values[0], id=str(i)) for i in range(MAX_ARTICLES + 1)]
    elif change == 'duplicate_ids':
        values[1]['id'] = values[0]['id']
    elif change == 'copies_only':
        values = [dict(values[0], id=str(i)) for i in range(10)]
    elif change == 'empty':
        values[0]['text'] = ' '
    else:
        values[0]['text'] = 'x' * 256_001
    with pytest.raises(IntelligenceError):
        run(values, client)
    client.embed.assert_not_called()


def test_empty_time_window_is_unavailable_and_noise_stays_in_denominator():
    values = articles()
    for article in values:
        article['published'] = '2026-11-10'
    groups = documents(values)
    import numpy as np
    labels = np.asarray([0] * 4 + [1] * 4 + [-1] * 4)
    trend = _trends(groups, labels, date(2026, 11, 11))['7']
    assert trend['current_total'] == 12 and trend['previous_total'] == 0
    assert trend['topics'][0]['share'] == pytest.approx(1 / 3)
    assert trend['topics'][0]['change_percentage_points'] is None


def test_undated_and_future_articles_are_not_misrepresented_as_recent():
    values = articles()
    values[0]['published'], values[1]['published'] = '', '2099-01-01'
    import numpy as np
    result = _trends(documents(values), np.zeros(len(values), dtype=int), date(2026, 11, 11))
    assert result['30']['current_total'] == 10 and result['30']['undated_or_future'] == 2


def test_missing_optional_capture_metadata_keeps_articles_discoverable(client):
    values = articles()
    values[0].update(source=None, published=None, author=None)
    result = run(values, client)
    group = next(topic for topic in result['topics'] if values[0]['id'] in topic['article_ids'])
    assert group['publishers']['Unknown'] == 1
    assert result['time_windows']['30']['undated_or_future'] == 1


def test_corpus_wide_boilerplate_does_not_name_every_topic(client):
    values = articles()
    for article in values:
        article['text'] += ' Universal boilerplate notice. ' * 10
    result = run(values, client)
    assert len(result['topics']) == 3
    assert all(not any('boilerplate' in term or 'universal' in term for term in topic['keywords'])
               for topic in result['topics'])


def test_no_dense_groups_keeps_every_article_visible_as_unassigned(client):
    values = articles()[:4]
    client.embed.side_effect = lambda model, texts, **kwargs: [[float(i == j) for j in range(4)] for i in range(4)]
    result = run(values, client)
    assert result['topics'] == []
    assert set(result['outlier_article_ids']) == {article['id'] for article in values}


def test_second_embedding_batch_failure_leaves_no_partially_labeled_cache(client):
    values = articles()
    values[0]['text'] = '\n'.join(f'astronomy data section {i} ' + f'galaxy{i} ' * 170 for i in range(16))
    original = client.embed.side_effect
    calls = 0
    def interrupted(model, texts, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise IntelligenceError('interrupted')
        return original(model, texts, **kwargs)
    client.embed.side_effect = interrupted
    with pytest.raises(IntelligenceError, match='interrupted'):
        run(values, client)
    with storage.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0] == 0


def test_invalid_article_objects_fail_before_metadata_or_model_calls(client):
    with pytest.raises(IntelligenceError, match='objects'):
        run([None] * 4, client)
    client.embed.assert_not_called()


@pytest.mark.parametrize('change', ['url', 'publisher', 'date', 'model'])
def test_invalid_source_metadata_is_rejected_before_embedding(client, change):
    values = articles()
    if change == 'url':
        values[0]['url'] = 'javascript:alert(1)'
    elif change == 'publisher':
        values[0]['source'] = ['wrong']
    elif change == 'date':
        with pytest.raises(IntelligenceError, match='calendar date'):
            discover_topics(values, 'embed', client=client, as_of='not-a-date')
        client.embed.assert_not_called()
        return
    else:
        with pytest.raises(IntelligenceError, match='model name'):
            discover_topics(values, '', client=client)
        client.embed.assert_not_called()
        return
    with pytest.raises(IntelligenceError):
        run(values, client)
    client.embed.assert_not_called()


def test_upgrade_reuses_original_v1_vectors_without_embedding_calls(client):
    values = articles()
    inputs = [group['article']['title'] + '\n' + passage['text']
              for group in documents(values) for passage in group['passages']]
    namespace = 'topics-v1:' + fingerprint(dict(endpoint=client.base_url, model='embed',
        digest='a' * 64, version='density-topics-v1'))
    storage.save_embeddings(namespace, dict(zip(inputs, client.embed('embed', inputs))))
    client.embed.reset_mock()
    result = run(values, client)
    client.embed.assert_not_called()
    assert result['version'] == 'density-topics-v2'
    assert result['counts']['embeddings_reused'] == len(inputs)
    assert result['settings']['embedding_representation_version'] == 'density-topics-v1'


def test_reporting_words_are_filtered_and_single_class_still_has_keywords():
    from app.topic_discovery import _keywords, dependencies
    np, _, vectorizer = dependencies()
    values = articles()
    for article in values:
        article['text'] += ' said news reportedly article articles says reported ' * 30
    labels = np.asarray([int(group['article']['id'][1]) for group in documents(values)])
    terms = _keywords(documents(values), labels, np, vectorizer)
    excluded = {'said', 'says', 'news', 'reported', 'reportedly', 'article', 'articles'}
    assert all(words and all(not excluded.intersection(word.split()) for word in words)
               for words in terms.values())
    single = _keywords(documents(values[:4]), np.zeros(4, dtype=int), np, vectorizer)
    assert single[0] and any('astronomy' in term for term in single[0])


def test_leaf_subtopics_preserve_parent_copies_and_leave_noise_unassigned():
    from app.topic_discovery import _subtopics, dependencies
    np, cluster, vectorizer = dependencies()
    values = articles()[:8]
    values.append(dict(values[0], id='exact-copy', url='https://example.org/copy'))
    values.append(dict(values[0], id='lonely', text='An isolated distinct article body.', url='https://example.org/lonely'))
    groups = documents(values)
    vectors = []
    for group in groups:
        ident = group['article']['id']
        if ident == 'lonely':
            vectors.append([-1., -1., 0.])
        else:
            # Sorted IDs select exact-copy as the canonical source of t0-0.
            family = 0 if ident == 'exact-copy' else int(ident[1])
            index = 0 if ident == 'exact-copy' else int(ident[-1])
            vectors.append([1. if family == 0 else 0., 1. if family == 1 else 0., .005 * index])
    matrix = np.asarray(vectors)
    matrix /= np.linalg.norm(matrix, axis=1)[:, None]
    result = _subtopics(groups, matrix, list(range(len(groups))), 'parent', 3, np, cluster, vectorizer)
    assert result['subtopic_status'] == 'split'
    assert sorted(child['unique_articles'] for child in result['subtopics']) == [4, 4]
    assert result['subtopic_outlier_article_ids'] == ['lonely']
    members = [ident for child in result['subtopics'] for ident in child['article_ids']]
    assert len(members) == len(set(members)) == 9
    assert set(members) | {'lonely'} == {article['id'] for article in values}
    assert all(child['parent_id'] == 'parent' and set(child['representatives']) <= set(child['article_ids'])
               for child in result['subtopics'])
    copy_group = next(child for child in result['subtopics'] if 'exact-copy' in child['article_ids'])
    assert 't0-0' in copy_group['article_ids']


def test_subtopics_do_not_force_a_split_on_small_or_noise_only_parent():
    from app.topic_discovery import _subtopics, dependencies
    np, cluster, vectorizer = dependencies()
    groups = documents(articles()[:8])
    matrix = np.eye(8)
    too_small = _subtopics(groups, matrix, list(range(4)), 'small', 3, np, cluster, vectorizer)
    noise = _subtopics(groups, matrix, list(range(8)), 'noise', 3, np, cluster, vectorizer)
    assert too_small['subtopic_status'] == 'too_small' and too_small['subtopics'] == []
    assert noise['subtopic_status'] == 'no_split' and noise['subtopics'] == []
    assert set(noise['subtopic_outlier_article_ids']) == {group['article']['id'] for group in groups}
