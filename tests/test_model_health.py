"""Metadata-only checks; no model inference, service startup or library writes."""
import json
from unittest.mock import patch

import pytest
import requests

from app.model_health import inspect_ollama, residency, memory_share_label, MAX_METADATA_BYTES, observe_models, model_observation
from scripts import check_install


def reply(data, status=200, raw=None):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(data).encode() if raw is None else raw
    response._content_consumed = True
    return response


def inventory():
    return reply({'models': [{'name': 'qwen3:8b'}, {'name': 'qwen3-embedding:0.6b'}]})


@pytest.mark.parametrize('total,gpu,placement,percent', [
    (1000, 1000, 'gpu', 100.0), (1000, 0, 'cpu', 0.0), (1000, 800, 'mixed', 80.0),
    (0, 0, 'unknown', None), (None, 0, 'unknown', None), (100, None, 'unknown', None),
    (100, 101, 'unknown', None), (100, -1, 'unknown', None), (True, 1, 'unknown', None),
    (100.0, 20, 'unknown', None), (100, '80', 'unknown', None),
])
def test_memory_residency_never_invents_missing_or_invalid_gpu_data(total, gpu, placement, percent):
    result = residency(dict(size=total, size_vram=gpu, context_length=8192))
    assert result['placement'] == placement and result['gpu_memory_percent'] == percent
    assert result['context_tokens'] == 8192


@pytest.mark.parametrize('gpu,expected', [(99999, '>99.9%'), (1, '<0.1%')])
def test_mixed_memory_is_not_rounded_to_all_gpu_or_all_cpu(gpu, expected):
    memory = residency(dict(size=100000, size_vram=gpu))
    assert memory['placement'] == 'mixed'
    assert 0 < memory['gpu_memory_percent'] < 100
    assert memory_share_label(memory) == expected


def test_installed_but_unloaded_is_not_cpu_only_and_checks_are_get_only():
    with patch('app.model_health.requests.get', side_effect=[inventory(), reply({'version': '0.40.11'}), reply({'models': []})]) as get:
        report = inspect_ollama()
    assert report['answer_ready'] and report['search_ready']
    assert report['selected']['chat']['installed'] is True
    assert report['selected']['chat']['loaded'] is False and report['selected']['chat']['residency'] is None
    assert [call.args[0].rsplit('/', 1)[-1] for call in get.call_args_list] == ['tags', 'version', 'ps']
    assert all(call.kwargs['allow_redirects'] is False and 'json' not in call.kwargs for call in get.call_args_list)


def test_selected_loaded_model_and_remote_endpoint_are_reported_without_client_gpu_assumptions():
    loaded = {'name': 'qwen3:8b', 'size': 1000, 'size_vram': 800, 'context_length': 16384}
    with patch('app.model_health.requests.get', side_effect=[inventory(), reply({'version': '0.40.11'}), reply({'models': [loaded]})]):
        report = inspect_ollama('https://model.example.org/proxy')
    assert report['endpoint'] == 'https://model.example.org/proxy'
    assert report['selected']['chat']['residency']['placement'] == 'mixed'
    assert report['selected']['chat']['residency']['gpu_memory_percent'] == 80.0
    assert 'gpu_name' not in report  # The client machine is not necessarily the server.


def test_offline_service_stops_early_and_keeps_residency_unknown():
    with patch('app.model_health.requests.get', side_effect=requests.Timeout()) as get:
        report = inspect_ollama()
    assert get.call_count == 1 and not report['answer_ready']
    assert report['connection'] == 'unavailable'
    assert report['selected']['chat']['installed'] is None and report['selected']['chat']['loaded'] is None


@pytest.mark.parametrize('version', ['0.40.10', 'unknown', None, '9' * 200])
def test_old_or_unknown_runtime_does_not_report_generation_ready(version):
    with patch('app.model_health.requests.get', side_effect=[inventory(), reply({'version': version}), reply({'models': []})]):
        report = inspect_ollama()
    assert not report['answer_ready'] and report['search_ready']
    assert report['generation_compatible'] is False


def test_running_api_failure_does_not_falsely_mark_installed_models_as_cpu():
    with patch('app.model_health.requests.get', side_effect=[inventory(), reply({'version': '0.40.11'}), reply({}, 404)]):
        report = inspect_ollama()
    assert report['answer_ready'] and report['selected']['chat']['loaded'] is None
    assert report['errors'][0]['check'] == 'residency'


@pytest.mark.parametrize('bad', [reply({}, 302), reply({}, raw=b'not-json'), reply({'models': 'wrong'}),
                                  reply({}, raw=b' ' * (MAX_METADATA_BYTES + 1))])
def test_invalid_redirected_or_oversized_inventory_is_actionable(bad):
    with patch('app.model_health.requests.get', return_value=bad):
        report = inspect_ollama()
    assert report['connection'] == 'unavailable' and report['errors']
    assert report['installed_models'] is None


@pytest.mark.parametrize('endpoint', ['file:///tmp/models', 'https://user:secret@server', 'http://localhost:bad', 'http://localhost/?token=secret'])
def test_invalid_endpoint_is_rejected_before_contact(endpoint):
    with patch('app.model_health.requests.get') as get:
        with pytest.raises(ValueError):
            inspect_ollama(endpoint)
    get.assert_not_called()


def test_installation_cli_default_does_not_contact_ollama(capsys):
    with patch('app.model_health.requests.get') as get:
        check_install.main([])
    assert json.loads(capsys.readouterr().out)['ok'] is True
    get.assert_not_called()


