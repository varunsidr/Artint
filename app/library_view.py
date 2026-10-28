"""A searchable article list, reading room, and on-demand library exports."""
import json
import re
import sqlite3
from html import escape
from pathlib import Path

import streamlit as st
from markdown_it import MarkdownIt

from app.intelligence import ANALYSIS_VERSION
from app.capture_quality import saved_quality
from app import library_actions
from app.annotation_view import render_annotations
from app.backup_view import backup_dialog, open_backup
from app.storage import get_article, library_page, load_insight
from app.library_filters import clear_filters, render_controls
from app.exports import metadata_csv, page_pdf_zip, pdf_download_name
from app.ui import (
    display_date, empty_state, metrics, navigate, page_header, publisher,
    reading_minutes, topic_chips, pagination, reset_page_if_changed,
    literal_markdown,
)


def _reading_html(text, highlights=None):
    # Streamlit Markdown interprets paired currency dollar signs as mathematics.
    # CommonMark keeps prose literal and preserves extraction paragraph breaks.
    parser = MarkdownIt('commonmark', {'html': False, 'breaks': True}).enable('table').disable('image')
    tokens = parser.parse(text)
    ranges = [(item['start_offset'], item['end_offset']) for item in highlights or [] if item.get('current')]
    line_offsets, position = [0], 0
    for line in text.splitlines(keepends=True):
        position += len(line); line_offsets.append(position)
    for token in tokens:
        cursor = line_offsets[token.map[0]] if token.map else 0
        limit = line_offsets[min(token.map[1], len(line_offsets)-1)] if token.map else len(text)
        for child in token.children or []:
            if child.type == 'link_open':
                child.attrSet('target', '_blank')
                child.attrSet('rel', 'noopener noreferrer')
            if ranges and child.type in ('text', 'code_inline'):
                found = text.find(child.content, cursor, limit)
                if found >= 0:
                    child.meta['source_span'] = (found, found + len(child.content))
                    cursor = found + len(child.content)
    if ranges:
        def marked_text(children, index, options, environment):
            child = children[index]
            source = child.meta.get('source_span')
            content = child.content
            if not source:
                rendered = escape(content)
            else:
                spans = sorted((max(start, source[0])-source[0], min(end, source[1])-source[0])
                               for start, end in ranges if start < source[1] and end > source[0])
                merged = []
                for start, end in spans:
                    if merged and start <= merged[-1][1]:
                        merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                    else:
                        merged.append((start, end))
                pieces, cursor = [], 0
                for start, end in merged:
                    pieces.extend([escape(content[cursor:start]), '<mark class="saved-highlight">', escape(content[start:end]), '</mark>'])
                    cursor = end
                pieces.append(escape(content[cursor:]))
                rendered = ''.join(pieces)
            return '<code>' + rendered + '</code>' if child.type == 'code_inline' else rendered
        parser.renderer.rules['text'] = marked_text
        parser.renderer.rules['code_inline'] = marked_text
    rendered = parser.renderer.render(tokens, parser.options, {})
    return re.sub(r'<br\s*/?>\n', '<br><br>\n', rendered)


