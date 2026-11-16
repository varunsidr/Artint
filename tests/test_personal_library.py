import csv
import io
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

import pytest

from app import library_actions as actions, reports, storage
from app.exports import metadata_csv
from app.library_view import _reading_html
from tests.test_library_storage import article, _insight


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path/'library.db')
    monkeypatch.setattr(reports, 'PDF_DIR', tmp_path/'pdfs')


def saved(index=0):
    item = article(index, text='First evidence passage.\n\nRepeated finding. Then another sentence.\n\nRepeated finding.')
    item['pdf_path'] = str(reports.create_pdf(item))
    storage.upsert(item)
    return item


def test_notes_unicode_tags_and_collections_preserve_ai_and_share_export_predicates():
    item, other = saved(), saved(1)
    storage.save_insight(item, 'qwen3:8b', '1', _insight())
    before = storage.get_article(item['id'])['content_hash']
    actions.save_organization(item['id'], note='My research notes <script>not executable</script>',
                              tags='AI, ai, Caf\u00e9, \u00df', collection_ids=[], new_collection='Research project')
    state = actions.annotation_state(item['id'])
    assert state['tags'] == ['AI', 'Caf\u00e9', '\u00df']
    assert state['note'].startswith('My research notes') and len(state['collections']) == 1
    assert storage.get_article(item['id'])['content_hash'] == before
    assert storage.library_overview()['analyzed'] == 1
    result = storage.library_page(tags=['café'])
    assert [row['id'] for row in result['items']] == [item['id']]
    rows = list(csv.DictReader(io.StringIO(metadata_csv(tags=['café']).decode('utf-8-sig'))))
    assert [row['id'] for row in rows] == [item['id']]
    assert storage.library_page(collection_id=state['collections'][0])['total'] == 1
    actions.save_organization(other['id'], note='', tags=[], collection_ids=[], new_collection='research PROJECT')
    assert actions.annotation_state(other['id'])['collections'] == state['collections']


def test_highlight_anchors_the_selected_occurrence_and_tracks_text_revisions():
    item = saved()
    ident = actions.add_highlight(item['id'], 'Repeated finding.', occurrence=1, note='Follow this claim')
    state = actions.annotation_state(item['id'])
    anchor = state['highlights'][0]
    assert anchor['start_offset'] == item['text'].rfind('Repeated finding.') and anchor['current']
    html = _reading_html(item['text'], state['highlights'])
    assert html.count('class="saved-highlight"') == 1
    assert 'Repeated finding.</mark>' in html
    # A metadata-only update does not make a text anchor stale.
    storage.upsert(dict(item, title='Updated metadata'))
    assert actions.annotation_state(item['id'])['highlights'][0]['current']
    storage.upsert(dict(item, text='A changed body. ' + item['text']))
    stale = actions.annotation_state(item['id'])['highlights'][0]
    assert not stale['current'] and stale['quote'] == 'Repeated finding.'
    assert 'saved-highlight' not in _reading_html(storage.get_article(item['id'])['text'], [stale])
    actions.update_highlight_note(item['id'], ident, 'Preserve the old observation')
    assert actions.annotation_state(item['id'])['highlights'][0]['note'] == 'Preserve the old observation'


def test_highlight_rendering_preserves_markdown_and_escapes_untrusted_markup():
    text = 'Use **trusted evidence** and [original sources](https://example.org).\n\n<script>unsafe()</script>'
    item = article(text=text)
    storage.upsert(item)
    actions.add_highlight(item['id'], 'trusted evidence')
    html = _reading_html(text, actions.annotation_state(item['id'])['highlights'])
    assert '<strong><mark class="saved-highlight">trusted evidence</mark></strong>' in html
    assert 'href="https://example.org"' in html and '<script>' not in html
    assert '&lt;script&gt;' in html


def test_missing_passages_and_concurrent_source_edits_are_not_silently_reanchored():
    item = saved()
    with pytest.raises(ValueError, match='exactly'):
        actions.add_highlight(item['id'], 'Not in the source')
    with pytest.raises(ValueError, match='saved text changed'):
        actions.add_highlight(item['id'], 'Repeated finding.', expected_text_hash='wrong')
    assert actions.annotation_state(item['id'])['highlights'] == []


