from pathlib import Path
from unittest.mock import patch

import pytest
from pypdf import PdfReader

from app.reports import create_pdf


@pytest.fixture
def article():
    return dict(id='sample123', title='Sample Article', url='https://example.org/article',
                source='Example', author='Writer', published='2026-01-01',
                fetched_at='2026-10-27T00:00:00Z',
                text='First paragraph of the article.\n\nSecond paragraph containing references.')


@pytest.fixture(autouse=True)
def isolated_output(tmp_path, monkeypatch):
    monkeypatch.setattr('app.reports.PDF_DIR', tmp_path)


def pdf_contents(path):
    reader = PdfReader(path)
    text = '\n'.join(page.extract_text() for page in reader.pages)
    uris = []
    for page in reader.pages:
        for reference in page.get('/Annots', []):
            annotation = reference.get_object()
            if annotation.get('/Subtype') == '/Link':
                action = annotation.get('/A', {})
                assert action.get('/S') == '/URI'
                uris.append(str(action['/URI']))
    return reader, text, uris


def test_pdf_contains_readable_article_metadata_and_source(article):
    _, text, links = pdf_contents(create_pdf(article))
    for expected in ('Sample Article', 'Writer', '2026-01-01', '2026-10-27T00:00:00Z',
                     'First paragraph of the article.', 'Second paragraph containing references.',
                     'Original source [1]', 'Page 1'):
        assert expected in text
    assert article['url'] in links


def test_markdown_links_have_readable_labels_and_real_destinations(article):
    target = 'https://example.net/topic_(science)?a=1&b=2'
    article['text'] = f'Read [the **original** study]({target}), then [related coverage](/related).'
    _, text, links = pdf_contents(create_pdf(article))
    assert 'the original study' in text
    assert 'related coverage' in text
    assert '](' not in text
    assert '**' not in text
    assert target not in text
    assert target in links
    assert 'https://example.org/related' in links


def test_article_structure_tables_and_image_references_remain_readable(article):
    article['text'] = (
        '# Research findings\n\nA **strong** result with *uncertainty*.\n\n'
        '- First finding\n- Second finding\n\n'
        '3. Third item\n4. Fourth item\n\n'
        '> Reported by the researchers.\n\n'
        '| Measure | Value |\n| --- | --- |\n| Accuracy | 92 percent |\n\n'
        '```python\nresult = "a < b"\n```\n\n'
        '![Experimental apparatus](https://example.net/image.png)'
    )
    _, text, links = pdf_contents(create_pdf(article))
    for expected in ('Research findings', 'strong', 'uncertainty', 'First finding',
                     'Second finding', '3.', 'Third item', '4.', 'Fourth item',
                     'Reported by the researchers.', 'Measure', 'Accuracy', '92 percent',
                     'result = "a < b"', '[Image: Experimental apparatus]'):
        assert expected in text
    assert '# Research' not in text
    assert '| ---' not in text
    assert 'https://example.net/image.png' not in links


@pytest.mark.parametrize('destination', [
    'javascript:alert(1)', 'file:///private/file', 'data:text/html,hello',
    'mailto:person@example.net', 'https://user:password@example.net/secret',
])
def test_article_cannot_create_unsafe_link_annotations(article, destination):
    article['text'] = f'[Untrusted destination]({destination})'
    article['url'] = destination
    _, _, links = pdf_contents(create_pdf(article))
    assert links == []


def test_raw_article_markup_is_text_and_never_executed(article):
    article['text'] = (
        '<b>Literal tag</b> & ordinary text\n\n'
        '<a href="file:///private/file">not an active link</a>\n\n'
        '<img src="https://example.net/image.png">'
    )
    _, text, links = pdf_contents(create_pdf(article))
    assert '<b>Literal tag</b>' in text
    assert 'not an active link' in text
    assert links and set(links) == {article['url']}


def test_multipage_article_preserves_last_paragraph_and_page_numbers(article):
    article['text'] = '\n\n'.join(
        f'Paragraph {index}: ' + 'The saved article provides supporting evidence. ' * 12
        for index in range(35)
    ) + '\n\nFINAL EVIDENCE MARKER'
    reader, text, links = pdf_contents(create_pdf(article))
    assert len(reader.pages) > 1
    assert 'Paragraph 0:' in text
    assert 'FINAL EVIDENCE MARKER' in text
    for number, page in enumerate(reader.pages, 1):
        assert f'Page {number}' in page.extract_text()
    assert article['url'] in links


def test_failed_generation_preserves_previous_pdf_and_cleans_temporary_file(article, tmp_path):
    previous = create_pdf(article).read_bytes()
    with patch('app.reports.SimpleDocTemplate.build', side_effect=RuntimeError('Rendering failed')):
        with pytest.raises(RuntimeError, match='Rendering failed'):
            create_pdf(article)
    assert (tmp_path / 'sample123.pdf').read_bytes() == previous
    assert sorted(path.name for path in tmp_path.iterdir()) == ['sample123.pdf']


def test_failed_replacement_preserves_previous_pdf_and_cleans_temporary_file(article, tmp_path):
    previous = create_pdf(article).read_bytes()
    with patch.object(Path, 'replace', side_effect=PermissionError('PDF viewer holds file open')):
        with pytest.raises(PermissionError):
            create_pdf(article)
    assert (tmp_path / 'sample123.pdf').read_bytes() == previous
    assert sorted(path.name for path in tmp_path.iterdir()) == ['sample123.pdf']
