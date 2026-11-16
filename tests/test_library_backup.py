import io
import json
import sqlite3
import stat
import zipfile
from pathlib import Path

import pytest

from app import library_actions as actions, library_backup as backups, reports, storage
from app.discovery_imports import create_batch
from tests.test_library_storage import article, _insight


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path/'original.db')
    monkeypatch.setattr(reports, 'PDF_DIR', tmp_path/'original-pdfs')


def populate(count=1):
    for number in range(count):
        item = article(number, text='Evidence for personal research.\n\nAn inspectable passage about astronomy and glass.')
        item['pdf_path'] = str(reports.create_pdf(item))
        storage.upsert(item)
        actions.save_organization(item['id'], note='Private research notes', tags='Follow up, Science', collection_ids=[], new_collection='Research project')
        actions.add_highlight(item['id'], 'inspectable passage', note='Check the evidence')
        storage.save_insight(item, 'qwen3:8b', '1', _insight())
    storage.save_embeddings('embedding', {'shared source passage': [1.,0.]})
    return storage.all_articles()


def destination(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path/'restored.db')
    monkeypatch.setattr(reports, 'PDF_DIR', tmp_path/'restored-pdfs')


def rewrite(blob, mutate=None, extra=None):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    data = json.loads(members['library.json'])
    if mutate:
        mutate(data)
    members['library.json'] = json.dumps(data).encode()
    if extra:
        members.update(extra)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_portable_round_trip_preserves_text_notes_highlights_collections_analysis_and_vectors(tmp_path, monkeypatch):
    original = populate()[0]
    state = actions.annotation_state(original['id'])
    original_pdf = Path(original['pdf_path']).read_bytes()
    blob, stats = backups.create_backup()
    assert stats == {'articles':1,'pdfs':1,'missing_pdfs':0,'research_sessions':0}
    data = backups.inspect_backup(blob)
    assert str(reports.PDF_DIR) not in json.dumps(data)
    destination(tmp_path, monkeypatch)
    assert backups.restore_preview(data)['new'] == 1
    result = backups.restore_backup(blob)
    restored = storage.get_article(original['id'])
    assert result['articles'] == result['notes'] == result['highlights'] == result['pdfs'] == 1
    assert restored['text'] == original['text'] and restored['content_hash'] == original['content_hash']
    assert Path(restored['pdf_path']).parent == reports.PDF_DIR
    assert Path(restored['pdf_path']).read_bytes() == original_pdf
    assert actions.annotation_state(original['id']) == state
    assert storage.library_page(query='astronomy')['total'] == 1
    assert storage.library_overview()['analyzed'] == 1
    assert storage.cached_embeddings('embedding',['shared source passage']) == {'shared source passage':[1.,0.]}
    again = backups.restore_backup(blob)
    assert again['articles'] == again['notes'] == again['highlights'] == again['pdfs'] == 0
    with storage.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM research_collections').fetchone()[0] == 1


def test_merge_keeps_current_notes_and_text_and_does_not_rebase_old_analysis_ids(tmp_path, monkeypatch):
    original = populate()[0]
    blob,_ = backups.create_backup()
    destination(tmp_path,monkeypatch)
    current = dict(original, id='different-id',pdf_path='')
    storage.upsert(current)
    actions.save_organization(current['id'], note='Keep my current note', tags='Current', collection_ids=[])
    backups.restore_backup(blob)
    assert storage.get_article(original['id']) is None
    state = actions.annotation_state(current['id'])
    assert state['note'] == 'Keep my current note'
    assert set(state['tags']) == {'Current','Follow up','Science'}
    assert state['highlights'][0]['current']
    assert storage.load_insight(current,'qwen3:8b','1') is None


def test_changed_source_text_is_not_overwritten_or_given_incompatible_annotations(tmp_path,monkeypatch):
    original = populate()[0]
    blob,_ = backups.create_backup()
    destination(tmp_path,monkeypatch)
    current = dict(original,text='My updated saved source.',pdf_path='')
    storage.upsert(current)
    assert backups.restore_preview(backups.inspect_backup(blob))['changed_text'] == 1
    result = backups.restore_backup(blob)
    assert result['changed_text_skipped'] == 1 and result['notes'] == result['highlights'] == 0
    assert storage.get_article(original['id'])['text'] == current['text']


def test_collection_id_conflicts_are_preserved_and_repeated_restore_is_idempotent(tmp_path,monkeypatch):
    original = populate()[0]
    blob,_ = backups.create_backup()
    collection = actions.annotation_state(original['id'])['collections'][0]
    destination(tmp_path,monkeypatch)
    storage.create_collection(collection,'A different project','Different query')
    backups.restore_backup(blob)
    backups.restore_backup(blob)
    with storage.connect() as con:
        assert con.execute('SELECT title FROM research_collections WHERE id=?',(collection,)).fetchone()[0] == 'A different project'
        assert con.execute('SELECT COUNT(*) FROM research_collections').fetchone()[0] == 2


@pytest.mark.parametrize('mutation', [
    lambda data: data['tables']['articles'][0].update(id='../outside'),
    lambda data: data['tables']['articles'][0].update(url='javascript:alert(1)'),
    lambda data: data['tables']['article_highlights'][0].update(quote='wrong source text'),
    lambda data: data['tables']['article_insights'][0].update(insight_json='{"summary":"wrong"}'),
    lambda data: data.update(version=99),
    lambda data: data['pdfs'][0].update(name='../outside.pdf'),
])
def test_invalid_backups_fail_before_writing_any_library_data(tmp_path,monkeypatch,mutation):
    populate()
    blob,_ = backups.create_backup()
    bad = rewrite(blob,mutation)
    destination(tmp_path,monkeypatch)
    with pytest.raises(ValueError):
        backups.restore_backup(bad)
    assert not storage.DB.exists() and not reports.PDF_DIR.exists()


