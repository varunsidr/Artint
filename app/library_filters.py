"""Library controls with durable values independent of widget cleanup."""
from copy import deepcopy
from datetime import date, timedelta

import streamlit as st

from app.facets import ENTITIES, LENSES
from app.observatory_data import collections
from app.storage import SORTS, library_filter_options

DEFAULTS = dict(search='', collection='', publishers=[], sort='Newest saved', status='All articles',
                published='Any time', date_from=None, date_until=None, length='Any length',
                lens='', entity='', topics=[], tags=[], page_size=25, ai_coverage=False)
PERIODS = {'Past 30 days': 30, 'Past 90 days': 90, 'Past year': 365}
LENGTHS = {'Any length': (None, None), 'Up to 5 min': (None, 1100),
           '6–15 min': (1101, 3300), 'Over 15 min': (3301, None)}


def remember_controls():
    saved = st.session_state.get('library_controls', {})
    st.session_state['library_controls'] = {
        name: deepcopy(st.session_state.get('library_' + name, saved.get(name, default)))
        for name, default in DEFAULTS.items()
    }


def clear_filters():
    for name, default in DEFAULTS.items():
        if name not in ('sort', 'page_size'):
            st.session_state['library_' + name] = deepcopy(default)
    st.session_state['library_page'] = 1
    remember_controls()


def build_filters(values, today=None):
    """One predicate contract for list results, counts, and metadata exports."""
    values = dict(DEFAULTS, **values)
    today = today or date.today()
    minimum, maximum = LENGTHS[values['length']]
    filters = dict(query=values['search'], collection_id=values['collection'] or None,
                   sources=values['publishers'] or None, status=values['status'], topics=values['topics'],
                   lens=values['lens'] or None, entity=values['entity'] or None,
                   min_words=minimum, max_words=maximum, tags=values['tags'])
    period = values['published']
    if period in PERIODS:
        filters.update(start_date=(today - timedelta(days=PERIODS[period])).isoformat(),
                       end_date=today.isoformat(), date_status='dated')
    elif period == 'Date unavailable':
        filters['date_status'] = 'undated'
    elif period == 'Custom dates':
        start, end = values['date_from'], values['date_until']
        if start and end and start > end:
            raise ValueError('Published from must be on or before Published until.')
        if start or end:
            filters.update(start_date=start.isoformat() if start else None,
                           end_date=end.isoformat() if end else None, date_status='dated')
    return filters


def active_labels(values, names):
    labels = []
    if values['search'].strip():
        labels.append('Search: ' + values['search'].strip())
    if values['collection']:
        labels.append(names[values['collection']])
    if values['publishers']:
        labels.append(values['publishers'][0] if len(values['publishers']) == 1 else f"{len(values['publishers'])} publishers")
    if values['status'] != 'All articles':
        labels.append(values['status'])
    if values['published'] != 'Any time':
        if values['published'] == 'Custom dates':
            start, end = values['date_from'], values['date_until']
            if start or end:
                labels.append(f"Published: {start:%d %b %Y}" if start and not end else
                              f"Published until {end:%d %b %Y}" if end and not start else
                              f"{start:%d %b %Y} – {end:%d %b %Y}")
        else:
            labels.append(values['published'])
    if values['length'] != 'Any length':
        labels.append(values['length'] + ' read')
    if values['lens']:
        labels.append(next(lens['label'] for lens in LENSES if lens['id'] == values['lens']))
    if values['entity']:
        labels.append(values['entity'])
    if values['topics']:
        labels.append(f"{len(values['topics'])} saved topic{'s' if len(values['topics']) != 1 else ''}")
    if values.get('tags'):
        labels.append(f"{len(values['tags'])} personal tag{'s' if len(values['tags']) != 1 else ''}")
    return labels