@st.dialog('Reading room', width='large', on_dismiss='rerun')
def reading_room(article, insight):
    from app.ai_dashboard import render_saved_insight
    latest = get_article(article['id'])
    if not latest:
        st.info('This article is no longer in the library.')
        return
    article = latest
    insight = load_insight(article, 'qwen3:8b', ANALYSIS_VERSION)
    annotations = library_actions.annotation_state(article['id'])

    st.html(f'<h2 class="reader-title">{escape(article["title"])}</h2>'
            f'<div class="reader-meta">{escape(publisher(article))} &nbsp; / &nbsp; '
            f'{escape(display_date(article.get("published")))} &nbsp; / &nbsp; '
            f'{reading_minutes(article)} min read<br>{escape(article.get("author") or "Author unavailable")}</div>')
    actions = st.columns([1, 1, 2])
    with actions[0]:
        st.link_button('Original source', article['url'], icon=':material/arrow_outward:')
    with actions[1]:
        pdf = Path(article['pdf_path']) if article.get('pdf_path') else None
        if pdf and pdf.is_file():
            st.download_button('Download PDF', pdf.read_bytes(), file_name=pdf_download_name(article),
                               mime='application/pdf', icon=':material/download:')
    reading, analysis, notes, details = st.tabs(['Article', 'Analysis', 'Notes & highlights', 'Source details'])
    with reading:
        if saved_quality(article)['status'] == 'needs_review':
            st.warning('This reading copy has capture warnings. Check Source details and compare it with the original before relying on it.')
        # Show image references as text rather than making the browser fetch them.
        with st.container(height=450, border=False):
            st.html('<article class="reading-copy">' + _reading_html(article['text'], annotations['highlights']) + '</article>')
    with analysis:
        if insight:
            render_saved_insight(article, insight, key_prefix='reader')
        else:
            empty_state('No saved analysis yet', 'Open Research to generate a summary and source-backed takeaways.')
    with notes:
        render_annotations(article, annotations)
    with details:
        st.caption('Retrieved ' + display_date(article['fetched_at']))
        st.caption('Captured with ' + ('browser rendering' if article.get('fetch_method') == 'browser' else 'HTML extraction'))
        quality = saved_quality(article)
        if quality['status'] == 'not_checked':
            st.caption('Capture checks have not been recorded for this saved copy.')
        else:
            st.write('Capture checks: ' + ('Needs review' if quality['status'] == 'needs_review' else 'Automated checks passed'))
            st.caption('Automated checks flag possible problems. They do not verify completeness or factual accuracy.')
            for finding in quality['warnings']:
                (st.warning if finding['severity'] == 'warning' else st.info)(literal_markdown(finding['message']))
            evidence = quality.get('evidence', {})
            if evidence.get('reference_paragraphs'):
                st.caption(f"Matched {evidence['matched_paragraphs']} of {evidence['reference_paragraphs']} substantial page text blocks. Lists and table rows are included where detectable.")
        st.write(f"{article['word_count']:,} extracted words")
        st.caption('A reading copy of the saved article. Check the original publisher for updates.')
        references = json.loads(article.get('links_json') or '[]')
        st.write(f'{len(references)} article links · {len(json.loads(article.get("images_json") or "[]"))} image references')
        for index, link in enumerate(references, 1):
            st.link_button(f'Source link {index}', link)
        with st.expander('Remove from library', icon=':material/delete:'):
            st.caption('Deletes this article, saved analysis, notes, tags, highlights, collection memberships and its managed PDF. Download a library backup first if you may need them later.')
            confirmed = st.checkbox('Delete this article and its saved work', key='delete_confirm_' + article['id'])
            if st.button('Delete article', key='delete_article_' + article['id'], disabled=not confirmed):
                try:
                    result = library_actions.delete_article(article['id'])
                    st.session_state['library_notice'] = 'Article and saved work deleted.' + (' PDF cleanup will retry when the file is available.' if result['cleanup_pending'] else '')
                    st.rerun()
                except (ValueError, OSError, sqlite3.Error) as exc:
                    st.warning(str(exc))


def _exports(result, filters, sort, revision):
    with st.popover('Export library', icon=':material/download:', width='stretch',
                     key='library_export_open', on_change='rerun'):
        st.caption(f"Metadata: {result['total']:,} matching articles. PDFs: current page only.")
        csv_scope = (revision, filters, sort)
        if st.button('Prepare metadata CSV', key='prepare_library_csv', width='stretch'):
            try:
                st.session_state['library_csv'] = metadata_csv(sort=sort, **filters)
                st.session_state['library_csv_scope'] = csv_scope
            except ValueError as exc:
                st.warning(str(exc))
        if st.session_state.get('library_csv_scope') == csv_scope:
            st.download_button('Download metadata CSV', st.session_state['library_csv'],
                               file_name='article_library.csv', mime='text/csv', width='stretch')
        zip_scope = (revision, tuple(a['id'] for a in result['items']))
        if st.button('Prepare page PDF ZIP', width='stretch'):
            try:
                data, count = page_pdf_zip(result['items'])
                st.session_state['library_zip'] = data
                st.session_state['library_zip_count'] = count
                st.session_state['library_zip_scope'] = zip_scope
            except (ValueError, OSError) as exc:
                st.warning(str(exc))
        if st.session_state.get('library_zip_scope') == zip_scope:
            st.download_button('Download page PDF ZIP', st.session_state['library_zip'],
                               file_name='article_pdfs.zip', mime='application/zip', width='stretch')
            st.caption(f"{st.session_state['library_zip_count']} PDFs included · 50 MB maximum per batch")
        st.divider()
        st.button('Backup & restore', icon=':material/inventory_2:', width='stretch', on_click=open_backup)
    # Keep the modal outside the popover's overlay/focus context.
    if st.session_state.get('library_backup_open'):
        backup_dialog()


