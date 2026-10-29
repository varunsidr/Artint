"""Topic discovery, inspectable previews, and explicit background imports."""
import math
import uuid
from datetime import date, timedelta
from html import escape

import streamlit as st

from app.discovery import DiscoveryError, LANGUAGES, PUBLISHERS, SearchSpec, highlighted, normalize_domain, phrases, search_articles
from app.discovery_imports import batches, cancel_batch, create_batch, ensure_worker, saved_urls
from app.extract import FETCH_HELP, FETCH_MODES
from app.capture_quality import ERROR_ACTIONS
from app.observatory_data import collections
from app.ui import display_date, empty_state, navigate, page_header, pagination, reset_page_if_changed

PAGE_SIZE = 10


@st.cache_data(ttl=600, max_entries=32, show_spinner=False)
def _search(spec, _progress=None):
    return search_articles(spec, progress=_progress)


def _change_selection(url, key):
    selected = set(st.session_state.get('discovery_selected', []))
    if st.session_state[key]:
        selected.add(url)
    else:
        selected.discard(url)
    st.session_state['discovery_selected'] = list(selected)


def _set_selection(urls):
    selected = list(dict.fromkeys(urls))
    st.session_state['discovery_selected'] = selected
    snapshot = st.session_state.get('discovery_result')
    if snapshot:
        for row in snapshot['items']:
            key = 'discovery_select_' + snapshot['id'] + '_' + row['id']
            st.session_state[key] = row['url'] in selected


def _open_collection(collection_id):
    from app.library_filters import clear_filters, remember_controls
    clear_filters()
    st.session_state['library_collection'] = collection_id
    remember_controls()
    navigate('Library')


def _remember_activity():
    st.session_state['discovery_show_imports'] = st.session_state['discovery_activity_open']


def _import_activity():
    ensure_worker()
    jobs = batches(5)
    if not jobs:
        return
    previous = st.session_state.get('discovery_job_states', {})
    changed = any(previous.get(job['id']) in ('queued', 'running') and job['state'] not in ('queued', 'running') for job in jobs)
    st.session_state['discovery_job_states'] = {job['id']: job['state'] for job in jobs}
    if changed:
        st.rerun()
    active = any(job['state'] in ('queued', 'running') for job in jobs)
    st.session_state.setdefault('discovery_show_imports', active)
    st.session_state['discovery_activity_open'] = st.session_state['discovery_show_imports']
    with st.expander('Import activity', expanded=False, key='discovery_activity_open',
                     on_change=_remember_activity, icon=':material/cloud_download:'):
        for job in jobs:
            st.write(job['title'])
            processed = job['saved'] + job['existing'] + job['failed'] + job['cancelled']
            state = 'Stopping after the current article' if job['cancel_requested'] and job['state'] == 'running' else job['state'].capitalize()
            st.progress(processed / job['total'], text=f"{state} · {processed} of {job['total']} processed")
            st.caption(f"{job['saved']} new · {job['existing']} already saved · {job['failed']} failed · {job['cancelled']} cancelled")
            if job['needs_review']:
                count = job['needs_review']
                st.warning(f"{count} saved capture{'s' if count != 1 else ''} {'need' if count != 1 else 'needs'} review. Open Source details for the findings.")
            if job['error']:
                st.warning(job['error'])
            if job['state'] in ('queued', 'running'):
                st.button('Stop after current article', key='stop_import_' + job['id'], disabled=bool(job['cancel_requested']),
                          on_click=cancel_batch, args=(job['id'],))
                st.caption('Imports continue when you switch pages. Interrupted batches resume after their five-minute worker lease expires.')
            if job['saved'] or job['existing']:
                if st.button('Open collection in Library', key='open_import_' + job['id']):
                    _open_collection(job['collection_id'])
                    st.rerun()
            if job['failures']:
                with st.expander(f"{job['failed']} unavailable articles"):
                    for failure in job['failures']:
                        st.text(failure['url'] + '\n' + failure['error'])
                        if failure['error_code']:
                            st.caption(ERROR_ACTIONS.get(failure['error_code'], ERROR_ACTIONS['extraction_error']))
            st.divider()


