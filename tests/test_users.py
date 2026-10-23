"""Test: meerdere gebruikers (beheerder/gast), inloggen, rechten, downloaden en beveiliging. Gebruik: python tests/test_users.py"""
import base64, os, shutil, sys, tempfile, time
import trimesh
from werkzeug.security import generate_password_hash
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.join(tempfile.gettempdir(), 'modelbib-users')
shutil.rmtree(ROOT, ignore_errors=True); M = f'{ROOT}/models'; os.makedirs(M); os.environ['CONFIG_DIR'] = f'{ROOT}/cfg'; sys.path.insert(0, APP)
import app as A
BOX = trimesh.exchange.stl.export_stl(trimesh.creation.box((40, 20, 10))); open(f'{M}/doos.stl', 'wb').write(BOX); os.utime(f'{M}/doos.stl', (time.time() - 600,) * 2)
A.init(); A.put('min_age', '0'); A.put('api_key', 'k' * 32)
with A.db() as d: d.execute('INSERT INTO roots(path) VALUES(?)', (M,))
A.scan(); bad = []
def check(n, ok, extra=''): print('OK  ' if ok else 'FOUT', n, extra); (None if ok else bad.append(n))
H = {'X-Requested-With': 'modelbib'}; mk = lambda: A.app.test_client()
admin, anon = mk(), mk()
basic = lambda u, p: {'Authorization': 'Basic ' + base64.b64encode(f'{u}:{p}'.encode()).decode()}
check('zonder accounts: iedereen is beheerder, inloggen niet verplicht', anon.get('/api/me').get_json() == {'auth': False, 'user': None, 'role': 'admin', 'can_download': True, 'can_upload': True} and anon.get('/api/library').status_code == 200)
mid = anon.get('/api/library').get_json()['models'][0]['id']; anon.post(f'/api/models/{mid}', json={'notes': 'privé notitie', 'favorite': True})
check('eerste account: slechte gegevens geweigerd', all(admin.post('/api/users', json=b).status_code == 400 for b in ({'username': 'a b', 'password': 'wachtwoord1'}, {'username': '', 'password': 'wachtwoord1'}, {'username': 'x' * 41, 'password': 'wachtwoord1'}, {'username': 'beheer', 'password': 'kort'})))
r = admin.post('/api/users', json={'username': 'beheer', 'password': 'geheim-123', 'role': 'viewer'}); me = admin.get('/api/me').get_json()
check('eerste account wordt altijd beheerder en is meteen ingelogd', r.status_code == 200 and r.get_json()['auto_login'] and me['role'] == 'admin' and me['user'] == 'beheer' and admin.get('/api/library').status_code == 200, me)
a = anon.get('/api/library')
check('daarna: anoniem krijgt 401 met login=true, zonder wachtwoordvenster van de browser', a.status_code == 401 and a.get_json()['login'] is True and 'WWW-Authenticate' not in a.headers)
check('open voor iedereen: inlogpagina, bestanden, ping, /api/me', anon.get('/').status_code == 200 and anon.get('/static/app.js').status_code == 200 and anon.get('/ping').status_code == 200 and anon.get('/api/me').get_json() == {'auth': True, 'user': None, 'role': None, 'can_download': False, 'can_upload': False})
check('ondertekende links werken zonder account (401 niet van toepassing)', anon.get('/dl/onzin/x.stl').status_code == 403)
# ---- inloggen en afremmen
for i in range(5): assert anon.post('/api/login', json={'username': 'beheer', 'password': 'fout'}).status_code == 401
check('na 5 foute pogingen: 429, ook met het juiste wachtwoord', anon.post('/api/login', json={'username': 'beheer', 'password': 'geheim-123'}).status_code == 429)
A.FAILS.clear(); lg = anon.post('/api/login', json={'username': 'BEHEER', 'password': 'geheim-123'})
sc = lg.headers.get('Set-Cookie', '')
check('inloggen (hoofdletterongevoelig); cookie is HttpOnly en SameSite=Lax', lg.status_code == 200 and 'HttpOnly' in sc and 'SameSite=Lax' in sc, sc[:90])
check('onbekende gebruiker en foute invoer: 401, geen crash', mk().post('/api/login', json={'username': 'nietbestaand', 'password': 'x'}).status_code == 401 and mk().post('/api/login', json={}).status_code == 401); A.FAILS.clear()
# ---- beveiliging tegen verzoeken vanaf andere websites; Basic en API-sleutel
check('sessie + wijzigend verzoek zonder X-Requested-With: 403; mét: 200', admin.post('/api/categories', json={'name': 'A'}).status_code == 403 and admin.post('/api/categories', json={'name': 'A'}, headers=H).status_code == 200)
check('Basic-authenticatie en API-sleutel hoeven die header niet', mk().post('/api/categories', json={'name': 'B'}, headers=basic('beheer', 'geheim-123')).status_code == 200 and mk().post('/api/categories', json={'name': 'C'}, headers={'X-Api-Key': 'k' * 32}).status_code == 200)
check('API-sleutel via de URL en foute Basic-gegevens: 401', mk().get('/api/library?apikey=' + 'k' * 32).status_code == 401 and mk().get('/api/library', headers=basic('beheer', 'fout')).status_code == 401)
# ---- gasten
check('gebruiker toevoegen: dubbele naam (hoofdletterongevoelig) 409', admin.post('/api/users', json={'username': 'Gast', 'password': 'wachtwoord1'}, headers=H).status_code == 200 and admin.post('/api/users', json={'username': 'gast', 'password': 'wachtwoord1'}, headers=H).status_code == 409)
admin.post('/api/users', json={'username': 'gast2', 'password': 'wachtwoord2', 'can_download': False}, headers=H)
g1, g2 = mk(), mk(); g1.post('/api/login', json={'username': 'gast', 'password': 'wachtwoord1'}); g2.post('/api/login', json={'username': 'gast2', 'password': 'wachtwoord2'})
ok_codes = lambda c, ps: [(m, p, getattr(c, m)(p, **({'json': {}, 'headers': H} if m == 'post' else {})).status_code) for m, p in ps]
allowed = [('get', '/api/library'), ('get', '/api/rev'), ('get', '/api/printers'), ('get', '/api/me'), ('get', '/api/thumb/1.png')]
denied = [('get', '/api/settings'), ('get', '/api/users'), ('get', '/api/status'), ('get', '/api/logs'), ('get', '/api/tasks'), ('get', '/api/history'), ('get', '/api/queue'), ('get', '/api/duplicates'), ('get', '/api/wanted'), ('get', f'/api/models/{mid}/prints'), ('get', '/api/fs'), ('get', '/api/roots'), ('get', '/api/spoolman/spools'),
          ('post', f'/api/models/{mid}'), ('post', '/api/categories'), ('post', '/api/assign'), ('post', '/api/roots'), ('post', '/api/settings'), ('post', '/api/users'), ('post', f'/api/models/{mid}/prints'), ('post', f'/api/models/{mid}/open'), ('post', '/api/tasks/scan/run'), ('post', f'/api/models/{mid}/trash'), ('post', '/api/models/bulk'), ('post', f'/api/models/{mid}/thumb'), ('post', '/api/users/clear')]