def test_installation_cli_reports_missing_models_with_nonzero_exit(capsys):
    with patch('app.model_health.requests.get', side_effect=[reply({'models': []}), reply({'version': '0.40.11'}), reply({'models': []})]):
        with pytest.raises(SystemExit) as stopped:
            check_install.main(['--ollama'])
    assert stopped.value.code == 1
    report = json.loads(capsys.readouterr().out)
    assert not report['ok'] and report['storage'] == 'Not opened or modified.'


def test_installation_cli_custom_models_can_be_checked_without_loading(capsys):
    with patch('app.model_health.requests.get', side_effect=[reply({'models': [{'name': 'custom:chat'}, {'name': 'custom:embed'}]}),
                                                          reply({'version': '0.40.11'}), reply({'models': []})]):
        check_install.main(['--ollama', '--chat-model', 'custom:chat', '--embedding-model', 'custom:embed'])
    report = json.loads(capsys.readouterr().out)
    assert report['ok'] and report['ollama']['loaded_models'] == []


def manifest(name='chat', digest='a' * 64, **kwargs):
    return dict(name=name, digest=digest, details=dict(format='gguf', family='qwen', parameter_size='8B',
                                                     quantization_level='Q4_K_M', private_path='/private/model'), **kwargs)


def observation(rows, names=('chat', 'embed')):
    with patch('app.model_health.requests.get', return_value=reply({'models': rows})):
        return observe_models('http://127.0.0.1:11434', list(names))


def test_selected_manifest_observation_is_bounded_get_only_and_excludes_other_models():
    with patch('app.model_health.requests.get', return_value=reply({'models': [manifest(), manifest('embed'),
                                                                                 manifest('private-model')]})) as get:
        snapshot = observe_models('https://model.example.org/proxy', ['chat', 'embed'])
    assert snapshot['state'] == 'complete' and snapshot['error'] is None
    assert set(snapshot['models']) == {'chat', 'embed'}
    assert snapshot['models']['chat']['digest'] == 'a' * 64
    assert snapshot['models']['chat']['details']['quantization_level'] == 'Q4_K_M'
    assert 'private_path' not in json.dumps(snapshot) and 'private-model' not in json.dumps(snapshot)
    assert get.call_count == 1 and get.call_args.args == ('https://model.example.org/proxy/api/tags',)
    assert get.call_args.kwargs == dict(timeout=(3, 3), stream=True, allow_redirects=False)


@pytest.mark.parametrize('rows', [[], [manifest(digest=None)], [manifest(digest='tag-only')],
                                [manifest(digest=True)], [manifest(digest='a' * 65)]])
def test_missing_models_or_manifest_digests_never_become_stable(rows):
    snapshot = observation(rows, names=('chat',))
    assert snapshot['state'] == 'incomplete'
    assert model_observation(snapshot, snapshot)['state'] == 'unavailable'


@pytest.mark.parametrize('bad', [reply({}, 302), reply({}, 500), reply({}, raw=b'invalid'),
                                reply({}, raw=b' ' * (MAX_METADATA_BYTES + 1)),
                                reply({'models': [manifest(), manifest()]}),
                                reply({'models': [manifest(str(index)) for index in range(513)]})])
def test_failed_or_ambiguous_model_observations_are_unavailable(bad):
    with patch('app.model_health.requests.get', return_value=bad):
        snapshot = observe_models('http://127.0.0.1:11434', ['chat'])
    assert snapshot['state'] == 'unavailable' and snapshot['error']
    assert snapshot['models']['chat']['installed'] is None


def test_unreachable_identity_metadata_does_not_raise_an_inference_error():
    with patch('app.model_health.requests.get', side_effect=requests.Timeout()):
        snapshot = observe_models('http://127.0.0.1:11434', ['chat'])
    assert snapshot['state'] == 'unavailable'
    assert snapshot['models']['chat']['digest'] is None


def test_model_observation_detects_retagging_and_removal_and_detaches_snapshots():
    before = observation([manifest(), manifest('embed')])
    stable = observation([manifest('embed'), manifest()])
    assert model_observation(before, stable)['state'] == 'stable'  # Timestamps/order are not identities.
    after = observation([manifest(digest='b' * 64), manifest('embed')])
    compared = model_observation(before, after)
    assert compared['state'] == 'changed'
    assert model_observation(before, observation([manifest()]))['state'] == 'changed'
    before['models']['chat']['digest'] = None
    after['models']['chat']['details'].clear()
    assert compared['before']['models']['chat']['digest'] == 'a' * 64
    assert compared['after']['models']['chat']['details']['quantization_level'] == 'Q4_K_M'


def test_known_manifest_change_is_retained_when_other_model_identity_is_missing():
    before = observation([manifest(), manifest('embed', digest=None)])
    after = observation([manifest(digest='b' * 64), manifest('embed', digest=None)])
    assert before['state'] == after['state'] == 'incomplete'
    assert model_observation(before, after)['state'] == 'changed'


def test_invalid_observation_selection_and_endpoint_make_no_network_request():
    with patch('app.model_health.requests.get') as get:
        for names in ([], ['a', 'b', 'c'], 'chat', [None], ['x' * 513]):
            with pytest.raises(ValueError):
                observe_models('http://127.0.0.1:11434', names)
        snapshot = observe_models('https://user:secret@example.org', ['chat'])
    assert snapshot['state'] == 'unavailable' and 'secret' not in json.dumps(snapshot)
    get.assert_not_called()
