"""Reviewable portable backups and non-overwriting restore."""
import hashlib
import sqlite3
from datetime import datetime

import streamlit as st

from app import library_backup, storage


def open_backup():
    st.session_state['library_export_open'] = False
    st.session_state['library_backup_open'] = True


def _dismiss_backup():
    st.session_state['library_backup_open'] = False


@st.dialog('Library backup & restore', width='large', on_dismiss=_dismiss_backup)
def backup_dialog():
    if not st.session_state.get('library_backup_open', True):
        st.rerun()
    backup, restore = st.tabs(['Create backup', 'Restore backup'])
    with backup:
        st.write('Keep your research together.')
        st.caption('Includes saved article text, notes, tags, highlights, collections, saved analyses, cached search vectors and managed PDFs. Import jobs are not included.')
        with storage.connect() as con:
            revision = con.execute('SELECT revision FROM library_state WHERE id=1').fetchone()[0]
        scope = (str(storage.DB.resolve()), revision)
        if st.button('Prepare full backup', type='primary'):
            try:
                with st.spinner('Preparing your library backup…'):
                    blob, stats = library_backup.create_backup()
                st.session_state['portable_backup'] = dict(blob=blob, stats=stats, scope=scope,
                                                           name='article-library-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.zip')
            except (ValueError, OSError, sqlite3.Error) as exc:
                st.warning(str(exc))
        prepared = st.session_state.get('portable_backup')
        if prepared and prepared['scope'] == scope:
            stats = prepared['stats']
            st.download_button('Download full library backup', prepared['blob'], file_name=prepared['name'], mime='application/zip', type='primary')
            st.caption(f"{stats['articles']:,} articles · {stats['pdfs']:,} PDFs · {len(prepared['blob']) / 1024**2:.1f} MB")
            if stats['missing_pdfs']:
                st.info(f"{stats['missing_pdfs']} reading PDFs were unavailable or outside the managed folder. Their article text and annotations are included.")
        st.caption('Version 1 supports up to 10,000 articles, 128 MB of metadata, 20 MB per PDF and a 250 MB ZIP. Large backups may take a moment.')
    with restore:
        st.write('Restore missing research without replacing your current copies.')
        st.caption('Existing article text and nonempty notes are kept. Tags, nonduplicate highlights and collection memberships are merged for matching saved text. Changed copies are left alone.')
        uploaded = st.file_uploader('Library backup ZIP', type=['zip'], max_upload_size=250, key='portable_restore_upload')
        if uploaded is not None:
            blob = uploaded.getvalue()
            fingerprint = hashlib.sha256(blob).hexdigest()
            if st.button('Inspect backup'):
                try:
                    with st.spinner('Checking backup integrity…'):
                        data = library_backup.inspect_backup(blob)
                        preview = library_backup.restore_preview(data)
                    st.session_state['portable_restore_check'] = dict(sha256=fingerprint, preview=preview)
                except (ValueError, OSError, sqlite3.Error) as exc:
                    st.session_state.pop('portable_restore_check', None)
                    st.warning(str(exc))
            checked = st.session_state.get('portable_restore_check', {})
            if checked.get('sha256') == fingerprint:
                preview = checked['preview']
                st.info(f"{preview['new']:,} new articles · {preview['existing']:,} already present · {preview['notes']:,} notes · {preview['highlights']:,} highlights in this backup")
                if preview['changed_text']:
                    st.warning(f"{preview['changed_text']} existing copies have different text. Their saved text and annotations will be kept.")
                if st.button('Restore missing data', type='primary'):
                    try:
                        with st.spinner('Restoring your research…'):
                            result = library_backup.restore_backup(blob)
                        st.session_state['library_notice'] = f"Restored {result['articles']} articles, {result['notes']} notes, {result['highlights']} highlights and {result['pdfs']} PDFs. Existing copies were kept."
                        if result['annotation_limit_skips']:
                            st.session_state['library_notice'] += f" {result['annotation_limit_skips']} tags/highlights could not be merged because an article reached its annotation limit. They remain in your backup."
                        st.session_state.pop('portable_backup', None)
                        st.session_state.pop('portable_restore_check', None)
                        st.session_state['library_backup_open'] = False
                        st.rerun()
                    except (ValueError, OSError, sqlite3.Error) as exc:
                        st.warning(str(exc))
