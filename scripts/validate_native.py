"""Launch a disposable native app and verify its live library without Ollama."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def stop(process):
    if process.poll() is None:
        if os.name == 'nt':
            # Only the process tree created by this validator, including the venv launcher.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], check=False, capture_output=True)
        else:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    from check_install import local_health

    with tempfile.TemporaryDirectory(prefix='artint-native-check-') as temporary:
        workspace = Path(temporary)
        environment = dict(os.environ, ARTICLE_LIBRARY_DB=str(workspace / 'data/library.db'),
                           ARTICLE_PDF_DIR=str(workspace / 'pdfs'), ARTINT_INSTALL_SMOKE='1',
                           OLLAMA_BASE_URL='http://127.0.0.1:9', STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')
        prepare = subprocess.run([sys.executable, 'scripts/smoke_install.py', '--persistent', 'prepare'],
                                 cwd=ROOT, env=environment, check=True, capture_output=True, text=True)
        record = json.loads(prepare.stdout)
        with socket.socket() as available:
            available.bind(('127.0.0.1', 0))
            port = available.getsockname()[1]
        command = [sys.executable, '-m', 'streamlit', 'run', 'app/dashboard.py',
                   '--server.address', '127.0.0.1', '--server.port', str(port)]
        with (workspace / 'server.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 40
                while True:
                    try:
                        local_health(f'http://127.0.0.1:{port}/_stcore/health')
                        break
                    except Exception:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError('Native app startup failed: ' + (workspace / 'server.log').read_text(encoding='utf-8'))
                        time.sleep(.25)
                environment.update(ARTINT_UI_SMOKE_URL=f'http://127.0.0.1:{port}', ARTINT_EXPECT_PDF_SHA=record['pdf_sha256'])
                subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests/test_installation.py',
                                '-k', 'running_installation'], cwd=ROOT, env=environment, check=True)
            finally:
                stop(process)
        subprocess.run([sys.executable, 'scripts/smoke_install.py', '--persistent', 'verify'],
                       cwd=ROOT, env=environment, check=True)
        print(json.dumps(dict(ok=True, native_startup=True, live_search_pdf_notes=True,
                              preserved_after_server_stop=True, ollama_required=False)))


if __name__ == '__main__':
    main()