def _research_desk(overview):
    count, total = overview['analyzed'], overview['total']
    st.html('<div class="research-card"><div class="eyebrow">THE RESEARCH DESK</div>'
            '<h2>Connect the dots.<br>Keep the sources.</h2>'
            '<p>Ask across selected articles. Follow each answer back to the passages behind it.</p>'
            f'<div class="card-foot">{total:,} saved sources · {count:,} article analyses</div></div>')
    with st.container(key='research_cta'):
        st.button('Open research', icon=':material/arrow_forward:', on_click=navigate,
                  args=('Research',), width='stretch')
    topics = overview['topics']
    st.html('<div class="side-section"><div class="side-label">Common topics</div>'
            + (topic_chips(topics[:10]) if topics else '<div class="coverage-caption">Topics appear after analysis.</div>')
            + '</div>')
    progress = 100 * count / total if total else 0
    st.html('<div class="side-section"><div class="side-label">Analysis coverage</div>'
            f'<div style="font-size:23px;color:var(--positive)">{progress:.0f}%'
            '<span style="font-size:10px;color:var(--subtle);margin-left:8px">of your library</span></div>'
            f'<div class="coverage-track"><div class="coverage-fill" style="width:{progress}%"></div></div>'
            f'<div class="coverage-caption">{count:,} of {total:,} articles have current saved insights.'
            '<br>Source passages remain available for checking.</div></div>')


def render_library(overview):
    page_header('Library', 'Article library', 'Read, compare, and return to what matters.', action=True)
    if st.session_state.get('library_notice'):
        st.success(st.session_state.pop('library_notice'))
    minutes = round(overview['words'] / 220)
    metrics([
        ('Saved articles', f"{overview['total']:,}", ''),
        ('Publishers', f"{len(overview['publishers']):,}", ''),
        ('Reading time', f'{minutes / 60:,.1f}' if minutes >= 60 else minutes, 'hours' if minutes >= 60 else 'min'),
        ('Analyzed', f"{overview['analyzed']:,}", f"/ {overview['total']:,}"),
    ])
    if not overview['total']:
        empty_state('A place for your next discovery', 'Import an article URL to begin your personal research library.')
        st.button('Add your first article', on_click=navigate, args=('Import articles',), type='primary')
        st.button('Restore a library backup', icon=':material/inventory_2:', on_click=open_backup)
        if st.session_state.get('library_backup_open'):
            backup_dialog()
        return

    try:
        filters, order, page_size, labels = render_controls(overview)
    except ValueError as exc:
        st.warning(str(exc))
        st.button('Clear filters', on_click=clear_filters)
        return
    scope = (filters, order, page_size)
    reset_page_if_changed('library', scope)
    result = library_page(page=st.session_state['library_page'], page_size=page_size, sort=order, **filters)
    with st.container(key='library_actions'):
        caption, reset, export = st.columns([4, 1, 1.35], vertical_alignment='center')
        with caption:
            st.html(f'<div class="section-note" style="margin:5px 0">{result["total"]:,} '
                    f'{"article matches" if result["total"] == 1 else "articles match"} your selection</div>')
        with reset:
            st.button('Clear filters', key='clear_library_filters', on_click=clear_filters,
                      disabled=not labels, width='stretch')
        with export:
            _exports(result, filters, order, overview['revision'])
    if labels:
        st.html('<div class="library-active-filters" aria-label="Active library filters">'
                + ''.join(f'<span>{escape(label)}</span>' for label in labels) + '</div>')
    main, aside = st.columns([3.3, 1.15], gap='large')
    with main:
        st.html('<div class="list-heading"><span>Article / source</span><span>Reading & analysis</span></div>')
        for article in result['items']:
            insight = article['insight']
            excerpt = insight['summary']['text'] if insight else article['excerpt'].replace('\n', ' ')
            with st.container(key='article_row_' + article['id']):
                detail, state, action = st.columns([6.6, 1.5, 1], gap='small')
                with detail:
                    st.html('<div class="article-meta">'
                            f'<span class="publisher-mark">{escape(publisher(article)[0].upper())}</span>'
                            f'{escape(publisher(article))}<span>·</span>{escape(display_date(article.get("published")))}</div>'
                            f'<div class="article-title">{escape(article["title"])}</div>'
                            f'<div class="article-excerpt">{escape(excerpt[:240])}</div>' + topic_chips(article.get('tags', [])[:4]))
                with state:
                    state_class = 'article-state' if insight else 'article-state pending'
                    st.html(f'<span class="{state_class}">{"Analyzed" if insight else "Not analyzed"}</span>'
                            f'<div class="reading-time">{reading_minutes(article)} min read</div>')
                with action:
                    if st.button('Read', key='read_' + article['id'], help='Open reading copy and analysis'):
                        full = get_article(article['id'])
                        if full:
                            reading_room(full, load_insight(full, 'qwen3:8b', ANALYSIS_VERSION))
                        else:
                            st.info('This article is no longer in the library. Refresh your selection.')
        if not result['items']:
            empty_state('No matching articles', 'Broaden your selection or clear the filters to return to your library.')
        pagination(result, 'library')
    with aside:
        _research_desk(overview)
