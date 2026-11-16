"""Explicit, bounded corpus discovery; independent of saved labels and question retrieval."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
from importlib.metadata import version
import json
import math
from time import perf_counter
import unicodedata

from app import storage
from app.intelligence import IntelligenceError, OllamaClient, article_passages
from app.model_health import observe_models, model_observation
from app.research_export import _source_url

VERSION = 'density-topics-v2'
# Clustering/label changes do not change the sampled text or article vectors.
# Retain the original cache identity so an upgrade can reuse existing vectors.
EMBEDDING_VERSION = 'density-topics-v1'
REPORTING_STOP_WORDS = ('said', 'says', 'news', 'article', 'articles', 'reported', 'reportedly')
MAX_ARTICLES = 200
MAX_TEXT_BYTES = 8 * 1024 * 1024
PASSAGES_PER_ARTICLE = 6


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def dependencies():
    try:
        import numpy as np
        from sklearn.cluster import HDBSCAN
        from sklearn.feature_extraction.text import CountVectorizer
    except ImportError as exc:
        raise IntelligenceError('Install the optional topic backend: python -m pip install -r requirements-topics.txt') from exc
    return np, HDBSCAN, CountVectorizer


def documents(articles):
    """Collapse exact normalized body copies, retaining every source identity."""
    if not isinstance(articles, list) or not 4 <= len(articles) <= MAX_ARTICLES:
        raise IntelligenceError(f'Choose 4–{MAX_ARTICLES} saved articles for topic discovery.')
    if any(not isinstance(article, dict) for article in articles):
        raise IntelligenceError('Topic discovery needs saved article objects.')
    seen, groups, total = set(), {}, 0
    for article in sorted(articles, key=lambda item: str(item.get('id', ''))):
        if (not isinstance(article.get('id'), str) or not article['id'] or article['id'] in seen
                or not isinstance(article.get('text'), str) or not article['text'].strip()
                or len(article['text']) > 256_000 or not isinstance(article.get('title'), str)
                or len(article['title']) > 2000):
            raise IntelligenceError('Topic discovery needs unique source IDs, titles and bounded nonempty saved text.')
        try:
            _source_url(article.get('url'))
        except ValueError as exc:
            raise IntelligenceError('Topic discovery needs valid HTTP(S) source URLs.') from exc
        if any(article.get(key) is not None and not isinstance(article[key], str) for key in ('source', 'published', 'author')):
            raise IntelligenceError('Topic discovery needs text metadata for publisher, date and author.')
        seen.add(article['id'])
        total += len(article['text'].encode('utf-8'))
        if total > MAX_TEXT_BYTES:
            raise IntelligenceError('Narrow this discovery to at most 8 MiB of saved article text.')
        normalized = ' '.join(unicodedata.normalize('NFKC', article['text']).casefold().split())
        key = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        if key not in groups:
            passages = article_passages(article)
            count = min(PASSAGES_PER_ARTICLE, len(passages))
            indices = [0] if count == 1 else [round(i * (len(passages) - 1) / (count - 1)) for i in range(count)]
            groups[key] = dict(key=key, article=article, copies=[], passages=[passages[i] for i in indices],
                               total_passages=len(passages))
        groups[key]['copies'].append(article)
    result = list(groups.values())
    if len(result) < 4:
        raise IntelligenceError('At least four distinct article bodies are needed after exact-copy deduplication.')
    return result


def _vectors(values, expected, np):
    if (not isinstance(values, list) or len(values) != expected or any(not isinstance(row, list)
            or not 1 <= len(row) <= 4096 or any(type(x) not in (int, float) or not math.isfinite(x) for x in row)
            for row in values) or len({len(row) for row in values}) != 1):
        raise IntelligenceError('The topic embedding model returned inconsistent or invalid vectors.')
    matrix = np.asarray(values, dtype=float)
    norms = np.linalg.norm(matrix, axis=1)
    if not np.isfinite(norms).all() or (norms == 0).any():
        raise IntelligenceError('Topic embeddings must have finite, nonzero norms.')
    return matrix / norms[:, None]


def _keywords(groups, labels, np, CountVectorizer):
    """Class TF-IDF representations in original text; no generated labels."""
    classes = sorted(set(int(label) for label in labels))
    texts = [' '.join(p['text'] for i, group in enumerate(groups) if int(labels[i]) == label
                      for p in group['passages']) for label in classes]
    try:
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        vectorizer = CountVectorizer(stop_words=sorted(ENGLISH_STOP_WORDS.union(REPORTING_STOP_WORDS)),
            ngram_range=(1, 2), max_features=8000, max_df=.9 if len(classes) > 1 else 1.0)
        counts = vectorizer.fit_transform(texts).toarray().astype(float)
    except ValueError:  # A collection can contain only punctuation or stop words.
        return {label: [] for label in classes}
    lengths = counts.sum(axis=1)
    weights = counts / np.maximum(lengths[:, None], 1)
    weights *= np.log1p(lengths.mean() / np.maximum(counts.sum(axis=0), 1))
    terms = vectorizer.get_feature_names_out()
    return {label: [str(terms[j]) for j in sorted(range(len(terms)), key=lambda j: (-weights[i, j], terms[j]))[:6]
                    if weights[i, j] > 0] for i, label in enumerate(classes)}


def _topic(groups, matrix, indices, keywords, *, parent_id=None):
    centroid = matrix[indices].mean(axis=0)
    norm = float((centroid @ centroid) ** .5)
    ranked = sorted(indices, key=lambda i: (-float(matrix[i] @ centroid / norm) if norm else 0,
                                            groups[i]['article']['id']))
    members = sorted(groups[i]['key'] for i in indices)
    ident = ('subtopic-' + fingerprint(dict(parent=parent_id, members=members))[:12] if parent_id
             else 'topic-' + fingerprint(members)[:12])
    return dict(id=ident, keywords=keywords, unique_articles=len(indices),
        article_ids=[copy['id'] for i in indices for copy in groups[i]['copies']],
        representatives=[groups[i]['article']['id'] for i in ranked[:3]],
        publishers=dict(Counter(copy.get('source') or 'Unknown' for i in indices for copy in groups[i]['copies'])))


def _subtopics(groups, matrix, indices, parent_id, minimum, np, HDBSCAN, CountVectorizer):
    """One bounded leaf refit inside a parent; never force a split or assign noise."""
    copies = [copy['id'] for i in indices for copy in groups[i]['copies']]
    if len(indices) < 2 * minimum:
        return dict(subtopics=[], subtopic_outlier_article_ids=copies, subtopic_status='too_small')
    subset = [groups[i] for i in indices]
    vectors = matrix[indices]
    labels = HDBSCAN(min_cluster_size=minimum, min_samples=2, metric='euclidean',
                     cluster_selection_method='leaf', allow_single_cluster=False, copy=True).fit_predict(vectors)
    found = sorted(set(int(value) for value in labels if value >= 0))
    if len(found) < 2:
        return dict(subtopics=[], subtopic_outlier_article_ids=copies, subtopic_status='no_split')
    terms = _keywords(subset, labels, np, CountVectorizer)
    children = []
    for label in found:
        child = _topic(subset, vectors, [i for i, value in enumerate(labels) if value == label],
                       terms[label], parent_id=parent_id)
        child['parent_id'] = parent_id
        children.append(child)
    return dict(subtopics=sorted(children, key=lambda child: (-child['unique_articles'], child['id'])),
        subtopic_outlier_article_ids=[copy['id'] for i, group in enumerate(subset) if labels[i] == -1
                                     for copy in group['copies']], subtopic_status='split')


def _published(group, as_of):
    dates = []
    for article in group['copies']:
        try:
            value = date.fromisoformat((article.get('published') or '')[:10])
            if value <= as_of:
                dates.append(value)
        except (TypeError, ValueError):
            pass
    return min(dates) if dates else None


def _trends(groups, labels, as_of):
    dates = [_published(group, as_of) for group in groups]
    result = {}
    for days in (7, 30, 90):
        start = as_of - timedelta(days=days - 1)
        previous = start - timedelta(days=days)
        recent = [i for i, value in enumerate(dates) if value is not None and start <= value <= as_of]
        prior = [i for i, value in enumerate(dates) if value is not None and previous <= value < start]
        result[str(days)] = dict(current_total=len(recent), previous_total=len(prior),
            undated_or_future=sum(value is None for value in dates), topics={})
        for label in set(int(value) for value in labels if value >= 0):
            current, old = sum(int(labels[i]) == label for i in recent), sum(int(labels[i]) == label for i in prior)
            share = current / len(recent) if recent else None
            old_share = old / len(prior) if prior else None
            result[str(days)]['topics'][label] = dict(current=current, previous=old, share=share,
                previous_share=old_share, change_percentage_points=100 * (share - old_share)
                    if share is not None and old_share is not None else None)
    return result


def discover_topics(articles, embedding_model='qwen3-embedding:0.6b', *, client=None,
                    min_cluster_size=3, as_of=None, progress=None):
    """Fit optional HDBSCAN on averaged, normalized article passage embeddings.

    Topic vectors use a separate digest/endpoint/version cache namespace. New
    vectors are committed only after a stable before/after inventory observation.
    Legacy question-retrieval caches and saved article labels are never read.
    """
    started = perf_counter()
    if not isinstance(embedding_model, str) or not embedding_model.strip() or len(embedding_model) > 256:
        raise IntelligenceError('Choose a nonempty installed topic embedding model name (at most 256 characters).')
    groups = documents(articles)
    if type(min_cluster_size) is not int or not 2 <= min_cluster_size <= min(20, len(groups)):
        raise IntelligenceError('Minimum topic size must be between 2 and the number of distinct articles (at most 20).')
    np, HDBSCAN, CountVectorizer = dependencies()
    try:
        as_of = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of or date.today()
        if type(as_of) is not date:
            raise ValueError
    except ValueError as exc:
        raise IntelligenceError('Use an ISO calendar date for publication-window comparisons.') from exc
    client = client or OllamaClient()
    before = observe_models(client.base_url, [embedding_model])
    if before['state'] != 'complete':
        raise IntelligenceError('Topic discovery needs an installed embedding model with a readable manifest digest. Check Ollama model status.')
    identity = before['models'][embedding_model]['digest']
    namespace = 'topics-v1:' + fingerprint(dict(endpoint=client.base_url, model=embedding_model, digest=identity,
                                               version=EMBEDDING_VERSION))
    inputs = list(dict.fromkeys(group['article']['title'] + '\n' + passage['text']
                                for group in groups for passage in group['passages']))
    vectors = storage.cached_embeddings(namespace, inputs)
    missing = [text for text in inputs if text not in vectors]
    new = {}
    for offset in range(0, len(missing), 16):
        batch = missing[offset:offset + 16]
        generated = client.embed(embedding_model, batch, keep_alive='1m' if offset + 16 < len(missing) else 0)
        _vectors(generated, len(batch), np)
        new.update(zip(batch, generated))
        if progress:
            progress(min(offset + len(batch), len(missing)), len(missing))
    vectors.update(new)
    normalized = _vectors([vectors[text] for text in inputs], len(inputs), np)
    by_text = dict(zip(inputs, normalized))
    matrix = []
    for group in groups:
        mean = np.mean([by_text[group['article']['title'] + '\n' + p['text']] for p in group['passages']], axis=0)
        norm = np.linalg.norm(mean)
        if not norm or not np.isfinite(norm):
            raise IntelligenceError('An article has no usable average embedding; choose a different embedding model.')
        matrix.append(mean / norm)
    matrix = np.asarray(matrix)
    # Density clustering leaves weakly connected articles unassigned. Distances
    # are Euclidean in normalized semantic space, without a 2D projection.
    labels = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=2, metric='euclidean',
                     cluster_selection_method='eom', allow_single_cluster=False, copy=True).fit_predict(matrix)
    terms = _keywords(groups, labels, np, CountVectorizer)
    trends = _trends(groups, labels, as_of)
    topics = []
    for label in sorted(set(int(value) for value in labels if value >= 0)):
        indices = [i for i, value in enumerate(labels) if value == label]
        topic = _topic(groups, matrix, indices, terms[label])
        topic['trends'] = {window: data['topics'][label] for window, data in trends.items()}
        topic.update(_subtopics(groups, matrix, indices, topic['id'], min_cluster_size,
                                np, HDBSCAN, CountVectorizer))
        topics.append(topic)
    centered = matrix - matrix.mean(axis=0)
    u, singular, _ = np.linalg.svd(centered, full_matrices=False)
    coordinates = np.zeros((len(groups), 2))
    width = min(2, len(singular))
    coordinates[:, :width] = u[:, :width] * singular[:width]
    total_variance = float((singular ** 2).sum())
    topic_by_article = {ident: topic['id'] for topic in topics for ident in topic['article_ids']}
    projection = dict(method='PCA for display only; clustering uses the full normalized embedding space',
        explained_variance=float((singular[:2] ** 2).sum()) / total_variance if total_variance else 0,
        points=[dict(article_id=group['article']['id'], x=float(coordinates[i, 0]), y=float(coordinates[i, 1]),
                     topic_id=topic_by_article.get(group['article']['id'])) for i, group in enumerate(groups)])
    observation = model_observation(before, observe_models(client.base_url, [embedding_model]))
    if observation['state'] != 'stable':
        raise IntelligenceError('The embedding model changed or its identity became unavailable. No new topic embeddings were cached; retry after checking Ollama.')
    if new:
        storage.save_embeddings(namespace, new)
    return dict(version=VERSION, created_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        as_of=as_of.isoformat(), embedding_model=embedding_model, model_observation=observation,
        settings=dict(min_cluster_size=min_cluster_size, min_samples=2, metric='euclidean',
                      cluster_selection_method='eom', subtopic_selection_method='leaf', subtopic_depth=1,
                      embedding_representation_version=EMBEDDING_VERSION, reporting_stop_words=list(REPORTING_STOP_WORDS),
                      projection='none', passages_per_article=PASSAGES_PER_ARTICLE,
                      representation='class-tf-idf', keyword_max_class_fraction=.9, sklearn_version=version('scikit-learn')),
        source_fingerprints={article['id']: storage.article_fingerprint(article) for article in articles},
        corpus_fingerprint=fingerprint(sorted((article['id'], storage.article_fingerprint(article)) for article in articles)),
        topics=sorted(topics, key=lambda topic: (-topic['unique_articles'], topic['id'])),
        projection=projection,
        outlier_article_ids=[copy['id'] for i, group in enumerate(groups) if labels[i] == -1 for copy in group['copies']],
        articles=[dict(id=article['id'], title=article['title'], url=article['url'],
                       source=article.get('source', ''), published=article.get('published', '')) for article in articles],
        sampling=[dict(article_id=group['article']['id'], copies=[copy['id'] for copy in group['copies']],
                       used=len(group['passages']), total=group['total_passages'],
                       excerpts=[passage['text'] for passage in group['passages']]) for group in groups],
        counts=dict(articles=len(articles), distinct_articles=len(groups), exact_copies=len(articles) - len(groups),
                    embedding_inputs=len(inputs), embeddings_created=len(new), embeddings_reused=len(inputs) - len(new),
                    partial_articles=sum(len(group['passages']) < group['total_passages'] for group in groups)),
        time_windows={window: {key: value for key, value in data.items() if key != 'topics'} for window, data in trends.items()},
        elapsed_seconds=round(perf_counter() - started, 3),
        notice='Experimental corpus themes, not verified event matches or claims. Keyword labels use sampled saved text. '
               'Subtopics are a separate leaf refit within each parent; unsplit and unassigned members retain their parent. '
               'Exact normalized body copies count once. Group IDs can change when the corpus changes. '
               'Window shares describe this saved corpus using its dates, including unassigned articles in denominators. '
               'English stop words are used; multilingual topic quality is not established.')
