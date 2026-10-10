import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright, expect

BASE=os.environ['LIMITS_URL']
from urllib.parse import urlsplit
args=['--no-sandbox']
if os.environ.get('LIMITS_HOST_IP'):
 args.append(f"--host-resolver-rules=MAP {urlsplit(BASE).hostname} {os.environ['LIMITS_HOST_IP']}")
OUT=Path(os.environ.get('LIMITS_SCREENSHOT_DIR', '/tmp/limits-browser-review'))
OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as playwright:
 browser=playwright.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=args)
 for name,width,height in [('mobile',390,844),('desktop',1440,1000)]:
  context=browser.new_context(viewport={'width':width,'height':height})
  page=context.new_page();errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  with page.expect_response(lambda response: response.url==BASE+'api/usage') as usage_response:
   response=page.goto(BASE,wait_until='networkidle')
  assert response.status==200
  assert page.evaluate('isSecureContext')
  expect(page.locator('.status')).to_have_text(['Current','Current'],timeout=15000)
  live=usage_response.value.json()
  for provider in live['providers']:
   section=page.locator('.provider.'+provider['id'])
   for key in ['fiveHour','weekly']:
    left = 100 - provider['windows'][key]['usedPercent']
    expect(section.locator(f'[data-window="{key}"] .percentage')).to_have_text(f'{left:g}% left')
    assert section.locator(f'[data-window="{key}"] progress').evaluate('(bar) => bar.value') == left
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  assert not errors
  page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
  print(name+': private HTTPS, certificate validation, real usage, no overflow/JS errors')
  if name=='mobile':
   page.evaluate('navigator.serviceWorker.ready')
   page.wait_for_function('navigator.serviceWorker.controller !== null')
   assert page.evaluate('navigator.serviceWorker.controller.scriptURL')==BASE+'sw.js'
   manifest=page.evaluate('fetch("./manifest.webmanifest").then(r=>r.json())')
   assert manifest['display']=='standalone' and manifest['start_url']=='./'
   post=page.evaluate('fetch("./api/refresh",{method:"POST"}).then(r=>r.status)')
   assert post in [202,429]
   context.set_offline(True);page.reload(wait_until='domcontentloaded')
   expect(page.locator('#connection')).to_contain_text('Offline')
   expect(page.locator('.status')).to_have_text(['Stale','Stale'])
   page.screenshot(path=str(OUT/'offline.png'),full_page=True)
   print('HTTPS offline shell, scoped service worker and sanitized saved usage passed')
  context.close()
 browser.close()
