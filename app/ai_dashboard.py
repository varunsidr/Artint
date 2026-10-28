"""Research workspace with optional local models and inspectable saved evidence."""
import json
from html import escape

import streamlit as st

from app.intelligence import (
    ANALYSIS_VERSION, IntelligenceError, OllamaClient, analyze_article, answer_question,
    article_passages, semantic_search,
)
from app.storage import get_article, library_overview, library_page, load_articles, load_insight
from app.observatory_data import collections
from app.ui import display_date, empty_state, page_header, topic_chips, pagination, reset_page_if_changed


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
            st.link_button(label, passage['url'], icon=':material/arrow_outward:')
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
    st.html('<div class="quiet-status">'
            f'<span class="status-dot" style="background:var(--{"positive" if ready else "subtle"})"></span>'
            f'{"Local model connected" if ready else "Model offline"} &nbsp; / &nbsp; '
            f'{overview["analyzed"]:,} current saved analyses in your library</div>')

    collection_options = collections()
    collection_names = {row['id']: row['title'] for row in collection_options}
    selected_collection = st.selectbox('Research collection', list(collection_names),
                                       format_func=collection_names.get, key='research_collection')
    search, source = st.columns([2, 1])
    with search:
        query = st.text_input('Find source articles', placeholder='Search titles, authors, or article text',
                              max_chars=256, key='research_search', icon=':material/search:')
    with source:
        chosen_source = st.selectbox('Publisher', ['All publishers'] + overview['publishers'], key='research_publisher')
    topics = st.multiselect('Filter by topic', overview['topics'])
    filters = dict(collection_id=selected_collection or None,
                   query=query, sources=None if chosen_source == 'All publishers' else [chosen_source],
                   topics=topics, model=model, version=ANALYSIS_VERSION)
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
        scope = (model, embedding_model, tuple(research_ids), overview['revision'])
        with st.form('article_question'):
            question = st.text_area('Research question', max_chars=2000, height=110,
                                    placeholder='What are the main findings across these selected articles?')
            action = st.radio('Research mode', ['Answer with citations', 'Search passages'], horizontal=True)
            submitted = st.form_submit_button('Research', type='primary', icon=':material/arrow_upward:',
                                              disabled=bool(error) or not embedding_model)
        if not embedding_model or error:
            st.caption('Saved insights remain available in the next tab. Connect a model in Research settings to ask a new question.')
        if submitted:
            st.session_state.pop('ai_research', None)
            try:
                if action == 'Answer with citations' and not ready:
                    raise IntelligenceError('Choose an installed analysis model in Research settings.')
                selected_articles = load_articles(research_ids)
                with st.spinner('Reading the relevant passages...'):
                    if action == 'Search passages':
                        answer = dict(question=question, passages=semantic_search(
                            question, selected_articles, embedding_model, client))
                    else:
                        answer = answer_question(question, selected_articles, model, embedding_model, client)
                    st.session_state['ai_research'] = dict(scope=scope, result=answer)
            except IntelligenceError as exc:
                st.error(str(exc))
        research = st.session_state.get('ai_research')
        if research and research['scope'] == scope:
            answer = research['result']
            st.html('<div class="section-title" style="margin-top:24px">' + escape(answer['question']) + '</div>')
            if answer.get('supported') is False:
                st.info('These articles do not contain enough evidence to answer this question.')
            labels = {p['id']: f'Source {index:02}' for index, p in enumerate(answer['passages'], 1)}
            for claim in answer.get('claims', []):
                _show_claim(claim, labels)
            with st.expander('Retrieved source passages', expanded='supported' not in answer):
                _show_evidence(answer['passages'], numbered=True)

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
