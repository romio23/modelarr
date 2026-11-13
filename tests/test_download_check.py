"""Test: een duidelijke melding bij een download van een ontbrekend bestand (mount offline of bestand weg). Gebruik: python tests/test_download_check.py"""
import os, shutil, sys, tempfile, time
import trimesh
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.join(tempfile.gettempdir(), 'modelbib-storage')
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(f'{ROOT}/m'); os.environ['CONFIG_DIR'] = f'{ROOT}/cfg'; sys.path.insert(0, APP)
import app as A
A.init(); A.put('min_age', '0'); bad = []
def check(n, ok, extra=''): print('OK  ' if ok else 'FOUT', n, extra); (None if ok else bad.append(n))
trimesh.creation.box((10, 10, 10)).export(f'{ROOT}/m/doos.stl'); os.utime(f'{ROOT}/m/doos.stl', (time.time() - 600,) * 2)
with A.db() as d: d.execute('INSERT INTO roots(path, allow_write) VALUES(?, 0)', (f'{ROOT}/m',))
for _ in range(50):
    if A.scan() is not False: break
    time.sleep(.2)
c = A.app.test_client(); H = {'X-Requested-With': 'modelbib'}
mid = c.get('/api/library').get_json()['models'][0]['id']
check('  download-controle ok, download zelf werkt', c.get(f'/api/file/{mid}/check').get_json()['ok'] and c.get(f'/api/file/{mid}').status_code == 200)
os.rename(f'{ROOT}/m/doos.stl', f'{ROOT}/doos.stl')   # share 'leeg'
r = c.get(f'/api/file/{mid}/check')
check('  download: 404 met duidelijke melding over de mount', r.status_code == 404 and 'mount' in r.get_json()['error'], r.get_json())
shutil.rmtree(f'{ROOT}/m'); r = c.get(f'/api/file/{mid}/check')
check('  map weg (onbereikbaar): dezelfde melding', r.status_code == 404 and 'mount' in r.get_json()['error'])
os.makedirs(f'{ROOT}/m'); open(f'{ROOT}/m/ander.txt', 'w').write('x')   # map terug, bestand blijft weg
r = c.get(f'/api/file/{mid}/check')
check('bestand verwijderd terwijl de map er is: melding over verplaatst/verwijderd', r.status_code == 404 and 'niet meer op de schijf' in r.get_json()['error'], r.get_json())
print('\nAlles goed.' if not bad else f'\n{len(bad)} fout(en)'); sys.exit(1 if bad else 0)
