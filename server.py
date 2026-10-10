#!/usr/bin/env python3
"""Loopback PWA; CodexBar is the only quota/authentication collector."""
import concurrent.futures
import datetime as dt
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PROVIDERS = ('claude', 'codex')
INTERVAL = 300
STALE_AFTER = 900
ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
COLLECTOR = os.environ.get('CODEXBAR_BIN', 'codexbar')
STATE = Path(os.environ.get('STATE_DIRECTORY', str(Path.home() / '.local/state/subscription-limits')))
PUBLIC_HOST = os.environ.get('PUBLIC_HOST', 'localhost')


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Missing timestamp')
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Missing timezone')
    return result.timestamp()


def iso_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def saved_resets(raw):
    """Expose only the authoritative count and expiry timestamps."""
    if not isinstance(raw, dict):
        return None
    count = raw.get('availableCount')
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 2**53 - 1:
        return None
    expiries = []
    credits = raw.get('credits')
    if isinstance(credits, list):
        for credit in credits:
            if not isinstance(credit, dict) or credit.get('status') != 'available':
                continue
            expiry = credit.get('expires_at')
            try:
                timestamp(expiry)
            except (ValueError, TypeError, OverflowError):
                expiry = None
            expiries.append(expiry)
            if len(expiries) >= min(count, 100):
                break
    return {'availableCount': count, 'expiresAt': expiries if count else []}


def normalize(row, provider, now=None):
    """Allowlist data; never forward identity, tokens, raw errors or details."""
    now = time.time() if now is None else now
    if row.get('provider') != provider or row.get('error'):
        raise ValueError('Provider failed')
    usage = row.get('usage')
    if not isinstance(usage, dict):
        raise ValueError('Missing usage')
    updated = usage.get('updatedAt')
    if timestamp(updated) > now + 60:
        raise ValueError('Future timestamp')
    windows = {}
    for name, field, minutes in [('fiveHour', 'primary', 300), ('weekly', 'secondary', 10080)]:
        raw = usage.get(field)
        window = None
        if isinstance(raw, dict) and raw.get('windowMinutes') == minutes:
            used = raw.get('usedPercent')
            if isinstance(used, (int, float)) and not isinstance(used, bool) and math.isfinite(used) and 0 <= used <= 100:
                reset = raw.get('resetsAt')
                try:
                    timestamp(reset)
                except (ValueError, TypeError, OverflowError):
                    reset = None
                window = {'usedPercent': used, 'resetsAt': reset}
        windows[name] = window
    if not any(windows.values()):
        raise ValueError('No known windows')
    return {'id': provider, 'lastSuccess': updated, 'windows': windows,
            'savedResets': saved_resets(usage.get('codexResetCredits')) if provider == 'codex' else None}


def error_kind(row):
    message = str(row.get('error', {}).get('message', '')).lower()
    if any(word in message for word in ('oauth', 'token expired', 'unauthorized', 'credential', 'login', 'sign in', 'authentication')):
        return 'auth'
    if any(word in message for word in ('429', 'rate limit', 'too many requests')):
        return 'rateLimited'
    return 'collector'


def fetch(provider):
    # Explicit OAuth avoids browser-cookie imports and broad local cost scans.
    # Claude CLI can renew its own saved OAuth login when that token expires.
    for source in ('oauth', 'cli') if provider == 'claude' else ('oauth',):
        try:
            result = subprocess.run([COLLECTOR, 'usage', '--provider', provider, '--source', source,
                                     '--format', 'json'], capture_output=True, text=True, timeout=45)
            rows = json.loads(result.stdout)
            if not isinstance(rows, list):
                raise ValueError('Invalid root')
            rows = [row for row in rows if isinstance(row, dict) and row.get('provider') == provider]
            if len(rows) != 1:
                raise ValueError('Ambiguous account')
            row = rows[0]
            if row.get('error'):
                kind = error_kind(row)
                if provider == 'claude' and source == 'oauth' and kind == 'auth':
                    continue
                return None, kind
            return normalize(row, provider), None
        except subprocess.TimeoutExpired:
            return None, 'timeout'
        except (OSError, ValueError, TypeError, OverflowError):
            return None, 'collector'
    return None, 'auth'


