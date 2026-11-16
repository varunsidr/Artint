"""Offline saved-research navigation, explicit persistence and evidence removal."""
import sqlite3
from datetime import datetime, timezone

import streamlit as st

from app import research_sessions
from app.ui import empty_state, literal_markdown


def _view(value):
    st.session_state['research_workspace_view'] = value


def _move(delta):
    st.session_state['research_history_page'] = max(1, st.session_state.get('research_history_page', 1) + delta)


def save_control(result):
    if st.button('Save research', key='research_save_result', icon=':material/bookmark_add:'):
        try:
            research_sessions.save_result(result)
            st.session_state['research_saved_notice'] = 'Saved. Reopen this result from Saved research, including after restarting the app.'
            st.rerun()
        except (ValueError, sqlite3.Error) as exc:
            st.warning(literal_markdown(str(exc)))


def research_navigation():
    saved = st.session_state.get('research_workspace_view') == 'saved'
    new, history, count = st.columns([1, 1, 4], vertical_alignment='center')
    with new:
        st.button('New research', key='research_view_new', on_click=_view, args=('new',),
                  type='secondary' if saved else 'primary', width='stretch', icon=':material/edit_note:')
    with history:
        st.button('Saved research', key='research_view_saved', on_click=_view, args=('saved',),
                  type='primary' if saved else 'secondary', width='stretch', icon=':material/bookmarks:')
    with count:
        total = research_sessions.sessions_page(page_size=1)['total']
        st.caption(f'{total:,} saved {"result" if total == 1 else "results"} · available offline')
    if notice := st.session_state.pop('research_saved_notice', None):
        st.success(notice)
    if saved:
        render_saved_research()
    return saved


def render_saved_research():
    from app.ai_dashboard import _research_answer

    st.caption('Original answers and quoted evidence, saved on this device. Source updates do not rewrite them. '
               'Deleting a source article also deletes research saved from it.')
    query = st.text_input('Find saved research', max_chars=256, placeholder='Search your saved questions', key='research_history_search')
    if query != st.session_state.get('research_history_previous_query', ''):
        st.session_state['research_history_page'] = 1
        st.session_state['research_history_previous_query'] = query
    page = research_sessions.sessions_page(query, st.session_state.get('research_history_page', 1))
    st.session_state['research_history_page'] = page['page']
    if not page['items']:
        empty_state('No saved research here yet' if not query else 'No matching saved questions',
                    'Use Save research below a completed answer or passage search to keep its evidence.')
        return
    previous, position, following = st.columns([1, 3, 1], vertical_alignment='center')
    with previous:
        st.button('Previous saved', disabled=page['page'] <= 1, on_click=_move, args=(-1,), icon=':material/chevron_left:')
    with position:
        st.caption(f"Page {page['page']} of {page['pages']} · {page['total']:,} saved {'result' if page['total'] == 1 else 'results'}")
    with following:
        st.button('Next saved', disabled=page['page'] >= page['pages'], on_click=_move, args=(1,), icon=':material/chevron_right:')
    choices = {row['id']: row for row in page['items']}
    key = 'research_history_selected'
    if st.session_state.get(key) not in choices:
        st.session_state[key] = next(iter(choices))
    ident = st.selectbox('Saved question', list(choices), key=key,
        format_func=lambda value: literal_markdown(choices[value]['question'][:100]) + ' · '
            + choices[value]['created_at'].replace('T', ' ').replace('+00:00', ' UTC'))
    saved = None
    try:
        saved = research_sessions.load_session(ident)
        if saved is None:
            st.info('This result was removed, possibly because one of its source articles was deleted.')
            return
        when = datetime.fromisoformat(saved['created_at']).astimezone(timezone.utc)
        st.caption('Saved ' + when.strftime('%d %b %Y, %H:%M UTC'))
        if saved['changed_sources']:
            amount = saved['changed_sources']
            st.info(f"{amount} source {'copy has' if amount == 1 else 'copies have'} changed since this research. The original answer and passages are shown below.")
        if saved['unverified_sources']:
            st.caption(f"{saved['unverified_sources']} sources have no comparable revision fingerprint, including remapped identifiers. Check the original saved evidence.")
        _research_answer(saved['result'], key_prefix='saved_' + ident)
    except (ValueError, sqlite3.Error) as exc:
        st.warning(literal_markdown(str(exc)))
    with st.expander('Remove saved research', icon=':material/delete:'):
        st.caption('Removes this saved answer and its quoted evidence from this library. Article copies and analyses remain. Earlier downloaded exports/backups keep their copies.')
        confirmed = st.checkbox('Delete this saved result and its evidence', key='research_delete_confirm_' + ident)
        if st.button('Delete saved research', key='research_delete_saved', disabled=not confirmed):
            research_sessions.delete_session(ident)
            active = st.session_state.get('ai_research')
            if saved and active and active['result'] == saved['result']:
                st.session_state.pop('ai_research', None)
                st.session_state.pop('ai_research_error', None)
            st.rerun()
