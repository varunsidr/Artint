"""Research workspace with optional local models and inspectable saved evidence."""
import json
from html import escape
from time import perf_counter

import streamlit as st

from app.intelligence import (
    ANALYSIS_VERSION, IntelligenceError, OllamaClient, analyze_article, answer_question,
    article_passages, semantic_search,
)
from app.storage import get_article, library_filter_options, library_overview, library_page, load_articles, load_insight
from app.library_filters import build_filters, LENGTHS, PERIODS
from app.observatory_data import collections
from app.ui import display_date, empty_state, page_header, topic_chips, pagination, reset_page_if_changed, navigate, literal_markdown


@st.cache_data(ttl=30, show_spinner=False)
def _model_status(base_url):
    try:
        return OllamaClient(base_url).models(), None
    except IntelligenceError as exc:
        return [], str(exc)


def _show_claim(claim, source_labels=None):
    st.html('<div class="claim-text">' + escape(claim['text']) + '</div>'
            '<div class="claim-citations">Evidence: '
            + escape(' / '.join(source_labels.get(source, source) if source_labels
                                else source.rsplit(':', 1)[-1] for source in claim['sources'])) + '</div>')


def _show_evidence(passages, ids=None, numbered=False):
    for index, passage in enumerate(passages, 1):
        if ids is None or passage['id'] in ids:
            st.caption(passage['id'])
            label = f'{index:02} · {passage["title"]}' if numbered else passage['title']
            st.link_button(literal_markdown(label), passage['url'], icon=':material/arrow_outward:')
            st.text(passage['text'])
            st.divider()


def render_saved_insight(article, insight, key_prefix='insight'):
    st.html(topic_chips(insight['topics']))
    st.html('<div class="section-title" style="margin-top:24px">The overview</div>')
    _show_claim(insight['summary'])
    st.html('<div class="section-title">Key takeaways</div>')
    for index, point in enumerate(insight['key_points'], 1):
        st.html(f'<div class="section-note" style="margin:14px 0 3px">{index:02}</div>')
        _show_claim(point)
    if insight.get('partial', False):
        st.info(f"Partial analysis: {insight['passages_analyzed']} of {insight['total_passages']} passages were analyzed.")
    ids = set(insight['summary']['sources'])
    ids.update(source for point in insight['key_points'] for source in point['sources'])
    with st.expander('Inspect supporting passages', icon=':material/format_quote:'):
        _show_evidence(article_passages(article), ids)
    st.caption(f"Saved {display_date(insight.get('generated_at', ''))} / {insight.get('model', 'Model unavailable')} / Check the source evidence before relying on a claim.")
    st.download_button('Export analysis', json.dumps(insight, ensure_ascii=False, indent=2),
                       file_name=f"{article['id']}_insights.json", mime='application/json',
                       key=f"{key_prefix}_download_{article['id']}", icon=':material/download:')


def _clear_article_focus():
    st.session_state.pop('research_focus_article', None)


def _focused_analysis(article_id, model, client, ready, force):
    """A reading-room handoff never inherits filters or starts a bulk job."""
    st.button('Back to research library', on_click=_clear_article_focus,
              icon=':material/arrow_back:')
    article = get_article(article_id)
    if not article:
        st.warning('This article is no longer in the library. Return to the research library to choose another source.')
        return
    st.subheader(literal_markdown(article['title']))
    st.caption('Analysis for this article only. Your library and research filters are preserved.')
    st.link_button('Original source', article['url'], icon=':material/arrow_outward:')
    insight = load_insight(article, model, ANALYSIS_VERSION)
    if st.button('Generate analysis' if not insight else 'Refresh analysis' if force else 'View saved analysis',
                 key='focused_analyze_' + article_id, type='primary', disabled=not ready):
        try:
            with st.spinner('Reading and summarizing this article...'):
                insight = analyze_article(article, model, client, force=force)
        except IntelligenceError as exc:
            st.error(str(exc))
    if insight:
        render_saved_insight(article, insight, key_prefix='focused')
    elif not ready:
        st.info('Connect your local model in Research settings above, then generate the analysis. No embedding model is needed for an article summary.')
    else:
        st.write('Ready to generate a summary and cited takeaways using ' + model + '.')
    st.button('Return to Library', on_click=navigate, args=('Library',), icon=':material/book_2:')


