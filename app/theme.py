"""Shared semantic colors for the workspace, native controls, and charts."""
import streamlit as st


PALETTES = {
    'light': {
        'ink': '#252c28', 'body': '#434d3c', 'muted': '#626f5e', 'subtle': '#697461',
        'line': '#e4e7df', 'green': '#285447', 'paper': '#fafaf7',
        'sidebar': '#f0f1ec', 'surface': '#f0f1e9', 'hover': '#e5e9df',
        'active': '#e0e7de', 'active-ink': '#244d3d', 'link': '#285447',
        'primary': '#285447', 'on-primary': '#ffffff', 'positive': '#55734c',
        'positive-bg': '#edf1e8', 'pending': '#786b50', 'pending-bg': '#f1eee5',
        'card': '#264b3e', 'card-ink': '#f0f2e7', 'card-muted': '#c0cdb6',
        'card-line': '#4a6853', 'card-hover': '#355f4e', 'card-eyebrow': '#b5c8ad',
        'track': '#e9ecdf', 'fill': '#69805b', 'notice': '#eef1e8',
        'chart-1': '#61815e', 'chart-2': '#829570', 'chart-3': '#a1b28b',
        'panel': '#ffffff', 'tone-blue': '#3972ad', 'tone-purple': '#7b5aa5',
        'tone-teal': '#2b806f', 'tone-amber': '#9b6a22', 'tone-clay': '#ad5c5b',
        'tone-slate': '#61708a',
    },
    'dark': {
        'ink': '#e5e9df', 'body': '#ccd4c4', 'muted': '#a5b09c', 'subtle': '#99a68f',
        'line': '#303c32', 'green': '#9dbb8c', 'paper': '#151b17',
        'sidebar': '#111713', 'surface': '#202a22', 'hover': '#2b382d',
        'active': '#293c2e', 'active-ink': '#c0d6b0', 'link': '#b3ce9e',
        'primary': '#426d52', 'on-primary': '#f4f7ef', 'positive': '#b5cda2',
        'positive-bg': '#283a2c', 'pending': '#d7c8a3', 'pending-bg': '#383326',
        'card': '#213e2f', 'card-ink': '#edf2e5', 'card-muted': '#c0d0b5',
        'card-line': '#42604a', 'card-hover': '#2e503b', 'card-eyebrow': '#b6cea5',
        'track': '#2c382c', 'fill': '#9ab17e', 'notice': '#253227',
        'chart-1': '#9bb884', 'chart-2': '#799b76', 'chart-3': '#b7c8a0',
        'panel': '#1c2520', 'tone-blue': '#83b2e4', 'tone-purple': '#b8a2dd',
        'tone-teal': '#77c4b3', 'tone-amber': '#dbb170', 'tone-clay': '#e09b95',
        'tone-slate': '#a3b2cc',
    },
}


def initialize_theme():
    if 'dark_mode' not in st.session_state:
        st.session_state['dark_mode'] = st.query_params.get('theme') == 'dark'


def theme_name():
    return 'dark' if st.session_state.get('dark_mode', False) else 'light'


def palette():
    return PALETTES[theme_name()]


def remember_theme():
    # Session-specific; keeps the selected appearance on refresh without changing
    # process-global Streamlit settings or another visitor's theme.
    st.query_params['theme'] = theme_name()


def theme_variables():
    values = ';'.join(f'--{name}:{value}' for name, value in palette().items())
    return ':root{' + values + ';color-scheme:' + theme_name() + ';}'