check('gast mag bekijken (geen 401/403)', all(c not in (401, 403) for _, _, c in ok_codes(g1, allowed)), ok_codes(g1, allowed))
res = ok_codes(g1, denied); check('gast mag niets wijzigen of beheren (alles 403)', all(c == 403 for _, _, c in res), [x for x in res if x[2] != 403])
check('gast met download-recht: bestand, 3D-weergave en slicer-link', g1.get(f'/api/file/{mid}').data == BOX and g1.get(f'/api/mesh/{mid}.stl').status_code == 200 and g1.post(f'/api/models/{mid}/link', headers=H).status_code == 200)
check('gast zonder download-recht: alles 403, maar de bibliotheek wel', all(g2.get(f'/api/file/{mid}').status_code == 403 for _ in [0]) and g2.get(f'/api/mesh/{mid}.stl').status_code == 403 and g2.post(f'/api/models/{mid}/link', headers=H).status_code == 403 and g2.get('/api/library').status_code == 200)
lib_a, lib_g = admin.get('/api/library').get_json()['models'][0], g1.get('/api/library', environ_overrides={'REMOTE_ADDR': '127.0.0.1'}).get_json()
mg = lib_g['models'][0]
check('beheerder ziet pad en notitie', lib_a['path'].startswith(M) and lib_a['notes'] == 'privé notitie' and lib_a['favorite'] is True)
check('gast ziet geen bestandspad, notitie, favoriet of foutmelding; geen bewerken/openen/Spoolman', not mg['path'].startswith('/') and ROOT not in mg['path'] and mg['notes'] == '' and mg['favorite'] is False and mg['can_rename'] is False and lib_g['local'] is False and lib_g['spoolman'] is False, mg['path'])
ev = [h for h in admin.get('/api/history').get_json() if h['event'].startswith('Download')]
check('downloads van gasten staan in de geschiedenis met de naam', any('Gast downloadde doos' in h['message'] for h in ev) and any('Gast opende doos.stl in de slicer' in h['message'] for h in ev), [h['message'] for h in ev])
link = g1.post(f'/api/models/{mid}/link', headers=H).get_json()['path']; check('slicer-link van een gast werkt zonder inloggen (10 min)', mk().get(link).data == BOX)
# ---- e-mailadres
check('e-mailadres: ongeldig 400, geldig 200, dubbel (hoofdletterongevoelig) 409', admin.post('/api/users', json={'username': 'kees', 'password': 'wachtwoord4', 'email': 'geen-adres'}, headers=H).status_code == 400
      and admin.post('/api/users', json={'username': 'kees', 'password': 'wachtwoord4', 'email': 'Kees@Example.nl', 'role': 'viewer'}, headers=H).status_code == 200
      and admin.post('/api/users', json={'username': 'piet', 'password': 'wachtwoord5', 'email': 'kees@example.NL'}, headers=H).status_code == 409)
