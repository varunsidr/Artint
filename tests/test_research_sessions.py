"""Durable research must preserve evidence, restore safely and honor deletion."""
import copy
import hashlib
import io
import json
import sqlite3
from contextlib import closing
import zipfile

import pytest

from app import library_actions, library_backup, reports, research_sessions as sessions, storage
from tests.test_library_storage import article


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path/'source.db')
    monkeypatch.setattr(reports, 'PDF_DIR', tmp_path/'pdfs')


@pytest.fixture
def result():
    item = article(1, text='The original project budget is $42 million.')
    storage.upsert(item)
    return dict(question='What budget was reported?', model='qwen3:8b', supported=True,
        claims=[dict(text='The project budget is $42 million.', sources=[item['id'] + ':P1'])],
        passages=[dict(id=item['id'] + ':P1', article_id=item['id'], title=item['title'], url=item['url'],
                       text=item['text'], score=0.8)],
        completed_at='2026-11-05T08:00:00+00:00', elapsed_seconds=1.2,
        retrieval=dict(passages_searched=1, embeddings_reused=0, embeddings_created=2,
                       embedding_batches=1, retrieval_seconds=0.012),
        source_scope=dict(selected_article_ids=[item['id']], searched_article_ids=[item['id']],
            source_fingerprints={item['id']:storage.article_fingerprint(item)}, library_revision=1,
            embedding_model='qwen3-embedding:0.6b', context_policy='adaptive-8k-16k-v1'))


def test_saved_evidence_survives_connections_and_source_revisions_without_mutating_input(result):
    original = copy.deepcopy(result)
    ident = sessions.save_result(result)
    assert sessions.load_session(ident)['result'] == original
    item = storage.get_article(result['passages'][0]['article_id'])
    storage.upsert(dict(item, text='The revised budget is $99 million.'))
    saved = sessions.load_session(ident)
    assert saved['result'] == original and saved['changed_sources'] == 1
    assert saved['unverified_sources'] == 0 and result == original


def test_duplicate_save_is_idempotent_and_does_not_invalidate_source_reuse(result):
    library_revision = storage.library_overview()['revision']
    ident = sessions.save_result(result)
    before = sessions.revision()
    when = sessions.load_session(ident)['created_at']
    assert sessions.save_result(copy.deepcopy(result)) == ident
    assert sessions.sessions_page()['total'] == 1 and sessions.revision() == before
    assert sessions.load_session(ident)['created_at'] == when
    assert storage.library_overview()['revision'] == library_revision


def test_deleting_any_selected_source_purges_complete_saved_answer_atomically(result):
    second = article(2)
    storage.upsert(second)
    result['source_scope']['selected_article_ids'].append(second['id'])
    ident = sessions.save_result(result)
    assert sessions.article_session_count(second['id']) == 1
    library_actions.delete_article(second['id'])
    assert sessions.load_session(ident) is None
    assert storage.get_article(result['passages'][0]['article_id'])
    with storage.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM research_session_sources').fetchone()[0] == 0


def test_removed_sources_cannot_be_resaved_from_an_old_browser_result(result):
    library_actions.delete_article(result['passages'][0]['article_id'])
    with pytest.raises(ValueError, match='removed'):
        sessions.save_result(result)
    assert sessions.sessions_page()['total'] == 0


@pytest.mark.parametrize('mutation', [
    lambda r:r['claims'][0].update(sources=['invented:P1']),
    lambda r:r['passages'][0].update(url='javascript:alert(1)'),
    lambda r:r['passages'][0].update(article_id='../outside'),
    lambda r:r.update(elapsed_seconds=float('nan')),
    lambda r:r.update(retrieval={'passages_searched':True}),
    lambda r:r.update(source_scope=[]),
    lambda r:r['source_scope']['source_fingerprints'].update(unselected='0'*64),
    lambda r:r.update(extra='x'*(sessions.MAX_SESSION_BYTES + 1)),
])
def test_invalid_or_oversized_evidence_is_rejected_without_writing(result, mutation):
    mutation(result)
    with pytest.raises((ValueError, TypeError)):
        sessions.save_result(result)
    assert sessions.sessions_page()['total'] == 0


def test_passage_search_and_abstention_keep_their_meaning(result):
    result.update(supported=False, claims=[])
    abstention = sessions.save_result(result)
    search = copy.deepcopy(result)
    del search['supported']
    search['model'] = 'qwen3-embedding:0.6b'
    ident = sessions.save_result(search)
    assert sessions.load_session(abstention)['result']['supported'] is False
    assert 'supported' not in sessions.load_session(ident)['result']


