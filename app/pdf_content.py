"""Convert saved Markdown into safe reading content without fetching resources."""
from urllib.parse import urljoin, urlparse
from xml.sax.saxutils import escape

from markdown_it import MarkdownIt
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import HRFlowable, LongTable, Paragraph, TableStyle


def safe_link(url, base_url=''):
    """Allow navigable web links only; never interpret a URL as ReportLab markup."""
    try:
        resolved = urljoin(base_url, url)
        parsed = urlparse(resolved)
        if (parsed.scheme.lower() in ('http', 'https') and parsed.hostname
                and not parsed.username and not parsed.password
                and not any(ord(char) < 32 for char in resolved)):
            return resolved
    except ValueError:
        pass
    return None


def _inline(tokens, base_url):
    parts, links = [], []
    tags = {'strong_open': '<b>', 'strong_close': '</b>',
            'em_open': '<i>', 'em_close': '</i>'}
    for token in tokens or []:
        if token.type in tags:
            parts.append(tags[token.type])
        elif token.type == 'link_open':
            destination = safe_link(token.attrGet('href') or '', base_url)
            links.append(bool(destination))
            if destination:
                quoted = escape(destination, {'"': '&quot;'})
                parts.append(f'<link href="{quoted}" color="#1264A3">')
        elif token.type == 'link_close':
            if links.pop():
                parts.append('</link>')
        elif token.type == 'softbreak':
            # Extraction uses single newlines between article paragraphs.
            parts.append('<br/><br/>')
        elif token.type == 'hardbreak':
            parts.append('<br/>')
        elif token.type == 'code_inline':
            parts.append('<font name="Courier">' + escape(token.content) + '</font>')
        elif token.type == 'image':
            parts.append(escape('[Image: ' + (token.content or 'reference only') + ']'))
        else:
            # Includes raw HTML when encountered: article markup is always text.
            parts.append(escape(token.content))
    return ''.join(parts)


def _table(tokens, styles, base_url, width):
    rows, row = [], []
    cell_style = ParagraphStyle('ArticleTableCell', parent=styles['ArticleBodyCustom'],
                                fontSize=9, leading=12, spaceAfter=0)
    for token in tokens:
        if token.type == 'tr_open':
            row = []
        elif token.type == 'inline':
            row.append(Paragraph(_inline(token.children, base_url) or '&#160;', cell_style))
        elif token.type == 'tr_close':
            rows.append(row)
    count = max(len(row) for row in rows)
    table = LongTable(rows, colWidths=[width / count] * count, repeatRows=1,
                      hAlign='LEFT', splitInRow=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAF0F6')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    table.spaceAfter = 10
    return table


def article_flowables(text, styles, base_url, width):
    """Preserve basic article structure while emitting only controlled PDF markup."""
    tokens = MarkdownIt('commonmark', {'html': False}).enable('table').parse(text)
    result, lists = [], []
    quote_depth, heading, index = 0, None, 0
    while index < len(tokens):
        token = tokens[index]
        kind = token.type
        if kind in ('bullet_list_open', 'ordered_list_open'):
            lists.append({'next': int(token.attrGet('start') or 1)
                          if kind == 'ordered_list_open' else None, 'marker': None})
        elif kind in ('bullet_list_close', 'ordered_list_close'):
            lists.pop()
        elif kind == 'list_item_open':
            current = lists[-1]
            current['marker'] = '-' if current['next'] is None else f"{current['next']}."
            if current['next'] is not None:
                current['next'] += 1
        elif kind == 'list_item_close':
            lists[-1]['marker'] = None
        elif kind == 'blockquote_open':
            quote_depth += 1
        elif kind == 'blockquote_close':
            quote_depth -= 1
        elif kind == 'heading_open':
            heading = min(int(token.tag[1:]), 3)
        elif kind == 'heading_close':
            heading = None
        elif kind == 'table_open':
            end = index + 1
            while tokens[end].type != 'table_close':
                end += 1
            result.append(_table(tokens[index + 1:end], styles, base_url,
                                 width - 16 * len(lists) - 12 * quote_depth))
            index = end
        elif kind in ('inline', 'fence', 'code_block'):
            parent = styles[f'Heading{heading}'] if heading else styles['ArticleBodyCustom']
            indent = 16 * len(lists) + 12 * quote_depth
            style = ParagraphStyle('ArticleBlock', parent=parent,
                                   leftIndent=indent, bulletIndent=max(0, indent - 12))
            if quote_depth:
                style.textColor = colors.HexColor('#526477')
            if kind == 'inline':
                markup = _inline(token.children, base_url)
            else:
                style.fontName, style.fontSize, style.leading = 'Courier', 9, 12
                markup = escape(token.content.rstrip('\n')).replace(' ', '&#160;').replace('\n', '<br/>')
            bullet = lists[-1]['marker'] if lists else None
            if lists:
                lists[-1]['marker'] = None
            result.append(Paragraph(markup or '&#160;', style, bulletText=bullet))
        elif kind == 'hr':
            result.append(HRFlowable(width='100%', color=colors.HexColor('#E0E7EF'), spaceAfter=10))
        index += 1
    return result