def test_unknown_archive_paths_and_symlinks_are_rejected(tmp_path,monkeypatch):
    populate()
    blob,_ = backups.create_backup()
    with pytest.raises(ValueError,match='unexpected files'):
        backups.inspect_backup(rewrite(blob,extra={'../outside.txt':b'unsafe'}))
    with zipfile.ZipFile(io.BytesIO(blob)) as source:
        members = {name:source.read(name) for name in source.namelist()}
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        for name,content in members.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info,content)
    with pytest.raises(ValueError,match='linked'):
        backups.inspect_backup(output.getvalue())


def test_corrupt_pdf_and_duplicate_json_keys_are_rejected():
    populate()
    blob,_ = backups.create_backup()
    name = backups.inspect_backup(blob)['pdfs'][0]['name']
    with pytest.raises(ValueError,match='checksum|size'):
        backups.inspect_backup(rewrite(blob,extra={name:b'%PDF-corrupt'}))
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('library.json',b'{"format":"one","format":"two"}')
    with pytest.raises(ValueError,match='invalid JSON'):
        backups.inspect_backup(output.getvalue())


def test_existing_unrelated_pdf_is_never_overwritten(tmp_path,monkeypatch):
    item = populate()[0]
    blob,_ = backups.create_backup()
    destination(tmp_path,monkeypatch)
    reports.PDF_DIR.mkdir()
    unrelated = reports.PDF_DIR/(item['id']+'.pdf')
    unrelated.write_bytes(b'%PDF-unrelated file')
    with pytest.raises(ValueError,match='different file'):
        backups.restore_backup(blob)
    assert unrelated.read_bytes() == b'%PDF-unrelated file'
    assert storage.library_overview()['total'] == 0


def test_restore_database_failure_rolls_back_only_its_created_files(tmp_path,monkeypatch):
    populate(count=2)
    blob,_ = backups.create_backup()
    destination(tmp_path,monkeypatch)
    reports.PDF_DIR.mkdir()
    unrelated = reports.PDF_DIR/'unrelated.pdf'
    unrelated.write_bytes(b'Unrelated PDF')
    original = storage._upsert
    calls = []
    def failing(con,item):
        calls.append(item)
        if len(calls) == 2:
            raise sqlite3.OperationalError('Simulated failure')
        original(con,item)
    monkeypatch.setattr(storage,'_upsert',failing)
    with pytest.raises(sqlite3.OperationalError):
        backups.restore_backup(blob)
    assert storage.library_overview()['total'] == 0
    assert list(reports.PDF_DIR.iterdir()) == [unrelated]


def test_limits_are_checked_before_decompression(monkeypatch):
    populate()
    blob,_ = backups.create_backup()
    monkeypatch.setattr(backups,'MAX_EXPANDED',1)
    with pytest.raises(ValueError,match='oversized'):
        backups.inspect_backup(blob)


def test_active_imports_prevent_delete_restore_and_full_backup(tmp_path,monkeypatch):
    item = populate()[0]
    blob,_ = backups.create_backup()
    create_batch(['https://example.org/queued'],'Queued sources','')
    with pytest.raises(ValueError,match='active imports'):
        backups.create_backup()
    with pytest.raises(ValueError,match='active imports'):
        backups.restore_backup(blob)
    with pytest.raises(ValueError,match='active imports'):
        actions.delete_article(item['id'])
    assert storage.get_article(item['id']) is not None and Path(item['pdf_path']).is_file()


def test_empty_notes_do_not_get_rewritten_on_repeated_restore(tmp_path,monkeypatch):
    item = populate()[0]
    actions.save_organization(item['id'],note='',tags=[],collection_ids=[])
    blob,_ = backups.create_backup()
    destination(tmp_path,monkeypatch)
    backups.restore_backup(blob)
    assert backups.restore_backup(blob)['notes'] == 0


def test_case_colliding_article_ids_are_rejected_for_portable_pdf_safety(tmp_path,monkeypatch):
    item = populate()[0]
    blob,_ = backups.create_backup()
    data = backups.inspect_backup(blob)
    collision = dict(data['tables']['articles'][0],id=item['id'].upper(),url='https://example.org/different')
    data['tables']['articles'].append(collision)
    bad = rewrite(blob,lambda value: value.update(tables=data['tables']))
    with pytest.raises(ValueError,match='duplicate articles'):
        backups.inspect_backup(bad)
    destination(tmp_path,monkeypatch)
    storage.upsert(article(id=item['id'].upper(),url='https://example.org/another'))
    with pytest.raises(ValueError,match='different existing URL'):
        backups.restore_backup(blob)


@pytest.mark.parametrize('reserved', ['CON', 'nul', 'COM1', 'lpt9'])
def test_windows_device_names_cannot_be_restored_as_managed_files(tmp_path,monkeypatch,reserved):
    populate()
    blob,_ = backups.create_backup()
    bad = rewrite(blob,lambda data:data['tables']['articles'][0].update(id=reserved))
    destination(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='invalid record ID'):
        backups.restore_backup(bad)
    assert not storage.DB.exists() and not reports.PDF_DIR.exists()
