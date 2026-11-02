"""Read-only installation diagnostics; optional local browser and health checks."""
import argparse
import asyncio
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def local_health(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username or parsed.password:
        raise ValueError('Health checks accept only a local HTTP URL.')
    with urlopen(url, timeout=3) as response:
        if response.status != 200 or response.read(16).strip() != b'ok':
            raise ValueError('Streamlit is not healthy.')


async def browser_check():
    from app.browser_render import _launch
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await _launch(playwright)
        try:
            page = await browser.new_page()
            result = {'version': browser.version, 'sandbox_requested': True}
            if sys.platform == 'linux':
                await page.goto('chrome://sandbox')
                text = await page.locator('body').inner_text()
                # Chromium's own internal page, not an inference from launch success.
                import re
                namespace = (re.search(r'Layer 1 Sandbox\s+Namespace\b', text)
                             or re.search(r'Namespace sandbox\s+Yes\b', text))
                if not namespace:
                    raise RuntimeError(f'Chromium did not report namespace isolation enabled: {text}')
                for label in ('PID namespaces', 'Network namespaces', 'Seccomp-BPF sandbox'):
                    if not re.search(re.escape(label) + r'\s+Yes\b', text):
                        raise RuntimeError(f'Chromium did not report {label} enabled: {text}')
                result['namespace_and_seccomp_sandbox'] = True
            return result
        finally:
            await browser.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true', help='Launch a local blank browser; verify Linux sandbox status.')
    parser.add_argument('--health-url', help='Check an existing local Streamlit health endpoint only.')
    parser.add_argument('--apparmor-profile', action='store_true', help='Print a profile for the installed Chromium path; does not install or load it.')
    parser.add_argument('--ollama', action='store_true', help='Read model inventory, runtime compatibility and loaded GPU/CPU residency; no inference.')
    parser.add_argument('--ollama-url', help='Model endpoint for --ollama; defaults to OLLAMA_BASE_URL or native loopback.')
    parser.add_argument('--chat-model', default='qwen3:8b', help='Selected answer model checked with --ollama.')
    parser.add_argument('--embedding-model', default='qwen3-embedding:0.6b', help='Selected search model checked with --ollama.')
    args = parser.parse_args(argv)
    try:
        if args.ollama:
            if args.apparmor_profile or args.health_url or args.browser:
                raise ValueError('Run --ollama separately from browser, AppArmor or Streamlit health checks.')
            from app.model_health import inspect_ollama
            report = inspect_ollama(args.ollama_url, chat_model=args.chat_model, embedding_model=args.embedding_model)
            ok = report['answer_ready'] and report['search_ready']
            print(json.dumps(dict(ok=ok, ollama=report, storage='Not opened or modified.'), indent=2))
            if not ok:
                raise SystemExit(1)
            return
        if args.ollama_url:
            raise ValueError('--ollama-url requires --ollama.')
        if args.apparmor_profile:
            if sys.platform != 'linux':
                raise ValueError('AppArmor profiles apply to Linux only.')
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                executable = playwright.chromium.executable_path
            if any(character in executable for character in '\r\n\0'):
                raise ValueError('Browser path contains control characters.')
            escaped = executable.replace('\\', '\\\\').replace('"', '\\"')
            print('abi <abi/4.0>,\ninclude <tunables/global>\n'
                  f'profile artint-chromium "{escaped}" flags=(unconfined) {{\n  userns,\n}}')
            return
        if args.health_url:
            local_health(args.health_url)
            print('ok')
            return
        with sqlite3.connect(':memory:') as con:
            con.execute('CREATE VIRTUAL TABLE install_check USING fts5(text)')
        result = dict(python=platform.python_version(), platform=platform.platform(), sqlite=sqlite3.sqlite_version,
                      fts5=True, streamlit=version('streamlit'), playwright=version('playwright'),
                      library_db=os.getenv('ARTICLE_LIBRARY_DB', str(ROOT / 'data/articles.db')),
                      pdf_dir=os.getenv('ARTICLE_PDF_DIR', str(ROOT / 'output/pdfs')),
                      ollama='Optional; no model service was contacted.', storage='Not opened or modified.')
        if args.browser:
            result['browser'] = asyncio.run(browser_check())
        print(json.dumps(dict(ok=True, **result), indent=2))
    except Exception as exc:
        print(json.dumps(dict(ok=False, error=str(exc))), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
