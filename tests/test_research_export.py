"""An exported brief must retain correct citations and literal untrusted text."""
import copy
import json

from markdown_it import MarkdownIt
import pytest

from app.research_export import research_exports


@pytest.fixture
def answer():
    return dict(question='What does the saved report say?', model='qwen3:8b', supported=True,
        claims=[dict(text='The reported budget is $42 million.', sources=['one:P1'])],
        passages=[dict(id='one:P1', article_id='one', title='Original fictional report',
                       text='The planned budget is $42 million. It is not a signed contract.', url='https://example.org/report'),
                  dict(id='two:P1', article_id='two', title='Unused retrieved report',
                       text='Unrelated evidence.', url='https://example.org/unused')],
        generation=dict(context_window=8192, prompt_tokens=350), retrieval=dict(passages_searched=2))


def test_brief_keeps_cited_passage_and_full_json_keeps_retrieval_context(answer):
    original = copy.deepcopy(answer)
    markdown, snapshot = research_exports(answer)
    parsed = json.loads(snapshot)
    assert '[Source 01](#source-1)' in markdown and 'The planned budget' in markdown
    assert 'Unused retrieved report' not in markdown
    assert parsed['passages'] == original['passages'] and parsed['generation'] == original['generation']
    assert parsed['export_version'] == 1 and parsed['exported_at'].endswith('+00:00')
    assert answer == original


def test_source_and_model_markup_remains_literal_and_cannot_create_external_assets(answer):
    attack = '<script>alert(1)</script> ![image](https://example.org/image) [run](javascript:alert(1))'
    answer['question'] = attack
    answer['claims'][0]['text'] += '\n' + attack
    answer['passages'][0]['title'] = attack
    answer['passages'][0]['text'] += '\n' + attack
    markdown, _ = research_exports(answer)
    rendered = MarkdownIt('commonmark', {'html': True}).render(markdown)
    assert '<img' not in rendered and '<script>' not in rendered and 'href="javascript:' not in rendered
    assert '$42 million' in rendered and 'href="https://example.org/report"' in rendered


@pytest.mark.parametrize('change', ['citation', 'duplicate', 'url', 'no_claims', 'false_claims', 'missing_status'])
def test_incomplete_or_inconsistent_results_are_not_exported_as_valid_briefs(answer, change):
    if change == 'citation':
        answer['claims'][0]['sources'] = ['invented:P1']
    elif change == 'duplicate':
        answer['passages'].append(copy.deepcopy(answer['passages'][0]))
    elif change == 'url':
        answer['passages'][0]['url'] = 'javascript:alert(1)'
    elif change == 'no_claims':
        answer['claims'] = []
    elif change == 'false_claims':
        answer['supported'] = False
    else:
        del answer['supported']
    with pytest.raises(ValueError):
        research_exports(answer)


def test_abstention_and_passage_search_export_retrieved_evidence_without_an_answer(answer):
    answer.update(supported=False, claims=[])
    markdown, _ = research_exports(answer)
    assert 'did not provide enough evidence' in markdown and 'Unused retrieved report' in markdown
    del answer['supported']
    markdown, _ = research_exports(answer)
    assert markdown.startswith('# Passage search') and 'no answer was generated' in markdown


@pytest.mark.parametrize('url,expected', [
    ('https://例え.テスト/資料?q=桜', 'https://xn--r8jz45g.xn--zckzah/%E8%B3%87%E6%96%99?q=%E6%A1%9C'),
    ('https://bücher.example:8443/a(b)#c', 'https://xn--bcher-kva.example:8443/a%28b%29#c'),
    ('https://[2001:db8::1]:8443/report', 'https://[2001:db8::1]:8443/report'),
])
def test_source_links_keep_valid_international_hosts_paths_ports_and_ipv6(answer, url, expected):
    answer['passages'][0]['url'] = url
    markdown, exported = research_exports(answer)
    assert f'[Original source](<{expected}>)' in markdown
    assert json.loads(exported)['passages'][0]['url'] == url


def test_export_preserves_original_scope_and_completion_time(answer):
    scope = dict(selected_article_ids=['one', 'two', 'three'], searched_article_ids=['one', 'two'],
                 source_fingerprints={'one': 'a' * 64, 'two': 'b' * 64}, embedding_model='local:embedding')
    answer.update(source_scope=scope, completed_at='2026-11-02T10:00:00+00:00')
    markdown, exported = research_exports(answer)
    assert 'Scope: 2 saved articles searched; 2 passages retrieved.' in markdown
    assert 'Search model: local:embedding' in markdown
    snapshot = json.loads(exported)
    assert snapshot['source_scope'] == scope and snapshot['completed_at'] == answer['completed_at']