def _research_answer(answer, reused=False):
    st.subheader('Research answer' if 'supported' in answer else 'Matching passages')
    st.text(answer['question'])
    if answer.get('supported') is False:
        st.info('These articles do not contain enough evidence to answer this question.')
    passages = answer['passages']
    by_id = {passage['id']: passage for passage in passages}
    labels = {p['id']: f'Source {index:02}' for index, p in enumerate(passages, 1)}
    for index, claim in enumerate(answer.get('claims', []), 1):
        with st.container(border=True):
            st.html(f'<div class="answer-claim"><span>{index:02}</span><p>{escape(claim["text"])}</p></div>')
            cited = [by_id[source] for source in claim['sources'] if source in by_id]
            with st.expander(f'Inspect {len(cited)} cited {"passage" if len(cited) == 1 else "passages"}',
                             icon=':material/format_quote:'):
                for passage in cited:
                    st.caption(labels[passage['id']])
                    _show_evidence([passage])
    with st.expander('All retrieved passages', expanded='supported' not in answer):
        _show_evidence(passages, numbered=True)
    trace = answer.get('retrieval', {})
    if trace:
        st.caption(f"{trace['passages_searched']:,} passages searched · {len(passages)} retrieved · "
                   f"{trace['embeddings_reused']:,} embeddings reused · {trace['embeddings_created']:,} created")
    if 'elapsed_seconds' in answer:
        prefix = 'Reused the previous result for this exact question and source selection' if reused else 'Completed'
        st.caption(f"{prefix} · original run {answer['elapsed_seconds']:.1f}s. Check the cited evidence before relying on a claim.")


