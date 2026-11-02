"""A linked analytics component with bounded server-side evidence queries."""
import json
import time
from datetime import date
from pathlib import Path

import streamlit as st

from app import storage
from app.exports import metadata_csv
from app.intelligence import ANALYSIS_VERSION
from app.library_view import reading_room
from app.observatory_data import clean_filters, collections, snapshot
from app.theme import palette, theme_name
from app.ui import empty_state, page_header

ASSETS = Path(__file__).parent / 'assets'
COMPONENT_KEY = 'coverage_observatory'
_observatory = st.components.v2.component(
    'research_observatory', html=(ASSETS / 'observatory.html').read_text(encoding='utf-8'),
    css=(ASSETS / 'observatory.css').read_text(encoding='utf-8'),
    js=(ASSETS / 'observatory.js').read_text(encoding='utf-8'), isolate_styles=True,
)


@st.cache_data(show_spinner=False, max_entries=64)
def _snapshot(database, revision, serialized_filters, calendar_day):
    # The database path and mutation revision isolate cached results across local
    # libraries and invalidate them after content, collection, or facet changes.
    # Calendar day also invalidates publication windows without a library edit.
    return snapshot(json.loads(serialized_filters), as_of=calendar_day)


def render_analytics(overview):
    page_header('Analytics', 'Research observatory', 'Follow the coverage. Inspect the evidence. Find what connects.')
    if not overview['total']:
        empty_state('Start with a question worth exploring', 'Import a collection of articles to see the coverage take shape.')
        return
    choices = collections()
    state = st.session_state.get(COMPONENT_KEY, {})
    raw = state.get('filters', {}) if hasattr(state, 'get') else {}
    filters = clean_filters(raw, choices)
    result = _snapshot(str(storage.DB.resolve()), overview['revision'], json.dumps(filters, sort_keys=True),
                       date.today().isoformat())
    filters['page'] = result['page']
    request = raw.get('_request', 0) if isinstance(raw, dict) else 0
    request = request if isinstance(request, int) and 0 <= request < 10**9 else 0
    payload = dict(snapshot=result, filters=filters, collections=choices, colors=palette(),
                   theme=theme_name(), request=request, render_epoch=time.monotonic())
    export_request = state.get('export') if hasattr(state, 'get') else None
    if export_request and export_request != st.session_state.get('coverage_export_handled'):
        st.session_state['coverage_export_handled'] = export_request
        try:
            payload['download'] = dict(id=str(export_request), text=metadata_csv(**result['export_filters']).decode('utf-8-sig'))
        except (ValueError, OSError) as exc:
            st.warning(str(exc))
    mounted = _observatory(
        key=COMPONENT_KEY, data=payload, default={'filters': filters},
        on_filters_change=lambda: None, on_open_article_change=lambda: None,
        on_export_change=lambda: None, on_refresh_change=_snapshot.clear,
        width='stretch', height='content',
    )
    article_id = mounted.get('open_article')
    allowed = {row['id'] for row in result['rows']}
    allowed.update(row['id'] for rows in result['evidence'].values() for row in rows)
    if article_id in allowed:
        article = storage.get_article(article_id)
        if article:
            reading_room(article, storage.load_insight(article, 'qwen3:8b', ANALYSIS_VERSION))
