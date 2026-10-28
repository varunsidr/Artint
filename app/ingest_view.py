"""Focused URL ingestion with results that survive a dashboard rerun."""
from html import escape

import streamlit as st

from app.extract import FETCH_HELP, FETCH_MODES, extract_article
from app.capture_quality import ERROR_ACTIONS, failure_details, saved_quality
from app.library_actions import FILE_LOCK
from app.reports import create_pdf
from app.storage import upsert
from app.ui import navigate, page_header


def render_import():
    page_header('Import', 'Make room for a new perspective.', 'Save public articles as clean reading copies, ready for research.')
    main, side = st.columns([2.2, 1], gap='large')
    with main:
        with st.form('import_articles'):
            st.html('<div class="section-title">Add article URLs</div>')
            raw = st.text_area('Public article URLs', placeholder='https://publisher.com/article\nhttps://another-source.com/story',
                               height=230, label_visibility='collapsed')
            st.caption('One URL per line · Up to 10 articles per import')
            mode = st.selectbox('Article capture', list(FETCH_MODES), format_func=FETCH_MODES.get,
                                help=FETCH_HELP, key='import_fetch_mode', persist_state='session')
            submitted = st.form_submit_button('Import articles', icon=':material/add:', type='primary')
        if submitted:
            urls = list(dict.fromkeys(line.strip() for line in raw.splitlines() if line.strip()))
            if not urls:
                st.warning('Add at least one article URL.')
            elif len(urls) > 10:
                st.warning('Import up to 10 articles at a time.')
            else:
                results = []
                progress = st.progress(0, text='Preparing your reading copies…')
                for index, url in enumerate(urls, 1):
                    try:
                        article = extract_article(url, mode=mode)
                        with FILE_LOCK:
                            article['pdf_path'] = str(create_pdf(article))
                            upsert(article)
                        results.append({'ok': True, 'title': article['title'], 'quality': saved_quality(article)})
                    except Exception as exc:
                        failure = failure_details(exc)
                        if isinstance(exc, OSError):
                            failure['code'] = 'pdf_failed'
                            failure['action'] = ERROR_ACTIONS['pdf_failed']
                        results.append({'ok': False, 'title': url, 'error': failure['message'], 'failure': failure})
                    progress.progress(index / len(urls), text=f'Processed {index} of {len(urls)} articles')
                st.session_state['import_results'] = results
                st.session_state.pop('library_zip_scope', None)
                st.rerun()
        results = st.session_state.get('import_results', [])
        if results:
            st.html('<div class="section-title" style="margin-top:22px">Import results</div>')
            for result in results:
                if result['ok']:
                    st.success(result['title'], icon=':material/check:')
                    quality = result.get('quality', {})
                    if quality.get('status') == 'needs_review':
                        st.warning('Saved with capture warnings. ' + ' '.join(w['message'] for w in quality['warnings'] if w['severity'] == 'warning'))
                else:
                    st.error(f'{result["title"]}: {result["error"]}')
                    if result.get('failure'):
                        st.caption(result['failure']['action'])
            st.button('Go to library', icon=':material/arrow_forward:', on_click=navigate, args=('Library',))
    with side:
        st.html('''<div class="import-guide"><div class="side-label">A source worth keeping</div>
          <div class="guide-step"><strong>01 &nbsp; Bring an article</strong>Paste a public article URL. We’ll extract the text and available publisher details.</div>
          <div class="guide-step"><strong>02 &nbsp; Keep a reading copy</strong>Each article gets its own searchable PDF, with a link back to the original.</div>
          <div class="guide-step"><strong>03 &nbsp; Find the connections</strong>Open Research for summaries, key takeaways, and questions grounded in your saved sources.</div>
          <div class="coverage-caption">Public articles only. Auto can render pages that need JavaScript. Paywalls and access restrictions are respected. Some pages may be unavailable or incomplete.</div></div>''')
