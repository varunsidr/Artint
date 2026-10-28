"""Local article research workspace. Run with Streamlit from the project directory."""
import streamlit as st

from app.ai_dashboard import render_intelligence
from app.analytics_view import render_analytics
from app.ingest_view import render_import
from app.library_view import render_library
from app.discovery_view import render_discovery
from app.discovery_imports import ensure_worker
from app.library_actions import recover_pending_deletions
from app.storage import library_overview
from app.ui import apply_styles, render_sidebar


st.set_page_config(page_title='Article Intelligence', page_icon=':material/book_2:', layout='wide',
                   initial_sidebar_state='expanded')
apply_styles()
recover_pending_deletions()
ensure_worker()
overview = library_overview()
view = render_sidebar(overview['total'])

if view == 'Library':
    render_library(overview)
elif view == 'Analytics':
    render_analytics(overview)
elif view == 'Research':
    render_intelligence(overview)
elif view == 'Import articles':
    render_import()
elif view == 'Search articles':
    render_discovery()
