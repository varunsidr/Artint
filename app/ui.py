"""Shared presentation primitives for the local research workspace."""
import math
import re
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from app.theme import initialize_theme, remember_theme, theme_variables


NAVIGATION = {
    'Library': ':material/book_2:',
    'Analytics': ':material/bar_chart:',
    'Research': ':material/neurology:',
    'Search articles': ':material/travel_explore:',
    'Import articles': ':material/add:',
}


def literal_markdown(value):
    """Keep untrusted widget/alert labels literal, including image syntax."""
    return re.sub(r'([\\`*_{}\[\]()<>#!|+\-.])', r'\\\1', str(value))


def apply_styles():
    initialize_theme()
    stylesheet = Path(__file__).parent / 'assets' / 'dashboard.css'
    st.html('<style>' + stylesheet.read_text(encoding='utf-8') + theme_variables() + '</style>')


def navigate(view):
    st.session_state['workspace_view'] = view
    if view != 'Research':
        st.session_state.pop('research_focus_article', None)


def open_article_research(article_id):
    navigate('Research')
    st.session_state['research_focus_article'] = article_id


def publisher(article):
    value = article.get('source') or urlparse(article.get('url', '')).hostname or 'Unknown'
    return value.removeprefix('www.')


def display_date(value):
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return f'{date.day} {date:%b %Y}'
    except (ValueError, TypeError, AttributeError):
        return 'Date unavailable'


def reading_minutes(article):
    return max(1, math.ceil(article.get('word_count', 0) / 220))


def page_header(section, title, description, action=False):
    st.html(f'<div class="breadcrumb">WORKSPACE<span>/</span>{escape(section.upper())}</div>')
    left, right = st.columns([4, 1], vertical_alignment='center')
    with left:
        st.html(f'<h1 class="page-heading">{escape(title)}</h1>'
                f'<p class="page-description">{escape(description)}</p>')
    with right:
        if action:
            st.button('Import articles', icon=':material/add:', type='primary',
                      on_click=navigate, args=('Import articles',), width='stretch')
        else:
            st.html('<div class="top-note"><span class="status-dot"></span>Personal workspace</div>')


def metrics(items):
    cells = ''.join(
        f'<div class="metric"><div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(str(value))}'
        f'<small>{escape(unit)}</small></div></div>'
        for label, value, unit in items
    )
    st.html('<div class="metrics">' + cells + '</div>')


def topic_chips(topics):
    return ''.join(f'<span class="topic-chip">{escape(topic)}</span>' for topic in topics)


def empty_state(title, description):
    st.html(f'<div class="empty-state"><h3>{escape(title)}</h3>'
            f'<p>{escape(description)}</p></div>')


def render_sidebar(article_count):
    with st.sidebar:
        st.html('''<div class="brand"><div class="brand-symbol">
          <svg width="23" height="23" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M5 5h6v14H5zM14 5h5v14h-5z" stroke="currentColor" stroke-width="1.2"/>
          <path d="M8 8v8M16.5 8v8" stroke="currentColor" stroke-width="1.2"/></svg>
          </div><div><div class="brand-name">article</div><div class="brand-sub">INTELLIGENCE</div></div></div>''')
        st.html('<div class="nav-caption">YOUR WORKSPACE</div>')
        current = st.session_state.setdefault('workspace_view', 'Library')
        for label, icon in NAVIGATION.items():
            st.button(label, icon=icon, key='nav_' + label.lower().replace(' ', '_'),
                      type='primary' if current == label else 'secondary', width='stretch',
                      on_click=navigate, args=(label,))
        count = article_count
        st.html(f'<div class="sidebar-note"><strong>{count:,} saved {"article" if count == 1 else "articles"}</strong>'
                '<br>Your library stays on this device.</div>')
        with st.container(key='theme_switch'):
            st.toggle('Dark mode', key='dark_mode', on_change=remember_theme)
        st.html('<div class="sidebar-footer"><span class="workspace-mark">P</span>'
                '<div>Personal library<br><span style="font-size:10px;color:var(--subtle)">Local workspace</span></div></div>')
    return current


def reset_page_if_changed(key, scope):
    # Page state belongs to the view, not a widget that Streamlit removes when
    # another view is rendered. Also repair sessions created by older versions.
    st.session_state.setdefault(key + '_page', 1)
    if st.session_state.get(key + '_scope') != scope:
        st.session_state[key + '_page'] = 1
        st.session_state[key + '_scope'] = scope


def _step_page(key, delta):
    st.session_state[key + '_page'] = st.session_state.get(key + '_page', 1) + delta


def _choose_page(key):
    st.session_state[key + '_page'] = st.session_state[key + '_page_input']


def pagination(result, key):
    st.session_state[key + '_page'] = result['page']
    with st.container(key=key + '_pagination', horizontal=True, vertical_alignment='center', gap='small'):
        start = (result['page'] - 1) * result['page_size'] + 1 if result['total'] else 0
        end = min(result['page'] * result['page_size'], result['total'])
        with st.container(width='stretch'):
            st.caption(f'{start:,}–{end:,} of {result["total"]:,} articles')
        if result['pages'] > 1:
            with st.container(horizontal=True, width='content', vertical_alignment='center', gap='small'):
                st.button('Previous', key=key + '_previous', icon=':material/chevron_left:',
                          disabled=result['page'] <= 1, on_click=_step_page, args=(key, -1))
                with st.popover(f'{result["page"]:,} / {result["pages"]:,}', help='Go to a page'):
                    st.session_state[key + '_page_input'] = result['page']
                    st.number_input('Go to page', min_value=1, max_value=result['pages'], step=1,
                                    key=key + '_page_input', on_change=_choose_page, args=(key,))
                st.button('Next', key=key + '_next', icon=':material/chevron_right:',
                          disabled=result['page'] >= result['pages'], on_click=_step_page, args=(key, 1))
