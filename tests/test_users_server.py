"""Test: inloggen met cookies over echte HTTP (zoals een browser), tegen de draaiende server. Gebruik: python tests/test_users_server.py"""
import http.cookiejar, json, os, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
import trimesh
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.join(tempfile.gettempdir(), 'modelbib-usrv'); PORT = 8791
shutil.rmtree(ROOT, ignore_errors=True); M = f'{ROOT}/models'; os.makedirs(M); os.makedirs(f'{ROOT}/cfg')
trimesh.creation.box((40, 20, 10)).export(f'{M}/doos.stl'); os.utime(f'{M}/doos.stl', (time.time() - 600,) * 2)
env = dict(os.environ, CONFIG_DIR=f'{ROOT}/cfg', MODELS_DIR=M, PORT=str(PORT), YIELD_TO_USERS='0')
srv = subprocess.Popen([sys.executable, 'app.py'], cwd=APP, env=env, stdout=open(f'{ROOT}/out.txt', 'w'), stderr=subprocess.STDOUT)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
def browser():  # eigen cookie-opslag per "browser"
    jar = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
    def call(u, m='GET', b=None, h=None):
        r = urllib.request.Request(f'http://127.0.0.1:{PORT}' + u, method=m, data=json.dumps(b).encode() if b is not None else None, headers={'Content-Type': 'application/json', 'X-Requested-With': 'modelbib', **(h or {})})
        try:
            with op.open(r) as x: d = x.read(); return x.status, d, x.headers
        except urllib.error.HTTPError as e: return e.code, e.read(), e.headers
    return call, jar
J = lambda r: json.loads(r[1] or b'{}')
bad = []
def check(n, ok, extra=''): print('OK  ' if ok else 'FOUT', n, extra); (None if ok else bad.append(n))
try:
    for _ in range(60):
        try: urllib.request.urlopen(f'http://127.0.0.1:{PORT}/ping'); break
        except Exception: time.sleep(.3)
    owner, jar = browser(); anon, _ = browser()
    t0 = time.time()
    while time.time() - t0 < 60 and not J(owner('/api/library')).get('models'): time.sleep(1)
    mid = J(owner('/api/library'))['models'][0]['id']
    r = owner('/api/users', 'POST', {'username': 'beheer', 'password': 'geheim-123'}); sc = r[2].get('Set-Cookie', '')
    check('eerste account maken: cookie gezet (HttpOnly, SameSite=Lax) en meteen ingelogd', r[0] == 200 and 'HttpOnly' in sc and 'SameSite=Lax' in sc and J(owner('/api/me'))['user'] == 'beheer', sc[:60])
    check('anoniem: inlogpagina en bestanden zonder inloggen, gegevens niet', anon('/')[0] == 200 and anon('/static/app.js')[0] == 200 and anon('/api/library')[0] == 401 and anon('/api/thumb/1.png')[0] == 401 and anon(f'/api/file/{mid}')[0] == 401)
    check('beheerder (cookie) ziet alles, incl. instellingen en volledig pad', owner('/api/settings')[0] == 200 and J(owner('/api/library'))['models'][0]['path'].startswith(M))
    owner('/api/users', 'POST', {'username': 'gast', 'password': 'wachtwoord1', 'role': 'viewer', 'can_download': True})
    guest, gjar = browser(); lr = guest('/api/login', 'POST', {'username': 'gast', 'password': 'wachtwoord1'})
    check('gast logt in over HTTP', lr[0] == 200 and J(lr)['role'] == 'viewer' and any(c.name == 'session' for c in gjar))
    g = J(guest('/api/library'))['models'][0]
    check('gast: bibliotheek zonder pad op de schijf; thumbnail laden mag', ROOT not in g['path'] and g['path'] == 'doos.stl' and guest(f"/api/thumb/{g['id']}.png")[0] in (200, 404))
    d = guest(f"/api/file/{g['id']}"); check('gast: downloadt het bestand', d[0] == 200 and len(d[1]) > 100 and 'doos.stl' in d[2].get('Content-Disposition', ''))
    check('gast: kan niets beheren of wijzigen (403)', guest('/api/settings')[0] == 403 and guest('/api/users')[0] == 403 and guest(f"/api/models/{g['id']}", 'POST', {'notes': 'x'})[0] == 403 and guest('/api/tasks/scan/run', 'POST', {})[0] == 403)
    hist = J(owner('/api/history')); check('beheerder ziet de download van de gast in de geschiedenis', any(h['event'] == 'Download' and 'gast' in h['message'].lower() for h in hist))
    check('uitloggen: sessie meteen ongeldig', guest('/api/logout', 'POST', {})[0] == 200 and guest('/api/library')[0] == 401)
    forged = browser(); _, fj = forged
    check('zonder X-Requested-With: wijzigend verzoek met geldige cookie wordt geweigerd', owner('/api/categories', 'POST', {'name': 'x'}, {'X-Requested-With': ''})[0] == 403)
    owner('/api/users', 'POST', {'username': 'gast2', 'password': 'wachtwoord2', 'role': 'viewer', 'can_download': False})
    g2, _ = browser(); g2('/api/login', 'POST', {'username': 'gast2', 'password': 'wachtwoord2'})
    check('gast zonder download-recht: bibliotheek ja, bestand en 3D-weergave nee', g2('/api/library')[0] == 200 and g2(f"/api/file/{g['id']}")[0] == 403 and g2(f"/api/mesh/{g['id']}.stl")[0] == 403)
finally:
    srv.terminate(); srv.wait()
print('--- fouten in uitvoer:', [l for l in open(f'{ROOT}/out.txt') if 'Traceback' in l][:2])
sys.exit(1 if bad else 0)