def test_delete_removes_owned_data_and_pdf_without_touching_another_article():
    item, other = saved(), saved(1)
    actions.save_organization(item['id'], note='Notes', tags='AI', collection_ids=[], new_collection='Project')
    actions.add_highlight(item['id'], 'First evidence passage.')
    storage.save_insight(item, 'qwen3:8b', '1', _insight())
    storage.save_embeddings('embedding', {'shared passage': [1., 0.]})
    result = actions.delete_article(item['id'])
    assert result['pdf_removed'] and not result['cleanup_pending']
    assert storage.get_article(item['id']) is None
    assert Path(other['pdf_path']).is_file() and not Path(item['pdf_path']).exists()
    assert storage.library_page(query='First')['total'] == 1
    with storage.connect() as con:
        for table in ('article_notes','article_tags','article_highlights','article_insights','article_facets','collection_articles'):
            assert con.execute(f'SELECT COUNT(*) FROM {table} WHERE article_id=?', (item['id'],)).fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0] == 1


def test_delete_keeps_a_pdf_outside_the_managed_folder(tmp_path):
    external = tmp_path/'unrelated.pdf'
    external.write_bytes(b'Keep this unrelated file')
    item = article(pdf_path=str(external))
    storage.upsert(item)
    actions.delete_article(item['id'])
    assert external.read_bytes() == b'Keep this unrelated file'


def test_delete_keeps_a_legacy_pdf_referenced_by_another_article():
    first = saved()
    storage.upsert(article(1,pdf_path=first['pdf_path']))
    result = actions.delete_article(first['id'])
    assert not result['pdf_removed'] and Path(first['pdf_path']).is_file()
    assert storage.get_article('article0001') is not None


@pytest.mark.parametrize('committed', [False, True])
def test_interrupted_deletion_recovers_only_its_journaled_pdf(committed):
    item = saved()
    path = Path(item['pdf_path'])
    op = 'a'*32
    stage = path.parent/('.delete-'+op+'-'+item['id']+'.pdf')
    untouched = path.parent/'unrelated.pdf'
    untouched.write_bytes(b'Unrelated')
    with storage.connect() as con:
        con.execute('INSERT INTO pending_pdf_deletions VALUES(?,?,?,?)', (op,item['id'],path.name,stage.name))
        if committed:
            con.execute('DELETE FROM articles WHERE id=?', (item['id'],))
    path.rename(stage)
    assert actions.recover_pending_deletions() == 0
    assert path.exists() is (not committed) and not stage.exists()
    assert untouched.read_bytes() == b'Unrelated'


def test_database_failure_restores_the_original_pdf_and_article(monkeypatch):
    item = saved()
    original = storage.connect
    @contextmanager
    def failing():
        with original() as con:
            class Proxy:
                def execute(self, sql, *args):
                    if sql.startswith('DELETE FROM articles'):
                        raise sqlite3.OperationalError('Simulated commit-path failure')
                    return con.execute(sql, *args)
                def __getattr__(self, name): return getattr(con,name)
            yield Proxy()
    monkeypatch.setattr(storage, 'connect', failing)
    with pytest.raises(sqlite3.OperationalError):
        actions.delete_article(item['id'])
    assert storage.get_article(item['id']) is not None
    assert Path(item['pdf_path']).read_bytes().startswith(b'%PDF-')


def test_v5_upgrade_preserves_source_records_and_adds_personal_tables():
    item = saved()
    with storage.connect() as con:
        # Retained IF NOT EXISTS tables also exercise downgrade-shaped test fixtures.
        con.execute('PRAGMA user_version=5')
    assert storage.get_article(item['id'])['text'] == item['text']
    assert actions.annotation_state(item['id'])['note'] == ''
    backup = next((storage.DB.parent/'backups').glob(f'*before-v{storage.SCHEMA_VERSION}-*.db'))
    with closing(sqlite3.connect(backup)) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 5
