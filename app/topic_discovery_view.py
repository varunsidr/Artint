"""Optional topic discovery with explicit scope, inspectable sources and retained results."""
import json
from html import escape

import streamlit as st

from app import storage
from app.intelligence import IntelligenceError, OllamaClient
from app.observatory_data import collections
from app.topic_discovery import MAX_ARTICLES, dependencies, discover_topics
from app.ui import empty_state, literal_markdown, page_header


def _sources(collection_id):
    """Bound body reads before fitting; never silently sample the first page."""
    with storage.connect() as con:
        con.execute('BEGIN')
        where = ' WHERE a.id IN (SELECT article_id FROM collection_articles WHERE collection_id=?)' if collection_id else ''
        parameters = [collection_id] if collection_id else []
        total = con.execute('SELECT COUNT(*) FROM articles a' + where, parameters).fetchone()[0]
        if total > MAX_ARTICLES:
            raise IntelligenceError(f'This scope has {total} articles. Choose a collection of at most {MAX_ARTICLES}; no subset was analyzed.')
        size = con.execute('SELECT COALESCE(SUM(length(CAST(a.text AS BLOB))),0) FROM articles a' + where, parameters).fetchone()[0]
        from app.topic_discovery import MAX_TEXT_BYTES
        if size > MAX_TEXT_BYTES:
            raise IntelligenceError('This collection exceeds 8 MiB of saved text. Choose a smaller collection.')
        return [dict(row) for row in con.execute('SELECT a.* FROM articles a' + where + ' ORDER BY a.id', parameters)]


def _show_sources(ids, by_id, result):
    for ident in ids:
        item = by_id[ident]
        st.text(item['title'])
        st.caption(literal_markdown((item.get('source') or 'Unknown publisher') + ' · ' +
                                   (item.get('published') or 'Date unavailable')))
        if st.button('Read saved article', key='topic_read_' + ident):
            from app.library_view import reading_room
            article = storage.get_article(ident)
            if article:
                if storage.article_fingerprint(article) != result['source_fingerprints'][ident]:
                    st.warning('This source has changed since discovery. The reader shows its current saved copy.')
                reading_room(article, storage.load_insight(article, 'qwen3:8b', '1'))
            else:
                st.warning('This source was removed from the library. Its original metadata remains in this result.')


def _map_selection_changed():
    st.session_state['topic_map_selection_changed'] = True


