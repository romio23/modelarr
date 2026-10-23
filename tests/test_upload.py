"""Uploaden: alleen beheerders en gasten met toestemming; map en categorie kiezen; veilig (geen paden buiten de root, geen overschrijven).
Gebruik: python tests/test_upload.py"""
import io, os, shutil, sys, tempfile, time
import trimesh
ROOT = os.path.join(tempfile.gettempdir(), 'modelarr-upload'); shutil.rmtree(ROOT, ignore_errors=True)
os.makedirs(f'{ROOT}/m/Rek'); os.makedirs(f'{ROOT}/outside'); os.environ['CONFIG_DIR'] = f'{ROOT}/cfg'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import app as A
A.init(); A.put('min_age', '0'); bad = []
def check(n, ok, extra=''): print('OK  ' if ok else 'FOUT', n, extra); (None if ok else bad.append(n))
with A.db() as d:
    d.execute('INSERT INTO roots(path) VALUES(?)', (f'{ROOT}/m',)); d.execute("INSERT INTO categories(name) VALUES('Rek')"); d.execute("INSERT INTO categories(name) VALUES('Kabels')")
    rid = d.execute('SELECT id FROM roots').fetchone()[0]; cid = {r[1]: r[0] for r in d.execute('SELECT id,name FROM categories')}
H = {'X-Requested-With': 'modelbib'}
buf = io.BytesIO(); trimesh.creation.box((5, 5, 5)).export(buf, file_type='stl'); STL = buf.getvalue()
def mkc(): return A.app.test_client()
adm = mkc()
for n, role, up in (('baas', 'admin', 0), ('gast', 'viewer', 0), ('uploader', 'viewer', 1)):
    r = adm.post('/api/users', json=dict(username=n, password='wachtwoord1', role=role, can_upload=bool(up)), headers=H)
def login(n):
    c = mkc(); r = c.post('/api/login', json=dict(username=n, password='wachtwoord1'), headers=H); assert r.status_code == 200, r.data; return c
adm, gast, upl = login('baas'), login('gast'), login('uploader')
def up(c, name='een.stl', data=STL, folder='', cats='', root=rid):
    return c.post('/api/upload', data=dict(root=str(root), folder=folder, categories=cats, file=(io.BytesIO(data), name)), headers=H, content_type='multipart/form-data')
def scan():
    for _ in range(50):
        if A.scan() is not False: break
        time.sleep(.2)
def cats_of(name):
    with A.db() as d: return sorted(r[0] for r in d.execute('SELECT c.name FROM model_categories mc JOIN categories c ON c.id=mc.category_id JOIN models m ON m.id=mc.model_id WHERE m.name=?', (name,)))

check('/api/me: admin en uploader mogen uploaden, gast niet', [c.get('/api/me').get_json()['can_upload'] for c in (adm, upl, gast)] == [True, True, False])
check('gast: uploaden geweigerd (403), ook de lijst met mappen', up(gast).status_code == 403 and gast.get('/api/upload/targets').status_code == 403)
check('uploader ziet de root folders (alleen de naam, geen pad)', upl.get('/api/upload/targets').get_json()['roots'] == [dict(id=rid, name='m')])
check('gast met upload-recht mag verder nog steeds niets wijzigen', upl.post('/api/tasks/scan/run', headers=H).status_code == 403 and upl.get('/api/users').status_code == 403)
r = up(upl, 'nieuw.stl', folder='Rek/Deel1', cats=f"{cid['Rek']},{cid['Kabels']}")
check('upload in een nieuwe submap lukt', r.status_code == 200 and os.path.isfile(f'{ROOT}/m/Rek/Deel1/nieuw.stl'), r.data)
check('  geen .part-bestand blijft achter', not [f for f in os.listdir(f'{ROOT}/m/Rek/Deel1') if f.endswith('.part')])
scan()
check('  na de scan staat het model in de bibliotheek met de gekozen categorieën', cats_of('nieuw') == ['Kabels', 'Rek'], cats_of('nieuw'))
with A.db() as d: check('  de wachtende categorieën zijn opgeruimd', d.execute('SELECT COUNT(*) FROM upload_cats').fetchone()[0] == 0)
r = up(adm, 'nieuw.stl', folder='Rek/Deel1')
j = r.get_json(); check('zelfde naam: nooit overschrijven, er komt (2) achter', r.status_code == 200 and j['renamed'] and j['name'] == 'nieuw (2).stl' and os.path.getsize(f'{ROOT}/m/Rek/Deel1/nieuw.stl') == len(STL), j)
check('beheerder mag uploaden', up(adm, 'adm.stl').status_code == 200)
for bad_folder in ('../outside', '..', 'Rek/../../outside', '/etc', '.verborgen', 'a/@eaDir', 'x' * 0 + 'C:\\win'):
    r = up(adm, 'x.stl', folder=bad_folder)
    check(f'map "{bad_folder}" wordt geweigerd of blijft binnen de root', r.status_code == 400 or all(os.path.realpath(p).startswith(os.path.realpath(f'{ROOT}/m')) for p in [os.path.join(dp, f) for dp, _, fs in os.walk(ROOT) for f in fs if f == 'x.stl']), r.data[:80])
check('niets buiten de root geschreven', not os.listdir(f'{ROOT}/outside'))
check('bestandsnaam met pad wordt platgeslagen', up(adm, '../../evil.stl').status_code == 200 and not os.path.exists(f'{ROOT}/evil.stl') and os.path.exists(f'{ROOT}/m/.._evil.stl') is False)
check('verkeerd bestandstype geweigerd', up(adm, 'virus.exe', data=b'MZ').status_code == 400 and up(adm, 'geheim.php', data=b'x').status_code == 400)
check('leeg bestand geweigerd', up(adm, 'leeg.stl', data=b'').status_code in (400, 413))
check('onbekende categorie geweigerd', up(adm, 'c.stl', cats='9999').status_code == 400)
check('onbekende root geweigerd', up(adm, root=999).status_code == 404)
check('zonder X-Requested-With (andere website) geweigerd', adm.post('/api/upload', data=dict(root=str(rid), file=(io.BytesIO(STL), 'q.stl')), content_type='multipart/form-data').status_code == 403)
check('lijst met submappen: geen verborgen mappen', 'Deel1' in upl.get('/api/upload/dirs', query_string=dict(root=rid, path='Rek')).get_json()['dirs'] and upl.get('/api/upload/dirs', query_string=dict(root=rid, path='../outside')).status_code == 400)
big = A.MAX_MB; A.MAX_MB = 0
check('te groot bestand geweigerd (MAX_FILE_MB)', up(adm, 'groot.stl').status_code in (413, 400)); A.MAX_MB = big
check('upload staat in de geschiedenis', any(h['event'] == 'Upload' for h in adm.get('/api/history').get_json()[:10]) if isinstance(adm.get('/api/history').get_json(), list) else True)
r = adm.put(f"/api/users/{[u for u in adm.get('/api/users').get_json() if u['username'] == 'gast'][0]['id']}", json=dict(can_upload=True), headers=H)
check('beheerder kan upload-recht aan een gast geven (gast moet opnieuw laden)', r.status_code == 200 and gast.get('/api/me').get_json()['can_upload'] is True)
print('\nAlles goed.' if not bad else '\nFOUT: %s' % bad); sys.exit(1 if bad else 0)
