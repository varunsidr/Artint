"""Bounded, anonymous Playwright rendering for public JavaScript articles.

All HTTP traffic is intercepted and fetched through the public-URL policy.
No personal browser profile, sign-in, form submission or challenge solving.
"""
import asyncio
from contextlib import suppress
import importlib.util
import os
import sys
import time
from urllib.parse import urljoin, urlparse

import requests

from app import extract

RENDER_SECONDS = 40
MAX_REQUESTS = 60
MAX_HOSTS = 12
MAX_RESOURCE_BYTES = 2_000_000
MAX_TRANSFER_BYTES = 15_000_000
ALLOWED_RESOURCES = {'document', 'script', 'stylesheet', 'xhr', 'fetch'}

# Rendered snapshots contain visible reading content and ordinary metadata,
# never hidden paywall text, executable scripts or JSON article-body payloads.
VISIBLE_SNAPSHOT = r'''() => {
  const root = document.body;
  if (!root) return '';
  const copy = root.cloneNode(true);
  const originals = [...root.querySelectorAll('*')];
  const clones = [...copy.querySelectorAll('*')];
  const omitted = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'IFRAME', 'FORM', 'BUTTON', 'OBJECT', 'EMBED']);
  originals.forEach((node, i) => {
    const style = getComputedStyle(node);
    if (omitted.has(node.tagName) || node.hidden || node.getAttribute('aria-hidden') === 'true'
        || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') clones[i].remove();
  });
  const head = [...document.head.querySelectorAll('title,meta,link[rel=canonical]')].map(node => node.outerHTML).join('');
  return '<!doctype html><html><head>' + head + '</head>' + copy.outerHTML + '</html>';
}'''


def installed():
    return importlib.util.find_spec('playwright') is not None


def _navigation_policy(url):
    parsed = extract.validate_public_url(url)
    policy = extract._robots(f'{parsed.scheme}://{parsed.netloc}')
    if not policy.can_fetch(extract.UA, url):
        raise extract.ExtractionError('robots.txt disallows this browser navigation.')
    rate = policy.request_rate(extract.UA)
    interval = max(1.0, policy.crawl_delay(extract.UA) or 0, rate.seconds / rate.requests if rate else 0)
    if interval > 30:
        raise extract.ExtractionError('Publisher crawl delay exceeds the browser fetch budget.')
    extract._rate_limit(url, interval)


def _read_resource(url, headers, maximum, remaining):
    """Stream a single validated hop; the browser never follows an unchecked redirect."""
    extract.validate_public_url(url)
    try:
        with requests.get(url, headers=headers, timeout=(min(5, remaining), min(12, remaining)),
                          stream=True, allow_redirects=False) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                destination = response.headers.get('Location')
                if not destination:
                    raise extract.ExtractionError('Browser resource redirect has no destination.')
                extract.validate_public_url(urljoin(url, destination))
                return response.status_code, {'Location': destination}, b''
            chunks, size, started = [], 0, time.monotonic()
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > maximum or time.monotonic() - started >= remaining:
                    raise extract.ExtractionError('Browser resource exceeded its size or time limit.')
                chunks.append(chunk)
            # iter_content has decompressed the response. Strip transfer headers
            # so Chromium does not attempt to decompress or truncate it again.
            result_headers = {key: value for key, value in response.headers.items()
                              if key.lower() not in ('content-encoding', 'content-length', 'transfer-encoding', 'connection')}
            return response.status_code, result_headers, b''.join(chunks)
    except requests.RequestException as exc:
        raise extract.ExtractionError('A browser resource could not be fetched within the network limits.') from exc


async def _launch(playwright):
    requested = os.getenv('ARTICLE_BROWSER_CHANNEL', 'auto').lower()
    if requested not in ('auto', 'chrome', 'msedge', 'chromium'):
        raise extract.ExtractionError('ARTICLE_BROWSER_CHANNEL must be auto, chrome, msedge or chromium.')
    choices = ['chrome', 'msedge', 'chromium'] if requested == 'auto' else [requested]
    for channel in choices:
        try:
            options = dict(headless=True, timeout=8000)
            if channel != 'chromium':
                options['channel'] = channel
            return await playwright.chromium.launch(**options)
        except Exception:
            continue
    raise extract.ExtractionError('No supported browser could start. Install Chrome/Edge or run: python -m playwright install chromium. HTML-only imports remain available.')


