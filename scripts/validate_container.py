"""Build/test a disposable compose project; never use the user's app volumes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def validate(report_path=None):
    project = 'artint-check-' + uuid.uuid4().hex[:12]
    environment = dict(os.environ, ARTINT_PORT='0', OLLAMA_BASE_URL='http://127.0.0.1:9')
    result = dict(ok=False, project=project)
    owns_project = False

    def run(args, capture=False):
        completed = subprocess.run(args, cwd=ROOT, env=environment, check=True, text=True,
                                   stdout=subprocess.PIPE if capture else None)
        return completed.stdout.strip() if capture else None

    with tempfile.TemporaryDirectory(prefix='artint-compose-') as temporary:
        empty_env = Path(temporary) / 'empty.env'
        empty_env.write_text('', encoding='utf-8')
        compose = ['docker', 'compose', '--env-file', str(empty_env), '-p', project, '-f', str(ROOT / 'compose.yaml')]
        try:
            if run(compose + ['ps', '-aq'], capture=True):
                raise RuntimeError('Disposable project name already exists.')
            if run(['docker', 'volume', 'ls', '--filter', 'label=com.docker.compose.project=' + project,
                    '--format', '{{.Name}}'], capture=True):
                raise RuntimeError('Disposable project volumes already exist.')
            owns_project = True
            run(compose + ['up', '--build', '-d', '--wait', '--wait-timeout', '180'])
            container = run(compose + ['ps', '-q', 'artint'], capture=True)
            metadata = json.loads(run(['docker', 'inspect', container], capture=True))[0]
            host = metadata['HostConfig']
            binding = metadata['NetworkSettings']['Ports']['8501/tcp']
            if not binding or any(item['HostIp'] != '127.0.0.1' for item in binding):
                raise RuntimeError('App port is not restricted to host loopback.')
            if metadata['Config']['User'] not in ('artint', '10001', '10001:10001') or not host['ReadonlyRootfs']:
                raise RuntimeError('Expected non-root/read-only runtime.')
            if 'ALL' not in host['CapDrop'] or any(item['Type'] != 'volume' for item in metadata['Mounts']):
                raise RuntimeError('Expected capability drop and isolated named volumes.')
            if not any(option in ('no-new-privileges:true', 'no-new-privileges=true') for option in host['SecurityOpt']):
                raise RuntimeError('Expected no-new-privileges.')
            if not any(option.startswith('seccomp=') and option != 'seccomp=unconfined' for option in host['SecurityOpt']):
                raise RuntimeError('Expected a confined seccomp profile.')
            for mount in metadata['Mounts']:
                volume = json.loads(run(['docker', 'volume', 'inspect', mount['Name']], capture=True))[0]
                if volume['Labels'].get('com.docker.compose.project') != project:
                    raise RuntimeError('Volume is outside the disposable project.')
            result.update(local_binding=True, non_root=True, read_only=True, isolated_volumes=True)
            run(compose + ['exec', '-T', 'artint', 'python', 'scripts/check_install.py', '--browser'])
            run(compose + ['exec', '-T', 'artint', 'python', 'scripts/smoke_install.py'])
            prepared = json.loads(run(compose + ['exec', '-T', '-e', 'ARTINT_INSTALL_SMOKE=1', 'artint',
                                               'python', 'scripts/smoke_install.py', '--persistent', 'prepare'], capture=True))
            run(compose + ['up', '-d', '--force-recreate', '--wait', '--wait-timeout', '180'])
            run(compose + ['exec', '-T', '-e', 'ARTINT_INSTALL_SMOKE=1', 'artint',
                           'python', 'scripts/smoke_install.py', '--persistent', 'verify'])
            result.update(sandbox=True, offline_export_restore=True, recreation_persistence=True)
            container = run(compose + ['ps', '-q', 'artint'], capture=True)
            test_image = project + ':test'
            run(['docker', 'build', '--target', 'test', '-t', test_image, '.'])
            run(['docker', 'run', '--rm', '--init', '--read-only', '--cap-drop', 'ALL',
                 '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=' + str(ROOT / 'docker/chromium-seccomp.json'),
                 '--shm-size', '256m', '--tmpfs', '/tmp:rw,size=268435456,mode=1777', '--pids-limit', '256',
                 '--network', 'container:' + container,
                 '-e', 'ARTINT_UI_SMOKE_URL=http://127.0.0.1:8501',
                 '-e', 'ARTINT_EXPECT_PDF_SHA=' + prepared['pdf_sha256'],
                 test_image, 'python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests'])
            result.update(ok=True, container_tests=True, live_ui_pdf_search=True)
        except Exception as exc:
            result['error'] = str(exc)
            subprocess.run(compose + ['logs', '--tail', '40'], cwd=ROOT, env=environment, check=False)
            raise
        finally:
            # Only the randomly named project created above is removed. No -v
            # is ever run against the ordinary user's compose project.
            if owns_project:
                cleanup = subprocess.run(compose + ['down', '--volumes', '--remove-orphans'], cwd=ROOT, env=environment, check=False)
                result['cleanup'] = cleanup.returncode == 0
            if report_path:
                path = Path(report_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    validate(parser.parse_args().report)