ul = {u['username']: u for u in admin.get('/api/users').get_json()}; kid = ul['kees']['id']
check('lijst toont het e-mailadres; gebruikers zonder adres tonen leeg', ul['kees']['email'] == 'Kees@Example.nl' and ul['beheer']['email'] == '')
check('inloggen met e-mailadres (hoofdletterongevoelig) en Basic met e-mailadres', mk().post('/api/login', json={'username': 'KEES@example.nl', 'password': 'wachtwoord4'}).status_code == 200 and mk().get('/api/library', headers=basic('kees@example.nl', 'wachtwoord4')).status_code == 200 and mk().get('/api/library', headers=basic('kees', 'wachtwoord4')).status_code == 200)
check('adres wijzigen (ongeldig 400, dubbel 409, eigen adres opnieuw ok) en wissen', admin.put(f'/api/users/{kid}', json={'email': 'x'}, headers=H).status_code == 400 and admin.put(f'/api/users/{kid}', json={'email': 'gast-anders@example.nl'}, headers=H).status_code == 200
      and admin.put(f'/api/users/{kid}', json={'email': 'gast-anders@example.nl'}, headers=H).status_code == 200 and admin.put(f'/api/users/{kid}', json={'email': ''}, headers=H).status_code == 200
      and {u['username']: u for u in admin.get('/api/users').get_json()}['kees']['email'] == '' and mk().post('/api/login', json={'username': 'gast-anders@example.nl', 'password': 'wachtwoord4'}).status_code == 401)