async def _render(url, initial_html):
    from playwright.async_api import Error, TimeoutError as BrowserTimeout, async_playwright

    _navigation_policy(url)
    initial = initial_html.encode('utf-8')
    if len(initial) > extract.MAX_HTML_BYTES:
        raise extract.ExtractionError('Initial browser HTML exceeds the 5 MB limit.')
    started = time.monotonic()
    budget = dict(requests=0, transferred=0, reserved=0, navigations=0, hosts=set(), failure=None, seeded=False)
    semaphore = asyncio.Semaphore(2)
    async with async_playwright() as playwright:
        browser = await asyncio.wait_for(_launch(playwright), timeout=max(.1, RENDER_SECONDS - (time.monotonic() - started)))
        try:
            context = await browser.new_context(user_agent=extract.UA, service_workers='block',
                                               accept_downloads=False, viewport={'width': 1280, 'height': 900},
                                               # Fail closed if Chromium creates any unhandled traffic.
                                               # All allowed responses are fulfilled by the Python transport.
                                               proxy={'server': 'http://browser-network-disabled.invalid:9',
                                                      'bypass': '<-loopback>'})
            await context.route_web_socket('**/*', lambda route: route.close())
            await context.add_init_script('''
                window.open = () => null;
                window.RTCPeerConnection = undefined;
                window.webkitRTCPeerConnection = undefined;
                navigator.sendBeacon = () => false;
            ''')
            page = await context.new_page()
            page.on('dialog', lambda dialog: dialog.dismiss())

            async def route_request(route, request):
                if request.method != 'GET' or request.resource_type not in ALLOWED_RESOURCES:
                    await route.abort(); return
                is_document = request.resource_type == 'document'
                if is_document and request.frame != page.main_frame:
                    await route.abort(); return
                try:
                    async with semaphore:
                        remaining = RENDER_SECONDS - (time.monotonic() - started)
                        if remaining <= 0 or budget['requests'] >= MAX_REQUESTS:
                            raise extract.ExtractionError('Browser rendering reached its request or time limit.')
                        budget['requests'] += 1
                        parsed = extract.validate_public_url(request.url)
                        budget['hosts'].add((parsed.hostname, parsed.port))
                        if len(budget['hosts']) > MAX_HOSTS:
                            raise extract.ExtractionError('Browser rendering reached its host limit.')
                        hops, previous = 0, request.redirected_from
                        while previous:
                            hops += 1; previous = previous.redirected_from
                        if hops >= 5:
                            raise extract.ExtractionError('Browser resource exceeded five redirect hops.')
                        if is_document:
                            budget['navigations'] += 1
                            if budget['navigations'] > 5:
                                raise extract.ExtractionError('Browser page exceeded its navigation limit.')
                            if not (request.url == url and not budget['seeded']):
                                await asyncio.to_thread(_navigation_policy, request.url)
                        if request.url == url and is_document and not budget['seeded']:
                            budget['seeded'] = True
                            status, headers, body = 200, {'Content-Type': 'text/html; charset=utf-8'}, initial
                        else:
                            headers = {'User-Agent': extract.UA, 'Accept': request.headers.get('accept', '*/*')}
                            for key in ('referer', 'origin', 'cookie'):
                                if key in request.headers:
                                    headers[key] = request.headers[key]
                            maximum = extract.MAX_HTML_BYTES if is_document else MAX_RESOURCE_BYTES
                            maximum = min(maximum, MAX_TRANSFER_BYTES - budget['transferred'] - budget['reserved'])
                            if maximum <= 0:
                                raise extract.ExtractionError('Browser rendering exceeded its transfer limit.')
                            budget['reserved'] += maximum
                            try:
                                target, request_headers = request.url, headers
                                for hop in range(5):
                                    if hop:
                                        remaining = RENDER_SECONDS - (time.monotonic() - started)
                                        if remaining <= 0 or budget['requests'] >= MAX_REQUESTS:
                                            raise extract.ExtractionError('Browser resource reached its request or time limit.')
                                        budget['requests'] += 1
                                        parsed = extract.validate_public_url(target)
                                        budget['hosts'].add((parsed.hostname, parsed.port))
                                        if len(budget['hosts']) > MAX_HOSTS:
                                            raise extract.ExtractionError('Browser rendering reached its host limit.')
                                    status, headers, body = await asyncio.to_thread(_read_resource, target, request_headers, maximum, max(.1, remaining))
                                    if status not in (301, 302, 303, 307, 308):
                                        break
                                    # Chromium can follow a fulfilled redirect without
                                    # invoking this handler again. Follow resource hops
                                    # in the validated transport; never fulfill a 3xx.
                                    if is_document:
                                        raise extract.ExtractionError('This rendered page redirected. Import the final publisher URL directly instead.')
                                    destination = next((value for key, value in headers.items() if key.lower() == 'location'), '')
                                    if not destination:
                                        raise extract.ExtractionError('Browser resource redirect has no destination.')
                                    target = urljoin(target, destination)
                                    extract.validate_public_url(target)
                                    # Never carry cookies or origin headers to a redirected host.
                                    request_headers = {'User-Agent': extract.UA, 'Accept': '*/*'}
                                else:
                                    raise extract.ExtractionError('Browser resource exceeded its redirect limit.')
                            finally:
                                budget['reserved'] -= maximum
                        budget['transferred'] += len(body)
                        if budget['transferred'] > MAX_TRANSFER_BYTES:
                            raise extract.ExtractionError('Browser rendering exceeded its 15 MB transfer limit.')
                        if is_document:
                            if status in (401, 403, 429):
                                raise extract.ExtractionError(f'Publisher blocked browser access (HTTP {status}).')
                            content_type = next((value for key, value in headers.items() if key.lower() == 'content-type'), '')
                            if status == 200 and 'html' not in content_type.lower():
                                raise extract.ExtractionError('Browser navigation did not return an HTML article.')
                        await route.fulfill(status=status, headers=headers, body=body)
                except extract.ExtractionError as exc:
                    # A private/invalid resource is blocked even if unrelated to
                    # the body. Document policy failures also fail the capture.
                    if is_document or 'limit' in str(exc).lower() or 'budget' in str(exc).lower():
                        budget['failure'] = str(exc)
                    await route.abort()
                except Error:
                    pass  # The bounded render may already have closed its page.

            await context.route('**/*', route_request)
            async with asyncio.timeout(max(.1, RENDER_SECONDS - (time.monotonic() - started))):
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                    try:
                        await page.wait_for_function('''() => {
                            const root = document.querySelector('article,[itemprop=articleBody],main,[role=main]') || document.body;
                            return root && root.innerText.trim().length >= 320 && root.querySelectorAll('p').length >= 2;
                        }''', timeout=15000)
                    except BrowserTimeout:
                        pass  # Snapshot is still validated by the article parser.
                    await page.wait_for_timeout(800)
                    if budget['failure']:
                        raise extract.ExtractionError(budget['failure'])
                    gate = extract.access_gate(await page.content())
                    if gate:
                        raise extract.ExtractionError(gate)
                    html = await page.evaluate(VISIBLE_SNAPSHOT)
                    final_url = page.url
                    extract.validate_public_url(final_url)
                    if len(html.encode('utf-8')) > extract.MAX_HTML_BYTES:
                        raise extract.ExtractionError('Rendered HTML exceeds the 5 MB limit.')
                    return html, final_url
                except Error as exc:
                    raise extract.ExtractionError(budget['failure'] or 'Browser rendering could not load readable public content.') from exc
        finally:
            with suppress(Error, TimeoutError):
                await asyncio.wait_for(browser.close(), timeout=5)


def render_article_html(url, initial_html):
    if not installed():
        raise extract.ExtractionError('This JavaScript page needs Playwright. Install project requirements, or choose HTML only.')
    try:
        # Use a local subprocess-capable loop on Windows; do not replace
        # Streamlit/Tornado's process-global event-loop policy.
        factory = asyncio.ProactorEventLoop if sys.platform == 'win32' else asyncio.new_event_loop
        with asyncio.Runner(loop_factory=factory) as runner:
            return runner.run(_render(url, initial_html))
    except TimeoutError as exc:
        raise extract.ExtractionError('Browser rendering exceeded its 40-second time budget.') from exc
