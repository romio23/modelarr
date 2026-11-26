"""Beveiligingsheaders en bescherming tegen cross-site verzoeken (CSRF).

Wordt in app.py aangezet met ``security.install(app)``.

* Content-Security-Policy: scripts alleen van de eigen server (het importmap-blok in index.html is toegestaan via zijn hash),
  geen plug-ins, de pagina mag niet in een frame, formulieren sturen alleen naar de eigen server.
* Verzoeken die iets wijzigen (POST, PUT, PATCH, DELETE) worden geweigerd als de browser meldt dat ze van een andere
  website komen (Sec-Fetch-Site: cross-site of same-site). Andere programma's (curl, scripts) sturen die header niet en
  worden dus niet geblokkeerd.
* Als de pagina via https wordt bediend (bijv. achter een reverse proxy) krijgt de sessiecookie het Secure-kenmerk en
  stuurt de server Strict-Transport-Security mee. Over gewoon http op het eigen netwerk verandert er niets.
"""
import base64
import hashlib
import os
import re

from flask import request, jsonify
from flask.sessions import SecureCookieSessionInterface

SAFE = ('GET', 'HEAD', 'OPTIONS')


def _importmap_hash(static_dir):
    """Hash van het inline importmap-blok in index.html (voor script-src)."""
    try:
        with open(os.path.join(static_dir, 'index.html'), encoding='utf-8') as f:
            html = f.read()
    except OSError:
        return None
    m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
    if not m:
        return None
    return "'sha256-%s'" % base64.b64encode(hashlib.sha256(m.group(1).encode('utf-8')).digest()).decode()


def csp(static_dir):
    script = ["'self'"]
    h = _importmap_hash(static_dir)
    if h:
        script.append(h)
    return '; '.join([
        "default-src 'self'",
        'script-src ' + ' '.join(script),
        "style-src 'self' 'unsafe-inline'",   # de schermen gebruiken style-attributen
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])


def is_https():
    return request.is_secure or request.headers.get('X-Forwarded-Proto', '').split(',')[0].strip().lower() == 'https'


class _Sessions(SecureCookieSessionInterface):
    def get_cookie_secure(self, app):
        try:
            return is_https()
        except RuntimeError:  # geen verzoek actief
            return False


def install(app):
    policy = csp(app.static_folder)
    app.session_interface = _Sessions()

    @app.before_request
    def _cross_site():
        if request.method in SAFE:
            return None
        site = request.headers.get('Sec-Fetch-Site')
        if site in ('cross-site', 'same-site'):
            return jsonify({'error': 'Verzoek van een andere website geweigerd'}), 403
        return None

    @app.after_request
    def _headers(resp):
        h = resp.headers
        h.setdefault('X-Content-Type-Options', 'nosniff')
        h.setdefault('Referrer-Policy', 'same-origin')
        h.setdefault('X-Frame-Options', 'DENY')
        h.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        h.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
        # Pagina: het beleid hierboven. Al het andere (modelbestanden, thumbnails, JSON): niets mag uitvoeren,
        # zodat een bestand dat per ongeluk als pagina wordt geopend geen scripts kan draaien.
        h.setdefault('Content-Security-Policy', policy if resp.mimetype == 'text/html' else "default-src 'none'; sandbox")
        if is_https():
            h.setdefault('Strict-Transport-Security', 'max-age=31536000')
        return resp
