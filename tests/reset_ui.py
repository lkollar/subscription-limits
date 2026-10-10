"""Browser regressions against a running app, using synthetic API responses."""
import copy
import datetime as dt
import os
import shutil
from playwright.sync_api import sync_playwright, expect

base = os.environ.get('LIMITS_URL', 'http://127.0.0.1:18740/limits/')
now = dt.datetime.now(dt.timezone.utc).isoformat()
fixture = {'serverTime': now, 'staleAfterSeconds': 900, 'providers': [
    {'id': provider, 'lastSuccess': now, 'status': 'fresh', 'error': None,
     'windows': {key: {'usedPercent': 25, 'resetsAt': '2030-01-17T17:00:00Z'}
                 for key in ['fiveHour', 'weekly']},
     'savedResets': {'availableCount': 2, 'expiresAt': ['2030-01-18T17:00:00Z', None]}
                    if provider == 'codex' else None}
    for provider in ['claude', 'codex']]}
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
    for zone, clock in [('Europe/London', '17:00'), ('America/New_York', '12:00')]:
        context = browser.new_context(viewport={'width': 320, 'height': 740}, timezone_id=zone, locale='en-GB')
        page = context.new_page()
        data = copy.deepcopy(fixture)
        page.route('**/api/usage', lambda route: route.fulfill(json=data))
        page.goto(base, wait_until='networkidle')
        expect(page.locator('.reset-time').first).to_contain_text(clock)
        expect(page.locator('.provider.claude .resets-unavailable')).to_be_visible()
        expect(page.locator('.provider.codex .reset-count')).to_have_text('2 available ›')
        page.locator('.provider.codex summary').click()
        expect(page.locator('.reset-expiries li')).to_have_count(2)
        expect(page.locator('.reset-expiries li').last).to_contain_text('Expiry unavailable')
        page.wait_for_timeout(1100)
        assert page.locator('.saved-resets').last.get_attribute('open') is not None
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        data['providers'][1]['savedResets'] = {'availableCount': 0, 'expiresAt': []}
        page.reload(wait_until='networkidle')
        expect(page.locator('.provider.codex .reset-count')).to_have_text('0 available ›')
        data['providers'][1]['savedResets'] = None
        page.reload(wait_until='networkidle')
        expect(page.locator('.provider.codex .resets-unavailable')).to_be_visible()
        data['providers'][1]['savedResets'] = {'availableCount': 2, 'expiresAt': ['2020-01-01T00:00:00Z']}
        page.reload(wait_until='networkidle')
        expect(page.locator('.provider.codex .reset-count')).to_have_text('2 at last refresh ›')
        page.locator('.provider.codex summary').click()
        expect(page.locator('.provider.codex .reset-hint')).to_contain_text('may have changed')
        data['providers'][1]['status'] = 'stale'
        data['providers'][1]['savedResets']['expiresAt'] = ['2030-01-18T17:00:00Z']
        page.reload(wait_until='networkidle')
        expect(page.locator('.provider.codex .reset-count')).to_have_text('2 at last refresh ›')
        context.close()
    browser.close()
print('Timezone conversion, expiry/zero/unavailable/stale resets, expansion and 320px layout passed')