def _show_result(saved, revision, scope):
    result = saved['result']
    if saved['revision'] != revision or saved['scope'] != scope:
        st.info('Showing the last completed discovery and its original sources. The library or current selection has changed; rerun to update the groups.')
    counts = result['counts']
    st.subheader('Discovered themes')
    st.caption(f"{len(result['topics'])} themes · {counts['distinct_articles']} distinct bodies · "
               f"{counts['exact_copies']} additional exact copies · {len(result['outlier_article_ids'])} unassigned source copies")
    subtopic_count = sum(len(topic.get('subtopics', [])) for topic in result['topics'])
    if subtopic_count:
        st.caption(f'{subtopic_count} finer subtopics inside the parent themes. Open a theme to browse its subtopics and remaining articles.')
    st.caption(literal_markdown(f"Completed {result['created_at']} · {result['embedding_model']} · "
               f"{counts['embeddings_reused']} embeddings reused / {counts['embeddings_created']} created · "
               f"{result['elapsed_seconds']:.1f}s"))
    if counts['partial_articles']:
        st.info(f"{counts['partial_articles']} long articles used up to six passages spread across the text. Inspect the sampled excerpts below.")
    by_id = {article['id']: article for article in result['articles']}
    import pandas as pd
    import plotly.express as px
    labels = {topic['id']: f"{index}. " + (' / '.join(topic['keywords'][:3]) or topic['id'])[:60]
              for index, topic in enumerate(result['topics'], 1)}
    points = [dict(x=point['x'], y=point['y'], article_id=point['article_id'],
                   title=escape(by_id[point['article_id']]['title']),
                   theme=labels.get(point['topic_id'], 'Unassigned')) for point in result['projection']['points']]
    figure = px.scatter(pd.DataFrame(points), x='x', y='y', color='theme', hover_name='title',
                        custom_data=['article_id'], labels={'theme': 'Theme', 'x': 'Display axis 1', 'y': 'Display axis 2'})
    figure.update_traces(marker=dict(size=10, opacity=.85))
    figure.update_layout(height=390, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation='h'))
    selected = st.plotly_chart(figure, width='stretch', key='topic_map',
                               on_select=_map_selection_changed, selection_mode='points')
    selected_ids = {point.get('customdata', [None])[0] for point in selected.get('selection', {}).get('points', [])
                    if isinstance(point.get('customdata'), (list, tuple)) and point['customdata']}
    selection_changed = st.session_state.pop('topic_map_selection_changed', False)
    st.caption(f"Each point is a distinct body; exact copies share one point. This two-dimensional PCA view retains "
               f"{100 * result['projection']['explained_variance']:.1f}% of embedding variance. Clustering uses the full space. "
               'Select a point to expand its theme below.')
    window = st.selectbox('Compare publication windows', [7, 30, 90], index=1, key='topic_window')
    totals = result['time_windows'][str(window)]
    st.caption(f"Each window spans {window} days, ending {result['as_of']}. Denominators: "
               f"{totals['current_total']} recent / {totals['previous_total']} prior distinct bodies, including unassigned ones. "
               f"{totals['undated_or_future']} bodies have no usable date. Exact copies use their earliest usable date.")
    if not result['topics']:
        st.info('No dense themes were found with these settings. Unassigned articles remain available below; try another collection or minimum group size.')
    for topic in result['topics']:
        label = labels[topic['id']]
        expanded_key = 'topic_expand_' + topic['id']
        # A stable expander key preserves browsing state. Map events update its
        # tracked value explicitly; ordinary source/window reruns leave it alone.
        if selection_changed or expanded_key not in st.session_state:
            st.session_state[expanded_key] = bool(selected_ids.intersection(topic['article_ids']))
        with st.expander(literal_markdown(label) + f" · {topic['unique_articles']} distinct articles",
                         key=expanded_key, on_change='rerun'):
            st.text('Keywords: ' + ', '.join(topic['keywords']))
            trend = topic['trends'][str(window)]
            share = f"{100 * trend['share']:.1f}%" if trend['share'] is not None else 'unavailable'
            delta = (f"{trend['change_percentage_points']:+.1f} percentage points" if trend['change_percentage_points'] is not None
                     else 'unavailable (a comparison window is empty)')
            st.write(f"Publication share: {share} · change: {delta}. "
                     f"{trend['current']} recent / {trend['previous']} prior distinct articles.")
            st.caption('Publication share measures this saved collection, not importance or wider news coverage.')
            children = topic.get('subtopics', [])
            shown = topic
            source_ids = topic['article_ids']
            if children:
                st.write('Finer subtopics')
                choices = {'all': f"All parent articles ({len(topic['article_ids'])} source copies)"}
                by_child = {child['id']: child for child in children}
                for child in children:
                    title = ' / '.join(child['keywords'][:3]) or child['id']
                    choices[child['id']] = title + f" · {child['unique_articles']} distinct articles"
                    st.text(choices[child['id']])
                remaining = topic['subtopic_outlier_article_ids']
                if remaining:
                    choices['remaining'] = f'Parent articles without a subtopic ({len(remaining)} source copies)'
                st.caption('Subtopics use the same article vectors within this parent. Remaining articles keep their parent theme; no subtopic is forced.')
                key = 'topic_browse_' + topic['id']
                if st.session_state.get(key) not in choices:
                    st.session_state[key] = 'all'
                selected_child = st.selectbox('Browse sources in this theme', list(choices),
                    format_func=lambda ident: literal_markdown(choices[ident]), key=key)
                if selected_child == 'remaining':
                    source_ids = remaining
                    shown = None
                elif selected_child != 'all':
                    shown = by_child[selected_child]
                    source_ids = shown['article_ids']
                    st.text('Subtopic keywords: ' + ', '.join(shown['keywords']))
            elif 'subtopic_status' in topic:
                st.caption('No finer split was found with these settings.' if topic['subtopic_status'] == 'no_split'
                           else 'Too few distinct articles for two subtopics at this minimum size.')
            st.write('Representative articles' if shown else 'Articles without a finer assignment')
            for ident in shown['representatives'] if shown else []:
                st.text(by_id[ident]['title'])
            st.write(f'Source copies ({len(source_ids)})')
            _show_sources(source_ids, by_id, result)
    with st.expander(f"Unassigned articles ({len(result['outlier_article_ids'])})"):
        _show_sources(result['outlier_article_ids'], by_id, result)
        st.caption('Unassigned means no dense group was found; it does not mean irrelevant or low quality.')
    with st.expander('Inspect sampled source excerpts'):
        for sample in result['sampling']:
            st.text(by_id[sample['article_id']]['title'])
            st.caption(f"{sample['used']} of {sample['total']} passages; {len(sample['copies'])} source copies")
            for excerpt in sample['excerpts']:
                st.text(excerpt)
    st.download_button('Download topic discovery', json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
                       file_name='topic-discovery.json', mime='application/json', key='topic_export', on_click='ignore')
    st.caption('Groups and keyword labels are exploratory themes. They do not establish the same event, agreement, truth or claim support.')
    if st.button('Clear discovery result', key='topic_clear'):
        st.session_state.pop('topic_discovery_result', None)
        st.rerun()


