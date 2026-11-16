"""Original synthetic live-embedding diagnostic; no publisher fetch or personal-library mutation."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import storage
from app.topic_discovery import discover_topics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'output').resolve()):
        parser.error('Use a new directory under the project output/ folder.')
    output.mkdir(parents=True, exist_ok=False)
    from sklearn.metrics import adjusted_rand_score
    texts = {
        'astronomy': ('Astronomers study exoplanets orbiting distant stars using telescope spectra and transit observations.',
            ['planetary atmospheres', 'infrared spectroscopy', 'orbital periods', 'stellar brightness',
             'planet formation', 'telescope calibration', 'transit detection', 'galaxy observations']),
        'marine': ('Marine biologists restore tropical coral reefs by monitoring ocean temperature, reef fish and coral nursery growth.',
            ['coral bleaching', 'reef restoration', 'ocean warming', 'fish biodiversity',
             'coral transplant survival', 'underwater surveys', 'reef nursery sites', 'marine ecosystems']),
        'finance': ('Banking researchers study household mortgage lending, interest rates, credit risk and bank capital requirements.',
            ['mortgage refinancing', 'borrower repayment', 'loan default risk', 'interest rate changes',
             'bank liquidity', 'credit regulation', 'housing finance', 'capital reserves']),
        'agriculture': ('Agricultural scientists study wheat farming, soil moisture, irrigation and crop yields during drought.',
            ['wheat irrigation', 'soil water retention', 'drought resistant crops', 'fertilizer trials',
             'farm harvest yields', 'seed varieties', 'soil moisture sensors', 'crop rotation']),
    }
    articles, expected = [], {}
    today = datetime.now(timezone.utc).date()
    for family, (body, aspects) in texts.items():
        for index, aspect in enumerate(aspects):
            ident = family + '-' + str(index)
            article = dict(id=ident, title=f'{aspect.title()} research update',
                text=f'{body} This fictional study investigates {aspect}. '
                     f'Its study identifier is {index + 1}. This original synthetic text is not publisher reporting.',
                source='Fictional publisher ' + str(index % 4 + 1), author='Synthetic fixture',
                published=(today - timedelta(days=index * 6)).isoformat(),
                fetched_at=datetime.now(timezone.utc).isoformat(), url=f'https://example.org/topics/{ident}',
                word_count=45, links_json='[]', images_json='[]', pdf_path='')
            articles.append(article)
            expected[ident] = family
    for index in (0, 8):
        article = dict(articles[index], id='copy-' + str(index), source='Fictional syndication',
                       url=f'https://example.org/topics/copy-{index}')
        articles.append(article)
        expected[article['id']] = expected[articles[index]['id']]
    original_db = storage.DB
    try:
        storage.DB = output / 'library.db'
        storage.create_collection('topics-demo', 'Original topic-discovery demo', 'Four fictional research themes')
        for article in articles:
            storage.upsert(article, collection_id='topics-demo')
        result = discover_topics(articles, min_cluster_size=3, as_of=today)
        with (output / 'discovery.json').open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
        shuffled = list(articles)
        random.Random(1729).shuffle(shuffled)
        repeat = discover_topics(shuffled, min_cluster_size=3, as_of=today)
        assert {topic['id']: sorted(topic['article_ids']) for topic in result['topics']} == {
            topic['id']: sorted(topic['article_ids']) for topic in repeat['topics']}
        assert repeat['counts']['embeddings_created'] == 0
        assigned = {ident: topic['id'] for topic in result['topics'] for ident in topic['article_ids']}
        canonical = [sample['article_id'] for sample in result['sampling']]
        score = adjusted_rand_score([expected[ident] for ident in canonical],
                                    [assigned.get(ident, 'unassigned') for ident in canonical])
        receipt = dict(kind='original synthetic diagnostic', articles=len(articles),
            distinct_bodies=result['counts']['distinct_articles'], topics=len(result['topics']),
            unassigned=len(result['outlier_article_ids']), adjusted_rand_index=score,
            initial_seconds=result['elapsed_seconds'], cached_seconds=repeat['elapsed_seconds'],
            cached_embeddings_created=repeat['counts']['embeddings_created'], order_memberships_equal=True,
            model_observation_state=result['model_observation']['state'], human_quality_gate='not_established',
            source_files={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in ('app/topic_discovery.py', 'app/topic_discovery_view.py', 'requirements-topics.txt')})
        with (output / 'receipt.json').open('x', encoding='utf-8') as handle:
            json.dump(receipt, handle, indent=2)
        with (output / 'fixture.json').open('x', encoding='utf-8') as handle:
            json.dump(dict(articles=articles, expected_families=expected), handle, ensure_ascii=False, indent=2)
        print(json.dumps(receipt))
    finally:
        storage.DB = original_db


if __name__ == '__main__':
    main()
