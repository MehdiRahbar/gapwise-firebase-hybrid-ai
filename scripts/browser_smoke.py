import json,os,shutil,socket,subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
OUT=root/'evidence'
OUT.mkdir(exist_ok=True)
env=os.environ.copy()
node_dir=str(Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'NodeJS-24.20.0'/'node-v24.20.0-win-x64')
if Path(node_dir).is_dir():env['PATH']=node_dir+';'+env.get('PATH','')
node_exe=shutil.which('node.exe' if os.name=='nt' else 'node',path=env.get('PATH')) or 'node'
vite_bin=root/'node_modules'/'vite'/'bin'/'vite.js'
use_preview=(root/'dist'/'index.html').is_file() and vite_bin.is_file()
cmd=[node_exe,str(vite_bin),'preview','--host','127.0.0.1','--port','18199','--strictPort'] if use_preview else [sys.executable,'-m','http.server','18199','--bind','127.0.0.1','--directory',str(root/'web')]
server=subprocess.Popen(cmd,cwd=str(root),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for _ in range(50):
 try:
  with socket.create_connection(('127.0.0.1',18199),timeout=0.3):break
 except OSError:time.sleep(0.1)

def launch_browser(p):
 for ch in (None, 'msedge', 'chrome'):
  try:
   return p.chromium.launch(channel=ch) if ch else p.chromium.launch()
  except Exception:
   continue
 return p.chromium.launch()

results={}
try:
 with sync_playwright() as p:
  browser=launch_browser(p)
  page=browser.new_page(viewport={'width':1440,'height':900})
  errors=[];console_errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('console',lambda m:console_errors.append(m.text) if m.type=='error' else None)
  page.goto('http://127.0.0.1:18199/',wait_until='networkidle')
  assert 'MORE INFORMATION REQUIRED' in page.locator('#result').inner_text()
  assert page.locator('#aiProgress').get_attribute('aria-live')=='polite'
  results['initial_decision']='ASK'
  page.locator('#loadSampleSourceBtn').click()
  page.locator('.review-item').first.wait_for()
  assert page.locator('.review-item').count()==2,page.locator('#reviewQueue').inner_text()
  results['new_requirements_from_fictional_source']=2
  # Untested source cannot yield positive, despite all Yes.
  for b in page.locator('.cond-controls button[data-value="yes"]').all():b.click()
  page.locator('#sourceVerified').check();page.locator('#coverageReviewed').check()
  assert 'MORE INFORMATION REQUIRED' in page.locator('#result').inner_text()
  results['positive_blocked_on_unreviewed_source']='PASS'
  for _ in range(2):page.locator('.review-item:not(.review-finished) [data-review="add"]').first.click()
  assert page.locator('#reviewCounter').inner_text().startswith('0')
  for b in page.locator('.cond-controls button[data-value="yes"]').all():b.click()
  page.locator('#reviewerName').fill('QA Lead Audit')
  page.locator('#sourceVerified').check();page.locator('#coverageReviewed').check()
  res_text=page.locator('#result').inner_text()
  assert 'CONDITIONAL · HUMAN-ATTESTED' in res_text,res_text
  results['bounded_yes_after_human_attestations']='PASS'
  with page.expect_download() as dl:page.locator('#exportBtn').click()
  download=dl.value
  target=OUT/'smoke_audit_download.json'
  download.save_as(target)
  payload=json.loads(target.read_text(encoding='utf-8'))
  assert payload['decision']['status']=='YES'
  assert payload['certificationTier']=='CONDITIONAL_HUMAN_ATTESTED'
  assert payload['independentVerification'] is False
  assert len(payload['policy']['terms'])==6
  results['audit_download_contains_6_requirements']='PASS'
  page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
  # Check NO, CONFLICT, OUT_OF_SCOPE and verify scope toggle invalidates coverageReviewed
  page.locator('.cond-controls button[data-value="no"]').first.click()
  assert 'NOT ELIGIBLE UNDER THIS POLICY' in page.locator('#result').inner_text()
  page.locator('.cond-controls button[data-value="conflict"]').nth(1).click()
  assert 'CONFLICTING EVIDENCE' in page.locator('#result').inner_text()
  page.locator('#scopeAccepted').uncheck()
  assert 'OUTSIDE THE POLICY SCOPE' in page.locator('#result').inner_text()
  assert not page.locator('#coverageReviewed').is_checked(),'Scope toggle must invalidate coverageReviewed'
  page.locator('#scopeAccepted').check()
  page.locator('.cond-controls button[data-value="yes"]').first.click()
  page.locator('.cond-controls button[data-value="yes"]').nth(1).click()
  page.locator('#coverageReviewed').check()
  assert 'CONDITIONAL · HUMAN-ATTESTED' in page.locator('#result').inner_text()
  results['no_conflict_out_of_scope_and_invalidation']='PASS'
  # sourceName change & question change invalidate provenance/coverage; XSS never executes; inline dismiss works
  page.locator('#sourceNameInput').fill('Edited policy title')
  assert not page.locator('#sourceVerified').is_checked()
  assert not page.locator('#coverageReviewed').is_checked()
  page.locator('#sourceText').fill('Policy requires seal <img src=x onerror="window.__xss=1"> before return.')
  assert 'MORE INFORMATION REQUIRED' in page.locator('#result').inner_text()
  assert page.evaluate('window.__xss === undefined')
  results['source_change_invalidates_and_xss_safe']='PASS'
  assert page.locator('.dismiss-box').first.is_hidden()
  page.locator('.review-item:not(.review-finished) [data-review="dismiss"]').first.click()
  assert not page.locator('.dismiss-box').first.is_hidden()
  page.locator('[data-dismiss-input]').first.fill('Covered under manual review')
  page.locator('[data-review="confirm-dismiss"]').first.click()
  assert page.locator('#reviewCounter').inner_text().startswith('0')
  results['inline_dismiss_with_reason']='PASS'
  # Overlong >550-char single clause must NOT allow human-attested YES and must display truncation warning
  page.locator('#examples button[data-index="0"]').click()
  overlong_single_clause=('This refund policy applies to ordinary requests received through our service team '*10)+' Cash refunds require a verified original payment method'
  assert len(overlong_single_clause)>550
  page.locator('#sourceText').fill(overlong_single_clause)
  for b in page.locator('.cond-controls button[data-value="yes"]').all():b.click()
  page.locator('#sourceVerified').check();page.locator('#coverageReviewed').check()
  overlong_res=page.locator('#result').inner_text()
  assert 'CONDITIONAL · HUMAN-ATTESTED' not in overlong_res,overlong_res
  assert 'MORE INFORMATION REQUIRED' in overlong_res,overlong_res
  assert 'Source scan truncated' in overlong_res,overlong_res
  results['overlong_clause_blocks_human_attested_yes']='PASS'
  # Shorter normal document still works without regression
  page.locator('#loadSampleSourceBtn').click()
  assert page.locator('.review-item').count()==2
  for _ in range(2):page.locator('.review-item:not(.review-finished) [data-review="add"]').first.click()
  for b in page.locator('.cond-controls button[data-value="yes"]').all():b.click()
  page.locator('#sourceVerified').check();page.locator('#coverageReviewed').check()
  assert 'CONDITIONAL · HUMAN-ATTESTED' in page.locator('#result').inner_text()
  results['shorter_doc_normal_flow_after_overlong']='PASS'
  # Short standalone prohibitions ("No refunds.", "No return.", "Void.") must surface and block human-attested YES
  for short_ban, key in [('No refunds.', 'short_no_refunds_blocks_human_attested_yes'), ('No return.', 'short_no_return_blocks_human_attested_yes'), ('Void.', 'short_void_blocks_human_attested_yes')]:
    page.locator('#examples button[data-index="0"]').click()
    short_doc = (
      'Request is within 14 days of delivery.\n'
      'Customer can provide order proof.\n'
      'Item is unused and in original condition.\n'
      'Item is not marked final sale.\n'
      f'{short_ban}'
    )
    page.locator('#sourceText').fill(short_doc)
    for b in page.locator('.cond-controls button[data-value="yes"]').all(): b.click()
    page.locator('#sourceVerified').check()
    page.locator('#coverageReviewed').check()
    res_short = page.locator('#result').inner_text()
    assert 'MORE INFORMATION REQUIRED' in res_short, res_short
    assert 'CONDITIONAL · HUMAN-ATTESTED' not in res_short, res_short
    results[key] = 'PASS'
  # Adaptive Inquiry UI check: Turn 1 -> Turn 2 -> HUMAN-ATTESTED YES + "I don't know" non-nag persistent ASK
  page.locator('#examples button[data-index="0"]').click()
  page.locator('#loadSampleSourceBtn').click()
  assert page.locator('#nextQuestion .adaptive-item').count() >= 1, page.locator('#nextQuestion').inner_text()
  assert page.locator('#nextQuestion .adaptive-cite').count() >= 1
  for b in page.locator('.cond-controls button[data-value="yes"]').all(): b.click()
  # Resolve the 2 discovered clauses directly through Adaptive Inquiry Yes buttons
  for _ in range(2):
    yes_aq = page.locator('#nextQuestion [data-aq-act="yes"]').first
    yes_aq.wait_for()
    yes_aq.click()
  # Answer both attestation checkboxes and verify transition to CONDITIONAL HUMAN-ATTESTED
  page.locator('#sourceVerified').check()
  page.locator('#coverageReviewed').check()
  assert 'CONDITIONAL · HUMAN-ATTESTED' in page.locator('#result').inner_text(), page.locator('#result').inner_text()
  results['adaptive_inquiry_resolve_to_yes'] = 'PASS'

  # Reset to Case 0 and test "I don't know" on first missing condition: stays ASK and stops nagging on that item
  page.locator('#examples button[data-index="0"]').click()
  first_aq_id = page.locator('#nextQuestion [data-aq-act="dunno"]').first.get_attribute('data-aq-id')
  assert first_aq_id
  page.locator('#nextQuestion [data-aq-act="dunno"]').first.click()
  assert 'MORE INFORMATION REQUIRED' in page.locator('#result').inner_text()
  remaining_ids = [el.get_attribute('data-aq-id') for el in page.locator('#nextQuestion [data-aq-act="dunno"]').all()]
  assert first_aq_id not in remaining_ids, remaining_ids
  results['adaptive_dunno_no_nag_persistent_ask'] = 'PASS'

  # Dialog Escape focus restore check
  page.locator('#settingsBtn').click()
  page.wait_for_timeout(120)
  page.keyboard.press('Escape')
  page.wait_for_timeout(120)
  assert page.evaluate('document.activeElement?.id')=='settingsBtn'
  results['dialog_focus_restore']='PASS'
  # Tablet 768x1024, Mobile 390x844, and Compact Mobile 360x740
  for name,w,h in [('tablet',768,1024),('mobile',390,844),('mobile_360',360,740)]:
   page.set_viewport_size({'width':w,'height':h})
   page.wait_for_timeout(120)
   page.screenshot(path=str(OUT/f'{name}.png'),full_page=True)
   overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 2')
   assert not overflow,f'Horizontal scroll overflows {w}x{h} viewport'
   results[f'{name}_{w}_no_horizontal_scroll']='PASS'
  assert not errors,errors
  assert not console_errors,console_errors
  results['browser_page_errors']=[]
  results['console_errors']=[]
  browser.close()
finally:
 server.terminate();server.wait(timeout=4)
(OUT/'browser_smoke.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