def render_topic_discovery(overview):
    page_header('Analytics', 'Topic discovery', 'Explore themes across your saved articles, then inspect their sources.')
    st.caption('Experimental · Separate from saved per-article labels. Runs only when requested; no chat model is required.')
    choices = {item['id']: item['title'] for item in collections()}
    if st.session_state.get('topic_collection') not in choices:
        st.session_state['topic_collection'] = ''
    collection = st.selectbox('Collection to discover', list(choices),
                              format_func=lambda ident: literal_markdown(choices[ident]), key='topic_collection')
    with st.form('topic_discovery_form'):
        model = st.text_input('Topic embedding model', value='qwen3-embedding:0.6b', max_chars=256)
        minimum = st.number_input('Minimum distinct articles per theme', min_value=2, max_value=20, value=3, step=1)
        st.caption('Also looks for finer subtopics inside each parent theme. This minimum applies at both levels; articles may remain without a subtopic.')
        submitted = st.form_submit_button('Discover topics', type='primary')
    scope = (collection, model, int(minimum))
    if submitted:
        bar = None
        try:
            dependencies()
            articles = _sources(collection)
            bar = st.progress(0, text='Preparing article embeddings...')
            result = discover_topics(articles, model, client=OllamaClient(), min_cluster_size=int(minimum),
                                     progress=lambda done, total: bar.progress(done / total, text=f'Embedded {done} of {total} new passages'))
            st.session_state['topic_discovery_result'] = dict(result=result, revision=overview['revision'], scope=scope)
        except (IntelligenceError, ValueError, OSError) as exc:
            st.error(literal_markdown(str(exc)))
        finally:
            if bar is not None:
                bar.empty()
    saved = st.session_state.get('topic_discovery_result')
    if saved:
        _show_result(saved, overview['revision'], scope)
    elif not overview['total']:
        empty_state('Save a collection first', 'At least four distinct saved article bodies are needed for discovery.')
    else:
        st.write(f'Choose 4–{MAX_ARTICLES} articles in a collection. Exact body copies count once; unrelated articles may remain unassigned.')
        st.caption('Native optional backend: python -m pip install -r requirements-topics.txt. Results remain in this browser session; download JSON to keep a snapshot.')
