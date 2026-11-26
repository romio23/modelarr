// Toegankelijkheid: vult na elke wijziging van de pagina de attributen aan die de schermlezer en het toetsenbord nodig hebben.
// De schermen worden als tekst opgebouwd in app.js; zo hoeft niet elke sjabloon apart aangepast te worden.
(() => {
  'use strict';
  const T = s => (window.I18N && window.I18N.tr ? window.I18N.tr(s) : s);
  const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
  let uid = 0;
  const id = (el, p) => el.id || (el.id = p + (++uid));

  // Landmarks en een link om de navigatie over te slaan
  function landmarks() {
    const nav = document.getElementById('nav'), main = document.getElementById('main'), toast = document.getElementById('toast');
    if (nav && !nav.hasAttribute('aria-label')) nav.setAttribute('aria-label', 'Hoofdmenu');
    if (main && !main.hasAttribute('role')) main.setAttribute('role', 'main');
    const title = document.getElementById('title');
    if (title && !title.hasAttribute('role')) { title.setAttribute('role', 'heading'); title.setAttribute('aria-level', '1'); }
    const view = document.getElementById('view');
    if (view && !view.hasAttribute('tabindex')) view.setAttribute('tabindex', '-1');
    if (toast && !toast.hasAttribute('role')) { toast.setAttribute('role', 'status'); toast.setAttribute('aria-live', 'polite'); }
    for (const n of ['banner', 'rootalert']) { const e = document.getElementById(n); if (e && !e.hasAttribute('role')) e.setAttribute('role', 'status'); }
    if (!document.getElementById('skiplink') && view) {
      const a = document.createElement('a');
      a.id = 'skiplink'; a.href = '#view'; a.className = 'skip'; a.textContent = 'Naar de inhoud';
      a.onclick = e => { e.preventDefault(); view.focus(); };
      document.body.prepend(a);
    }
  }

  // Namen voor velden, knoppen en afbeeldingen
  function names(root) {
    for (const c of root.querySelectorAll('input,select,textarea')) {
      if (c.type === 'hidden' || c.hasAttribute('aria-label') || c.hasAttribute('aria-labelledby') || (c.labels && c.labels.length)) continue;
      const f = c.closest('.f');
      const small = f && f.querySelector(':scope > small, :scope > label');
      if (small && !small.contains(c)) { c.setAttribute('aria-labelledby', id(small, 'lbl')); continue; }
      let prev = c.previousElementSibling;                      // <label>Tekst</label><input> zonder for=
      while (prev && !/^(LABEL|SMALL)$/.test(prev.tagName) && prev.previousElementSibling && prev.matches('small,br')) prev = prev.previousElementSibling;
      if (prev && prev.tagName === 'LABEL' && !prev.contains(c) && prev.textContent.trim()) { c.setAttribute('aria-labelledby', id(prev, 'lbl')); continue; }
      const t = c.getAttribute('title') || c.getAttribute('placeholder');
      if (t) c.setAttribute('aria-label', t);
      else if (c.tagName === 'SELECT' && c.options.length) c.setAttribute('aria-label', c.options[0].textContent.trim());   // filters: "Alle categorieën" e.d.
      else if (c.type === 'checkbox') c.setAttribute('aria-label', T(c.id === 'all' ? 'Alles selecteren' : 'Selecteren'));
    }
    for (const b of root.querySelectorAll('button')) {
      if (b.hasAttribute('aria-label')) continue;
      const t = b.getAttribute('title'), v = b.textContent.trim();
      if (!t) continue;
      if (!/[\p{L}\p{N}]/u.test(v)) b.setAttribute('aria-label', t);                       // alleen een pictogram: de titel is de naam
      else if (v.length < 4 && !t.toLowerCase().includes(v.toLowerCase())) b.setAttribute('aria-label', v + ' – ' + t);  // korte tekst (NL, EN): tekst + uitleg
    }
    for (const i of root.querySelectorAll('img:not([alt])')) i.setAttribute('alt', '');
    for (const h of root.querySelectorAll('th:not([scope])')) h.setAttribute('scope', 'col');
    for (const h of root.querySelectorAll('th:last-child:empty')) { const sp = document.createElement('span'); sp.className = 'sr-only'; sp.textContent = 'Acties'; h.append(sp); }   // laatste kolom zonder kop = knoppen
    for (const h of root.querySelectorAll('#view h3:not([aria-level])')) h.setAttribute('aria-level', '2');   // de paginatitel is niveau 1
    for (const a of root.querySelectorAll('nav a.on')) a.setAttribute('aria-current', 'page');
    for (const a of root.querySelectorAll('nav a:not(.on)[aria-current]')) a.removeAttribute('aria-current');
  }

  // Rijen en kaarten die je aanklikt, bereikbaar met het toetsenbord
  function clickables(root) {
    for (const e of root.querySelectorAll('tr[data-id],.card[data-id]')) {
      if (!e.hasAttribute('tabindex')) e.setAttribute('tabindex', '0');
    }
  }
  document.addEventListener('keydown', e => {
    const t = e.target;
    if (!(t instanceof Element) || e.defaultPrevented || e.isComposing) return;
    if ((e.key === 'Enter' || e.key === ' ') && t.matches('tr[data-id],.card[data-id]')) { e.preventDefault(); t.click(); }
  });

  // Vensters: rol, titel, focus erin, Tab blijft binnen het venster, Escape sluit, focus gaat terug
  let opener = null, last = null;
  function dialogs() {
    const modal = document.getElementById('modal');
    const box = modal && modal.querySelector('.back > *');
    if (box === last) return;
    if (box) {
      opener = document.activeElement && document.activeElement !== document.body ? document.activeElement : opener;
      box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true');
      const head = box.querySelector('b,h1,h2,h3');
      if (head) box.setAttribute('aria-labelledby', id(head, 'dlg'));
      else if (!box.hasAttribute('aria-label')) box.setAttribute('aria-label', 'Venster');
      if (!box.contains(document.activeElement)) { const f = box.querySelector(FOCUSABLE); if (f) f.focus(); }
    } else if (opener && opener.isConnected) { opener.focus(); opener = null; }
    last = box;
  }
  document.addEventListener('keydown', e => {
    const modal = document.getElementById('modal'), back = modal && modal.querySelector('.back');
    if (!back || e.isComposing) return;
    if (e.key === 'Escape' && !e.defaultPrevented) { back.click(); return; }
    if (e.key !== 'Tab') return;
    const items = [...back.querySelectorAll(FOCUSABLE)].filter(x => x.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], end = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); end.focus(); }
    else if (!e.shiftKey && document.activeElement === end) { e.preventDefault(); first.focus(); }
  });

  // Eigen vensters buiten #modal (bijv. het wachtwoordvenster) gebruiken dit
  window.A11Y = {dialog(el, label) {
    el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); if (label) el.setAttribute('aria-label', label);
  }};

  let queued = false;
  function all() { queued = false; landmarks(); names(document); clickables(document); dialogs(); }
  const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(all); } };
  function start() { all(); new MutationObserver(schedule).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['class']}); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
