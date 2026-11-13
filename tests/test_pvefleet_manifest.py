"""Test: pvefleet-app.json (voor de Apps-pagina van PVE Fleet) is geldig JSON en de versie klopt met app.py. Gebruik: python tests/test_pvefleet_manifest.py"""
import json, os, re, sys
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); bad = []
def check(n, ok, extra=''): print('OK  ' if ok else 'FOUT', n, extra); (None if ok else bad.append(n))
m = json.load(open(os.path.join(APP, 'pvefleet-app.json')))
ver = re.search(r"VERSION\s*=\s*'([^']+)'", open(os.path.join(APP, 'app.py')).read()).group(1)
check('versie in pvefleet-app.json = VERSION in app.py (verhoog ze samen)', m['version'] == ver, (m['version'], ver))
check('systemd-dienst modelarr in /opt/modelarr met venv', m['type'] == 'systemd' and m['service'] == 'modelarr' and m['dir'] == '/opt/modelarr' and m['venv'] == 'venv')
print('\nAlles goed.' if not bad else f'\n{len(bad)} fout(en)'); sys.exit(1 if bad else 0)