def render_controls(overview):
    saved = st.session_state.get('library_controls', {})
    for name, default in DEFAULTS.items():
        st.session_state.setdefault('library_' + name, deepcopy(saved.get(name, default)))
    names = {row['id']: row['title'] for row in collections()}
    names[''] = 'All collections'
    if st.session_state['library_collection'] not in names:
        st.session_state['library_collection'] = ''
    # Topic/tag validity belongs to the scoped query below, not the global
    # overview's capped label list (which can omit a valid rare selection).
    for name, options in (('publishers', overview['publishers']),):
        st.session_state['library_' + name] = [value for value in st.session_state['library_' + name] if value in options]

    def control(name):
        return dict(key='library_' + name, on_change=remember_controls, persist_state='session')

    with st.container(key='library_toolbar'):
        search, collection, publishers, sorting = st.columns([2.2, 1.15, 1.6, 1.15], vertical_alignment='bottom')
        with search:
            st.text_input('Search articles', placeholder='Search your library', max_chars=256,
                          icon=':material/search:', **control('search'))
        with collection:
            st.selectbox('Collection', list(names), format_func=names.get, **control('collection'))
        with publishers:
            st.multiselect('Publishers', overview['publishers'], placeholder='All publishers', **control('publishers'))
        with sorting:
            st.selectbox('Sort articles', list(SORTS), **control('sort'))
        with st.expander('General filters', icon=':material/tune:'):
            status, published, length = st.columns(3)
            with status:
                st.selectbox('Analysis status', ['All articles', 'Analyzed', 'Needs analysis'], **control('status'))
            with published:
                st.selectbox('Published', ['Any time', *PERIODS, 'Custom dates', 'Date unavailable'], **control('published'))
            with length:
                st.selectbox('Reading length', list(LENGTHS), help='Estimated at 220 words per minute.', **control('length'))
            if st.session_state['library_published'] == 'Custom dates':
                start, end = st.columns(2)
                with start:
                    st.date_input('Published from', value=None, format='DD/MM/YYYY', **control('date_from'))
                with end:
                    st.date_input('Published until', value=None, format='DD/MM/YYYY', **control('date_until'))
            st.selectbox('Articles per page', [25, 50, 100], **control('page_size'))
            st.caption('General filters apply to every topic. Date ranges exclude articles without a publication date.')

        values = {name: st.session_state['library_' + name] for name in DEFAULTS}
        base = build_filters(dict(values, topics=[], tags=[], lens='', entity=''))
        if st.session_state.get('library_topic_scope') != base:
            st.session_state['library_ai_coverage'] = False
            st.session_state['library_lens'] = ''
            st.session_state['library_entity'] = ''
            st.session_state['library_topic_scope'] = base
        options = library_filter_options(**base, retain_topics=st.session_state['library_topics'],
                                         retain_tags=st.session_state['library_tags'])
        for name in ('topics', 'tags'):
            st.session_state['library_' + name] = [value for value in st.session_state['library_' + name] if value in options[name]]
        st.session_state['library_tags'] = st.session_state['library_tags'][:20]
        if st.session_state['library_lens'] not in options['lenses']:
            st.session_state['library_lens'] = ''
        if st.session_state['library_entity'] not in options['entities']:
            st.session_state['library_entity'] = ''
        with st.expander('Topic filters', icon=':material/filter_alt:'):
            st.caption(f"Choices from all {options['total']:,} articles matching your general filters; {options['analyzed']:,} have current saved analyses.")
            if len(options['topics']) == 100 or len(options['tags']) == 100:
                st.caption('Up to 100 labels are shown, retaining valid selections. Narrow your search or collection to find less common labels.')
            topics, tags = st.columns(2)
            with topics:
                st.multiselect('Saved analysis topics', options['topics'], placeholder='Topics in matching articles',
                               disabled=not options['topics'],
                               help='Labels from current saved analyses in this search or collection. Selecting several matches any label.', **control('topics'))
            with tags:
                st.multiselect('Personal tags', list(options['tags']), format_func=options['tags'].get,
                               max_selections=20,
                               disabled=not options['tags'], placeholder='Tags in matching articles',
                               help='Your saved tags in this search or collection. Matches any selected tag.', **control('tags'))
            if not options['topics']:
                st.caption('No saved analysis topics in this selection. Narrow the articles by keyword, or analyze them in Research to add topic labels.')
            if options['lenses'] or options['entities']:
                st.checkbox('Show AI investment filters',
                            help='Optional AI investment keyword lenses and tracked companies. These are separate from the general topic labels above.', **control('ai_coverage'))
            else:
                st.session_state['library_ai_coverage'] = False
            if st.session_state['library_ai_coverage']:
                lens, company = st.columns(2)
                with lens:
                    labels = {'': 'All coverage themes', **{item['id']: item['label'] for item in LENSES if item['id'] in options['lenses']}}
                    st.selectbox('AI investment coverage', list(labels), format_func=labels.get,
                                 help='English keyword signals in matching saved articles; not sentiment or verified claims.', **control('lens'))
                with company:
                    st.selectbox('Tracked company mentioned', ['', *[name for name in ENTITIES if name in options['entities']]],
                                 format_func=lambda value: value or 'All tracked companies', **control('entity'))
            else:
                st.session_state['library_lens'] = ''
                st.session_state['library_entity'] = ''
            st.caption('Topics and tags match any selected value within each control. Selections combine with your general filters.')
    values = {name: st.session_state['library_' + name] for name in DEFAULTS}
    remember_controls()
    return build_filters(values), values['sort'], values['page_size'], active_labels(values, names)
