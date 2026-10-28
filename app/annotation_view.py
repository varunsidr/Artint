"""Native, theme-aware personal organization controls inside the reader."""
import math

import streamlit as st

from app import library_actions as actions
from app.observatory_data import collections
from app.ui import literal_markdown


def _default(key, value):
    return None if key in st.session_state else value


def _save(article_id):
    try:
        actions.save_organization(article_id, note=st.session_state['reader_note_' + article_id],
                                  tags=st.session_state['reader_tags_' + article_id],
                                  collection_ids=st.session_state['reader_collections_' + article_id],
                                  new_collection=st.session_state['reader_new_collection_' + article_id])
        state = actions.annotation_state(article_id)
        st.session_state['reader_collections_' + article_id] = state['collections']
        st.session_state['reader_tags_' + article_id] = ', '.join(state['tags'])
        st.session_state['reader_new_collection_' + article_id] = ''
        st.session_state['reader_flash_' + article_id] = ('success', 'Notes and organization saved.')
    except ValueError as exc:
        st.session_state['reader_flash_' + article_id] = ('warning', str(exc))


def _highlight(article):
    ident = article['id']
    try:
        actions.add_highlight(ident, st.session_state['reader_quote_' + ident],
                              note=st.session_state['reader_quote_note_' + ident],
                              occurrence=(st.session_state['reader_occurrence_' + ident] or 1) - 1,
                              expected_text_hash=actions.text_hash(article['text']))
        st.session_state['reader_quote_' + ident] = ''
        st.session_state['reader_quote_note_' + ident] = ''
        st.session_state['reader_occurrence_' + ident] = 1
        st.session_state['reader_flash_' + ident] = ('success', 'Highlight saved.')
    except ValueError as exc:
        st.session_state['reader_flash_' + ident] = ('warning', str(exc))


def _edit_highlight(article_id, highlight_id, *, remove=False):
    try:
        if remove:
            actions.remove_highlight(article_id, highlight_id)
        else:
            actions.update_highlight_note(article_id, highlight_id, st.session_state['highlight_note_' + highlight_id])
        st.session_state['reader_flash_' + article_id] = ('success', 'Highlight removed.' if remove else 'Highlight note saved.')
    except ValueError as exc:
        st.session_state['reader_flash_' + article_id] = ('warning', str(exc))


def render_annotations(article, state):
    ident = article['id']
    message = st.session_state.pop('reader_flash_' + ident, None)
    if message:
        (st.success if message[0] == 'success' else st.warning)(message[1])
    names = {row['id']: row['title'] for row in collections() if row['id']}
    with st.form('reader_organization_' + ident):
        st.text_area('Your notes', value=_default('reader_note_' + ident, state['note']), max_chars=20_000, height=150,
                     placeholder='What matters here? Add your own observations and questions.', key='reader_note_' + ident)
        st.text_input('Personal tags', value=_default('reader_tags_' + ident, ', '.join(state['tags'])), max_chars=1000,
                      placeholder='AI infrastructure, Follow up, Reading list', help='Separate tags with commas. Up to 20 tags, 40 characters each.', key='reader_tags_' + ident)
        st.multiselect('Collections', list(names), default=_default('reader_collections_' + ident, [member for member in state['collections'] if member in names]),
                       format_func=names.get, placeholder='Add to a collection', key='reader_collections_' + ident)
        st.text_input('New collection (optional)', value=_default('reader_new_collection_' + ident, ''), max_chars=120, placeholder='Create a project for this source', key='reader_new_collection_' + ident)
        st.form_submit_button('Save notes & organization', type='primary', on_click=_save, args=(ident,))
    st.caption('Your notes and tags stay separate from the publisher text and AI analysis.')
    with st.expander('Add a highlight', icon=':material/format_quote:'):
        with st.form('reader_highlight_' + ident):
            st.text_area('Passage to highlight', value=_default('reader_quote_' + ident, ''), max_chars=5000, height=110,
                         help='Paste an exact passage from the saved article. A shorter phrase works best across formatted text.', key='reader_quote_' + ident)
            st.text_area('Highlight note (optional)', value=_default('reader_quote_note_' + ident, ''), max_chars=5000, height=80, key='reader_quote_note_' + ident)
            st.number_input('Occurrence', min_value=1, max_value=200, value=_default('reader_occurrence_' + ident, 1),
                            help='Use 2 for the second matching passage if the same words appear more than once.', key='reader_occurrence_' + ident)
            st.form_submit_button('Save highlight', on_click=_highlight, args=(article,))
    highlights = state['highlights']
    st.write(f"{len(highlights)} saved highlight{'s' if len(highlights) != 1 else ''}")
    if not highlights:
        st.caption('Keep a passage and the thought it sparked. Highlights appear in the Article tab where their text can be located.')
        return
    pages = max(1, math.ceil(len(highlights) / 10))
    page = st.selectbox('Highlights page', list(range(1, pages + 1)), key='reader_highlight_page_' + ident) if pages > 1 else 1
    for highlight in highlights[(page-1)*10:page*10]:
        with st.expander(literal_markdown(highlight['quote'].replace('\n', ' ')[:85]), expanded=False):
            st.text(highlight['quote'])
            if not highlight['current']:
                st.warning('From an earlier saved copy. Its original position no longer matches the current text.')
            else:
                st.caption('Anchored to the current saved copy.')
            with st.form('highlight_edit_' + highlight['id']):
                st.text_area('Highlight note', value=_default('highlight_note_' + highlight['id'], highlight['note']), max_chars=5000, height=90, key='highlight_note_' + highlight['id'])
                save, remove = st.columns(2)
                with save:
                    st.form_submit_button('Save note', on_click=_edit_highlight, args=(ident, highlight['id']))
                with remove:
                    st.form_submit_button('Remove highlight', on_click=_edit_highlight, args=(ident, highlight['id']), kwargs={'remove': True})
