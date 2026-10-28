import tempfile
import os
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

from app.pdf_content import article_flowables, safe_link

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = Path(os.getenv('ARTICLE_PDF_DIR', str(ROOT / 'output' / 'pdfs')))

def create_pdf(article):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{article['id']}.pdf"
    target = PDF_DIR / filename
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ArticleTitleCustom', parent=styles['Title'], fontSize=19, leading=24,
        textColor=colors.HexColor('#17324D'), spaceAfter=14, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='ArticleBodyCustom', parent=styles['BodyText'], fontSize=10.5,
        leading=16, spaceAfter=10))
    styles.add(ParagraphStyle(name='SmallCustom', parent=styles['Normal'], fontSize=8.5,
        leading=12, textColor=colors.HexColor('#526477')))
    story = [Paragraph(escape(article['title']), styles['ArticleTitleCustom'])]
    for k, v in [('Publisher', article['source']), ('Author', article['author']),
                 ('Published', article['published']), ('Retrieved (UTC)', article['fetched_at'])]:
        if v:
            story.append(Paragraph(f'<b>{k}:</b> {escape(str(v))}', styles['SmallCustom']))
    destination = safe_link(article['url'])
    source_link = escape(article['url'])
    if destination:
        quoted = escape(destination, {'"': '&quot;'})
        source_link = f'<link href="{quoted}" color="#1264A3">{source_link}</link>'
    story += [Paragraph(f'<b>Original source [1]:</b> {source_link}', styles['SmallCustom']),
              Spacer(1, 15), HRFlowable(width='100%', thickness=1, color=colors.HexColor('#E0E7EF')),
              Spacer(1, 15)]
    story.extend(article_flowables(article['text'], styles, article['url'], width=491.27))
    story += [Spacer(1, 15), Paragraph('<b>Source reference</b>', styles['Heading3']),
              Paragraph(f'[1] {escape(article["source"] or "Source")}: ' + source_link,
                        styles['SmallCustom']),
              Paragraph('This document is an extracted reading copy, not a pixel-perfect page archive. '
                        'Content may be incomplete; original publishers retain their rights.', styles['SmallCustom'])]
    def footer(canvas, pdf):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(52, 30, 'Article Intelligence | Source [1]')
        canvas.drawRightString(543, 30, f'Page {pdf.page}')
        canvas.restoreState()
    # Same-directory replacement preserves an existing PDF if rendering fails.
    with tempfile.NamedTemporaryFile(dir=PDF_DIR, prefix=f'.{article["id"]}-', suffix='.tmp', delete=False) as handle:
        temporary = Path(handle.name)
    try:
        doc = SimpleDocTemplate(str(temporary), pagesize=(595.27, 841.89), rightMargin=52,
            leftMargin=52, topMargin=50, bottomMargin=55, title=article['title'], author='Article Intelligence')
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
