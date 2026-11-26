"""Test: beveiligingsheaders, CSP-hash van het importmap-blok, weigeren van cross-site schrijfverzoeken en de
statische toegankelijkheidsmodule. Gebruik: python tests/test_security.py"""
import base64, hashlib, os, re, shutil, sys, tempfile
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.join(tempfile.gettempdir(), 'modelarr-security')
shutil.rmtree(ROOT, ignore_errors=True); os.makedirs(ROOT); os.environ['CONFIG_DIR'] = f'{ROOT}/cfg'; sys.path.insert(0, APP)
import app as A
A.init(); bad = []
def check(n, ok, extra=''): print('OK  ' if ok else 'FOUT', n, extra); (None if ok else bad.append(n))
c = A.app.test_client()

r = c.get('/')
h = r.headers
csp = h.get('Content-Security-Policy', '')
check('pagina: CSP aanwezig', "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp, csp)
check('pagina: geen unsafe-inline of unsafe-eval voor scripts', not re.search(r"script-src[^;]*'unsafe-", csp), csp)
html = open(os.path.join(APP, 'static', 'index.html'), encoding='utf-8').read()
imap = re.search(r'<script type="importmap">(.*?)</script>', html, re.S).group(1)
want = "'sha256-%s'" % base64.b64encode(hashlib.sha256(imap.encode()).digest()).decode()
check('pagina: hash van het importmap-blok staat in script-src', want in csp, want)
check('pagina: overige headers', h.get('X-Content-Type-Options') == 'nosniff' and h.get('X-Frame-Options') == 'DENY'
      and h.get('Referrer-Policy') == 'same-origin' and 'camera=()' in h.get('Permissions-Policy', ''))
check('http: geen HSTS en geen Secure-cookie', 'Strict-Transport-Security' not in h)
r = c.get('/api/rev')
check('JSON: sandbox-CSP (niets mag uitvoeren)', r.headers.get('Content-Security-Policy') == "default-src 'none'; sandbox")

r = c.get('/', headers={'X-Forwarded-Proto': 'https'})
check('https via proxy: HSTS', 'max-age' in r.headers.get('Strict-Transport-Security', ''))

# cross-site schrijfverzoeken
r = c.post('/api/logout', headers={'Sec-Fetch-Site': 'cross-site'})
check('POST cross-site: geweigerd (403)', r.status_code == 403, r.status_code)
r = c.post('/api/logout', headers={'Sec-Fetch-Site': 'same-site'})
check('POST same-site (andere subdomein): geweigerd (403)', r.status_code == 403, r.status_code)
r = c.post('/api/logout', headers={'Sec-Fetch-Site': 'same-origin'})
check('POST same-origin: toegestaan', r.status_code == 200, r.status_code)
r = c.post('/api/logout')
check('POST zonder Sec-Fetch-Site (curl, scripts): toegestaan', r.status_code == 200, r.status_code)
r = c.get('/api/rev', headers={'Sec-Fetch-Site': 'cross-site'})
check('GET cross-site: toegestaan (leest alleen)', r.status_code == 200)

# toegankelijkheid
check('index laadt a11y.js', '/static/a11y.js' in html)
check('a11y.js wordt geserveerd', c.get('/static/a11y.js').status_code == 200)
js = open(os.path.join(APP, 'static', 'app.js'), encoding='utf-8').read()
check("geen innerHTML = '' meer (replaceChildren)", "innerHTML = ''" not in js)
print('\n%s' % ('ALLES OK' if not bad else 'FOUT: %s' % bad)); sys.exit(1 if bad else 0)
