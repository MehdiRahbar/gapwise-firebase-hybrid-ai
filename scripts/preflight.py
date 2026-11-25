"""No external dependencies. Check source-tree integrity before handing off."""
import json,re,hashlib,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
html=(root/'web/index.html').read_text(encoding='utf-8')
app=(root/'web/app.mjs').read_text(encoding='utf-8')
ids=set(re.findall(r'\bid="([^"]+)"',html))
used=set(re.findall(r"\$\('([^']+)'\)",app))
missing=sorted(used-ids)
assert not missing,f'Missing DOM IDs: {missing}'
assert len(re.findall(r'<script[^>]+src="app.mjs"',html))==1
checks={}
for p in (root/'web').glob('*.mjs'):
 r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True)
 checks[p.name]=r.returncode==0
 if r.returncode:raise AssertionError(f'JavaScript syntax failure {p.name}: {r.stderr}')
fh_txt=(root/'web/firebase-hybrid.mjs').read_text()
assert "import('firebase/ai')" in fh_txt
assert 'initializeDeviceModel' in fh_txt
assert 'inferenceSource' in fh_txt
assert 'ReCaptchaEnterpriseProvider' in fh_txt or 'ReCaptchaV3Provider' in fh_txt
pkg=json.loads((root/'package.json').read_text())
assert pkg['dependencies']['firebase'].startswith('13.')
assert json.loads((root/'firebase.json').read_text())['hosting']['public']=='dist'
checks['html_dom_id_references']=len(used)
checks['firebase_npm_runtime_imports']=True
checks['app_check_runtime_configuration']=True
checks['credential_files_committed']=False
tracked = subprocess.run(['git', 'ls-files'], cwd=str(root), capture_output=True, text=True)
if tracked.returncode == 0:
 for rel in tracked.stdout.splitlines():
  if rel.endswith('.env') or rel.endswith('.env.local') or rel.endswith('google-services.json') or rel.endswith('serviceAccountKey.json') or rel.endswith('.keystore') or rel.endswith('.jks'):
   raise AssertionError('Forbidden secret/config file tracked in git: ' + rel)
for f in root.rglob('*'):
 if not f.is_file():continue
 if any(part in ('node_modules','dist','.git','.firebase','.gradle','build','scratch') for part in f.parts):continue
 if f.name=='.env.local':
  txt=f.read_text(encoding='utf-8',errors='ignore')
  if re.search(r'(APPCHECK_DEBUG_TOKEN\s*=|PRIVATE KEY|service_account)',txt,re.I):
   raise AssertionError('Forbidden secret token in .env.local')
  continue
 if (f.name.startswith('.env.') and f.name!='.env.example') or f.name in ('.env','serviceAccountKey.json','firebase-adminsdk.json'):
  raise AssertionError('Forbidden secrets file in output: '+str(f))
print(json.dumps({'status':'PASS','checks':checks,'scope':'static integrity, not browser or Firebase live verification'},indent=2))
