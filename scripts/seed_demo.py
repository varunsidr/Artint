"""Build an isolated, offline demo. Never seed the user's default library."""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PUBLISHERS = [
    ('Field Notes', 'field-notes.example'),
    ('Signal Review', 'signal-review.example'),
    ('Compute Journal', 'compute-journal.example'),
    ('Research Desk', 'research-desk.example'),
]
TOPICS = [
    ('The infrastructure bill comes due', 'Infrastructure',
     'Capital expenditure on data centres is only the beginning of the infrastructure spending story. '
     'Our imaginary operator separates the cost of buildings, equipment and maintenance before estimating utilisation.'),
    ('What a funding round leaves unanswered', 'Valuations',
     'A funding round gives an imaginary company a headline valuation. The example asks readers to compare '
     'venture capital terms, expected cash needs and earnings multiples before interpreting that number.'),
    ('From pilot projects to recurring revenue', 'Revenue',
     'Revenue growth and enterprise adoption are different measurements. In this fictional scenario, '
     'a research team tracks repeat purchases, productivity gains and the return on investment of a pilot project.'),
    ('Following the financing behind the build-out', 'Financing',
     'Debt and vendor financing can move risk between participants. An invented financing chain includes '
     'a supplier, a customer and a lender; readers can trace credit exposure without assuming every loan is equivalent.'),
    ('Power availability becomes the planning constraint', 'Capacity',
     'Electricity supply, cooling and power grid connections constrain an imaginary data centre. '
     'The example compares capacity constraints with the risk of overcapacity when demand arrives later than expected.'),
    ('What the dot-com comparison can and cannot explain', 'History',
     'Historical parallels with the dot-com period help frame questions about technology bubbles. '
     'This fictional classroom exercise distinguishes speculative investment risks from useful long-lived infrastructure.'),
]
COMPANIES = [('Microsoft', 'OpenAI'), ('Nvidia', 'Amazon'), ('Alphabet', 'Anthropic'), ('Meta', 'Microsoft')]
QUOTE = 'A useful research collection keeps the assumptions beside the evidence.'


def demo_articles():
    """Original synthetic text, fixed dates and reserved domains; no copied news."""
    for index in range(36):
        title, topic, premise = TOPICS[index % len(TOPICS)]
        publisher, domain = PUBLISHERS[index % len(PUBLISHERS)]
        company_a, company_b = COMPANIES[(index // 3) % len(COMPANIES)]
        month, day = 1 + (index * 7 % 10), 2 + (index * 3 % 24)
        published = date(2026, month, day).isoformat()
        url = f'https://{domain}/demo/{index + 1:02d}'
        article_id = hashlib.sha256(url.encode()).hexdigest()[:16]
        text = (
            'Synthetic demonstration article. This is original fictional material, not a news report. '
            'It does not describe actual financial results or investment advice.\n\n'
            f'## The question\n\n{premise}\n\n'
            f'This exercise mentions {company_a} and {company_b} only to demonstrate company filters. '
            'The organisations have not supplied or endorsed this example. All scenarios below are invented.\n\n'
            '## Reading the evidence\n\n'
            'The fictional research desk compares a cautious scenario with a higher-demand scenario. '
            'In the first, customers adopt tools gradually and equipment sits idle between contracts. '
            'In the second, real demand grows and operators see stronger cash flow. These are assumptions '
            'to inspect, rather than a forecast or a conclusion that an AI bubble exists.\n\n'
            f'{QUOTE} A total alone can hide differences in time periods, reporting definitions and '
            'the populations being measured. Record those differences before combining estimates. '
            'A source can discuss investment risks and productivity gains in the same piece.\n\n'
            '## Questions to carry forward\n\n'
            '- Which assumptions change the conclusion most?\n'
            '- What would count as evidence against the preferred explanation?\n'
            '- Does the comparison use the same reporting period?\n\n'
            'This synthetic reading copy exists to demonstrate library search, coverage analytics, '
            'PDF export, notes and source-linked highlights. The reserved example domain is not a live publisher. '
            'Replace the demo with sources you are authorised to collect when beginning your own research.'
        )
        yield dict(id=article_id, url=url, title=f'{title} | Demo {index + 1:02d}',
                   source=domain, author=f'{publisher} / Synthetic desk', published=published,
                   fetched_at=f'{published}T12:00:00Z', text=text, word_count=len(text.split()),
                   links_json='[]', images_json='[]', pdf_path='', demo_topic=topic)


def seed_demo(output):
    """Require a new/empty destination, then temporarily redirect storage and PDFs."""
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Demo destination must be a new or empty directory. Choose another --output path.')
    # Import only after validating the destination. Importing these modules does not open a library.
    from app import library_actions, reports, storage
    from app.intelligence import ANALYSIS_VERSION, article_passages

    original_db, original_pdfs = storage.DB, reports.PDF_DIR
    output.mkdir(parents=True, exist_ok=True)
    storage.DB, reports.PDF_DIR = output / 'library.db', output / 'pdfs'
    try:
        storage.create_collection('demo-ai-investment', 'AI investment / Synthetic demo', 'Fictional demonstration sources')
        storage.create_collection('demo-reading-list', 'Reading list / Synthetic demo', 'Example personal organisation')
        articles = list(demo_articles())
        for index, article in enumerate(articles):
            article['pdf_path'] = str(reports.create_pdf(article))
            storage.upsert(article, collection_id='demo-ai-investment')
            if index < 12:
                passages = article_passages(article)
                quote_source = next(passage['id'] for passage in passages if QUOTE in passage['text'])
                storage.save_insight(article, 'qwen3:8b', ANALYSIS_VERSION, {
                    'summary': {'text': 'Synthetic example analysis: ' + TOPICS[index % 6][2],
                                'sources': [article['id'] + ':P1']},
                    'key_points': [{'text': QUOTE, 'sources': [quote_source]}],
                    'topics': [article['demo_topic'], 'Synthetic demo'],
                    'model': 'Hand-authored demo fixture / no model run', 'partial': False,
                })
        featured = max(articles, key=lambda article: (article['fetched_at'], article['id']))
        library_actions.save_organization(featured['id'],
            note='Synthetic research note: compare the assumptions before drawing a conclusion.\n\n'
                 'Follow up on utilisation, reporting periods and the original evidence. '
                 'This collection demonstrates the workflow; it contains no real reporting.',
            tags=['Follow up', 'Reading list'], collection_ids=['demo-ai-investment', 'demo-reading-list'])
        library_actions.add_highlight(featured['id'], QUOTE,
            note='Keep this question visible when comparing sources. Synthetic example annotation.')
        manifest = dict(synthetic=True, articles=len(articles), publishers=len(PUBLISHERS),
                        example_analyses=12, featured_article=featured['id'], database='library.db', pdfs='pdfs',
                        notice='Fictional articles and hand-authored analyses. No publisher or model calls were made.')
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        return manifest
    finally:
        storage.DB, reports.PDF_DIR = original_db, original_pdfs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'demo',
                        help='New or empty demo directory (default: output/demo). Existing files are never overwritten.')
    args = parser.parse_args()
    try:
        manifest = seed_demo(args.output)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Created {manifest['articles']} synthetic articles in {args.output.resolve()}")
    print('See README.md for the two environment overrides to open this isolated demo.')


if __name__ == '__main__':
    main()