def test_storage_limit_is_atomic_but_identical_snapshots_can_still_be_reused(result, monkeypatch):
    ident = sessions.save_result(result)
    monkeypatch.setattr(sessions, 'MAX_SESSIONS', 1)
    assert sessions.save_result(result) == ident
    changed = dict(result, question='A different question')
    with pytest.raises(ValueError, match='limit reached'):
        sessions.save_result(changed)
    assert sessions.sessions_page()['total'] == 1


def test_saved_question_search_is_literal_and_pages_do_not_load_full_evidence(result):
    for index in range(23):
        sessions.save_result(dict(result, question=f'Question {index}'))
    sessions.save_result(dict(result, question='100% _ literal characters'))
    first, second = sessions.sessions_page(page_size=20), sessions.sessions_page(page=2, page_size=20)
    assert first['total'] == 24 and len(first['items']) == 20 and len(second['items']) == 4
    assert not ({r['id'] for r in first['items']} & {r['id'] for r in second['items']})
    assert all(set(row) == {'id','question','created_at'} for row in first['items'])
    assert sessions.sessions_page('% _')['total'] == 1
    assert sessions.sessions_page("'; DROP TABLE articles; --")['total'] == 0
    assert storage.library_overview()['total'] == 1


def test_tampered_snapshot_or_missing_links_cannot_be_rendered_as_original(result):
    ident = sessions.save_result(result)
    with storage.connect() as con:
        con.execute('UPDATE research_sessions SET result_json=? WHERE id=?',
                    (json.dumps(dict(result, question='Tampered')), ident))
    with pytest.raises(ValueError, match='integrity'):
        sessions.load_session(ident)
    sessions.delete_session(ident)
    ident = sessions.save_result(result)
    with storage.connect() as con:
        con.execute('DELETE FROM research_session_sources WHERE session_id=?', (ident,))
    with pytest.raises(ValueError, match='source links'):
        sessions.load_session(ident)


def test_v6_upgrade_preserves_library_and_keeps_a_v6_backup(result):
    item = storage.get_article(result['passages'][0]['article_id'])
    with storage.connect() as con:
        con.execute('DROP TRIGGER research_purge_source')
        con.execute('DROP TABLE research_session_sources')
        con.execute('DROP TABLE research_sessions')
        con.execute('DROP TABLE research_state')
        con.execute('PRAGMA user_version=6')
    assert storage.get_article(item['id'])['content_hash'] == storage.article_fingerprint(item)
    assert sessions.sessions_page()['total'] == 0
    backup = next((storage.DB.parent/'backups').glob('*before-v7-*.db'))
    with closing(sqlite3.connect(backup)) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 6
        assert con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='research_sessions'").fetchone()[0] == 0


def test_source_delete_rollback_restores_saved_research_and_links(result):
    ident = sessions.save_result(result)
    with pytest.raises(RuntimeError, match='rollback'):
        with storage.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('DELETE FROM articles WHERE id=?', (result['passages'][0]['article_id'],))
            raise RuntimeError('Simulated rollback')
    assert sessions.load_session(ident)['result'] == result
    assert sessions.article_session_count(result['passages'][0]['article_id']) == 1


def rewrite(blob, mutate):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        files={name:archive.read(name) for name in archive.namelist()}
    data=json.loads(files['library.json']);mutate(data);files['library.json']=json.dumps(data).encode()
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in files.items():archive.writestr(name,value)
    return output.getvalue()