def render_discovery():
    page_header('Discover', 'Search articles', 'Start with a topic. Find the sources worth keeping.')
    st.html('<div class="discovery-intro"><span class="discovery-source-dot"></span>'
            'Free news discovery <span>·</span> Bing News RSS <span>·</span> Personal, non-commercial research</div>')
    with st.container(key='discovery_search'):
        with st.form('discover_articles', enter_to_submit=False):
            st.text_input('Topics', placeholder='Layoffs, housing policy, AI investment', max_chars=500,
                          help='Enter one to five topics separated by commas. Results can match any topic.',
                          key='discover_topics', persist_state='session')
            st.caption('Topic refinements')
            words, matching = st.columns([2, 1])
            with words:
                st.text_input('Priority keywords (optional)', placeholder='A company, location, or phrase to focus on', max_chars=400,
                              help='Separate words or phrases with commas. Matches are highlighted in titles and previews.',
                              key='discover_keywords', persist_state='session')
            with matching:
                st.selectbox('Keyword matching', ['Highlight only', 'Match any', 'Match all'],
                             help='Required keywords must appear in the title or search preview.',
                             key='discover_keyword_mode', persist_state='session')
            st.caption('General filters')
            publishers, language, number = st.columns([2, 1, 1])
            with publishers:
                st.multiselect('Publishers', list(PUBLISHERS), placeholder='All publishers',
                               key='discover_publishers', persist_state='session')
            with language:
                st.selectbox('Language', list(LANGUAGES), key='discover_language', persist_state='session')
            with number:
                st.selectbox('Results wanted', [5, 10, 25, 50, 100, 'Custom'], index=2,
                             key='discover_count', persist_state='session')
            with st.expander('Date and search options', icon=':material/tune:'):
                period, sorting = st.columns(2)
                with period:
                    st.selectbox('Date window', ['Available news', 'Today', 'Past 7 days', 'Past 30 days', 'Custom dates'],
                                 key='discover_period', persist_state='session')
                with sorting:
                    st.selectbox('Result order', ['Best match', 'Newest first'], key='discover_sort', persist_state='session')
                start, end, custom = st.columns(3)
                with start:
                    st.date_input('Custom start date', value=None, format='DD/MM/YYYY', key='discover_start', persist_state='session')
                with end:
                    st.date_input('Custom end date', value=None, format='DD/MM/YYYY', key='discover_end', persist_state='session')
                with custom:
                    st.number_input('Custom result count', min_value=1, max_value=100, value=25,
                                    help='Used when Results wanted is Custom.', key='discover_custom_count', persist_state='session')
                st.text_input('Additional publisher domains', placeholder='economist.com, science.org', max_chars=300,
                              help='Optional domains, without https:// or paths. Up to eight publishers total.',
                              key='discover_domains', persist_state='session')
                st.caption('Custom date fields apply only to Custom dates. Dates are reported by the feed; language is a provider search request. Availability and extraction are checked separately.')
            st.caption('This free feed mainly covers recent news. Older date windows may have few or no results.')
            submitted = st.form_submit_button('Search articles', type='primary', icon=':material/search:', width='stretch')
    if submitted:
        try:
            domains = [PUBLISHERS[name] for name in st.session_state['discover_publishers']]
            domains += [normalize_domain(value) for value in phrases(st.session_state['discover_domains'])]
            period = st.session_state['discover_period']
            start, end = None, None
            if period == 'Custom dates':
                start, end = st.session_state['discover_start'], st.session_state['discover_end']
                if not start and not end:
                    raise DiscoveryError('Choose at least one custom date, or select Available news.')
            elif period != 'Available news':
                days = {'Today': 0, 'Past 7 days': 6, 'Past 30 days': 29}[period]
                start, end = date.today() - timedelta(days=days), date.today()
            count = st.session_state['discover_count']
            spec = SearchSpec(topics=tuple(phrases(st.session_state['discover_topics'], limit=5, length=120)),
                              keywords=tuple(phrases(st.session_state['discover_keywords'])),
                              keyword_mode=st.session_state['discover_keyword_mode'], domains=tuple(dict.fromkeys(domains)),
                              language=st.session_state['discover_language'], start=start, end=end,
                              target=st.session_state['discover_custom_count'] if count == 'Custom' else count,
                              sort=st.session_state['discover_sort'])
            spec.validate()
            bar = st.progress(0, text='Searching publisher coverage…')
            try:
                result = _search(spec, _progress=lambda found, wanted: bar.progress(min(found / wanted, 1), text=f'Found {found} of {wanted} requested results…'))
            finally:
                bar.empty()
            for key in list(st.session_state):
                if key.startswith('discovery_select_'):
                    del st.session_state[key]
            st.session_state['discovery_result'] = dict(result, spec=spec, id=uuid.uuid4().hex[:12])
            st.session_state['discovery_selected'] = []
            st.session_state['discovery_page'] = 1
            base = ', '.join(spec.topics)[:85] + ' · ' + date.today().strftime('%d %b')
            names = {row['title'].casefold() for row in collections()}
            title, number = base, 2
            while title.casefold() in names:
                title = f'{base} ({number})'; number += 1
            st.session_state['discovery_collection_name'] = title
            st.session_state.pop('discovery_error', None)
        except (DiscoveryError, ValueError) as exc:
            st.session_state['discovery_error'] = str(exc)
    if st.session_state.get('discovery_error'):
        st.error(st.session_state['discovery_error'])
        if st.session_state.get('discovery_result'):
            st.caption('The results below are from your previous successful search.')
    polling = any(job['state'] in ('queued', 'running') for job in batches(5))
    st.fragment(_import_activity, run_every=timedelta(seconds=2) if polling else None,
                key='discovery_import_status')()
    snapshot = st.session_state.get('discovery_result')
    if not snapshot:
        empty_state('Follow a topic beyond your library', 'Choose a result target, scan the previews, and import the sources you want to study.')
        return
    spec, rows = snapshot['spec'], snapshot['items']
    st.html('<div class="section-title" style="margin-top:24px">Results for ' + escape(', '.join(spec.topics)) + '</div>')
    labels = [f"{len(rows)} of {snapshot['requested']} requested", spec.language, spec.sort]
    if spec.domains:
        labels.append(' · '.join(spec.domains))
    if spec.start or spec.end:
        labels.append(f"{spec.start or 'Any start'} → {spec.end or 'Any end'}")
    st.html('<div class="library-active-filters">' + ''.join('<span>' + escape(label) + '</span>' for label in labels) + '</div>')
    st.caption('Search previews, not saved articles. ' + snapshot['date_note'] + ' ' + snapshot['language_note'])
    for warning in snapshot['warnings']:
        st.info(warning)
    if spec.language not in ('English', 'French', 'German', 'Spanish', 'Portuguese'):
        st.info('Saved reading text supports Unicode. PDF exports may not render every character in this language yet.')
    if not rows:
        empty_state('No matching news found', 'Try a broader topic, fewer required keywords, or more publishers.')
        return
    known = saved_urls([row['url'] for row in rows])
    selected_urls = set(st.session_state.get('discovery_selected', []))
    selected = [row['url'] for row in rows if row['url'] in selected_urls]
    reset_page_if_changed('discovery', snapshot['id'])
    pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
    page = max(1, min(st.session_state['discovery_page'], pages))
    shown = rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
    with st.container(key='discovery_selection'):
        caption, select_page, select_all, clear = st.columns([2.2, 1.2, 1.3, 1.1], vertical_alignment='center')
        with caption:
            st.caption(f'{len(selected)} selected · {len(known)} already saved')
        with select_page:
            st.button('Select page', on_click=_set_selection, args=(selected + [row['url'] for row in shown],), width='stretch')
        with select_all:
            st.button(f'Select all {len(rows)}', on_click=_set_selection, args=([row['url'] for row in rows],), width='stretch')
        with clear:
            st.button('Clear selection', on_click=_set_selection, args=([],), disabled=not selected, width='stretch')
        name, capture, save = st.columns([2.4, 1.2, 1.4], vertical_alignment='bottom')
        with name:
            title = st.text_input('Collection name', max_chars=120, key='discovery_collection_name', persist_state='session')
        with capture:
            mode = st.selectbox('Article capture', list(FETCH_MODES), format_func=FETCH_MODES.get,
                                help=FETCH_HELP, key='discovery_fetch_mode', persist_state='session')
        with save:
            if st.button(f'Import selected ({len(selected)})', type='primary', disabled=not selected or not title.strip(), width='stretch'):
                try:
                    job_id = create_batch(selected, title.strip(), ', '.join(spec.topics), fetch_mode=mode)
                    states = st.session_state.get('discovery_job_states', {})
                    st.session_state['discovery_job_states'] = dict(states, **{job_id: 'queued'})
                    st.session_state['discovery_show_imports'] = True
                    _set_selection([])
                    ensure_worker()
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))
        st.caption('Imports run in the background and create reading PDFs. Later imports using this search and collection name add to the same collection. Already saved URLs are reused. AI analysis is separate in Research.')
    for row in shown:
        key = 'discovery_select_' + snapshot['id'] + '_' + row['id']
        st.session_state.setdefault(key, row['url'] in selected)
        with st.container(key='discovery_row_' + row['id']):
            choose, copy, action = st.columns([.3, 6, .8], vertical_alignment='center', gap='small')
            with choose:
                st.checkbox('Select ' + row['title'], key=key, label_visibility='collapsed', persist_state='session',
                            on_change=_change_selection, args=(row['url'], key))
            with copy:
                state = ' · Already saved' if row['url'] in known else ''
                st.html('<div class="article-meta">' + escape(row['source'] or row['domain']) + '<span>·</span>'
                        + escape(display_date(row['published'])) + escape(state) + '</div>'
                        + '<div class="article-title">' + highlighted(row['title'], spec.keywords) + '</div>'
                        + '<div class="discovery-excerpt">' + highlighted(row['snippet'], spec.keywords) + '</div>')
            with action:
                st.link_button('Open', row['url'], help='Open the publisher article in your browser', width='stretch')
    pagination(dict(page=page, pages=pages, total=len(rows), page_size=PAGE_SIZE), 'discovery')
    st.caption(f"Bing News RSS · Searched {display_date(snapshot['searched_at'])} · Personal, non-commercial use. Preview text belongs to its publisher. Access blocks and paywalls may prevent import.")