class Collector:
    def __init__(self, state=STATE):
        self.state = state
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.refreshing = False
        self.last_attempt = 0
        self.good = {}
        self.errors = {}
        try:
            saved = json.loads((state / 'last-good.json').read_text())
            # Revalidate persistent data through the same allowlist.
            for provider in PROVIDERS:
                item = saved.get(provider)
                if item:
                    windows = item.get('windows', {})
                    usage = {'updatedAt': item.get('lastSuccess')}
                    resets = item.get('savedResets')
                    if isinstance(resets, dict):
                        expiries = resets.get('expiresAt')
                        usage['codexResetCredits'] = {
                            'availableCount': resets.get('availableCount'),
                            'credits': [{'status': 'available', 'expires_at': expiry}
                                        for expiry in expiries] if isinstance(expiries, list) else []}
                    for name, field, minutes in [('fiveHour', 'primary', 300), ('weekly', 'secondary', 10080)]:
                        raw = windows.get(name)
                        if isinstance(raw, dict):
                            usage[field] = {**raw, 'windowMinutes': minutes}
                    self.good[provider] = normalize({'provider': provider, 'usage': usage}, provider)
        except (OSError, ValueError, TypeError, AttributeError):
            self.good = {}

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            providers = []
            for provider in PROVIDERS:
                item = self.good.get(provider)
                reset_due = item and any(window and window['resetsAt'] and timestamp(window['resetsAt']) <= now for window in item['windows'].values())
                status = 'unavailable' if not item else 'stale' if provider in self.errors or reset_due or now - timestamp(item['lastSuccess']) > STALE_AFTER else 'fresh'
                providers.append({**(item or {'id': provider, 'lastSuccess': None, 'windows': {'fiveHour': None, 'weekly': None}, 'savedResets': None}),
                                  'status': status, 'error': self.errors.get(provider)})
            return {'providers': providers, 'refreshing': self.refreshing,
                    'serverTime': iso_now(), 'refreshIntervalSeconds': INTERVAL, 'staleAfterSeconds': STALE_AFTER}

    def refresh(self):
        with self.lock:
            self.refreshing = True
            self.last_attempt = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            jobs = {executor.submit(fetch, provider): provider for provider in PROVIDERS}
            for job in concurrent.futures.as_completed(jobs):
                provider = jobs[job]
                try:
                    item, error = job.result()
                except Exception:
                    item, error = None, 'collector'
                with self.lock:
                    if item:
                        self.good[provider] = item
                        self.errors.pop(provider, None)
                    else:
                        self.errors[provider] = error
        try:
            self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
            temporary = self.state / 'last-good.tmp'
            with self.lock:
                data = json.dumps(self.good, allow_nan=False)
            with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as handle:
                handle.write(data)
            temporary.replace(self.state / 'last-good.json')
        except OSError:
            print('Could not persist last-good quota data', flush=True)
        finally:
            with self.lock:
                self.refreshing = False

    def request_refresh(self):
        with self.lock:
            if self.refreshing or time.monotonic() - self.last_attempt < 60:
                return False
            self.wake.set()
            return True

    def run(self):
        while not self.stop.is_set():
            self.wake.clear()
            self.refresh()
            self.wake.wait(INTERVAL)


collector = Collector()
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/index.html': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8'),
          '/sw.js': ('sw.js', 'text/javascript; charset=utf-8'),
          '/manifest.webmanifest': ('manifest.webmanifest', 'application/manifest+json'),
          '/icon-180.png': ('icon-180.png', 'image/png'),
          '/icon-192.png': ('icon-192.png', 'image/png'),
          '/icon-512.png': ('icon-512.png', 'image/png')}


class Handler(BaseHTTPRequestHandler):
    def route(self):
        path = urlsplit(self.path).path
        return path.removeprefix('/limits') if path.startswith('/limits/') else path

    def allowed_host(self):
        try:
            host = urlsplit('http://' + self.headers.get('Host', '')).hostname
            return host in ('127.0.0.1', 'localhost', PUBLIC_HOST)
        except ValueError:
            return False

    def reply(self, code, body, mime='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if mime == 'application/json' else 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed_host():
            return self.reply(403, b'{}')
        if urlsplit(self.path).path == '/limits':
            self.send_response(308)
            self.send_header('Location', '/limits/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        path = self.route()
        if path == '/api/usage':
            return self.reply(200, json.dumps(collector.snapshot(), allow_nan=False).encode())
        if path == '/health':
            return self.reply(200, b'{"status":"ok"}')
        if path not in ASSETS:
            return self.reply(404, b'{}')
        filename, mime = ASSETS[path]
        return self.reply(200, (WEB / filename).read_bytes(), mime)

    def do_POST(self):
        if not self.allowed_host():
            return self.reply(403, b'{}')
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin', '')
        if origin not in (f'https://{host}', f'http://{host}'):
            return self.reply(403, b'{}')
        if self.route() != '/api/refresh':
            return self.reply(404, b'{}')
        accepted = collector.request_refresh()
        self.reply(202 if accepted else 429, json.dumps({'accepted': accepted}).encode())
        # No request bodies are accepted; close to avoid persistent-body ambiguity.
        self.close_connection = True

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    threading.Thread(target=collector.run, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', 18740), Handler)
    def shutdown(*_):
        collector.stop.set()
        collector.wake.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print('Subscription limits listening on 127.0.0.1:18740', flush=True)
    server.serve_forever()