@pytest.mark.parametrize('with_request_identity', [False, True])
def test_backup_round_trip_is_idempotent_and_preserves_immutable_evidence_with_id_remapping(result, tmp_path, monkeypatch, with_request_identity):
    if with_request_identity:
        result['generation'] = dict(context_window=8192,
            request_identity=dict(version='ollama-chat-request-v1', requested_model='qwen3:8b',
                                  model_digest=None, messages_sha256='a' * 64, schema_sha256='b' * 64),
            attempts=[dict(context_window=8192, request_sha256='c' * 64,
                           options=dict(temperature=0, num_ctx=8192, num_predict=1600))])
        from tests.test_model_health import manifest, observation
        from app.model_health import model_observation
        before = observation([manifest()], names=('chat',))
        after = observation([manifest(digest='b' * 64)], names=('chat',))
        result['model_observation'] = model_observation(before, after)
    ident = sessions.save_result(result)
    blob, stats = library_backup.create_backup()
    assert stats['research_sessions'] == 1
    original = storage.get_article(result['passages'][0]['article_id'])
    monkeypatch.setattr(storage,'DB',tmp_path/'destination.db')
    monkeypatch.setattr(reports,'PDF_DIR',tmp_path/'destination-pdfs')
    storage.upsert(dict(original,id='remapped'))
    assert library_backup.restore_backup(blob)['research_sessions'] == 1
    loaded=sessions.load_session(ident)
    assert loaded['result'] == result and loaded['unverified_sources'] == 1
    from app.research_export import research_exports
    exported = json.loads(research_exports(loaded['result'])[1])
    assert exported.get('generation') == result.get('generation')
    assert exported.get('model_observation') == result.get('model_observation')
    assert sessions.article_session_count('remapped') == 1
    assert library_backup.restore_backup(blob)['research_sessions'] == 0
    # Re-exported backups retain original evidence IDs and local link mappings.
    second,_=library_backup.create_backup()
    assert library_backup.inspect_backup(second)['tables']['research_sessions'][0]['snapshot_hash'] == hashlib.sha256(sessions.validate_result(result).encode()).hexdigest()
    library_actions.delete_article('remapped')
    assert sessions.load_session(ident) is None


def test_legacy_v1_backups_restore_without_saved_research(result):
    blob,_=library_backup.create_backup()
    def legacy(data):
        data['version']=1;data['schema_version']=6
        data['tables'].pop('research_sessions');data['tables'].pop('research_session_sources')
    data=library_backup.inspect_backup(rewrite(blob,legacy))
    assert data['tables']['research_sessions'] == data['tables']['research_session_sources'] == []


def test_restore_id_collision_preserves_both_distinct_results(result, tmp_path, monkeypatch):
    ident = sessions.save_result(result); blob,_ = library_backup.create_backup()
    item = storage.get_article(result['passages'][0]['article_id'])
    original_row = dict()
    with storage.connect() as con:
        original_row = dict(con.execute('SELECT * FROM research_sessions WHERE id=?', (ident,)).fetchone())
    monkeypatch.setattr(storage,'DB',tmp_path/'destination.db')
    storage.upsert(item)
    other = dict(result, question='Another saved question')
    encoded = sessions.validate_result(other)
    row = dict(original_row, question=other['question'], result_json=encoded,
               snapshot_hash=hashlib.sha256(encoded.encode()).hexdigest())
    with storage.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        sessions.insert_record(con,row,{item['id']:item['id']})
    assert library_backup.restore_backup(blob)['research_sessions'] == 1
    assert sessions.load_session(ident)['result'] == other
    assert sessions.sessions_page()['total'] == 2
    assert library_backup.restore_backup(blob)['research_sessions'] == 0


@pytest.mark.parametrize('bad', ['hash','link'])
def test_backup_rejects_tampered_or_detached_research_before_opening_target(result, tmp_path, monkeypatch, bad):
    sessions.save_result(result);blob,_=library_backup.create_backup()
    def mutate(data):
        if bad=='hash':data['tables']['research_sessions'][0]['question']='Altered'
        else:data['tables']['research_session_sources']=[]
    blob=rewrite(blob,mutate)
    monkeypatch.setattr(storage,'DB',tmp_path/'untouched.db')
    with pytest.raises(ValueError):library_backup.restore_backup(blob)
    assert not storage.DB.exists()


def test_restore_capacity_failure_rolls_back_new_articles_and_sessions(result, tmp_path, monkeypatch):
    sessions.save_result(result);blob,_=library_backup.create_backup()
    monkeypatch.setattr(storage,'DB',tmp_path/'destination.db')
    other = article(2)
    storage.upsert(other)
    existing = dict(question='Existing research', model='qwen3:8b', supported=False, claims=[],
        passages=[dict(id=other['id']+':P1', article_id=other['id'], title=other['title'], url=other['url'], text=other['text'])])
    original_id = sessions.save_result(existing)
    limit = len(sessions.validate_result(result).encode()) + len(sessions.validate_result(existing).encode()) - 1
    monkeypatch.setattr(sessions,'MAX_TOTAL_BYTES',limit)
    with pytest.raises(ValueError, match='limit reached'):library_backup.restore_backup(blob)
    assert storage.library_overview()['total']==1 and sessions.sessions_page()['total']==1
    assert storage.get_article(result['passages'][0]['article_id']) is None
    assert sessions.load_session(original_id)['result'] == existing
