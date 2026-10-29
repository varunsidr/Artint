"""Bounded plain-text previews; saved reading copies remain unchanged."""
import re

from markdown_it import MarkdownIt


def plain_excerpt(text, limit=240, title=''):
    # Parse only a bounded prefix. Collect visible prose, omitting image labels,
    # destinations and HTML; never render publisher-controlled markup here.
    parser = MarkdownIt('commonmark', {'html': True})
    pieces = []
    prefix = re.sub(r'<(script|style)\b[^>]*>.*?(?:</\1\s*>|$)', '', (text or '')[:2400], flags=re.I | re.S)
    for token in parser.parse(prefix):
        if token.type == 'inline':
            for child in token.children or []:
                if child.type in ('text', 'code_inline'):
                    pieces.append(child.content)
                elif child.type in ('softbreak', 'hardbreak'):
                    pieces.append(' ')
            pieces.append(' ')
    value = re.sub(r'https?://\S+', '', ''.join(pieces))
    value = re.sub(r'\s+', ' ', value).strip()
    if title and value.startswith(title):
        value = value[len(title):].lstrip(' .:–—-')
    if len(value) <= limit:
        return value
    return value[:max(0, limit - 1)].rstrip() + '…' if limit else ''
