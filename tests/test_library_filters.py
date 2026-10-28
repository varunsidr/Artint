import csv
import io
from datetime import date

import pytest

from app import storage
from app.exports import metadata_csv
from app.library_filters import build_filters


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'library.db')


def article(index, words, published):
    return dict(id=str(index), url=f'https://example.org/{index}', title=f'AI article {index}',
                source='Example', author='', published=published, fetched_at='2026-10-28',
                text='OpenAI capex and debt.', word_count=words, links_json='[]', images_json='[]', pdf_path='')


def test_reading_length_boundaries_and_export_match_the_visible_selection():
    storage.upsert_many([article(1, 1100, '2026-10-01'), article(2, 1101, '2026-10-10'),
                         article(3, 3300, '2026-10-27'), article(4, 3301, '')])
    for length, expected in [('Up to 5 min', {'1'}), ('6–15 min', {'2', '3'}), ('Over 15 min', {'4'})]:
        filters = build_filters(dict(length=length))
        assert {row['id'] for row in storage.library_page(**filters)['items']} == expected
        rows = csv.DictReader(io.StringIO(metadata_csv(**filters).decode('utf-8-sig')))
        assert {row['id'] for row in rows} == expected


def test_custom_end_date_excludes_undated_and_unknown_date_filter_is_explicit():
    storage.upsert_many([article(1, 200, '2026-10-01'), article(2, 200, ''), article(3, 200, '2026-10-28')])
    custom = build_filters(dict(published='Custom dates', date_until=date(2026, 10, 27)))
    assert [row['id'] for row in storage.library_page(**custom)['items']] == ['1']
    missing = build_filters(dict(published='Date unavailable'))
    assert [row['id'] for row in storage.library_page(**missing)['items']] == ['2']
    recent = build_filters(dict(published='Past 30 days'), today=date(2026, 10, 27))
    assert [row['id'] for row in storage.library_page(**recent)['items']] == ['1']


def test_publication_sort_keeps_missing_dates_last_and_stable_ties():
    storage.upsert_many([article(1, 200, '2026-10-01'), article(2, 200, ''), article(3, 200, '2026-10-28')])
    assert [row['id'] for row in storage.library_page(sort='Newest published')['items']] == ['3', '1', '2']
    assert [row['id'] for row in storage.library_page(sort='Oldest published')['items']] == ['1', '3', '2']
    assert [row['id'] for row in storage.library_page(sort='Shortest read')['items']] == ['1', '2', '3']


@pytest.mark.parametrize('arguments', [dict(min_words=-1), dict(max_words='100'), dict(date_status='invalid')])
def test_invalid_filter_bounds_are_rejected(arguments):
    with pytest.raises(ValueError):
        storage.library_page(**arguments)
