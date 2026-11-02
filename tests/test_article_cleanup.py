"""Publisher promotions must not become article text or RAG evidence."""
import json

from bs4 import BeautifulSoup
import pytest

from app.article_cleanup import remove_publisher_promotions
from app.capture_quality import inspect_capture, tokens
from app.extract import IncompleteArticle, _article_from_html, extract_document
from app.intelligence import article_passages
from app import reports
from pypdf import PdfReader
from tests.test_browser_extraction import PARAGRAPHS


URL = 'https://techtrendske.co.ke/fictional-capture-test/'
PROMOTION = (
    'Go to\u00a0<a href="https://techtrendske.co.ke/">TECHTRENDSKE.co.ke</a>\u00a0'
    'for more tech and business news from the African continent and across the world. '
    'Follow us on\u00a0<a href="https://whatsapp.com/channel/fixture">WhatsApp</a>,\u00a0'
    '<a href="https://t.me/fixture">Telegram</a>,\u00a0'
    '<a href="https://twitter.com/fixture">Twitter</a>, and\u00a0'
    '<a href="https://www.facebook.com/fixture/">Facebook</a>, or\u00a0'
    '<a href="https://newsletter.example/subscribe">subscribe to our weekly newsletter</a>\u00a0'
    'to ensure you don’t miss out on any\u00a0'
    '<a href="https://techtrendske.co.ke/category/news/">future updates</a>. '
    'Send tips to info@techtrendsmedia.co.ke')
HEADLINE = '<h2>Fictional network expansion report</h2>'


def document(block='', position='middle'):
    body = ['<p>' + paragraph + '</p>' for paragraph in PARAGRAPHS]
    if position == 'before':
        body = [block, HEADLINE, *body]
    elif position == 'after':
        body = [HEADLINE, *body, block]
    else:
        body = [HEADLINE, body[0], block, *body[1:]]
    return '<html><head><title>Fictional report</title></head><body><article>' + ''.join(body) + '</article></body></html>'


@pytest.mark.parametrize('position', ['before', 'middle', 'after'])
@pytest.mark.parametrize('tag', ['p', 'div'])
def test_promotion_is_removed_before_extraction_without_losing_following_article(position, tag):
    html = document(f'<{tag}>{PROMOTION}</{tag}>', position)
    article = _article_from_html(html, URL)
    assert 'Follow us on' not in article['text'] and 'Send tips' not in article['text']
    assert 'newsletter.example' not in article['text']
    assert 'Fictional network expansion report' in article['text']
    for paragraph in PARAGRAPHS:
        assert paragraph in article['text']
    assert article['word_count'] == len(tokens(article['text']))
    assert not any('Follow us' in passage['text'] for passage in article_passages(article))
    assert not any('whatsapp.com' in link for link in json.loads(article['links_json']))
    quality = json.loads(article['quality_json'])
    assert quality['evidence']['cleanup']['publisher_promotion_blocks_removed'] == 1
    assert quality['evidence']['paragraph_coverage'] == 1


@pytest.mark.parametrize('block', [
    '<blockquote><p>' + PROMOTION + '</p></blockquote>',
    '<p><q>' + PROMOTION + '</q></p>',
    '<p><code>' + PROMOTION + '</code></p>',
    '<p>The researchers examined the following publisher appeal: ' + PROMOTION + '</p>',
    '<p>' + PROMOTION + ' The researchers found that the campaign doubled subscriptions.</p>',
    '<p>Follow us on social media was the slogan. The company discussed WhatsApp and Telegram subscriptions.</p>',
    '<p>Researchers compared <a href="https://t.me/study">Telegram</a> and '
    '<a href="https://whatsapp.com/study">WhatsApp</a> as distribution channels for a newsletter.</p>',
    '<section>' + HEADLINE + '<p>' + PROMOTION + '</p><p>' + PARAGRAPHS[0] + '</p></section>',
])
def test_quotes_reporting_and_structural_containers_are_preserved(block):
    soup = BeautifulSoup(document(block), 'html.parser')
    before = str(soup)
    removed = remove_publisher_promotions(soup, URL)
    if block.startswith('<section>'):
        assert removed == 1 and soup.find('h2') and PARAGRAPHS[0] in soup.get_text()
    else:
        assert removed == 0 and str(soup) == before


def test_split_paragraphs_are_cleaned_and_malformed_links_do_not_break_capture():
    home, follow = PROMOTION.split('Follow us on', 1)
    block = '<p>' + home + '</p><p>Follow us on' + follow + '<a href="http://[broken"></a></p>'
    article = _article_from_html(document(block), URL)
    assert 'Follow us' not in article['text'] and 'Go to' not in article['text']
    assert json.loads(article['quality_json'])['evidence']['cleanup']['publisher_promotion_blocks_removed'] == 2


def test_another_publishers_home_link_does_not_authorize_removing_a_news_paragraph():
    home = PROMOTION.split('Follow us on')[0]
    soup = BeautifulSoup('<p>' + home + '</p>', 'html.parser')
    assert remove_publisher_promotions(soup, 'https://different.example/story') == 0


def test_removing_promotion_cannot_turn_an_excerpt_into_an_eligible_article():
    short = '<article><h1>Short excerpt</h1><p>A brief excerpt about network expansion.</p><p>' + PROMOTION + '</p></article>'
    with pytest.raises(IncompleteArticle):
        extract_document(short, URL, mode='html')


def test_cleanup_diagnostics_still_detect_missing_editorial_paragraphs():
    paragraphs = PARAGRAPHS * 2
    html = '<article><h1>Fictional report</h1><p>' + PROMOTION + '</p>' + ''.join(
        '<p>' + text + '</p>' for text in paragraphs) + '</article>'
    article = dict(url=URL, text=PARAGRAPHS[0], title='Fictional report')
    quality = inspect_capture(article, html)
    assert quality['evidence']['cleanup']['publisher_promotion_blocks_removed'] == 1
    assert any(warning['code'] == 'possible_missing_content' for warning in quality['warnings'])


def test_new_reading_pdf_uses_the_cleaned_body(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, 'PDF_DIR', tmp_path)
    article = _article_from_html(document('<p>' + PROMOTION + '</p>'), URL)
    pdf = reports.create_pdf(article)
    content = '\n'.join(page.extract_text() for page in PdfReader(pdf).pages)
    assert 'Follow us on' not in content and 'Send tips' not in content
    assert 'network expansion report' in content
    assert 'regional electricity systems' in content