def render_intelligence(overview):
    page_header('Research', 'Research workspace', 'Choose your sources. Check the evidence behind every answer.')
    if not overview['total']:
        empty_state('Good questions start with good sources', 'Import a few articles to begin your research.')
        return

    client = OllamaClient()
    models, error = _model_status(client.base_url)
    chat_models = [name for name in models if 'embed' not in name.lower() and 'cloud' not in name.lower()]
    embedding_models = [name for name in models if 'embed' in name.lower() and 'cloud' not in name.lower()]
    with st.expander('Research settings', icon=':material/tune:'):
        controls = st.columns([2, 2, 1])
        with controls[0]:
            if chat_models:
                default = chat_models.index('qwen3:8b') if 'qwen3:8b' in chat_models else 0
                model = st.selectbox('Analysis model', chat_models, index=default)
            else:
                model = st.text_input('Analysis model', value='qwen3:8b',
                                      help='Use the model name associated with your saved analyses.')
        with controls[1]:
            embedding_model = st.selectbox('Search model', embedding_models) if embedding_models else None
            if not embedding_models:
                st.caption('No embedding model connected.')
        with controls[2]:
            if st.button('Refresh models', icon=':material/refresh:'):
                _model_status.clear()
                st.rerun()
        force = st.checkbox('Regenerate existing analyses', value=False)
        if error:
            st.warning(error)
            st.code('ollama serve', language='powershell')
        if not chat_models and not error:
            st.code('ollama pull qwen3:8b', language='powershell')
        if not embedding_models:
            st.caption('For semantic search, install an embedding model:')
            st.code('ollama pull qwen3-embedding:0.6b', language='powershell')
        if client.base_url != 'http://127.0.0.1:11434':
            st.caption('Article passages are sent to the configured model endpoint: ' + client.base_url)

    if model != 'qwen3:8b':
        overview = library_overview(model, ANALYSIS_VERSION)
    ready = not error and model in chat_models
    focus = st.session_state.get('research_focus_article')
    if focus:
        _focused_analysis(focus, model, client, ready, force)
        return
    st.html('<div class="quiet-status">'
            f'<span class="status-dot" style="background:var(--{"positive" if ready else "subtle"})"></span>'
            f'{"Local model connected" if ready else "Model offline"} &nbsp; / &nbsp; '
            f'{overview["analyzed"]:,} current saved analyses in your library</div>')

    collection_options = collections()
    collection_names = {row['id']: row['title'] for row in collection_options}
    if st.session_state.get('research_collection', '') not in collection_names:
        st.session_state['research_collection'] = ''
    if st.session_state.get('research_publisher', 'All publishers') not in ['All publishers', *overview['publishers']]:
        st.session_state['research_publisher'] = 'All publishers'
    with st.expander('General filters', expanded=True, icon=':material/tune:'):
        collection, source = st.columns([2, 1])
        with collection:
            selected_collection = st.selectbox('Research collection', list(collection_names),
                                               format_func=collection_names.get, key='research_collection', persist_state='session')
        with source:
            chosen_source = st.selectbox('Publisher', ['All publishers'] + overview['publishers'],
                                        key='research_publisher', persist_state='session')
        query = st.text_input('Find source articles', placeholder='Enter a topic or keyword, e.g. layoffs',
                              max_chars=256, key='research_search', icon=':material/search:', persist_state='session')
        published, status, length = st.columns(3)
        with published:
            period = st.selectbox('Published', ['Any time', *PERIODS, 'Custom dates', 'Date unavailable'],
                                  key='research_published', persist_state='session')
        with status:
            chosen_status = st.selectbox('Analysis status', ['All articles', 'Analyzed', 'Needs analysis'],
                                          key='research_status', persist_state='session')
        with length:
            reading_length = st.selectbox('Reading length', list(LENGTHS), key='research_length', persist_state='session')
        start, end = None, None
        if period == 'Custom dates':
            first, last = st.columns(2)
            with first:
                start = st.date_input('Published from', value=None, format='DD/MM/YYYY',
                                      key='research_date_from', persist_state='session')
            with last:
                end = st.date_input('Published until', value=None, format='DD/MM/YYYY',
                                    key='research_date_until', persist_state='session')
        st.caption('Publisher, date, analysis status and reading length apply to every topic.')
    try:
        base = build_filters(dict(search=query, collection=selected_collection,
                                  publishers=[] if chosen_source == 'All publishers' else [chosen_source],
                                  published=period, date_from=start, date_until=end,
                                  status=chosen_status, length=reading_length))
        base.update(model=model, version=ANALYSIS_VERSION)
        options = library_filter_options(**base, retain_topics=st.session_state.get('research_topics', []),
                                         retain_tags=st.session_state.get('research_tags', []))
    except ValueError as exc:
        st.warning(str(exc))
        return
    for name in ('topics', 'tags'):
        key = 'research_' + name
        st.session_state[key] = [value for value in st.session_state.get(key, []) if value in options[name]]
    st.session_state['research_tags'] = st.session_state['research_tags'][:20]
    with st.expander('Topic filters', expanded=True, icon=':material/filter_alt:'):
        st.caption(f"Choices from all {options['total']:,} matching articles, including {options['analyzed']:,} with current saved analyses. They update when your search or general filters change.")
        if len(options['topics']) == 100 or len(options['tags']) == 100:
            st.caption('Up to 100 labels are shown, retaining valid selections. Narrow your search or collection to find less common labels.')
        topic, tags = st.columns(2)
        with topic:
            topics = st.multiselect('Saved analysis topics', options['topics'], key='research_topics',
                                    disabled=not options['topics'], persist_state='session',
                                    placeholder='Topics in matching articles',
                                    help='Saved labels for these sources, not topics from the rest of your library. Selecting several matches any label.')
        with tags:
            selected_tags = st.multiselect('Personal tags', list(options['tags']), format_func=options['tags'].get,
                                           max_selections=20,
                                           key='research_tags', disabled=not options['tags'], persist_state='session',
                                           placeholder='Tags in matching articles')
        if not options['topics']:
            st.caption('No saved analysis topics in this selection. You can still search these articles, use your tags, or analyze them in Saved insights to add labels.')
    filters = dict(base, topics=topics, tags=selected_tags)
    reset_page_if_changed('research', filters)
    result = library_page(page=st.session_state['research_page'], page_size=25, **filters)
    items = result['items']
    pagination(result, 'research')
    if not items:
        empty_state('No matching sources', 'Try a different keyword, publisher, or topic.')
        return

    ask_tab, insights_tab = st.tabs(['Ask library', 'Saved insights'])
    with ask_tab:
        st.html('<div class="section-title" style="margin-top:22px">What would you like to understand?</div>')
        with st.expander('Choose sources'):
            by_id = {article['id']: article for article in items}
            if 'research_selected_ids' in st.session_state:
                st.session_state['research_selected_ids'] = [value for value in st.session_state['research_selected_ids'] if value in by_id]
            selected_ids = st.multiselect('Articles on this page (empty means all shown)', list(by_id),
                                          format_func=lambda value: by_id[value]['title'], key='research_selected_ids')
            if result['total'] > 100:
                st.session_state['research_all_matches'] = False
            all_matches = st.checkbox('Include every match (up to 100 articles)',
                                       disabled=result['total'] > 100, key='research_all_matches')
            st.caption('Choose a collection, search, or publisher to narrow the sources. Each question can research up to 100 articles.')
        candidates = library_page(page_size=100, **filters)['items'] if all_matches and result['total'] <= 100 else items
        research_ids = selected_ids or [article['id'] for article in candidates]
        st.caption(f"This question will search {len(research_ids):,} articles out of {overview['total']:,} in your library. Other articles are outside this answer's scope.")
        scope = (model, embedding_model, tuple(research_ids), overview['revision'], client.base_url)
        with st.form('article_question'):
            question = st.text_area('Research question', max_chars=2000, height=110,
                                    placeholder='What are the main findings across these selected articles?')
            action = st.radio('Research mode', ['Answer with citations', 'Search passages'], horizontal=True)
            fresh = st.checkbox('Generate a fresh result', value=False,
                                help='Otherwise an identical question reuses its last result in this session, while the sources, models and mode are unchanged.')
            submitted = st.form_submit_button('Research', type='primary', icon=':material/arrow_upward:',
                                              disabled=bool(error) or not embedding_model)
        if not embedding_model or error:
            st.caption('Saved insights remain available in the next tab. Connect a model in Research settings to ask a new question.')
        reused = False
        if submitted:
            previous = st.session_state.get('ai_research')
            reused = bool(not fresh and previous and previous['scope'] == scope
                          and previous.get('action') == action
                          and previous['result']['question'] == question.strip())
        if submitted and not reused:
            st.session_state.pop('ai_research', None)
            try:
                if action == 'Answer with citations' and not ready:
                    raise IntelligenceError('Choose an installed analysis model in Research settings.')
                started = perf_counter()
                selected_articles = load_articles(research_ids)
                with st.spinner('Reading the relevant passages...'):
                    if action == 'Search passages':
                        trace = {}
                        answer = dict(question=question.strip(), passages=semantic_search(
                            question, selected_articles, embedding_model, client, stats=trace), retrieval=trace)
                    else:
                        answer = answer_question(question, selected_articles, model, embedding_model, client)
                    answer['elapsed_seconds'] = perf_counter() - started
                    st.session_state['ai_research'] = dict(scope=scope, result=answer, action=action)
            except IntelligenceError as exc:
                st.error(str(exc))
        research = st.session_state.get('ai_research')
        if research and research['scope'] == scope:
            _research_answer(research['result'], reused)

    with insights_tab:
        heading, analyze = st.columns([3, 1], vertical_alignment='center')
        with heading:
            st.html('<div class="section-title" style="margin-top:20px">Article insights</div>'
                    f'<div class="section-note">Browse {len(items)} sources on this page · {escape(model)}</div>')
        with analyze:
            if st.button('Analyze this page', type='primary', disabled=not ready, width='stretch'):
                targets = [article for article in items if force or not article['insight']]
                if not targets:
                    st.info('Every article on this page already has a current analysis.')
                else:
                    progress = st.progress(0, text='Preparing analysis...')
                    for index, article in enumerate(targets, 1):
                        try:
                            full = get_article(article['id'])
                            if full:
                                analyze_article(full, model, client, force=force)
                        except IntelligenceError as exc:
                            st.error(f"{article['title']}: {exc}")
                        progress.progress(index / len(targets), text=f'Processed {index} of {len(targets)} articles')
                    st.rerun()
        by_id = {article['id']: article for article in items}
        chosen = st.selectbox('Article', list(by_id), format_func=lambda value: by_id[value]['title'])
        article = get_article(chosen)
        if article:
            insight = load_insight(article, model, ANALYSIS_VERSION)
            if st.button('Analyze this article', key=f'analyze_{chosen}', disabled=not ready):
                try:
                    with st.spinner('Reading and summarizing...'):
                        analyze_article(article, model, client, force=force)
                    st.rerun()
                except IntelligenceError as exc:
                    st.error(str(exc))
            if insight:
                render_saved_insight(article, insight)
            else:
                empty_state('Ready when you are', "Connect a local model to generate this article's first analysis.")