admin.put(f'/api/users/{kid}', json={'email': 'kees@example.nl'}, headers=H); admin.post('/api/users', json={'username': 'piet', 'password': 'wachtwoord5', 'email': 'piet@example.nl'}, headers=H)
check('twee gebruikers kunnen niet hetzelfde adres krijgen via aanpassen', admin.put(f"/api/users/{[u for u in admin.get('/api/users').get_json() if u['username'] == 'piet'][0]['id']}", json={'email': 'KEES@example.nl'}, headers=H).status_code == 409)
check('gasten kunnen geen root-pad wijzigen of de gebruikerslijst met adressen zien', g1.post('/api/roots/1/move', json={'path': '/x'}, headers=H).status_code == 403 and g1.get('/api/users').status_code == 403)
# ---- accountbeheer
check('de laatste beheerder: niet verwijderen, niet degraderen, niet deactiveren', admin.delete('/api/users/1', headers=H).status_code == 400 and admin.put('/api/users/1', json={'role': 'viewer'}, headers=H).status_code == 400 and admin.put('/api/users/1', json={'active': False}, headers=H).status_code == 400)
gid = next(u['id'] for u in admin.get('/api/users').get_json() if u['username'].lower() == 'gast')
admin.put(f'/api/users/{gid}', json={'password': 'nieuw-wachtwoord'}, headers=H)
check('wachtwoord gewijzigd: lopende sessie van die gebruiker vervalt, nieuw wachtwoord werkt', g1.get('/api/library').status_code == 401 and mk().post('/api/login', json={'username': 'gast', 'password': 'wachtwoord1'}).status_code == 401 and mk().post('/api/login', json={'username': 'gast', 'password': 'nieuw-wachtwoord'}).status_code == 200)
check('te kort nieuw wachtwoord geweigerd', admin.put(f'/api/users/{gid}', json={'password': 'kort'}, headers=H).status_code == 400)
g3 = mk(); g3.post('/api/login', json={'username': 'gast', 'password': 'nieuw-wachtwoord'}); admin.put(f'/api/users/{gid}', json={'active': False}, headers=H)
check('gedeactiveerd: sessie en inloggen geweigerd', g3.get('/api/library').status_code == 401 and mk().post('/api/login', json={'username': 'gast', 'password': 'nieuw-wachtwoord'}).status_code == 401)
admin.put(f'/api/users/{gid}', json={'active': True, 'can_download': False}, headers=H); g4 = mk(); g4.post('/api/login', json={'username': 'gast', 'password': 'nieuw-wachtwoord'})
check('download-recht intrekken werkt direct, ook zonder opnieuw inloggen', g4.get(f'/api/file/{mid}').status_code == 403)
admin.put(f'/api/users/{gid}', json={'can_download': True}, headers=H); check('... en weer toestaan', g4.get(f'/api/file/{mid}').data == BOX)
check('eigen wachtwoord wijzigen: eigen sessie blijft geldig, oud wachtwoord niet', admin.put('/api/users/1', json={'password': 'geheim-456'}, headers=H).status_code == 200 and admin.get('/api/library').status_code == 200 and mk().get('/api/library', headers=basic('beheer', 'geheim-123')).status_code == 401 and mk().get('/api/library', headers=basic('beheer', 'geheim-456')).status_code == 200)
admin.post('/api/users', json={'username': 'beheer2', 'password': 'wachtwoord3', 'role': 'admin'}, headers=H)
check('met twee beheerders mag één gedegradeerd worden', admin.put('/api/users/1', json={'role': 'viewer'}, headers=H).status_code == 200 and admin.get('/api/users').status_code == 403)
b2 = mk(); b2.post('/api/login', json={'username': 'beheer2', 'password': 'wachtwoord3'}); b2.put('/api/users/1', json={'role': 'admin'}, headers=H)
# ---- via een reverse proxy lijkt iedereen lokaal
A.OPEN_OK = True; opened = []; A.open_file = opened.append
check('"openen met standaardprogramma": lokaal ja, via een reverse proxy (X-Forwarded-For) nee', b2.post(f'/api/models/{mid}/open', headers=H, environ_overrides={'REMOTE_ADDR': '127.0.0.1'}).status_code == 200 and b2.post(f'/api/models/{mid}/open', headers={**H, 'X-Forwarded-For': '203.0.113.9'}, environ_overrides={'REMOTE_ADDR': '127.0.0.1'}).status_code == 403 and len(opened) == 1)
# ---- inloggen uitzetten, oude inlog migreren, omgevingsvariabelen
check('"alle accounts verwijderen" vraagt bevestiging', b2.post('/api/users/clear', json={}, headers=H).status_code == 400)
check('alle accounts verwijderd: inloggen uit, iedereen heeft weer toegang', b2.post('/api/users/clear', json={'confirm': True}, headers=H).status_code == 200 and anon.get('/api/library').status_code == 200 and anon.get('/api/me').get_json()['auth'] is False)
A.put('auth_user', 'oud'); A.put('auth_hash', generate_password_hash('oudwachtwoord')); A.init()
check('oude enkele inlog wordt een beheerdersaccount met hetzelfde wachtwoord', mk().get('/api/library', headers=basic('oud', 'oudwachtwoord')).status_code == 200 and A.CFG['auth_user'] == '' and A.AUTH_ON[0] and mk().get('/api/me', headers=basic('oud', 'oudwachtwoord')).get_json()['role'] == 'admin')
c = mk(); c.post('/api/login', json={'username': 'oud', 'password': 'oudwachtwoord'}); c.post('/api/users/clear', json={'confirm': True}, headers=H)
os.environ['AUTH_USER'], os.environ['AUTH_PASS'] = 'envbeheer', 'env-wachtwoord'; A.bootstrap_env_admin()
check('AUTH_USER/AUTH_PASS maakt een beheerder aan als er nog geen accounts zijn', mk().get('/api/library', headers=basic('envbeheer', 'env-wachtwoord')).status_code == 200)
A.bootstrap_env_admin(); check('... maar niet nogmaals (geen dubbele of overschreven accounts)', len([u for u in c.get('/api/users', headers=basic('envbeheer', 'env-wachtwoord')).get_json()]) == 1)
sys.exit(1 if bad else 0)
