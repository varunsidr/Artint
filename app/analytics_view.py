"""Coverage analytics and optional explicitly requested corpus discovery."""
import streamlit as st

from app.observatory_view import render_analytics as render_coverage
from app.topic_discovery_view import render_topic_discovery


def render_analytics(overview):
    mode = st.radio('Analytics workspace', ['Coverage analytics', 'Topic discovery (experimental)'],
                    horizontal=True, key='analytics_workspace')
    if mode == 'Topic discovery (experimental)':
        render_topic_discovery(overview)
    else:
        render_coverage(overview)
