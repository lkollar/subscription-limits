import copy
import json
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright, expect

BASE=os.environ.get('LIMITS_URL','http://127.0.0.1:18740/limits/')
OUT=Path(os.environ.get('LIMITS_SCREENSHOT_DIR', '/tmp/limits-browser-review'))
OUT.mkdir(parents=True,exist_ok=True)

with sync_playwright() as playwright:
 browser=playwright.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 for device,width,height in [('mobile',390,844),('desktop',1440,1000),('small',320,740)]:
  context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
  page=context.new_page(); errors=[]
  page.on('pageerror',lambda error:errors.append(str(error)))
  with page.expect_response(lambda response: response.url==BASE+'api/usage') as usage_response:
   response=page.goto(BASE,wait_until='networkidle')
  assert response.status==200
  expect(page.locator('.status')).to_have_text(['Current','Current'],timeout=15000)
  live=usage_response.value.json()
  for item in live['providers']:
   section=page.locator('.provider.'+item['id'])
   for key in ['fiveHour','weekly']:
    left = 100 - item['windows'][key]['usedPercent']
    expect(section.locator(f'[data-window="{key}"] .percentage')).to_have_text(f'{left:g}% left')
    assert section.locator(f'[data-window="{key}"] progress').evaluate('(bar) => bar.value') == left
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),device+' horizontal overflow'
  assert not errors,errors
  page.screenshot(path=str(OUT/(device+'.png')),full_page=True)
  print(device+': live quota percentages, countdowns, no overflow or JS errors')
  if device=='mobile':
   page.evaluate('navigator.serviceWorker.ready')
   page.wait_for_function('navigator.serviceWorker.controller !== null')
   assert page.evaluate('navigator.serviceWorker.controller.scriptURL').endswith('/limits/sw.js')
   manifest=context.request.get(BASE+'manifest.webmanifest').json()
   assert manifest['display']=='standalone' and manifest['scope']=='./'
   for icon in manifest['icons']:
    assert context.request.get(BASE+icon['src'][2:]).body().startswith(b'\x89PNG')
   # Verify browser POST uses the actual host/origin and never requires a token.
   request=context.request.post(BASE+'api/refresh',headers={'Origin':BASE.split('/limits/')[0]})
   assert request.status in [202,429]
   assert context.request.post(BASE+'api/refresh',headers={'Origin':'https://untrusted.example'}).status==403
   assert context.request.get(BASE+'../../.claude/.credentials.json').status==404
   assert context.request.get(BASE+'api/usage').headers.get('cache-control')=='no-store'
   context.set_offline(True)
   page.reload(wait_until='domcontentloaded')
   expect(page.locator('#connection')).to_contain_text('Offline')
   expect(page.locator('.status')).to_have_text(['Stale','Stale'])
   assert page.locator('.percentage').first.inner_text()!='— unavailable'
   page.screenshot(path=str(OUT/'offline.png'),full_page=True)
   print('offline: app shell reloads; saved readings explicitly stale')
   context.set_offline(False)
   page.reload(wait_until='networkidle')
   expect(page.locator('.status')).to_have_text(['Current','Current'],timeout=15000)
   # Fault injection uses sanitized live readings, preserving actual quota values.
   broken=copy.deepcopy(live)
   broken['refreshing']=False
   broken['providers'][0].update(status='stale',error='auth')
   broken['providers'][1].update(status='unavailable',error='collector',lastSuccess=None,windows={'fiveHour':None,'weekly':None})
   page.route('**/api/usage',lambda route:route.fulfill(json=broken))
   page.reload(wait_until='networkidle')
   expect(page.locator('.status')).to_have_text(['Stale','Unavailable'])
   expect(page.locator('.provider.claude .issue')).to_contain_text('login on the server')
   expect(page.locator('.provider.codex .percentage').first).to_contain_text('unavailable')
   assert page.locator('.provider.codex progress:visible').count()==0
   page.screenshot(path=str(OUT/'unavailable.png'),full_page=True)
   print('failures: auth/stale and unavailable distinct; no false zero quota')
   old=copy.deepcopy(live)
   for item in old['providers']:
    item['lastSuccess']='2026-10-01T00:00:00Z'
    item['windows']['fiveHour']['resetsAt']='2026-10-01T00:00:00Z'
    item['windows']['weekly']['resetsAt']=None
   page.unroute('**/api/usage')
   page.route('**/api/usage',lambda route:route.fulfill(json=old))
   page.reload(wait_until='networkidle')
   expect(page.locator('.status')).to_have_text(['Stale','Stale'])
   expect(page.locator('.provider.claude [data-window="fiveHour"] .countdown')).to_have_text('Reset due · awaiting fresh usage')
   expect(page.locator('.provider.claude [data-window="weekly"] .countdown')).to_have_text('Reset time unavailable')
   print('aging: old success stale; expired/missing reset handled explicitly')
   # No successful data and no network must render a useful shell, too.
   page.unroute('**/api/usage')
   page.evaluate('localStorage.clear()')
   context.set_offline(True)
   page.reload(wait_until='domcontentloaded')
   expect(page.locator('.status')).to_have_text(['Unavailable','Unavailable'])
   print('offline without saved data: both providers unavailable')
  context.close()
 # Dark mode accessibility and layout sanity.
 context=browser.new_context(viewport={'width':390,'height':844},color_scheme='dark')
 page=context.new_page();page.goto(BASE,wait_until='networkidle')
 expect(page.locator('.status')).to_have_text(['Current','Current'],timeout=15000)
 assert page.evaluate('getComputedStyle(document.body).backgroundColor')=='rgb(20, 35, 31)'
 page.screenshot(path=str(OUT/'dark.png'),full_page=True)
 context.close();browser.close()
 print('dark: system preference applied')
