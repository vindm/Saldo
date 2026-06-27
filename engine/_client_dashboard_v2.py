"""_client_dashboard_v2.py — P3-12 (2026-05-17): client dashboard built on top of mental_model.

Main renderer for the client dashboard on top of mental_model.
Structure: header -> understanding snapshot (3 columns) -> active client tracks
-> waiting items + what I do NOT remember -> key decisions history
-> collapsed feed of today's signals (legacy blocks).
"""
import os
from datetime import date, timedelta
from _helpers import _esc, _esca, _format_date_ru, client_avatar
from _css import (
    DESIGN_TOKENS_CSS, OVERVIEW_SPECIFIC_CSS,
    PROMPT_MODAL_CSS, PROMPT_MODAL_HTML, PROMPT_MODAL_JS,
)
from _mental_model import load_mental_models
from _overview_v2 import (
    OVERVIEW_V2_CSS,
    render_tracks_zone, render_awaitings_zone, render_gaps_zone,
)
from _health import calculate_health
from _sidebar import render_sidebar, SIDEBAR_CSS
from _v2_sections import render_v2_block, V2_SECTIONS_CSS
from _track_modal import TRACK_MODAL_CSS, TRACK_MODAL_HTML, TRACK_MODAL_JS
from _strings import t
_t = t  # alias: several functions use a local var named `t` (loop/dict comp)


def _linked_ref_chip(lt_id, tasks_lookup, client_id, today, client_name=''):
    """Render ONE linked task id as the shared clickable reference chip
    (engine/_brief.ref_chip) — the SAME «referenced task» pattern the Plan uses for
    blockers. Resolve the title from tasks_lookup and build the data-track-* attrs
    via build_track_data_attrs so a click opens the canonical track modal. Only a
    task that actually resolves in tasks_lookup becomes clickable; an unknown id
    degrades to a non-clickable label. No leading icon — the trailing → already
    signals the chip navigates (keeps the cards calm)."""
    from _brief import ref_chip
    _has = bool(tasks_lookup) and lt_id in tasks_lookup
    title = (tasks_lookup.get(lt_id) if _has else None) or lt_id
    attrs = ''
    if _has and client_id:
        try:
            from _track_attrs import build_track_data_attrs
            attrs = build_track_data_attrs(
                {'id': lt_id, 'client_id': client_id, 'client_name': client_name or ''},
                _esca, today=today)
        except Exception:
            attrs = ''
    return ref_chip(title, attrs, _esc, glyph='')

# Internal enum tokens (accounting_system / filing.submission / signature_holder
# and a few access values) → clean English keys that flow through _t() for ru.
# Unknown tokens fall back to a humanized snake_case form.
_ENUM_MAP = {
    'excel': 'Excel', '1c': '1C', '1c_fresh': '1C Fresh', '1c_cloud': '1C (cloud)',
    '1c_on_executor_server': '1C on our server',
    'team_lead_via_finkoper': 'team lead via Finkoper', 'client_lk_fns': 'client via FNS portal',
    'finkoper': 'Finkoper', 'accountant': 'accountant', 'team_lead': 'team lead', 'client': 'client',
    'client_provides_export_or_credentials': 'client provides export/credentials',
}

def _enum_ru(v):
    v = (str(v) if v is not None else '').strip()
    if not v:
        return ''
    return _t(_ENUM_MAP.get(v, v.replace('_', ' ')))


def _md_bold(text):
    """Light markdown: **bold** -> <b>bold</b>. _esc first, then expansion."""
    import re as _re
    safe = _esc(text)
    return _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)


# ── Render-side auto-gloss ────────────────────────────────────────────────
# For a client whose jurisdiction differs from the operator's home (e.g. an
# Indonesian client under a Russian operator), native tax terms (PPh 21, BPJS,
# SPT Masa, LKPM, unifikasi…) are opaque to the operator. We wrap any term that
# appears in the jurisdiction's glossary in an <abbr> tooltip with the plain
# operator-locale explanation. This is a *view* derivation (engine's job): no
# state is written, and it always works — independent of what the runtime wrote.
import functools as _functools


@_functools.lru_cache(maxsize=8)
def _gloss_map(jurisdiction):
    """{matchable_token: plain_gloss} parsed from the pack glossary table."""
    juris = (jurisdiction or '').strip().lower()
    if not juris or juris == 'ru':
        return ()
    try:
        import os as _os
        import _jurisdiction as _J
        man = _J.load_jurisdiction(juris).manifest or {}
        grel = man.get('glossary')
        if not grel:
            return ()
        text = open(_os.path.join(_J._PACKS_DIR, juris, grel), encoding='utf-8').read()
    except Exception:
        return ()
    out = {}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln.startswith('|'):
            continue
        cells = [c.strip() for c in ln.strip('|').split('|')]
        if len(cells) < 2 or all(set(c) <= set('-: ') for c in cells):
            continue
        if cells[0].lower() == 'term':
            continue
        gloss = (cells[2] if len(cells) >= 3 and cells[2] else cells[1]).replace('**', '').strip()
        raw = cells[0].replace('**', '').strip().lstrip('—').strip()
        if not gloss:
            continue
        for tok in raw.split('/'):
            tok = tok.strip().strip('"').strip('«»').strip()
            if len(tok) < 3 or not any(ch.isalpha() for ch in tok):
                continue
            out[tok] = gloss
            # also index the space-free variant ("PPh 21" -> "PPh21")
            if ' ' in tok:
                out[tok.replace(' ', '')] = gloss
    # tuple of (token, gloss) sorted longest-first for greedy matching
    return tuple(sorted(out.items(), key=lambda kv: -len(kv[0])))


def _gloss_text(text, jurisdiction):
    """Escape `text`, then wrap glossary terms in <abbr> tooltips. Returns HTML."""
    safe = _esc(text or '')
    pairs = _gloss_map(jurisdiction)
    if not pairs or not safe:
        return safe
    import re as _re
    pattern = '|'.join(_re.escape(tok) for tok, _ in pairs)
    gloss_by_tok = {tok: g for tok, g in pairs}
    # case-insensitive lookup map
    lower_by = {tok.lower(): g for tok, g in pairs}
    rx = _re.compile(r'(?<![\w/])(' + pattern + r')(?![\w])', _re.IGNORECASE)

    def _wrap(m):
        word = m.group(1)
        g = gloss_by_tok.get(word) or lower_by.get(word.lower())
        if not g:
            return word
        title = _esc(g).replace('"', '&quot;')
        return '<abbr class="gl" title="' + title + '">' + word + '</abbr>'

    return rx.sub(_wrap, safe)


def render_action_buttons(kind, entity_id, entity_name, prompt_text, context_text=''):
    """Single unified action button → opens the shared prompt modal.

    One button, one modal (the editable prompt popup with the immutable context
    block + Win+H dictation inside). `prompt_text` is the editable default ask;
    `context_text` (optional) is the immutable context always prepended on copy.

    stopPropagation keeps the click off the card/row behind the button; because a
    stopped event never reaches the document-level data-prompt handler, we open
    the modal ourselves here.
    """
    ctx_attr = (' data-prompt-ctx="' + _esca(context_text) + '"') if context_text else ''
    # Header-level primary action (filled). Row-level "Разобрать" stays outline/ghost.
    return (
        '<button class="tm-btn tm-btn-primary tm-btn-sm" type="button" '
        'onclick="event.stopPropagation();if(window.openPromptModal)window.openPromptModal('
        "this.dataset.prompt,{ctx:this.getAttribute('data-prompt-ctx')||''});\" "
        'data-prompt="' + _esca(prompt_text) + '"' + ctx_attr + '>'
        + _t('🔍 Review') + '</button>'
    )


def render_client_snapshot(snapshot):
    """Understanding snapshot: 3 columns firm / in_progress / unclear."""
    firm = snapshot.get('firm') or []
    inp = snapshot.get('in_progress') or []
    unc = snapshot.get('unclear') or []
    if not (firm or inp or unc):
        return ''

    def col(title, items, color):
        if not items:
            inner = '<div class="empty">—</div>'
        else:
            rows = ''.join('<div class="row">' + _md_bold(it) + '</div>' for it in items[:8])
            if len(items) > 8:
                rows += ('<div class="row" style="color:var(--text-muted)">'
                         '... ' + _t('and {} more').format(len(items) - 8) + '</div>')
            inner = rows
        return (
            '<div class="snapshot-col">'
            '<div class="snapshot-col-title" style="color:' + color + '">'
            + _esc(title) + '</div>'
            '<div class="snapshot-list">' + inner + '</div>'
            '</div>'
        )

    return (
        '<div class="section-title"><h2>' + _t('🧭 Understanding snapshot') + '</h2></div>'
        '<section class="snapshot-grid">'
        + col(_t('Firmly understood'), firm, 'var(--accent-green)')
        + col(_t('In progress'), inp, 'var(--accent-yellow)')
        + col(_t('Not yet clarified'), unc, 'var(--text-secondary)')
        + '</section>'
    )


def render_client_history(history):
    """Key decisions history — a real timeline (rail + dots) built from state
    history. Each item is {date, summary, auto}; a filled dot marks an
    operator/system decision, a hollow ring an automatic event (same legend as
    the per-track event timeline in the track modal). Long summaries are softly
    clamped so the block stays scannable; the full text lives in the track."""
    if not history:
        return ''
    rows = []
    for it in history[:7]:
        if isinstance(it, dict):
            date = it.get('date') or ''
            summ = it.get('summary') or ''
            auto = bool(it.get('auto'))
        else:  # backward-compat: a plain '**date** — summary' string
            date, summ, auto = '', str(it), False
        if len(summ) > 240:
            summ = summ[:237].rstrip() + '…'
        cls = 'kdh-item auto' if auto else 'kdh-item'
        date_html = ('<span class="kdh-date">' + _esc(date) + '</span>') if date else ''
        rows.append('<div class="' + cls + '">' + date_html
                    + '<span class="kdh-text">' + _md_bold(summ) + '</span></div>')
    return (
        '<div class="section-title"><h2>' + _t('📜 Key decisions history') + '</h2>'
        '<span class="count">' + str(len(history)) + '</span></div>'
        '<section class="kdh-card"><div class="kdh-list">' + ''.join(rows) + '</div></section>'
    )


# (The header regime badge now reuses c['regime'] — the full localised label
# built by _jurisdiction.render_regime_label, identical to the client-list
# snippet — so the old short-label lookup table is no longer needed.)


CLIENT_V2_EXTRA_CSS = (
    ".breadcrumb{font-size:var(--fs-meta);color:var(--text-muted);"
    "margin-bottom:var(--space-xs)}"
    ".breadcrumb a:hover{color:var(--accent-blue)}"
    # Compact sticky header toolbar — stays pinned while the cockpit scrolls.
    # Block 1 — sticky title/actions bar (compact, stays pinned).
    ".client-topbar{position:sticky;top:0;z-index:30;display:flex;align-items:center;"
    "justify-content:space-between;gap:16px;padding:14px 0 12px;margin-bottom:0;"
    "background:var(--bg-canvas);border-bottom:1px solid transparent;"
    "transition:border-color .15s ease}"
    # blends with the page at rest; a thin divider appears only once it is pinned
    ".client-topbar.stuck{border-bottom-color:var(--border)}"
    ".client-topbar .ct-id{display:flex;align-items:center;gap:12px;min-width:0}"
    ".client-topbar h1{font-size:23px;font-weight:600;letter-spacing:-.015em;margin:0;"
    "display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0}"
    ".client-av{width:46px;height:46px;border-radius:50%;flex-shrink:0;"
    "display:inline-flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;"
    "border:1px solid var(--border)}"
    ".client-topbar .ct-act{display:flex;align-items:center;gap:10px;flex-shrink:0}"
    ".ct-btns{display:flex;align-items:center;gap:10px}"
    ".ct-meta{font-size:var(--fs-meta);color:var(--text-muted);text-align:right;"
    "line-height:1.65;flex-shrink:0;white-space:nowrap}"
    # Block 2 — description (left) and 'updated' stamp (right) share one row.
    ".client-desc{display:flex;justify-content:space-between;align-items:flex-start;"
    "gap:28px;margin:0 0 28px;border-top:1px solid var(--border);padding-top:14px}"
    ".client-desc-main{min-width:0;max-width:780px}"
    ".client-desc-text{font-size:14px;color:var(--text-secondary);line-height:1.5;font-style:italic}"
    ".client-desc .client-team-meta{margin-top:4px}"
    ".client-sub{color:var(--text-secondary);font-size:13.5px;line-height:1.5;"
    "margin:0 0 var(--space-lg);max-width:780px}"
    ".client-sub .client-team-meta{margin-top:4px}"
    "@media(max-width:760px){.client-topbar{flex-direction:column;align-items:flex-start;gap:10px}"
    ".client-topbar .ct-act{align-items:flex-start}.ct-meta{display:none}}"
    ".snapshot-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--space-md);"
    "margin-bottom:var(--space-lg)}"
    "@media(max-width:900px){.snapshot-grid{grid-template-columns:1fr}}"
    ".snapshot-col{background:var(--bg-card);border:1px solid var(--border);"
    "border-radius:var(--radius-card);padding:var(--space-md)}"
    ".snapshot-col-title{font-size:13px;text-transform:uppercase;letter-spacing:.04em;"
    "font-weight:500;margin-bottom:var(--space-sm)}"
    ".snapshot-list .row{font-size:var(--fs-meta);color:var(--text-secondary);"
    "line-height:1.5;padding:4px 0;border-bottom:1px dashed var(--border)}"
    ".snapshot-list .row:last-child{border-bottom:none}"
    ".snapshot-list .empty{color:var(--text-muted);font-size:var(--fs-meta);"
    "text-align:center;padding:var(--space-sm)}"
    # Key-decisions history as a real timeline: a continuous rail with a dot per
    # entry. Filled accent dot = operator/system decision; hollow ring = auto
    # event (same legend as the per-track event timeline in the track modal).
    ".kdh-card{background:var(--bg-card);border:1px solid var(--border);"
    "border-radius:var(--radius-card);padding:var(--space-sm) var(--space-md);"
    "margin-bottom:var(--space-lg)}"
    ".kdh-list{display:flex;flex-direction:column;position:relative}"
    ".kdh-list::before{content:'';position:absolute;left:4px;top:16px;bottom:16px;"
    "width:2px;background:var(--border);border-radius:2px}"
    ".kdh-item{position:relative;padding:9px 0 9px 26px;font-size:var(--fs-meta);"
    "line-height:1.55;color:var(--text-secondary)}"
    ".kdh-item::before{content:'';position:absolute;left:0;top:12px;width:10px;height:10px;"
    "border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--bg-card);z-index:1}"
    ".kdh-item.auto::before{background:var(--bg-card);border:2px solid var(--border-strong);"
    "box-shadow:0 0 0 2px var(--bg-card)}"
    ".kdh-date{display:inline-block;color:var(--text-muted);font-weight:600;"
    "font-family:var(--font-mono,monospace);font-size:12.5px;margin-right:9px}"
    ".kdh-text{color:var(--text-primary)}"
    # auto-gloss tooltip for foreign-jurisdiction terms (PPh 21, BPJS, LKPM…)
    "abbr.gl{text-decoration:none;border-bottom:1px dotted var(--text-muted);"
    "cursor:help;text-underline-offset:2px}"
)


def _filter_mm_by_client(mm, client_id):
    """Returns a sub-dict of mm for a single client only.

    v2 (2026-05-25): if the client has state/tasks.json, take tracks from there
    (single source of truth for tasks). Fallback: old mm['tracks'].
    """
    base = {
        'tracks': [t for t in mm.get('tracks', []) if t.get('client_id') == client_id],
        'awaitings': [w for w in mm.get('awaitings', []) if w.get('client_id') == client_id],
        'gaps': [g for g in mm.get('gaps', []) if g.get('client_id') == client_id],
    }
    try:
        from _loaders import load_client_state_tasks, state_tasks_to_mm_format
        state_data = load_client_state_tasks(client_id)
        if state_data:
            # On the client dashboard client_name='' so track cards don't duplicate the client name
            base['tracks'] = state_tasks_to_mm_format(state_data, client_name='')['tracks']
    except Exception:
        pass  # silent fallback to mm['tracks']
    return base



_REQ_ROLE_LABEL = {'Direktur': 'Director', 'Komisaris': 'Supervisor'}


def _render_requisites_foreign(c, row):
    """Client-details card for a non-RU jurisdiction, built from identity.json:
    local tax/registration identifiers, KBLI, management, capital, authority."""
    idy = {}
    try:
        from state_ops import state_read
        idy = state_read(c['id'], 'identity.json') or {}
    except Exception:
        idy = {}
    if not idy:
        return None
    nm = idy.get('name') or {}
    modal = idy.get('modal') or {}
    kbli = idy.get('kbli') or {}
    kmain = kbli.get('main') or {}
    kbli_s = ''
    if kmain.get('code'):
        kbli_s = kmain['code'] + ((' — ' + kmain['name']) if kmain.get('name') else '')
        _extra = [e.get('code', '') for e in (kbli.get('additional') or []) if e.get('code')]
        if _extra:
            kbli_s += ' (+' + ', '.join(_extra) + ')'
    cap = (_kpi_num(modal['ditempatkan_idr']) + ' Rp') if modal.get('ditempatkan_idr') else ''
    contacts = idy.get('contacts') or {}
    tax_office = idy.get('tax_office') or {}
    addr = (idy.get('addr') or {}).get('full') or c.get('addr') or ''
    bank = c.get('bank_name') or (c.get('bank_access') or {}).get('bank') or ''
    dir_rows = ''
    for m in (idy.get('management') or []):
        if m.get('name'):
            dir_rows += row(_t(_REQ_ROLE_LABEL.get(m.get('role', ''), 'Management')),
                            m['name'] + ((' — ' + m['role']) if m.get('role') else ''))
    left = (
        row(_t('Tax no. (NPWP)'), idy.get('npwp'), mono=True) +
        row(_t('Reg. no. (NIB)'), idy.get('nib'), mono=True) +
        row(_t('Legal form'), nm.get('legal_form')) +
        row(_t('Reg. date'), idy.get('reg_date') or c.get('reg_date')) +
        row(_t('OKVED (KBLI)'), kbli_s) +
        row(_t('Address'), addr)
    )
    right = (
        row(_t('Regime'), c.get('regime') or '') +
        row(_t('Capital'), cap, mono=True) +
        row(_t('Investment'), idy.get('penanaman_modal')) +
        row(_t('Scale'), idy.get('skala_usaha')) +
        dir_rows +
        row(_t('Tax authority'), tax_office.get('authority')) +
        row(_t('Portal'), tax_office.get('portal')) +
        row(_t('Phone'), contacts.get('phone') or c.get('phone'), mono=True) +
        row('Email', contacts.get('email') or c.get('email')) +
        row(_t('Bank'), bank)
    )
    if not left.strip() and not right.strip():
        return None
    return (
        '<div class="section-title"><h2>' + _t('📋 Client details') + '</h2></div>'
        '<section class="req-section">'
        '<div class="req-grid">'
        '<div class="req-col">' + left + '</div>'
        '<div class="req-col">' + right + '</div>'
        '</div>'
        '</section>'
    )


def render_client_requisites(c):
    """Compact client details card from clients_data.json."""
    def row(label, value, mono=False):
        if not value or str(value).strip() in ('-', 'None', ''):
            return ''
        val_class = 'req-val mono' if mono else 'req-val'
        return (
            '<div class="req-row">'
            '<span class="req-label">' + _esc(label) + '</span>'
            '<span class="' + val_class + '">' + _esc(str(value)) + '</span>'
            '</div>'
        )

    # Non-RU jurisdiction: render the local identifiers from identity.json
    # (NPWP/NIB/KBLI/management/…) instead of the RU INN/OGRNIP/OKVED set.
    _juris = (c.get('jurisdiction') or 'ru').strip().lower()
    if _juris and _juris != 'ru':
        _f = _render_requisites_foreign(c, row)
        if _f is not None:
            return _f

    inn = c.get('inn') or ''
    ogrnip = c.get('ogrnip') or ''
    reg_date = c.get('reg_date') or ''
    ifns = c.get('ifns') or ''
    okved = c.get('okved') or ''
    okved_name = c.get('okved_name') or ''
    addr = c.get('addr') or c.get('pill_region') or ''
    regime = c.get('regime') or ''
    phone = c.get('phone') or ''
    email = c.get('email') or ''
    tg = (c.get('messengers') or {}).get('telegram') or ''
    wa = (c.get('messengers') or {}).get('whatsapp') or ''
    bank = c.get('bank_name') or (c.get('bank_access') or {}).get('bank') or ''
    bik = c.get('bik') or ''
    acc_sys = c.get('accounting_system') or ''
    filing = c.get('filing_method') or {}
    submission = filing.get('submission') or ''
    sig = filing.get('signature_holder') or ''

    okved_full = (okved + ' — ' + okved_name) if okved and okved_name else okved

    left = (
        row(_t('INN'), inn, mono=True) +
        row(_t('OGRNIP'), ogrnip, mono=True) +
        row(_t('Reg. date'), reg_date) +
        row(_t('IFNS'), ifns) +
        row(_t('OKVED'), okved_full) +
        row(_t('Address'), addr)
    )
    right = (
        row(_t('Regime'), regime) +
        row(_t('Phone'), phone, mono=True) +
        row('Email', email) +
        row('Telegram', tg) +
        row('WhatsApp', wa) +
        row(_t('Bank'), bank) +
        row(_t('BIK'), bik, mono=True) +
        row(_t('Accounting'), _enum_ru(acc_sys)) +
        row(_t('Filing'), _enum_ru(submission)) +
        row(_t('Signature'), _enum_ru(sig))
    )

    if not left.strip() and not right.strip():
        return ''

    return (
        '<div class="section-title"><h2>' + _t('📋 Client details') + '</h2></div>'
        '<section class="req-section">'
        '<div class="req-grid">'
        '<div class="req-col">' + left + '</div>'
        '<div class="req-col">' + right + '</div>'
        '</div>'
        '</section>'
    )


REQ_CARD_CSS = (
    ".req-card{background:var(--bg-card);border:1px solid var(--border);"
    "border-radius:var(--radius-card);padding:var(--space-md);"
    "margin:0 0 var(--space-md)}"
    ".req-card > summary{cursor:pointer;font-size:var(--fs-h2);font-weight:500;"
    "list-style:none;display:flex;align-items:center;gap:var(--space-sm);margin:0}"
    ".req-card > summary::-webkit-details-marker{display:none}"
    ".req-card > summary::before{content:\"▸\";display:inline-block;"
    "transition:transform 150ms;color:var(--text-muted)}"
    ".req-card[open] > summary::before{transform:rotate(90deg)}"
    ".req-card[open] > summary{margin-bottom:var(--space-md);"
    "padding-bottom:var(--space-sm);border-bottom:1px solid var(--border)}"
    ".req-grid{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-lg)}"
    "@media(max-width:700px){.req-grid{grid-template-columns:1fr}}"
    ".req-row{display:flex;gap:var(--space-sm);padding:5px 0;"
    "border-bottom:1px dashed var(--border);font-size:var(--fs-meta)}"
    ".req-row:last-child{border-bottom:none}"
    ".req-label{color:var(--text-muted);min-width:90px;flex-shrink:0}"
    ".req-val{color:var(--text-primary);word-break:break-all}"
    ".req-val.mono{font-family:var(--font-mono,monospace);font-size:13px;"
    "color:var(--text-secondary)}"
)





_RISK_CATEGORY_RU = {
    'business': 'business',
    'business_positive': 'business',
    'client_relationship': 'client relationship',
    'regulatory': 'regulatory',
    'compliance': 'regulatory',
    'financial': 'finance',
    'operational': 'operations',
    'tax': 'taxes',
    'accounting': 'accounting',
    'data_quality': 'data gap',
    'infrastructure': 'infrastructure',
    'client_behavior': 'client behavior',
    'tax_regime': 'tax regime',
    'reporting': 'reporting',
    'legal': 'legal',
}


def _render_risk_card(r, tasks_lookup=None, client_id=None, today=None, client_name=''):
    """ONE risk card — the shared DS component used by BOTH the client
    «Client risks» section and the employee card «Risk zones», so the two read
    identically. Collapsible <details> with a severity edge; the summary is
    title + → next_action, the body reveals meta / description / linked tasks / law."""
    sev = str(r.get('severity') or 'grey').lower()
    sev = {'high': 'red', 'critical': 'red', 'medium': 'yellow', 'warn': 'yellow'}.get(sev, sev)
    if sev not in ('red', 'yellow', 'grey'):
        sev = 'grey'
    title = r.get('title', '') or ''
    desc = r.get('description', '') or ''
    next_action = r.get('next_action') or ''
    linked_tasks = r.get('linked_tasks') or []
    linked_law = r.get('linked_law') or ''

    meta_bits = []
    if r.get('category'):
        meta_bits.append(_t(_RISK_CATEGORY_RU.get(r['category'], r['category'])))
    if r.get('since'):
        meta_bits.append(_t('since') + ' ' + r['since'])
    meta = ' · '.join(meta_bits)

    summ_next = ('<span class="risk-next-inline">→ ' + _esc(next_action) + '</span>') if next_action else ''
    summary = (
        '<summary class="risk-summary">'
        '<span class="risk-title">' + _esc(title) + '</span>'
        + summ_next
        + '</summary>'
    )

    body_parts = []
    if meta:
        body_parts.append('<div class="risk-meta">' + _esc(meta) + '</div>')
    if desc:
        body_parts.append('<div class="risk-desc">' + _esc(desc) + '</div>')
    if linked_tasks:
        _n_lt = len(linked_tasks[:3])
        _lt_label = 'task already created' if _n_lt == 1 else 'tasks already created'
        _chips = ''.join(
            _linked_ref_chip(_lt_id, tasks_lookup, client_id, today, client_name)
            for _lt_id in linked_tasks[:3]
        )
        _more = ('<span class="risk-linked-more">…</span>' if len(linked_tasks) > 3 else '')
        body_parts.append(
            '<div class="risk-linked-tasks">'
            '<span class="risk-linked-label">' + _t(_lt_label) + ':</span> '
            + _chips + _more + '</div>'
        )
    if linked_law:
        body_parts.append('<div class="risk-law">⚖ ' + _esc(linked_law) + '</div>')

    return (
        '<details class="risk-card risk-sev-' + sev + '">'
        + summary
        + '<div class="risk-body">' + ''.join(body_parts) + '</div>'
        + '</details>'
    )


def render_client_risks(risks_data, tasks_lookup=None, client_id=None, today=None, client_name=''):
    """Section '⚠️ Client risks' — renders state/risks.json.
    Iter 9 (kind-split), 2026-06-13: only real risks are shown as cards
    (kind=risk or no kind — backward-compat for unmigrated). Open
    questions (kind=question) and onboarding/operational blockers (kind=blocker) are already
    visible in the tracks zone — they are not duplicated as cards here, but summarized in a footer line.
    Cards are collapsed: severity+title+next step visible; details under <details>.
    R11: green not shown. R12: resolved block removed.
    """
    if not risks_data:
        return ''
    risks = risks_data.get('risks') or []
    if not risks:
        return ''
    active_risks = [r for r in risks if r.get('severity') != 'green']
    if not active_risks:
        return ''

    sev_order = {'red': 0, 'yellow': 1, 'grey': 3}

    def _kind(r):
        k = r.get('kind')
        return k if k in ('risk', 'question', 'blocker') else 'risk'

    real_risks = [r for r in active_risks if _kind(r) == 'risk']
    questions = [r for r in active_risks if _kind(r) == 'question']
    blockers = [r for r in active_risks if _kind(r) == 'blocker']

    cards = [
        _render_risk_card(r, tasks_lookup, client_id, today, client_name)
        for r in sorted(real_risks, key=lambda x: sev_order.get(x.get('severity', 'grey'), 9))
    ]

    def _plural(n, one, few, many):
        n10, n100 = n % 10, n % 100
        if n10 == 1 and n100 != 11:
            return str(n) + ' ' + one
        if 2 <= n10 <= 4 and not (12 <= n100 <= 14):
            return str(n) + ' ' + few
        return str(n) + ' ' + many

    foot_bits = []
    if questions:
        foot_bits.append(str(len(questions)) + ' ' + (_t('open question') if len(questions) == 1 else _t('open questions')))
    if blockers:
        foot_bits.append(str(len(blockers)) + (' blocker' if len(blockers) == 1 else ' blockers'))
    footer = ''
    if foot_bits:
        footer = ('<div class="risks-derived">Also for this client: '
                  + ' and '.join(foot_bits) + ' — in the «Plan / Tracks» zone.</div>')

    if not cards and not footer:
        return ''

    # Plain total count, like the other sections. The old per-severity counter
    # used red/yellow emoji, which the global sanitizer strips — leaving a
    # confusing bare "1 2". Severity already shows via each card's coloured edge.
    counter = str(len(real_risks))

    grid = ('<section class="risks-grid">' + ''.join(cards) + '</section>') if cards else ''
    return (
        '<div class="section-title"><h2>' + _t('⚠️ Client risks') + '</h2>'
        '<span class="count">' + counter.strip() + '</span></div>'
        + grid + footer
    )


def _period_parity_chip(p):
    """Inline parity/cash chips for a period row (slots from migration 0017).

    Pure lens over `financials.json → periods[]`. Returns '' when nothing is
    recorded (parity_status null AND cash_reconciled not explicitly False), so a
    period that has never been reconciled renders exactly as before — additive and
    behaviour-preserving. Operator-locale labels via _t (i18n-guarded)."""
    bits = []
    ps = p.get('parity_status')
    if ps == 'pass':
        bits.append(('ok', _t('reconciled to source')))
    elif ps == 'fail':
        bits.append(('bad', _t('parity mismatch')))
    elif ps == 'pending':
        bits.append(('warn', _t('awaiting parity')))
    if p.get('cash_reconciled') is False:
        bits.append(('bad', _t('cash not reconciled')))
    return ''.join(
        '<span class="fin2-chip fin2-chip-%s">%s</span>' % (lvl, _esc(lbl))
        for lvl, lbl in bits
    )


def render_client_financials(fin, tasks_lookup=None, jurisdiction="ru", client_id=None, today_d=None, client_name=''):
    """💰 Financial model and calendar — from state/financials.json. Iter 19b (R4/R5/R6), 2026-05-25."""
    if not fin:
        return ''
    try:
        import _jurisdiction as _J
        _auth = _J.load_jurisdiction(jurisdiction).authorities
    except Exception:
        _auth = {}
    cur = _auth.get('currency_symbol') or '₽'
    inc_label = _auth.get('period_income_label') or 'USN income'
    periods = fin.get('periods') or []
    cal = fin.get('tax_calendar_2026') or []
    yp = fin.get('yearly_pace_2026') or {}
    if not (periods or cal):
        return ''

    _PERIOD_STATUS_RU = {
        'archive': 'archive',
        'archive_micro': 'archive (micro)',
        'calculated': 'calculated',
        'calculated_invoice_sent_to_client': 'invoice sent to client',
        'paid': 'paid',
        'current': 'current',
        'in_progress': 'in progress',
        'scheduled': 'scheduled',
        'pending': 'pending',
        'archive_pre_switch': 'archive (pre-switch)',
        'awaiting_extraction': 'waiting for statement',
        'calculated_paid': 'calculated, paid',
        'calculated_payment_pending_check': 'calculated, checking payment',
        'current_ausn': 'current (AUSN)',
        'last_period_serviced': 'last serviced period',
    }
    _CAL_STATUS_RU = {
        'overlapped_by_insurance': 'offset by contributions',
        'in_progress': 'in progress',
        'scheduled': 'scheduled',
        'scheduled_calc_by_fact': 'scheduled (calc by fact)',
        'paid': 'paid',
        'upcoming': 'upcoming',
        'overdue': 'overdue',
        'sent': 'sent',
        'cancelled': 'cancelled',
        'pending': 'pending',
        'done': 'done',
        'auto_passed': 'passed automatically',
        'awaiting_extraction_q1': 'waiting for Q1 statement',
        'decision_required': 'decision required',
        'payment_check_in_progress': 'checking payment',
        'presumably_paid': 'presumably paid',
        'scheduled_conditional': 'scheduled (conditional)',
        'scheduled_finalization': 'scheduled (finalization)',
    }

    def _fmt_money(v):
        if v is None:
            return '—'
        try:
            return '{:,.2f}'.format(float(v)).replace(',', ' ').replace('.00', '')
        except Exception:
            return str(v)

    # Pace caption — was a full-width grey bar; now a muted line beside the title.
    pace_html = ''
    if yp:
        ea = (yp.get('estimated_annual_income') or yp.get('estimated_annual_turnover_idr')
              or yp.get('estimated_annual'))   # multi-jurisdiction: ID stores turnover_idr
        gx = yp.get('growth_vs_prev_year_x')
        bits = []
        if ea:
            bits.append('~' + _fmt_money(ea) + ' ' + cur + ' ' + _t('annual'))
        if gx:
            bits.append(_t('growth') + ' \u00d7' + str(gx))
        if bits:
            pace_html = ('<span class="fin2-pace">\U0001F4C8 ' + _t('Pace') + ' 2026: '
                         + _esc(' \u00b7 '.join(bits)) + '</span>')

    # Status word -> chip tone. Chip-only signal, no rail (operator pick 2026-06-26).
    _STATUS_TONE = {
        'paid': 'ok', 'calculated_paid': 'ok',
        'current': 'info', 'current_ausn': 'info', 'in_progress': 'info',
        'last_period_serviced': 'info',
        'calculated_payment_pending_check': 'warn', 'decision_required': 'warn',
        'overdue': 'bad',
    }

    periods_section = ''
    if periods:
        from _strings import LOCALE as _LOC
        _RU_MONTHS = ('Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль',
                      'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь')

        def _fmt_period(per):
            import re as _re
            m = _re.fullmatch(r'(\d{4})-(\d{2})', str(per))
            if m and _LOC == 'ru':
                return _RU_MONTHS[int(m.group(2)) - 1] + ' ' + m.group(1)
            return str(per)

        rows = []
        for p in periods:
            per = p.get('period', '')
            inc_v = p.get('income_usn')
            if inc_v is None:
                inc_v = p.get('turnover_idr')   # non-RU jurisdictions store turnover here
            inc = _fmt_money(inc_v)
            est = ' (' + _t('est.') + ')' if (p.get('income_usn_estimated') or p.get('turnover_idr_estimated')) else ''
            taxes = p.get('taxes') or {}
            tbits = []
            if taxes.get('usn_advance') is not None:
                tbits.append(_t('USN advance') + ' ' + str(taxes['usn_advance']))
            if taxes.get('one_pct_overage'):
                tbits.append('1%=' + str(taxes['one_pct_overage']))
            if taxes.get('fixed_insurance_paid'):
                tbits.append(_t('fixed') + ' ' + _fmt_money(taxes['fixed_insurance_paid']))
            if not tbits and taxes:
                # Generic (non-RU) taxes column: sum the period's tax amounts.
                _tax_vals = [v for k, v in taxes.items()
                             if isinstance(v, (int, float)) and k not in ('payroll_net', 'payroll_net_idr')]
                if _tax_vals:
                    tbits.append(_t('taxes total') + ' ' + _fmt_money(sum(_tax_vals)) + ' ' + cur)
            tax_s = ' \u00b7 '.join(tbits) if tbits else '\u2014'
            status_raw = p.get('status', '')
            status_ru = _t(_PERIOD_STATUS_RU.get(status_raw, status_raw))
            tone = _STATUS_TONE.get(status_raw, 'neutral')
            parity = _period_parity_chip(p)
            # Готовность column: the readiness pill is primary; the archived/status
            # word shows only when no readiness is recorded (RU periods / year rows).
            if parity:
                ready_cell = parity
            elif status_ru:
                ready_cell = '<span class="fin2-chip fin2-chip-' + tone + '">' + _esc(status_ru) + '</span>'
            else:
                ready_cell = ''
            rows.append(
                '<div class="fin2-row">'
                '<span class="fin2-per">' + _esc(_fmt_period(per)) + '</span>'
                '<span class="fin2-turn">' + _esc(inc + ' ' + cur + est) + '</span>'
                '<span class="fin2-tax">' + _esc(tax_s) + '</span>'
                '<span class="fin2-st">' + ready_cell + '</span>'
                '</div>'
            )
        # Current open month — synthesize an "in progress" row when the latest closed
        # period is behind the current month, so the actionable period is always visible.
        from datetime import date as _date
        _cur_m = _date.today().strftime('%Y-%m')
        _ms = [s for s in (str(p.get('period', '')) for p in periods)
               if len(s) == 7 and s[:4].isdigit() and s[4] == '-']
        if _cur_m not in _ms and (not _ms or _cur_m > max(_ms)):
            rows.append(
                '<div class="fin2-row">'
                '<span class="fin2-per">' + _esc(_fmt_period(_cur_m)) + '</span>'
                '<span class="fin2-turn fin2-muted">' + _esc(_t('collecting…')) + '</span>'
                '<span class="fin2-tax">—</span>'
                '<span class="fin2-st"><span class="fin2-chip fin2-chip-info">'
                + _esc(_t('in progress')) + '</span></span>'
                '</div>'
            )
        _head = (
            '<div class="fin2-row fin2-head">'
            '<span class="fin2-per">' + _t('Period') + '</span>'
            '<span class="fin2-turn">' + _t('Turnover') + '</span>'
            '<span class="fin2-tax">' + _t('Taxes') + '</span>'
            '<span class="fin2-st">' + _t('Readiness') + '</span>'
            '</div>'
        )
        periods_section = (
            '<div class="section-title"><h2>' + _t('\U0001F4CA Periods') + '</h2>' + pace_html + '</div>'
            '<div class="fin2-card">' + _head + ''.join(rows) + '</div>'
            '<div class="fin2-note">' + _t('readiness note') + '</div>'
        )

    calendar_section = ''
    if cal:
        from datetime import date, timedelta
        today = date.today()
        today_iso = today.isoformat()
        cur_year = str(today.year)
        near_iso = (today + timedelta(days=70)).isoformat()   # detail horizon
        soon_iso = (today + timedelta(days=14)).isoformat()   # red date

        def _fmt_cal_date(d):
            parts = str(d).split('-')
            if len(parts) == 3:
                return parts[2] + '.' + parts[1] + ('' if parts[0] == cur_year else '.' + parts[0][2:])
            return str(d)

        def _ev_item(ev):
            what = _gloss_text(ev.get('what', ''), jurisdiction)
            amt, amt_est = ev.get('amount'), ev.get('amount_estimated')
            amt_html = ''
            if amt is not None:
                amt_html = '<span class="cal2-amt">' + _esc(_fmt_money(amt) + ' ' + cur) + '</span>'
            elif amt_est is not None:
                amt_html = '<span class="cal2-amt">~' + _esc(_fmt_money(amt_est) + ' ' + cur) + '</span>'
            task_html = ''
            lt = ev.get('linked_task') or ''
            if lt and (tasks_lookup or {}).get(lt):
                task_html = ('<span class="cal2-task">'
                             + _linked_ref_chip(lt, tasks_lookup, client_id, today_d or today, client_name)
                             + '</span>')
            return ('<div class="cal2-item"><span class="cal2-what">' + what + '</span>'
                    + amt_html + task_html + '</div>')

        def _group(events):
            evs = sorted(events, key=lambda e: e.get('date', ''))
            out, i = [], 0
            while i < len(evs):
                d = evs[i].get('date', '')
                grp = []
                while i < len(evs) and evs[i].get('date', '') == d:
                    grp.append(evs[i]); i += 1
                soon = ' cal2-soon' if (today_iso <= d <= soon_iso) else ''
                out.append('<div class="cal2-row"><div class="cal2-date' + soon + '">'
                           + _esc(_fmt_cal_date(d)) + '</div><div class="cal2-items">'
                           + ''.join(_ev_item(e) for e in grp) + '</div></div>')
            return '<div class="cal2">' + ''.join(out) + '</div>'

        near, later, past = [], [], []
        for ev in cal:
            d = ev.get('date', '')
            (past if d < today_iso else (near if d <= near_iso else later)).append(ev)

        near_html = _group(near) if near else (
            '<div class="fin2-empty">' + _t('nothing due soon') + '</div>')
        later_html = ('<details class="cal2-more"><summary>' + _t('Further ahead') + ' ('
                      + str(len(later)) + ')</summary>' + _group(later) + '</details>') if later else ''
        past_html = ('<details class="cal2-more"><summary>' + _t('Past in') + ' ' + cur_year + ' ('
                     + str(len(past)) + ')</summary>' + _group(past) + '</details>') if past else ''
        calendar_section = (
            '<div class="section-title"><h2>' + _t('\U0001F4C5 Tax calendar 2026') + '</h2></div>'
            '<div class="fin2-card fin2-cal">' + near_html + later_html + past_html + '</div>'
        )

    return periods_section + calendar_section


# Counterparty enum → English label (also a t() catalog key, routed through _t()
# for the operator locale). SHARED with state_lint.py so a new relation_type/
# category can't ship without a localized label (see DESIGN-SYSTEM.md §Localization;
# lint key i18n_cp_label). Keep keys in sync with the data's controlled vocabulary.
_CP_RELATION_LABEL = {
    'b2b_customer_main': 'B2B (main)',
    'b2b_customer': 'B2B',
    'b2b_supplier': 'Supplier',
    'agent': 'Agent',
    'payment_aggregator': 'Acquiring',
    'sz_executor': 'Self-employed contractor',
    'self_employed_contractor': 'Self-employed contractor',
    'npd_supplier': 'Self-employed supplier',
    'bookkeeping_service_provider_team_lead': 'Bookkeeping provider (team lead)',
}
_CP_CATEGORY_LABEL = {
    'gov_order': 'gov orders',
    'marketplace': 'marketplace',
    'marketplace_taxi': 'marketplace (taxi)',
    'rental': 'rental',
    'it_consulting': 'IT consulting',
    'labor': 'labor/individual contractors',
    'monthly_recurring': 'monthly',
    'payment_processor': 'payment processing',
    'production_client': 'client (production)',
    'production_executor': 'executor (production)',
    'rental_aggregator': 'rental (via aggregator)',
    'rental_tenant': 'tenant',
    'subcontractor_ip': 'subcontractor SP',
    'creditor': 'creditor',
    'property_management': 'property management',
    'recruiting_client': 'recruiting client',
    'recurring_executor': 'recurring executor',
    'rental_agent_short_term': 'rental (short-term, agent)',
    'rental_income': 'rental income',
    'services': 'services',
    'services_buyer': 'services buyer',
    'tenant_commercial': 'tenant (commercial)',
    'tenant_direct_long_term': 'tenant (direct, long-term)',
    'tenant_medical_equipment': 'tenant (medical equipment)',
}


def render_client_counterparties(cp_data, tasks_lookup=None, client_id=None, today=None, client_name=''):
    """🤝 Counterparties — from state/counterparties.json. Iter 21, 2026-05-25."""
    if not cp_data:
        return ''
    cps = cp_data.get('counterparties') or []
    if not cps:
        return ''

    cards = []
    for cp in cps:
        name = cp.get('name', '')
        inn = cp.get('inn') or '—'
        rel = cp.get('relation_type', '')
        rel_ru = _t(_CP_RELATION_LABEL.get(rel, rel or '—'))
        cat = cp.get('category') or ''
        cat_ru = _t(_CP_CATEGORY_LABEL.get(cat, cat))
        since = cp.get('since') or ''
        tags = cp.get('tags') or []
        notes = cp.get('notes') or ''
        linked_q = cp.get('linked_open_questions') or []
        linked_t = cp.get('linked_tasks') or []
        req = cp.get('requisites') or {}

        req_bits = []
        if req.get('bank_name'):
            req_bits.append(req['bank_name'])
        if req.get('bik'):
            req_bits.append('BIK ' + req['bik'])
        if req.get('account'):
            req_bits.append('acct …' + req['account'][-4:])
        if req.get('phone'):
            req_bits.append('tel ' + req['phone'])
        req_html = ('<div class="cp-req">' + _esc(' · '.join(req_bits)) + '</div>') if req_bits else ''

        meta_bits = [rel_ru]
        if cat_ru:
            meta_bits.append(cat_ru)
        if since:
            meta_bits.append(_t('since') + ' ' + since)
        meta = ' · '.join(meta_bits)

        tags_html = ''
        if tags:
            tags_html = '<div class="cp-tags">' + ''.join(
                '<span class="cp-tag">' + _esc(str(t).replace('_',' ')) + '</span>' for t in tags
            ) + '</div>'

        notes_html = ('<div class="cp-notes">' + _esc(notes) + '</div>') if notes else ''

        lq_html = ''
        if linked_q:
            lq_html = (
                '<div class="cp-linked">' + _t('open questions:') + ' '
                + ', '.join('<code>' + _esc(q) + '</code>' for q in linked_q)
                + '</div>'
            )
        lt_html = ''
        if linked_t:
            _cp_chips = ''.join(
                _linked_ref_chip(_lt, tasks_lookup, client_id, today, client_name) for _lt in linked_t
            )
            lt_html = (
                '<div class="cp-linked cp-linked-tasks">' + _t('tasks:') + ' '
                + _cp_chips
                + '</div>'
            )

        cards.append(
            '<div class="cp-card">'
            '<div class="cp-name">' + _esc(name) + '</div>'
            '<div class="cp-meta">' + _esc(meta) + '</div>'
            '<div class="cp-inn">' + _t('INN:') + ' <code>' + _esc(inn) + '</code></div>'
            + req_html + tags_html + notes_html + lq_html + lt_html
            + '</div>'
        )

    return (
        '<div class="section-title"><h2>' + _t('🤝 Counterparties') + '</h2>'
        '<span class="count">' + str(len(cps)) + '</span></div>'
        '<section class="cp-grid">' + ''.join(cards) + '</section>'
    )





def render_client_accounts(acc):
    """🏦 Accounts and registers — from state/accounts.json. v2 P2 25.05.2026.

    Supports the flat state structure (bank_name/bik/account/owner_type/etc).
    Shows ALL accounts (not only primary), including closed ones with a marker.
    Includes acquiring_channels[] and pending_corrections for kassas.
    """
    if not acc:
        return ''
    banks = acc.get('bank_accounts') or []
    foreign = acc.get('foreign_accounts') or []
    kassas = acc.get('kassas') or []
    acquiring = acc.get('acquiring_channels') or []
    bacc = acc.get('bank_access') or {}
    has_any = banks or foreign or kassas or acquiring or bacc.get('note') or bacc.get('primary_bank')
    if not has_any:
        return ''

    blocks = []

    # 💳 Bank accounts (ALL — primary + secondary + closed)
    if banks:
        rows = []
        for b in banks:
            bits = []
            bank_name = b.get('bank_name') or ''
            if bank_name:
                primary_mark = ' ⭐' if b.get('is_primary') else ''
                bits.append('<span class="acc-bank">' + _esc(str(bank_name)) + primary_mark + '</span>')
            acct = b.get('account')
            if acct:
                bits.append('<span class="acc-num">' + _esc('…' + str(acct)[-4:]) + '</span>')
            bik = b.get('bik')
            if bik:
                bits.append('<span class="acc-bik">BIK ' + _esc(str(bik)) + '</span>')
            purpose = b.get('purpose') or b.get('id', '')
            closed_at = b.get('closed_at')
            status_label = ''
            if closed_at:
                status_label = ' <span class="acc-status" style="color:#9ca3af;">' + _t('closed') + ' ' + _esc(str(closed_at)) + '</span>'
            elif b.get('bik_change_pending'):
                _at = b.get('bik_change_at', '')
                status_label = ' <span class="acc-status" style="color:#dc2626;">' + _t('BIK changing') + ' ' + _esc(str(_at)) + '</span>'
            rows.append(
                '<div class="acc-row">'
                + ' · '.join(bits)
                + (' <span class="acc-purpose">' + _esc(str(purpose)) + '</span>' if purpose else '')
                + status_label
                + '</div>'
            )
        blocks.append('<div class="acc-block-title">' + _t('Bank accounts') + ' (' + str(len(banks)) + ')</div>' + ''.join(rows))

    # 🌍 Foreign accounts
    if foreign:
        rows = []
        for f in foreign:
            bits = []
            bank = f.get('bank_name') or f.get('bank') or ''
            ctry = f.get('country') or ''
            owner = f.get('owner_type') or ''
            curr = f.get('currency') or ''
            head = (str(bank) + (' (' + str(ctry) + ')' if ctry else '')).strip()
            if head:
                bits.append('<span class="acc-bank">' + _esc(head) + '</span>')
            if curr:
                bits.append('<span class="acc-num">' + _esc(str(curr)) + '</span>')
            if owner:
                owner_ru = {'ip': 'SP account', 'individual': 'individual account', 'related_entity': 'related entity'}.get(owner, owner)
                bits.append('<span class="acc-purpose">' + _esc(_t(str(owner_ru))) + '</span>')
            note = f.get('notes') or ''
            rows.append(
                '<div class="acc-row">' + ' · '.join(bits)
                + ('<div class="acc-note">' + _esc(str(note)) + '</div>' if note else '')
                + '</div>'
            )
        blocks.append('<div class="acc-block-title">' + _t('Foreign accounts') + ' (' + str(len(foreign)) + ')</div>' + ''.join(rows))

    # 🧾 Registers and OFD (<vendor> 5 + RNM + pending_corrections if present)
    if kassas:
        rows = []
        for k in kassas:
            bits = []
            if k.get('model'):
                bits.append('<span class="acc-bank">' + _esc(str(k['model'])) + '</span>')
            if k.get('rnm'):
                bits.append('<span class="acc-num">RNM ' + _esc(str(k['rnm'])) + '</span>')
            _ofd = k.get('ofd_provider') or k.get('ofd')
            if _ofd:
                bits.append('<span class="acc-purpose">' + _esc(str(_ofd)) + '</span>')
            purpose = k.get('location_or_purpose') or k.get('purpose') or ''
            if purpose:
                bits.append('<span class="acc-purpose">' + _esc(str(purpose)) + '</span>')
            status = k.get('status', '')
            _kkt_status_ru = {
                'registering': 'registering',
                'active': 'active',
                'exists_details_unknown': 'exists, details TBD',
                'archived': 'archived',
            }
            if status == 'registering':
                bits.append('<span class="acc-status" style="color:#dc2626;">' + _t('registering') + '</span>')
            elif status:
                bits.append('<span class="acc-status">' + _esc(_t(_kkt_status_ru.get(status, status))) + '</span>')
            shifts = k.get('shifts_count_period')
            period = k.get('period')
            if shifts is not None and period:
                bits.append('<span class="acc-purpose">' + str(shifts) + ' ' + _t('shifts') + ' ' + _esc(str(period)) + '</span>')
            if not bits:
                bits.append('<span class="acc-bank">' + _t('KKT') + '</span>')
            row = '<div class="acc-row">' + ' · '.join(bits) + '</div>'
            _knote = k.get('notes')
            if _knote:
                row += ('<div class="acc-note" style="color:var(--text-muted);'
                        'font-size:13px;margin-top:2px;">' + _esc(str(_knote)) + '</div>')
            pc = k.get('pending_corrections')
            if pc and isinstance(pc, dict):
                amt = pc.get('total_amount')
                law = pc.get('law_violation', '')
                penalty = pc.get('potential_penalty_amount_max')
                escape = pc.get('escape_mechanism', '')
                row += ('<div class="acc-note" style="background:#fef2f2;border-left:3px solid #dc2626;padding:6px 8px;margin-top:4px;">'
                        '🔴 <b>Unrecorded revenue: ' + (str(amt) + ' ₽' if amt else '?') + '</b>'
                        + (' · ' + _esc(str(law)) if law else '')
                        + (' · penalty up to ' + str(penalty) + ' ₽' if penalty else '')
                        + ('<br>↪️ ' + _esc(str(escape)) if escape else '')
                        + '</div>')
            rows.append(row)
        blocks.append('<div class="acc-block-title">' + _t('Registers and OFD') + ' (' + str(len(kassas)) + ')</div>' + ''.join(rows))

    # 💳 Acquiring channels (the client 3 channels, the client Prodamus+YooKassa)
    if acquiring:
        rows = []
        for a in acquiring:
            bits = []
            _prov = a.get('provider') or a.get('provider_bank')
            if _prov:
                bits.append('<span class="acc-bank">' + _esc(str(_prov)) + '</span>')
            if a.get('provider_inn'):
                bits.append('<span class="acc-num">INN ' + _esc(str(a['provider_inn'])) + '</span>')
            _pages = a.get('pages') or ([a.get('url')] if a.get('url') else [])
            for _pg in _pages:
                if _pg:
                    bits.append('<span class="acc-purpose">' + _esc(str(_pg)) + '</span>')
            role = a.get('agent_role') or ''
            if role:
                _role_ru = {
                    'acquirer': 'acquirer',
                    'payment_gateway': 'payment gateway',
                    'payment_saas': 'payment service',
                }.get(role, role)
                bits.append('<span class="acc-purpose">' + _esc(_t(str(_role_ru))) + '</span>')
            since = a.get('since')
            if since:
                bits.append('<span class="acc-purpose">' + _t('since') + ' ' + _esc(str(since)) + '</span>')
            status = a.get('status', '')
            if status and status != 'active':
                _astat_ru = {
                    'idle_since_connection': 'idle since connection',
                }.get(status, status)
                bits.append('<span class="acc-status">' + _esc(_t(str(_astat_ru))) + '</span>')
            _purpose = a.get('purpose')
            if _purpose:
                bits.append('<span class="acc-purpose">' + _esc(str(_purpose)) + '</span>')
            if a.get('confirmed') is False:
                bits.append('<span class="acc-status">' + _t('not confirmed') + '</span>')
            if not bits:
                bits.append('<span class="acc-bank">' + _t('Acquiring') + '</span>')
            _arow = '<div class="acc-row">' + ' · '.join(bits) + '</div>'
            _anote = a.get('notes')
            if _anote:
                _arow += ('<div class="acc-note" style="color:var(--text-muted);'
                          'font-size:13px;margin-top:2px;">' + _esc(str(_anote)) + '</div>')
            rows.append(_arow)
        blocks.append('<div class="acc-block-title">' + _t('Acquiring channels') + ' (' + str(len(acquiring)) + ')</div>' + ''.join(rows))

    # 🔑 Online banking access
    if bacc.get('primary_bank') or bacc.get('access_level') or bacc.get('note'):
        bits = []
        if bacc.get('primary_bank'):
            bits.append('<span class="acc-bank">' + _esc(str(bacc['primary_bank'])) + '</span>')
        level = bacc.get('access_level')
        level_ru = {'none': 'no access', 'view_only': 'view only', 'full': 'full', 'via_partner': 'via partner'}.get(level, level)
        if level_ru:
            bits.append('<span class="acc-purpose">' + _esc(_t(str(level_ru))) + '</span>')
        if bacc.get('is_ausn_partner'):
            bits.append('<span class="acc-purpose" style="color:#059669;">' + _t('AUSN partner') + '</span>')
        head_row = '<div class="acc-row">' + (' · '.join(bits) if bits else '') + '</div>' if bits else ''
        note = bacc.get('note') or ''
        note_html = ('<div class="acc-note">ℹ️ ' + _esc(str(note)) + '</div>') if note else ''
        blocks.append('<div class="acc-block-title">' + _t('Online banking access') + '</div>' + head_row + note_html)

    return (
        '<div class="section-title"><h2>' + _t('🏦 Accounts and registers') + '</h2></div>'
        '<section class="acc-section">'
        + ''.join(blocks) +
        '</section>'
    )


def render_client_real_estate(re_data):
    """🏠 Real estate — from state/real_estate.json. P2 25.05.2026.
    Only for clients with a populated real_estate.json (currently the client).
    """
    if not re_data:
        return ''
    objects = re_data.get('objects') or []
    if not objects:
        return ''
    legal_basis = re_data.get('legal_basis') or {}
    summary = re_data.get('summary') or {}

    rows = []
    for o in objects:
        addr = o.get('address_short') or o.get('address_full', '')
        otype = o.get('type', '')
        otype_ru = {'non_residential': 'non-residential', 'residential': 'residential', 'land': 'land', 'commercial': 'commercial'}.get(otype, otype)
        area = o.get('area_sqm')
        cadastr = o.get('cadastr', '')
        ag = o.get('agreement') or {}
        ag_type = ag.get('type', '')
        ag_type_ru = {'direct_lease': 'direct lease', 'agent_rental': 'via agent', 'sublease': 'sublease'}.get(ag_type, ag_type)
        ag_to = ag.get('valid_to', '')
        rate = ag.get('rate_or_formula', '')
        ta = o.get('tenant_or_agent') or {}
        ta_name = ta.get('name', '')
        ta_inn = ta.get('inn', '')
        mort = o.get('mortgage')

        head_bits = []
        head_bits.append('<span class="acc-bank">' + _esc(str(addr)) + '</span>')
        if otype_ru:
            head_bits.append('<span class="acc-purpose">' + _esc(str(otype_ru)) + '</span>')
        if area:
            head_bits.append('<span class="acc-num">' + str(area) + ' m²</span>')

        deal_bits = []
        if ag_type_ru:
            deal_bits.append('<b>' + _esc(str(ag_type_ru)) + '</b>')
        if ta_name:
            deal_bits.append(_esc(str(ta_name)) + (' (INN ' + _esc(str(ta_inn)) + ')' if ta_inn else ''))
        if ag_to:
            deal_bits.append('until ' + _esc(str(ag_to)))
        if rate:
            deal_bits.append('💰 ' + _esc(str(rate)))

        mort_html = ''
        if mort and isinstance(mort, dict):
            mb = mort.get('bank', '')
            mu = mort.get('until', '')
            mort_html = '<div class="acc-note" style="color:#7c2d12;">🏦 Mortgage ' + _esc(str(mb)) + (' until ' + _esc(str(mu)) if mu else '') + '</div>'

        cadastr_html = ('<div class="acc-note" style="font-size:11px;color:#6b7280;">cadastral ' + _esc(str(cadastr)) + '</div>') if cadastr else ''

        rows.append(
            '<div class="acc-row" style="border-left:3px solid #059669;padding-left:8px;">'
            + ' · '.join(head_bits)
            + ('<div style="margin-top:2px;">' + ' · '.join(deal_bits) + '</div>' if deal_bits else '')
            + cadastr_html
            + mort_html
            + '</div>'
        )

    title_extra = ' (' + str(summary.get('total_objects')) + ')' if summary.get('total_objects') else ''

    legal_html = ''
    if legal_basis.get('marriage_contract_at'):
        legal_html = '<div class="acc-note" style="font-size:11px;color:#6b7280;margin-top:6px;">📜 Marriage contract dated ' + _esc(str(legal_basis['marriage_contract_at'])) + '</div>'

    return (
        '<div class="section-title"><h2>' + _t('Real estate') + title_extra + '</h2></div>'
        '<section class="acc-section">'
        + ''.join(rows)
        + legal_html
        + '</section>'
    )


def _parse_iso_date(v):
    """YYYY-MM-DD -> date, else None. Local to the roster panel."""
    try:
        from datetime import datetime as _dtp
        return _dtp.strptime(str(v)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


_EMPC_ASSETS = """
<style id="empc-css">
.empc-backdrop{position:fixed;inset:0;background:rgba(18,18,28,.34);
  backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);display:none;
  align-items:center;justify-content:center;padding:var(--space-lg);z-index:1200}
.empc-backdrop.open{display:flex}
.empc-modal{position:relative;width:100%;max-width:980px;max-height:90vh;
  background:var(--bg-card);border-radius:16px;overflow:hidden;display:flex;
  flex-direction:column;box-shadow:0 24px 64px -16px rgba(16,16,26,0.30),0 4px 12px rgba(16,16,26,0.06);
  border:1px solid var(--border);animation:empcpop .15s ease-out}
@keyframes empcpop{from{transform:translateY(6px) scale(.99);opacity:0}to{transform:none;opacity:1}}
.empc-bc{display:inline-block;font-size:14px;margin-bottom:14px}
.empc-x{position:absolute;top:18px;right:18px;width:32px;height:32px;border-radius:8px;border:none;
  background:none;color:var(--text-muted);font-size:18px;cursor:pointer;line-height:1;z-index:2;
  display:flex;align-items:center;justify-content:center;transition:all 120ms}
.empc-x:hover{background:var(--bg-page);color:var(--text-primary)}
.empc-body{flex:1 1 auto;overflow:auto;padding:34px 44px 28px;color:var(--text-primary);
  font-size:var(--fs-base);line-height:1.5}
.empc-name{font-size:23px;font-weight:600;letter-spacing:-0.02em;color:var(--text-primary);line-height:1.28;margin:2px 0 0}
.empc-sub{color:var(--text-muted);font-size:var(--fs-meta);margin-top:3px}
.empc-id{color:var(--text-muted);background:var(--bg-subtle);border-radius:var(--radius-badge);
  padding:1px 6px;font-size:11px;margin-left:6px}
.empc-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:11px;margin-bottom:18px}
.empc-tag{font-size:12px;padding:2px 10px;border-radius:20px;border:1px solid var(--border);
  background:var(--bg-page);color:var(--text-secondary)}
.empc-tag.flag{background:var(--accent-soft);border-color:var(--accent-soft-border);color:var(--accent-text)}
.empc-tag.gold{background:var(--bg-page);border-color:var(--border);color:var(--text-secondary)}
/* section (no card-island) — for risks, like the client card */
.empc-sec{margin-top:26px}
.empc-seclabel{font-size:11px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;
  color:var(--text-muted);margin:0 0 10px;display:flex;align-items:center;gap:8px}
.empc-seclabel:before{content:"";width:12px;height:2px;background:var(--accent);border-radius:2px}
.empc-hint{color:var(--text-muted);font-size:12px;margin-left:6px}
/* coverage in the narrow column: stack label over status */
.empc-cov .empc-row{flex-direction:column;gap:3px}
.empc-cov .empc-k{flex:none}
.empc-cov .empc-hint{margin-left:0;display:block;margin-top:2px}
/* sticky action footer (DS: .tm-actions pattern) */
.empc-foot{flex:0 0 auto;display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  padding:16px 44px;background:var(--bg-card);border-top:1px solid var(--border)}
@media(max-width:720px){.empc-body{padding:26px 22px 22px}.empc-foot{padding:14px 22px}}
.empc-foot .tm-btn{margin:0}
.empc-grid{display:grid;grid-template-columns:1fr 300px;gap:16px;margin-top:16px}
@media(max-width:780px){.empc-grid{grid-template-columns:1fr}}
.empc-card{padding:0;margin-top:26px}
.empc-ttl{font-size:11px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:var(--text-muted);
  margin:0 0 12px;display:flex;align-items:center;gap:8px}
.empc-ttl:before{content:"";width:12px;height:2px;background:var(--accent);border-radius:2px}
.empc-row{display:flex;flex-direction:column;gap:3px;padding:12px 0;border-top:1px solid var(--border)}
.empc-row:first-child{border-top:0;padding-top:0}
.empc-k{color:var(--text-muted);font-size:11px;font-weight:600;letter-spacing:.4px;text-transform:uppercase}
.empc-v{font-size:var(--fs-base)}
.empc-v b{color:var(--text-primary)}
.empc-code{color:var(--text-muted);font-size:12px;font-weight:400}
.empc-do{color:var(--text-secondary);font-size:12.5px}
.empc-arrow{color:var(--accent);font-weight:600}
.empc-pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:var(--radius-badge);margin-left:6px;
  border:1px solid var(--border);background:var(--bg-page);color:var(--text-secondary)}
.empc-pill.ok{background:var(--green-bg);border-color:transparent;color:var(--accent-green)}
.empc-pill.warn{background:var(--yellow-bg);border-color:transparent;color:var(--accent-yellow)}
.empc-pill.risk{background:var(--red-bg);border-color:transparent;color:var(--accent-red)}
.empc-pill.muted{background:var(--bg-subtle);border-color:transparent;color:var(--text-secondary)}
.empc-pills{display:flex;flex-wrap:wrap;gap:8px}
.empc-cv{display:flex;align-items:center;gap:7px;font-size:var(--fs-meta);padding:6px 11px;border-radius:var(--radius-btn);
  border:1px solid var(--border);background:var(--bg-page)}
.empc-dot{width:8px;height:8px;border-radius:50%;flex:0 0 8px}
.empc-dot.ok{background:var(--accent-green)}.empc-dot.warn{background:var(--accent-yellow)}.empc-dot.risk{background:var(--accent-red)}
.empc-tbl{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
.empc-tbl th,.empc-tbl td{text-align:right;padding:8px 6px;font-size:var(--fs-meta);border-bottom:1px solid var(--border)}
.empc-tbl th{color:var(--text-muted);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
.empc-tbl th:first-child,.empc-tbl td:first-child{text-align:left}
.empc-tbl tbody tr.empc-link{cursor:pointer;transition:background 120ms}
.empc-tbl tbody tr.empc-link:hover{background:var(--bg-subtle)}
.empc-tbl tbody tr.empc-link td:first-child{box-shadow:inset 2px 0 0 transparent;transition:box-shadow 120ms}
.empc-tbl tbody tr.empc-link:hover td:first-child{box-shadow:inset 2px 0 0 var(--accent)}
.empc-tbl tfoot td{font-weight:600;border-top:2px solid var(--border-strong);border-bottom:0;color:var(--text-primary)}
.empc-tcell{display:inline-flex;align-items:center;gap:6px}
.empc-tcell .empc-go{color:var(--text-muted);font-size:14px}
.empc-chip{display:inline-block;font-size:11px;padding:1px 7px;border-radius:var(--radius-badge)}
.empc-chip.ok{background:var(--green-bg);color:var(--accent-green)}.empc-chip.pend{background:var(--yellow-bg);color:var(--accent-yellow)}
.empc-annual{margin-top:12px;padding:10px 12px;background:var(--accent-soft);border:1px solid var(--accent-soft-border);
  border-radius:var(--radius-btn);font-size:var(--fs-meta);color:var(--accent-text)}
.empc-note{font-size:11px;color:var(--text-muted);margin-top:8px;text-align:right}
.empc-empty{color:var(--text-muted);font-size:var(--fs-meta)}
.empc-link-row{display:flex;align-items:flex-start;gap:8px;padding:10px 8px;margin:0;border-radius:var(--radius-btn);
  border-top:1px solid var(--border);cursor:pointer;transition:background 120ms;position:relative}
.empc-link-row:first-of-type{border-top:0}
.empc-link-row:hover{background:var(--bg-subtle)}
.empc-link-row:before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:2px;border-radius:2px;background:transparent;transition:background 120ms}
.empc-link-row:hover:before{background:var(--accent)}
.empc-lr-main{flex:1 1 auto;min-width:0}
.empc-tt{font-size:var(--fs-meta);font-weight:550;color:var(--text-primary)}
.empc-tm{color:var(--text-muted);font-size:12px;margin-top:2px}
.empc-go{flex:0 0 auto;color:var(--text-muted);font-size:16px;align-self:center}
.empc-rk{display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--border)}
.empc-rk:first-child{border-top:0;padding-top:0}.empc-rk .empc-ri{flex:0 0 8px;width:8px;height:8px;
  border-radius:50%;margin-top:5px}
.empc-ri.risk{background:var(--accent-red)}.empc-ri.warn{background:var(--accent-yellow)}.empc-ri.navy{background:var(--accent)}
.empc-rk .empc-rt{font-size:var(--fs-meta)}.empc-rk b{display:block;color:var(--text-primary)}
.ros-click{cursor:pointer}
</style>
<script>
function empcOpen(el){var id=el&&el.getAttribute('data-empc');var m=id&&document.getElementById(id);
  if(m){m.classList.add('open');document.body.style.overflow='hidden';}}
function empcClose(id){var m=document.getElementById(id);if(m){m.classList.remove('open');}
  document.body.style.overflow='';}
function empcBack(ev){if(ev.target&&ev.target.classList.contains('empc-backdrop')){
  ev.target.classList.remove('open');document.body.style.overflow='';}}
document.addEventListener('keydown',function(ev){if(ev.key==='Escape'){
  var o=document.querySelector('.empc-backdrop.open');if(o){o.classList.remove('open');document.body.style.overflow='';}}});
</script>
"""


def _re_sub_id(s):
    """Slug an employee id/name into a DOM-safe modal id fragment."""
    import re as _re
    return _re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-') or 'x'


# ── TK/K PTKP category → Indonesian TER monthly table (A/B/C). Drives the
#    "PTKP → TER table" line on the employee card. Resident PPh 21 only.
#    DISPLAY-ONLY mirror of `jurisdictions/id/ter.yaml → ptkp.ter_category` (the
#    statutory source the runtime computes from; there is no Python PPh calculator —
#    see the ter.yaml header). Keep this map in sync with that file if it changes.
_PTKP_TER_TABLE = {
    'TK/0': 'A', 'TK/1': 'A', 'K/0': 'A',
    'TK/2': 'B', 'TK/3': 'B', 'K/1': 'B', 'K/2': 'B',
    'K/3': 'C',
}


def _employee_card_modal(mid, e, runs, etasks, risks, fin, today, client_id='', client_name=''):
    """Large employee card modal — a fully DERIVED entity-linking view (no new state):
    roster record (e) + payroll run history (runs, by employee_id) + linked tasks
    (etasks, by refs/lines) + risks. All operator-facing text routes through _t()
    so this engine file stays Cyrillic-free (RU lives in _strings.py)."""
    import json
    name = str(e.get('name') or e.get('id') or '?')
    words = [w for w in name.split() if w]
    av = (''.join(w[0] for w in words[:2]) or '?').upper()
    cur = (fin or {}).get('currency') or 'Rp'
    fw = e.get('foreign_national') is True
    res = e.get('tax_residency')
    method = e.get('pph_method')
    # fall back to the method recorded on the latest run line
    if method is None and runs:
        method = (runs[-1][1] or {}).get('method')
    ptkp = e.get('ptkp_category')
    bpjs = e.get('bpjs') or {}

    def _days(d):
        dd = _parse_iso_date(d)
        return None if dd is None else (dd - today).days

    # ── header tags
    tags = []
    if fw:
        tags.append('<span class="empc-tag flag">' + _esc(_t('foreign worker')) + '</span>')
    if res in ('id', 'resident'):
        tags.append('<span class="empc-tag">' + _esc(_t('resident')) + ' · ID</span>')
    elif res in ('non_id', 'non-resident'):
        tags.append('<span class="empc-tag">' + _esc(_t('non-resident')) + '</span>')
    if ptkp:
        tags.append('<span class="empc-tag">PTKP ' + _esc(str(ptkp)) + '</span>')
    if fw:
        tags.append('<span class="empc-tag gold">' + _esc(_t('salary below expat floor')) + '</span>')

    nid = str(e.get('id') or '')
    # ── Action row: the unified «Разобрать» (prompt modal) + quick-action / decision
    #    buttons. Decisions are surfaced from the linked tasks' assist.actions plus a
    #    few derived from the employee's live state (BPJS gap, permit, parity).
    _ctx = ((_t('Client') + ': ' + client_name + ' · ') if client_name else '') \
        + _t('Employee') + ': ' + name + (' (' + nid + ')' if nid else '')
    review_btn = render_action_buttons(
        'employee', nid, name,
        _t('Review this employee: compute PPh 21 and BPJS for the open period, '
           'reconcile parity with the incumbent, and check BPJS coverage and the work permit.'),
        _ctx)

    def _qa(label, prompt, rec=False):
        cls = 'tm-btn tm-btn-sm' + (' tm-btn-primary' if rec else ' tm-btn-outline')
        return ('<button class="' + cls + '" type="button" data-prompt="' + _esca(prompt)
                + '" data-prompt-ctx="' + _esca(_ctx) + '" '
                "onclick=\"event.stopPropagation();if(window.openPromptModal)window.openPromptModal("
                "this.dataset.prompt,{ctx:this.getAttribute('data-prompt-ctx')||''});\">"
                + _esc(label) + '</button>')

    quick = []
    seen_labels = set()
    # decisions the runtime already proposed on the linked tasks (assist.actions)
    for tk in etasks:
        for a in ((tk.get('assist') or {}).get('actions') or []):
            lab = str(a.get('label') or '').strip()
            pr = str(a.get('prompt') or '').strip()
            if lab and pr and lab.lower() not in seen_labels:
                seen_labels.add(lab.lower())
                quick.append(_qa(lab, pr, rec=bool(a.get('recommended'))))
    # derived decisions from live state (roster status OR a billing-line gap)
    _kes = str((bpjs.get('kesehatan'))).lower()
    _ket = str((bpjs.get('ketenagakerjaan'))).lower()
    _last_bp = (runs[-1][1].get('bpjs') if runs else {}) or {}
    _line_kes = _last_bp.get('kesehatan')
    _line_ket = _last_bp.get('ketenagakerjaan')
    _line_gap = (_line_ket is None
                 or (isinstance(_line_kes, dict) and not (_line_kes.get('employee') or _line_kes.get('employer'))))
    if _kes == 'missing' or _ket in ('missing', 'none', 'null') or _line_gap:
        quick.append(_qa(_t('Close BPJS gap'),
                         _t('Register this employee in the missing BPJS kasse(s) before the next billing, then reconcile coverage.')))
    if fw:
        quick.append(_qa(_t('Check work permit'),
                         _t("Check this foreign worker's permit (KITAS/RPTKA): expiry, DPKK levy and the expat salary floor; plan the renewal.")))
    if any(str((r[1].get('parity_status') or '')).lower() in ('pending', 'mismatch') for r in runs):
        quick.append(_qa(_t('Resolve parity gap'),
                         _t('Investigate the parity gap with the incumbent (likely THR) for this employee and close it.')))
    action_html = review_btn + ''.join(quick[:5])

    # ── "How we calculate" rows
    rows = []

    def _row(k, v, note=''):
        g = (' <span class="empc-gloss">· ' + _esc(note) + '</span>') if note else ''
        rows.append('<div class="empc-row"><div class="empc-k">' + k
                    + '</div><div class="empc-v">' + v + g + '</div></div>')

    if res in ('id', 'resident'):
        _row(_t('Income tax'),
             _esc(_t('resident')) + ' <b class="empc-arrow">→</b> <b>PPh 21</b>'
             + '<span class="empc-pill ok">' + _esc(_t('not PPh 26')) + '</span>')
    elif res in ('non_id', 'non-resident'):
        _row(_t('Income tax'),
             _esc(_t('non-resident')) + ' <b class="empc-arrow">→</b> <b>PPh 26</b> '
             + '<span class="empc-code">' + _esc(_t('flat 20%, no PTKP')) + '</span>')
    else:
        _row(_t('Income tax'), '<span class="empc-pill warn">' + _esc(_t('residency: unknown')) + '</span>')

    # PTKP — lead with the plain meaning; the code (TK/0 · group A) is a muted reference.
    if ptkp:
        cat = str(ptkp)
        cu = cat.upper()
        marital = _t('not married') if cu.startswith('TK') else (_t('married') if cu.startswith('K') else '')
        try:
            ndep = int(cat.split('/')[1])
        except Exception:
            ndep = None
        deps = ('' if ndep is None else (_t('no dependents') if ndep == 0 else _t('dependents') + ': ' + str(ndep)))
        human = ', '.join([x for x in (marital, deps) if x])
        letter = _PTKP_TER_TABLE.get(cat)
        code = cat + (' · ' + _t('group') + ' ' + letter if letter else '')
        v = (('<b>' + _esc(human) + '</b> ') if human else '') + '<span class="empc-code">' + _esc(code) + '</span>'
        _row(_t('Family status'), v)

    # method — meaning first, code (TER / annualisasi) demoted
    if method == 'annualisasi':
        mv = '<b>' + _esc(_t('annual recalculation')) + '</b> <span class="empc-code">annualisasi · 1721-A1</span>'
    elif method == 'ter':
        mv = '<b>' + _esc(_t('flat monthly rate')) + '</b> <span class="empc-code">TER</span>'
    elif method in ('pph26', 'PPh26'):
        mv = '<b>PPh 26</b>'
    elif method is None:
        mv = '<span class="empc-pill warn">' + _esc(_t('method not set')) + '</span>'
    else:
        mv = '<b>' + _esc(str(method)) + '</b>'
    if fw and method == 'ter':
        mv += '<span class="empc-pill warn">' + _esc(_t('→ use annualisasi')) + '</span>'
    _row(_t('Method'), mv)

    # rate + monthly PPh range from runs
    pphs = [r[1].get('pph') for r in runs if isinstance(r[1].get('pph'), (int, float)) and r[1].get('pph')]
    last_rate = (runs[-1][1].get('ter_rate') if runs else None)
    rate_bits = []
    if isinstance(last_rate, (int, float)) and last_rate:
        rate_bits.append('≈ <b>' + ('{:.2f}'.format(last_rate * 100).rstrip('0').rstrip('.')) + '%</b> ' + _esc(_t('of salary')))
    if pphs:
        lo, hi = min(pphs), max(pphs)
        rng = _kpi_num(lo) if lo == hi else (_kpi_num(lo) + '–' + _kpi_num(hi))
        rate_bits.append('<b class="empc-arrow">→</b> ' + rng + ' ' + _esc(cur) + '/' + _esc(_t('mo')))
    if rate_bits:
        _row(_t('PPh 21 rate'), ' '.join(rate_bits))

    def _status_pill(level, text, do=''):
        s = '<span class="empc-pill ' + level + '">' + _esc(text) + '</span>'
        if do:
            s += ' <span class="empc-do">→ ' + _esc(do) + '</span>'
        return s

    # BPJS Kesehatan — Russian label leads (Медстраховка), BPJS code demoted, amount + status.
    kes = bpjs.get('kesehatan')
    kes_line = runs[-1][1].get('bpjs', {}).get('kesehatan') if runs else None
    kesv = '<span class="empc-code">BPJS Kesehatan</span> '
    if isinstance(kes_line, dict):
        kesv += (_esc(_t('employee')) + ' ' + _kpi_num(kes_line.get('employee') or 0)
                 + ' / ' + _esc(_t('employer')) + ' ' + _kpi_num(kes_line.get('employer') or 0) + ' ')
    _kes_gap = str(kes).lower() == 'missing' or (isinstance(kes_line, dict) and not (kes_line.get('employee') or kes_line.get('employer')))
    if _kes_gap:
        kesv += _status_pill('risk', _t('not in billing'), _t('register before next billing'))
    elif str(kes).lower() in ('active', 'exempt'):
        kesv += _status_pill('ok', _t('enrolled'))
    else:
        kesv += _status_pill('muted', _t('unconfirmed'), _t('verify enrolment'))
    _row(_t('health insurance'), kesv)

    # BPJS Ketenagakerjaan — Соцстрах
    ket = bpjs.get('ketenagakerjaan')
    ket_line = runs[-1][1].get('bpjs', {}).get('ketenagakerjaan') if runs else None
    ketv = '<span class="empc-code">BPJS Ketenagakerjaan</span> '
    if isinstance(ket_line, dict):
        ketv += (_esc(_t('employee')) + ' ' + _kpi_num(ket_line.get('employee') or 0)
                 + ' / ' + _esc(_t('employer')) + ' ' + _kpi_num(ket_line.get('employer') or 0) + ' ')
    if ket_line is None or str(ket).lower() in ('missing', 'none', 'null'):
        ketv += _status_pill('risk', _t('not in billing'), _t('register before next billing'))
    elif str(ket).lower() in ('active', 'exempt'):
        ketv += _status_pill('ok', _t('enrolled'))
    else:
        ketv += _status_pill('muted', _t('unconfirmed'), _t('verify enrolment'))
    _row(_t('social security'), ketv)

    # foreign-worker documents — Russian labels, codes demoted
    if fw:
        permit = e.get('permit') or {}
        nd = None
        for pk in ('kitas_expires', 'rptka_expires'):
            dl = _days(permit.get(pk))
            if dl is not None:
                nd = dl if nd is None else min(nd, dl)
        kdate = permit.get('kitas_expires') or permit.get('rptka_expires')
        pv = '<span class="empc-code">KITAS / e-ITAS</span> '
        if kdate:
            pv += _esc(_t('permit to')) + ' <b>' + _esc(str(kdate)) + '</b>'
            if nd is not None:
                cls = 'risk' if nd < 0 else ('warn' if nd <= 90 else 'ok')
                do = (_t('renew now') if nd < 0 else (_t('plan renewal') if nd <= 90 else ''))
                pv += _status_pill(cls, str(nd) + ' ' + _t('days'), do)
        else:
            pv += _status_pill('muted', _t('permit unconfirmed'), _t('clarify expiry'))
        _row(_t('Work permit'), pv)
        _row(_t('levy for a foreign worker'),
             '<span class="empc-code">DPKK · ~$100/' + _esc(_t('mo')) + '</span> '
             + (_status_pill('ok', _t('paid')) if permit.get('dpkk_paid')
                else _status_pill('muted', _t('unconfirmed'), _t('confirm payment'))))
        _row(_t('Expat threshold'),
             _esc(_t('salary below expat floor — verify at permit renewal')))

    calc_html = '<div class="empc-calc">' + ''.join(rows) + '</div>'

    # ── monthly runs table — each row opens its underlying payroll task (canonical
    #    track modal) via the global .track-card-clickable[data-track-id] handler.
    try:
        from _track_attrs import build_track_data_attrs as _btda
    except Exception:
        _btda = None
    mtable = ''
    if runs:
        trs = []
        tg = tt = tp = tn = 0
        for period, ln, tk in runs:
            g = ln.get('gross') or 0
            thr = ln.get('thr') or 0
            pph = ln.get('pph') or 0
            kl = ln.get('bpjs', {}).get('kesehatan') or {}
            ke = (kl.get('employer') if isinstance(kl, dict) else 0) or 0
            net = ln.get('net') or 0
            tg += g; tt += thr; tp += pph; tn += net
            par = str(ln.get('parity_status') or '').lower()
            chip = ''
            if par:
                pc = 'ok' if par in ('pass', 'ok', 'reconciled') else 'pend'
                lbl = _t('reconciled') if pc == 'ok' else _t('to review')
                chip = '<span class="empc-chip ' + pc + '">' + _esc(lbl) + '</span>'
            attrs = ''
            cls = ''
            if _btda and isinstance(tk, dict) and tk.get('id'):
                try:
                    attrs = _btda(dict(tk, client_id=(tk.get('client_id') or client_id)), _esca, today=today)
                    cls = ' class="empc-link track-card-clickable"'
                except Exception:
                    attrs = ''
            first = ('<span class="empc-tcell">' + _esc(str(period or ''))
                     + ('<span class="empc-go">›</span>' if attrs else '') + '</span>')
            trs.append('<tr' + cls + attrs + '><td>' + first + '</td><td>' + _kpi_num(g)
                       + '</td><td>' + _kpi_num(thr) + '</td><td>' + _kpi_num(pph)
                       + '</td><td>' + _kpi_num(ke) + '</td><td>' + _kpi_num(net)
                       + '</td><td>' + chip + '</td></tr>')
        foot = ('<tr><td>Σ ' + _esc(_t('lines')) + '</td><td>' + _kpi_num(tg) + '</td><td>'
                + _kpi_num(tt) + '</td><td>' + _kpi_num(tp) + '</td><td></td><td>'
                + _kpi_num(tn) + '</td><td></td></tr>')
        mtable = (
            '<table class="empc-tbl"><thead><tr><th>' + _esc(_t('Period')) + '</th><th>'
            + _esc(_t('Gross')) + '</th><th>THR</th><th>PPh 21</th><th>BPJS Kes.</th><th>'
            + _esc(_t('Net')) + '</th><th>' + _esc(_t('parity vs incumbent')) + '</th></tr></thead>'
            + '<tbody>' + ''.join(trs) + '</tbody><tfoot>' + foot + '</tfoot></table>'
            + '<div class="empc-annual">' + _esc(_t('annual 1721-A1 = sum of run lines for the year')) + '</div>')
    else:
        mtable = '<div class="empc-empty">' + _esc(_t('no payroll runs yet')) + '</div>'

    # ── linked tasks — each row opens the canonical track modal (clickable).
    tlist = []
    for tk in etasks:
        per = (tk.get('type_specific') or {}).get('period')
        sub = []
        if per:
            sub.append(str(per))
        st = tk.get('status')
        if st:
            sub.append(str(st))
        due = tk.get('due_date')
        if due:
            sub.append(_t('due') + ' ' + str(due))
        attrs = ''
        cls = 'empc-link-row'
        go = ''
        if _btda and isinstance(tk, dict) and tk.get('id'):
            try:
                attrs = _btda(dict(tk, client_id=(tk.get('client_id') or client_id)), _esca, today=today)
                cls += ' track-card-clickable'
                go = '<span class="empc-go">›</span>'
            except Exception:
                attrs = ''
        tlist.append('<div class="' + cls + '"' + attrs + '><div class="empc-lr-main">'
                     + '<div class="empc-tt">' + _esc(str(tk.get('title') or tk.get('id') or ''))
                     + '</div><div class="empc-tm">' + _esc(' · '.join(sub)) + '</div></div>'
                     + go + '</div>')
    tasks_html = ('<div class="empc-card"><p class="empc-ttl">' + _esc(_t('Tasks for employee'))
                  + '</p>' + (''.join(tlist) or '<div class="empc-empty">—</div>') + '</div>')

    # ── risk zones — rendered with the SAME DS component as the client card's
    #    «⚠️ Client risks» (collapsible .risk-card with the severity edge), so the
    #    employee risks read identically. Sources: real risk rows from risks.json
    #    that mention this employee (entity-linked) + standing derived lenses.
    _emp_risks = []
    for r in (risks or []):
        if not isinstance(r, dict):
            continue
        if str(r.get('severity') or '').lower() == 'green':
            continue
        blob = json.dumps(r, ensure_ascii=False).lower()
        if (nid and nid in blob) or (name and name.lower() in blob):
            # title fallback so summary/name variants still render a heading
            r = dict(r, title=str(r.get('title') or r.get('summary') or r.get('name') or ''))
            _emp_risks.append(r)
    # standing derived lenses → synthetic risk dicts fed to the SAME card component
    _bpjs_risk = (_line_gap or str(bpjs.get('ketenagakerjaan')).lower() in ('missing', 'none', 'null')
                  or str(kes).lower() == 'missing')
    if _bpjs_risk:
        _emp_risks.append({'severity': 'red', 'title': _t('BPJS gap'),
                           'next_action': _t('not in billing') + '. ' + _t('BPJS gap detail')})
    if fw:
        _emp_risks.append({'severity': 'yellow', 'title': _t('Expat threshold'),
                           'next_action': _t('salary below expat floor') + '. ' + _t('expat threshold detail')})
        _emp_risks.append({'severity': 'grey', 'title': _t('cross-border zone'),
                           'next_action': _t("employee's personal zone — company does not file") + '. ' + _t('cross-border detail')})
    risk_cards = [_render_risk_card(r, None, client_id, today, client_name) for r in _emp_risks]
    risks_html = ('<div class="empc-sec"><div class="empc-seclabel">' + _esc(_t('Risk zones')) + '</div>'
                  + ('<section class="risks-grid">' + ''.join(risk_cards) + '</section>'
                     if risk_cards else '<div class="empc-empty">—</div>') + '</div>')

    # ── assemble modal
    return (
        '<div class="empc-backdrop" id="' + _esc(mid) + '" onclick="empcBack(event)">'
        + '<div class="empc-modal" role="dialog" aria-modal="true">'
        + '<button class="empc-x" onclick="empcClose(\'' + _esc(mid) + '\')" aria-label="'
        + _esc(_t('Close')) + '">×</button>'
        + '<div class="empc-body">'
        # breadcrumb + title scroll together (mirrors the track modal — only the
        # footer is sticky); client now lives in the breadcrumb, not the subtitle
        + (('<a class="tm-bc-link empc-bc" href="dashboard_' + _esc(client_id) + '.html">← '
            + _esc(client_name) + '</a>') if (client_id and client_name) else '')
        + '<h2 class="empc-name">' + _esc(name) + '</h2>'
        + '<div class="empc-sub">'
        + _esc(str(e.get('position') or ''))
        + (' <span class="empc-id">' + _esc(nid) + '</span>' if nid else '')
        + '</div>'
        + '<div class="empc-tags">' + ''.join(tags) + '</div>'
        + '<div class="empc-card">' + calc_html + '</div>'
        + risks_html
        + tasks_html
        + '<div class="empc-card"><p class="empc-ttl">' + _esc(_t('Monthly — payroll runs')) + '</p>' + mtable
        + '<div class="empc-note">' + _esc(_t('All amounts in')) + ' ' + _esc(cur)
        + ' · ' + _esc(_t('derived view — no new state')) + '</div></div>'
        + '</div>'  # /empc-body
        + '<div class="empc-foot">' + action_html + '</div>'
        + '</div></div>'
    )


def render_client_payroll_roster(payroll, fin=None, tasks=None, risks=None, client_id='', client_name=''):
    """👥 Payroll roster — from state/payroll.json (employee slot, migration 0019).
    One row per employee: BPJS coverage (two kasses), tax residency + PPh method, and
    (foreign workers) the permit-expiry countdown. Renders only for a non-empty roster,
    so a non-payroll client shows nothing (additive). Severities mirror state_lint H3.

    Each row is clickable → opens the employee card modal: a fully DERIVED entity-linking
    view (no new state) that joins the roster record + payroll run lines (by employee_id)
    + linked tasks (by refs/lines) + risks. See _employee_card_modal.
    """
    if not payroll:
        return ''
    employees = payroll.get('employees') or []
    if not employees:
        return ''
    # Entity-link: build per-employee run history (by employee_id) and linked tasks
    # (by payroll_lines or type_specific.refs of type 'employee'). Derived, read-only.
    _runs = {}   # emp_id -> [(period, line, task)]
    _etasks = {} # emp_id -> [task]
    for _tk in (tasks or []):
        if not isinstance(_tk, dict):
            continue
        _sp = _tk.get('type_specific') or {}
        _matched = set()
        for _ln in (_sp.get('payroll_lines') or []):
            _eid = _ln.get('employee_id')
            if _eid:
                _runs.setdefault(_eid, []).append((_sp.get('period'), _ln, _tk))
                _matched.add(_eid)
        for _rf in (_sp.get('refs') or []):
            if isinstance(_rf, dict) and _rf.get('type') == 'employee' and _rf.get('id'):
                _matched.add(_rf.get('id'))
        for _eid in _matched:
            _etasks.setdefault(_eid, []).append(_tk)
    for _eid in _runs:
        _runs[_eid].sort(key=lambda r: str(r[0] or ''))
    try:
        import generate as _gen
        _today = _gen.TODAY
    except Exception:
        from datetime import date as _d
        _today = _d.today()

    def _pill(label, status):
        st = (str(status).lower() if status is not None else 'null')
        cls = {'active': 'ros-ok', 'exempt': 'ros-neutral',
               'missing': 'ros-bad'}.get(st, 'ros-warn')  # null/unknown -> warn
        txt = {'active': _t('ok'), 'exempt': _t('exempt'),
               'missing': _t('missing')}.get(st, _t('unconfirmed'))
        return ('<span class="ros-pill ' + cls + '">' + _esc(str(label)) + ': '
                + _esc(txt) + '</span>')

    def _days(d):
        dd = _parse_iso_date(d)
        if dd is None:
            return None
        return (dd - _today).days

    def _sev(e):
        """Worst severity for an employee row — 0 red (act now), 1 amber (verify),
        2 green (covered). Mirrors state_lint H3 so the card and the lint agree."""
        bpjs = e.get('bpjs') or {}
        red = amber = False
        for v in (str(bpjs.get('kesehatan')).lower(), str(bpjs.get('ketenagakerjaan')).lower()):
            if v == 'missing':
                red = True
            elif v not in ('active', 'exempt'):
                amber = True  # null / unknown -> unconfirmed
        fw = e.get('foreign_national') is True
        res, method = e.get('tax_residency'), e.get('pph_method')
        if res == 'non_id' and method not in (None, 'pph26'):
            red = True
        if fw and method == 'ter':
            amber = True
        if fw:
            permit = e.get('permit') or {}
            nd = None
            for pk in ('kitas_expires', 'rptka_expires'):
                dl = _days(permit.get(pk))
                if dl is not None:
                    nd = dl if nd is None else min(nd, dl)
            if nd is None:
                amber = True       # foreign worker, no permit date -> unverified
            elif nd < 0:
                red = True
            elif nd <= 90:
                amber = True
        return 0 if red else (1 if amber else 2)

    def _chip(e):
        """ONE chip per employee — the worst thing about them, else 'both contributions'.
        Keeps each row to a single line (the mockup look) instead of two verbose pills."""
        bpjs = e.get('bpjs') or {}
        kk = [str(bpjs.get('kesehatan')).lower(), str(bpjs.get('ketenagakerjaan')).lower()]
        fw = e.get('foreign_national') is True
        res, method = e.get('tax_residency'), e.get('pph_method')
        if 'missing' in kk:
            return 'bad', _t('no BPJS — enrol')
        if res == 'non_id' and method not in (None, 'pph26'):
            return 'bad', _t('PPh: check method')
        if fw:
            permit = e.get('permit') or {}
            nd = None
            for pk in ('kitas_expires', 'rptka_expires'):
                dl = _days(permit.get(pk))
                if dl is not None:
                    nd = dl if nd is None else min(nd, dl)
            if nd is not None and nd < 0:
                return 'bad', _t('permit expired')
            if nd is not None and nd <= 90:
                return 'warn', _t('permit') + ' · ' + str(nd) + ' ' + _t('days')
            if nd is None:
                return 'warn', _t('permit unconfirmed')
        if any(v not in ('active', 'exempt') for v in kk):
            return 'warn', _t('BPJS unconfirmed')
        if fw and method == 'ter':
            return 'warn', _t('→ use annualisasi')
        return 'ok', _t('both contributions')

    # Severity-sort worst-first, then render one tight row per employee.
    n_red = n_amber = 0
    enriched = []
    for e in employees:
        if not isinstance(e, dict):
            continue
        s = _sev(e)
        n_red += (s == 0)
        n_amber += (s == 1)
        enriched.append((s, str(e.get('name') or e.get('id') or '?'), e))
    enriched.sort(key=lambda t: (t[0], t[1].lower()))

    def _av_tint(txt):
        h = 0
        for ch in str(txt):
            h = (h * 31 + ord(ch)) & 0xffffffff
        hue = h % 360
        return 'background:hsl(%d 52%% 93%%);color:hsl(%d 42%% 34%%)' % (hue, hue)

    _N_VIS = 6
    def _val(v):
        return ('<div class="ros-val">' + (_kpi_num(v) if isinstance(v, (int, float)) and v
                else '<span class="ros-dash">—</span>') + '</div>')

    tot_g = tot_p = tot_kes = tot_ket = 0
    tperiod = ''

    def _bsum(d):
        return ((d.get('employee') or 0) + (d.get('employer') or 0)) if isinstance(d, dict) else None
    rows = []
    modals = []
    hidden_count = 0
    for idx, (s, name, e) in enumerate(enriched):
        words = [w for w in str(name).split() if w]
        av = (''.join(w[0] for w in words[:2]) or '?').upper()
        tag = ((' <span class="ros-tag">' + _esc(_t('foreign worker')) + '</span>')
               if e.get('foreign_national') is True else '')
        ck, ctxt = _chip(e)
        # Status pill only when there's something to act on; a fully covered employee
        # stays quiet (no repetitive green chip) — Linear/Asana restraint.
        chip_html = ('<span class="ros-pill ros-' + ck + ' ros-chip">' + _esc(ctxt) + '</span>') if ck != 'ok' else ''
        rail = '' if s == 2 else (' ros-rail-bad' if s == 0 else ' ros-rail-warn')
        # Collapse the long tail: keep the first N + every flagged row visible, hide the
        # rest behind a «show all» toggle (a clean roster never needs a 14-row wall).
        hide = idx >= _N_VIS and s == 2
        if hide:
            hidden_count += 1
        eid = str(e.get('id') or '')
        mid = 'empc-' + _re_sub_id(eid or name)

        # Money (оклад/PPh/на руки) from the latest run line + tax profile (метод, PTKP).
        # The column header carries the labels + per-column totals; rows are bare values.
        _rr = _runs.get(eid, [])
        ln = _rr[-1][1] if _rr else {}
        if _rr and _rr[-1][0]:
            tperiod = _rr[-1][0]

        method = e.get('pph_method') or (ln.get('method') if isinstance(ln, dict) else None)
        mlabel = {'ter': 'TER', 'annualisasi': 'annualisasi', 'pph26': 'PPh 26'}.get(str(method), '—' if method is None else str(method))
        mcls = 'ros-mchip' + (' ros-mchip-flag' if (e.get('foreign_national') is True and method == 'ter') else '')
        tax = '<span class="' + mcls + '">' + _esc(mlabel) + '</span>'
        if e.get('ptkp_category'):
            tax += '<span class="ros-pchip">' + _esc(str(e.get('ptkp_category'))) + '</span>'
        if chip_html:
            tax += chip_html
        _bp = ln.get('bpjs') if isinstance(ln, dict) else None
        _g = ln.get('gross') if isinstance(ln, dict) else None
        _p = ln.get('pph') if isinstance(ln, dict) else None
        _kes = _bsum((_bp or {}).get('kesehatan')) if isinstance(_bp, dict) else None
        _ket = _bsum((_bp or {}).get('ketenagakerjaan')) if isinstance(_bp, dict) else None
        if isinstance(_g, (int, float)): tot_g += _g
        if isinstance(_p, (int, float)): tot_p += _p
        if isinstance(_kes, (int, float)): tot_kes += _kes
        if isinstance(_ket, (int, float)): tot_ket += _ket

        rows.append(
            '<div class="ros-row ros-click' + rail + (' ros-hidden' if hide else '') + '" role="button" tabindex="0"'
            + ' data-empc="' + _esc(mid) + '" onclick="empcOpen(this)"'
            + ' onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();empcOpen(this);}">'
            + '<span class="ros-av" style="' + _av_tint(name) + '">' + _esc(av) + '</span>'
            + '<div class="ros-id"><div class="ros-name-row"><span class="ros-name">' + _esc(name) + '</span>' + tag + tax
            + '</div><div class="ros-pos">' + _esc(str(e.get('position') or '')) + '</div></div>'
            + _val(_g) + _val(_p) + _val(_kes) + _val(_ket)
            + '<span class="ros-chev">›</span>'
            + '</div>'
        )
        modals.append(_employee_card_modal(
            mid, e, _runs.get(eid, []), _etasks.get(eid, []),
            risks or [], fin, _today, client_id=client_id, client_name=client_name))

    # Coverage roll-up (shown muted in the totals lead).
    if n_red:
        summ = '<span class="ros-sum-bad">' + str(n_red) + ' ' + _esc(_t('no coverage')) + '</span>'
    elif n_amber:
        summ = '<span class="ros-sum-warn">' + str(n_amber) + ' ' + _esc(_t('to verify')) + '</span>'
    else:
        summ = '<span class="ros-sum-ok">' + _esc(_t('all covered')) + '</span>'

    cur = (fin or {}).get('currency') or 'Rp'

    def _tot(label, v):
        return ('<div class="ros-stat"><span class="ros-stat-l">' + _esc(label)
                + '</span><span class="ros-stat-v">' + (_kpi_num(v) if v else '—') + '</span></div>')

    # Borderless header row ABOVE the card: section title (left, flush, h2 size) + grey
    # salary-period suffix + per-column Σ aligned to the money columns in the rows below.
    header_row = (
        '<div class="ros-totals">'
        + '<div class="ros-id"><div class="ros-tot-lead">'
        + '<h2 class="ros-tot-title">' + _esc(_t('Payroll roster')) + ' ' + str(len(employees)) + '</h2>'
        + ((' <span class="ros-tot-per">' + _esc(_t('for period')) + ' ' + _esc(str(tperiod)) + '</span>') if tperiod else '')
        + '</div></div>'
        + _tot(_t('Gross'), tot_g) + _tot('PPh 21', tot_p)
        + _tot('BPJS Kes.', tot_kes) + _tot('BPJS Ket.', tot_ket)
        + '<span class="ros-chev"></span></div>')

    section_html = '<section class="ros-section">' + ''.join(rows) + '</section>'
    if hidden_count:
        section_html = (
            '<div class="ros-wrap">' + section_html
            + '<button class="ros-more" type="button" onclick="rosToggle(this)"'
            + ' data-more="' + _esca(_t('Show all') + ' (' + str(hidden_count) + ')')
            + '" data-less="' + _esca(_t('Collapse')) + '">'
            + _esc(_t('Show all')) + ' (' + str(hidden_count) + ')</button></div>'
            + '<script>function rosToggle(b){var w=b.closest(".ros-wrap");var s=w&&w.querySelector(".ros-section");'
              'if(!s)return;var on=s.classList.toggle("ros-expanded");'
              'b.textContent=on?b.getAttribute("data-less"):b.getAttribute("data-more");}</script>')
    return (
        _EMPC_ASSETS
        + header_row
        + section_html
        + ''.join(modals)
    )


def render_client_behavior(beh):
    """🗣 Client communication style — from state/behavior.json. UX-fix #6, 2026-05-25.
    Human-readable mapping of technical values: 2026-05-25.
    """
    if not beh:
        return ''
    comm = beh.get('communication') or {}
    channels = beh.get('channels') or {}
    if not (comm or channels):
        return ''

    # Dictionaries mapping technical values from state/behavior.json to display text
    _SPEED_RU = {
        'active_problem_solver': 'solves problems herself',
        'fast': 'fast',
        'fast_active': 'fast and active',
        'moderate_with_travel_delays': 'moderate (occasional pauses due to travel)',
        'passive': 'passive',
        'self_managing': 'self-managing',
        'slow': 'slow',
        'slow_polite': 'slow, polite',
        'slow_with_delays': 'slow, with delays',
        'technical_competent': 'technically competent',
        'variable': 'variable',
        'via_team_lead': 'via team lead',
    }
    _TONE_RU = {
        'formal_concise': 'formal, concise',
        'friendly': 'friendly',
        'friendly_curious': 'friendly, curious',
        'friendly_emoji': 'friendly, with emoji',
        'friendly_with_emoji': 'friendly, with emoji',
        'minimal': 'minimal',
        'minimal_via_team': 'minimal, via team',
        'polite': 'polite',
        'polite_thanks': 'polite, thankful',
        'polite_with_thanks': 'polite, thankful',
        'professional_active': 'professional and active',
        'professional_technical': 'professional, technical',
        'short_factual': 'short, factual',
        'via_team': 'via team',
    }
    _FORMALITY_RU = {
        'informal_ty': 'informal (ty)',
        'formal_vy': 'formal (vy)',
        'formal_team_distant': 'formal, via team',
        'neutral': 'neutral',
        'mixed': 'mixed',
    }
    _EMOJI_RU = {
        'frequent': 'frequent',
        'frequent_thanks': 'frequent (thanks)',
        'none': 'none',
        'occasional': 'occasional',
        'occasional_thank_you': 'occasional (thanks)',
        'rare': 'rare',
    }
    _CHANNEL_TYPE_RU = {
        'finkoper': 'Finkoper',
        'team_via_anastasia': 'team via assistant',
        'team_via_anastasia_and_representative': 'team via assistant and representative',
        'team_via_finkoper': 'team via Finkoper',
        'telegram': 'Telegram',
        'edo': 'EDO',
        'email': 'email',
        'phone': 'phone',
    }

    def _ru(d, v):
        return _t(d.get(v, v)) if v else v

    blocks = []

    # Channels
    primary = channels.get('primary') or {}
    secondary = channels.get('secondary') or []
    if primary or secondary:
        ch_bits = []
        if primary.get('id'):
            ptype = _ru(_CHANNEL_TYPE_RU, primary.get('type', ''))
            ch_bits.append('<span class="beh-ch-primary">📱 ' + _esc(ptype + ': ' + primary['id']) + '</span>')
        for s in secondary:
            if s.get('id'):
                stype = _ru(_CHANNEL_TYPE_RU, s.get('type', ''))
                ch_bits.append('<span class="beh-ch-secondary">' + _esc(stype + ': ' + s['id']) + '</span>')
        tz = channels.get('timezone')
        if tz:
            ch_bits.append('<span class="beh-tz">🌐 ' + _esc(tz) + '</span>')
        if ch_bits:
            blocks.append('<div class="beh-block">' + ''.join(ch_bits) + '</div>')

    # Style + speed
    style = comm.get('style') or {}
    speed = comm.get('response_speed') or {}
    parts = []
    if speed.get('level'):
        parts.append(_t('Speed:') + ' <b>' + _esc(_ru(_SPEED_RU, speed['level'])) + '</b>')
    if style.get('tone'):
        parts.append(_t('tone:') + ' ' + _esc(_ru(_TONE_RU, style['tone'])))
    if style.get('formality'):
        parts.append(_esc(_ru(_FORMALITY_RU, style['formality'])))
    if style.get('emoji_usage') and style['emoji_usage'] != 'none':
        parts.append(_t('emoji:') + ' ' + _esc(_ru(_EMOJI_RU, style['emoji_usage'])))
    if parts:
        blocks.append('<div class="beh-style">' + ' · '.join(parts) + '</div>')
    if speed.get('description'):
        blocks.append('<div class="beh-note">' + _esc(speed['description']) + '</div>')

    # Preferences
    prefs = comm.get('preferences') or {}
    likes = prefs.get('likes') or []
    dislikes = prefs.get('dislikes') or []
    asks = prefs.get('asks_for_pattern') or ''
    if likes or dislikes:
        pref_bits = []
        if likes:
            pref_bits.append('<div class="beh-likes">' + _t('likes:') + ' ' + _esc(', '.join(likes)) + '</div>')
        if dislikes:
            pref_bits.append('<div class="beh-dislikes">' + _t('dislikes:') + ' ' + _esc(', '.join(dislikes)) + '</div>')
        if asks:
            pref_bits.append('<div class="beh-asks">💭 ' + _esc(asks) + '</div>')
        blocks.append('<div class="beh-prefs">' + ''.join(pref_bits) + '</div>')

    notes_extra = beh.get('notes')
    if notes_extra:
        blocks.append('<div class="beh-note">' + _esc(notes_extra) + '</div>')

    return (
        '<div class="section-title"><h2>' + _t('🗣 Client communication style') + '</h2></div>'
        '<section class="beh-section">' + ''.join(blocks) + '</section>'
    )


# ============================================================
# 📊 KPI row — key metrics surfaced at the top of the client card.
# Jurisdiction-agnostic: turnover / taxes / headcount, read from
# state/financials.json (+ identity for headcount). Added 2026-06-25.
# All operator-facing labels go through _t() (i18n guard covers them).
# ============================================================
KPI_ROW_CSS = """
/* Metric band: flex so columns size to CONTENT and group left (no full-width
   grid stranding each number in empty space). The inline grid-template-columns
   the renderer emits is inert under flex. */
.kpi-row{display:flex;flex-wrap:wrap;gap:0;margin:0 0 var(--space-lg,20px);align-items:flex-start;}
.kpi-band .kpi-card{background:transparent;border:none;border-radius:0;box-shadow:none;padding:2px 26px;}
.kpi-band .kpi-card:first-child{padding-left:0;}
.kpi-band .kpi-card + .kpi-card{border-left:1px solid var(--border);}
.kpi-k{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--text-muted);font-weight:500;}
/* One uniform number size across all metrics — no lead/secondary mismatch. */
.kpi-val{font-size:22px;font-weight:600;letter-spacing:-.015em;color:var(--accent);margin-top:8px;font-variant-numeric:tabular-nums;white-space:nowrap;line-height:1.15;}
.kpi-val small{font-size:.5em;color:var(--gold);font-weight:600;vertical-align:.18em;margin-left:3px;letter-spacing:.01em;}
.kpi-sub{font-size:12.5px;color:var(--text-secondary);margin-top:10px;}
.kpi-delta{font-size:11px;font-weight:600;border-radius:20px;padding:2px 8px;}
.kpi-delta.up{color:var(--accent-green);background:var(--green-bg);}
.kpi-delta.down{color:var(--accent-red);background:var(--red-bg);}
.kpi-spark{display:flex;align-items:flex-end;gap:5px;height:24px;margin-top:12px;}
.kpi-spark i{width:9px;border-radius:2px;background:var(--border-strong);display:block;}
.kpi-spark i.c{background:var(--accent);}
/* Forward tier — flat, top hairline, gold diamond tick; same content-width band. */
.kpi-fwd-row{border-top:1px solid var(--border);margin-top:6px;padding-top:20px;}
.kpi-fwd-row .kpi-card{background:transparent;border:none;border-radius:0;box-shadow:none;position:relative;padding:0 44px 0 16px;}
.kpi-fwd-row .kpi-card::before{content:"";position:absolute;left:0;top:6px;width:7px;height:7px;background:var(--gold);border-radius:2px;transform:rotate(45deg);}
.kpi-fwd .kpi-val{font-size:19px;color:var(--text-primary);}
.kpi-chip{display:inline-block;font-size:11.5px;font-weight:500;color:var(--accent);background:var(--accent-soft);border-radius:20px;padding:2px 9px;margin-left:8px;vertical-align:middle;}
.kpi-chip.soon{color:var(--accent-red);background:var(--red-bg);}
@media(max-width:760px){.kpi-row{flex-direction:column;}
.kpi-band .kpi-card + .kpi-card,.kpi-fwd-row .kpi-card + .kpi-card{border-left:none;}
.kpi-band .kpi-card{padding:0 0 4px;}
.kpi-fwd-row .kpi-card{padding:10px 0 0 16px;}}
/* Context strip — KPIs demoted below the focus/tasks: quieter, smaller numbers. */
.ctx-strip{margin:0 0 var(--space-lg,20px);}
.ctx-label{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin:0 0 12px;}
.ctx-strip .kpi-val{font-size:19px;color:var(--text-secondary);}
.ctx-strip .kpi-val small{font-size:.6em;}
.ctx-strip .kpi-fwd-row{margin-top:14px;padding-top:16px;}
"""

_KPI_EN_MONTH = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May',
                 6: 'June', 7: 'July', 8: 'August', 9: 'September', 10: 'October',
                 11: 'November', 12: 'December'}
# Keys that live inside period.taxes but are NOT taxes (net payroll etc.) —
# excluded from the tax total. Mirrors the financials period-table convention.
_KPI_NON_TAX = ('payroll_net', 'payroll_net_idr', 'payroll_gross', 'headcount')


def _kpi_num(v):
    try:
        return '{:,.0f}'.format(float(v)).replace(',', ' ')
    except Exception:
        return str(v)


def _kpi_turnover(p):
    v = p.get('turnover_idr')
    if v is None:
        v = p.get('income_usn')
    if v is None:
        v = p.get('turnover')
    return v


def _kpi_tax_sum(p):
    total = 0.0
    for k, v in (p.get('taxes') or {}).items():
        if isinstance(v, bool):
            continue  # boolean meta-flags are not amounts
        if k in _KPI_NON_TAX:
            continue
        if isinstance(v, (int, float)):
            total += v
    return total


def _kpi_period_label(p):
    per = str(p.get('period', ''))
    if p.get('period_type') == 'month' and '-' in per:
        parts = per.split('-')
        try:
            return _t(_KPI_EN_MONTH[int(parts[1])])
        except Exception:
            return per
    return per


def _kpi_label_key(key):
    """Label for a YYYY-MM month key (-> month name); pass anything else through."""
    key = str(key)
    if '-' in key:
        parts = key.split('-')
        if len(parts) >= 2 and parts[1].isdigit():
            try:
                return _t(_KPI_EN_MONTH[int(parts[1])])
            except Exception:
                pass
    return key


def _kpi_monthly_points(periods):
    """Unified list of monthly data points {key, turnover, tax}, sorted by key.
    Sources: top-level period_type=='month' rows AND nested monthly breakdowns
    (e.g. AUSN clients keep months under period['ausn_monthly'][YYYY-MM])."""
    pts = []
    for p in periods:
        if p.get('period_type') == 'month':
            pts.append({'key': str(p.get('period', '')),
                        'turnover': _kpi_turnover(p), 'tax': _kpi_tax_sum(p)})
        nested = p.get('ausn_monthly') or p.get('monthly')
        if isinstance(nested, dict):
            for mk, entry in nested.items():
                if not isinstance(entry, dict):
                    continue
                tv = entry.get('income_base')
                if tv is None:
                    tv = entry.get('turnover')
                if tv is None:
                    tv = entry.get('income')
                tx = entry.get('tax_ausn')
                if tx is None:
                    tx = entry.get('tax')
                pts.append({'key': str(mk), 'turnover': tv, 'tax': tx or 0})
    pts.sort(key=lambda x: x['key'])
    return pts


def _kpi_quarter_points(periods):
    """Quarterly data points {key, turnover, tax} for clients that report by
    quarter (USN). Only quarters that actually carry a turnover figure are kept,
    so an empty current quarter never blanks the card or skews the trend."""
    pts = []
    for p in periods:
        if p.get('period_type') != 'quarter':
            continue
        tv = _kpi_turnover(p)
        if tv is None:
            continue
        pts.append({'key': str(p.get('period', '')),
                    'turnover': tv, 'tax': _kpi_tax_sum(p)})
    pts.sort(key=lambda x: x['key'])
    return pts


def _kpi_card(label, value_html, cur, sub_html, spark_html, extra_cls=''):
    val = ('<div class="kpi-val">' + value_html
           + ((' <small>' + _esc(cur) + '</small>') if cur else '') + '</div>')
    sub = ('<div class="kpi-sub">' + sub_html + '</div>') if sub_html else ''
    cls = 'kpi-card' + ((' ' + extra_cls) if extra_cls else '')
    return ('<div class="' + cls + '"><div class="kpi-k">' + _esc(label) + '</div>'
            + val + sub + (spark_html or '') + '</div>')


def _kpi_permit_chip(employees):
    """Nearest foreign-worker permit expiry across the roster -> a small chip for the
    headcount KPI. Red-ish if expired, amber within the 90-day window, else hidden.
    Reuses the existing .kpi-chip / .kpi-chip.soon style."""
    try:
        import generate as _gen
        today = _gen.TODAY
    except Exception:
        from datetime import date as _d
        today = _d.today()
    nearest = None
    for e in employees or []:
        if not isinstance(e, dict) or e.get('foreign_national') is not True:
            continue
        permit = e.get('permit') or {}
        for pk in ('kitas_expires', 'rptka_expires'):
            d = _parse_iso_date(permit.get(pk))
            if d is None:
                continue
            dl = (d - today).days
            nearest = dl if nearest is None else min(nearest, dl)
    if nearest is None:
        return ''
    if nearest < 0:
        return '<span class="kpi-chip soon">' + _esc(_t('permit expired')) + '</span>'
    if nearest <= 90:
        return ('<span class="kpi-chip soon">' + _esc(_t('renewal in')) + ' '
                + str(nearest) + ' ' + _esc(_t('days')) + '</span>')
    return ''


def render_kpi_row(fin, identity, jurisdiction='ru', payroll=None):
    """A compact 3-up KPI row: turnover / taxes / headcount. Cards appear only
    when their data exists, so it degrades gracefully across jurisdictions."""
    if not fin:
        return ''
    periods = fin.get('periods') or []
    if not periods:
        return ''
    try:
        import _jurisdiction as _J
        _auth = _J.load_jurisdiction(jurisdiction).authorities
    except Exception:
        _auth = {}
    cur = _auth.get('currency_symbol') or '₽'
    sp = sorted(periods, key=lambda p: str(p.get('period', '')))
    months = [p for p in sp if p.get('period_type') == 'month']
    last = months[-1] if months else sp[-1]
    cards = []

    # Trend points, finest granularity available: monthly (+ nested AUSN) first,
    # else quarterly. Keep only points that actually carry a turnover figure.
    points = [p for p in _kpi_monthly_points(periods) if p['turnover'] is not None]
    if not points:
        points = _kpi_quarter_points(periods)
    if points:
        lp = points[-1]
        pp = points[-2] if len(points) >= 2 else None
        tov = lp['turnover']
        tax = lp['tax']
        label = _kpi_label_key(lp['key'])
        prev_tov = pp['turnover'] if pp else None
        spark_vals = [(p['turnover'] or 0) for p in points[-5:]]
        n_pts = len(points)
    else:
        # Fallback: latest period that has a turnover figure (skip empty ones).
        with_tov = [p for p in sp if _kpi_turnover(p) is not None]
        base = with_tov[-1] if with_tov else last
        tov = _kpi_turnover(base)
        tax = _kpi_tax_sum(base)
        label = _kpi_period_label(base)
        prev_tov = None
        spark_vals = []
        n_pts = 0

    # 1) Turnover (+ MoM delta). No sparkline — Context is a clean uniform band.
    if tov is not None:
        delta = ''
        if prev_tov:
            d = (tov - prev_tov) / prev_tov * 100.0
            up = d >= 0
            delta = ('<span class="kpi-delta ' + ('up' if up else 'down') + '">'
                     + ('&#9650;' if up else '&#9660;') + ' '
                     + '{:.0f}'.format(abs(d)) + '%</span> ' + _esc(_t('vs prev.')))
        cards.append(_kpi_card(_t('Turnover') + ' · ' + label,
                               _kpi_num(tov), cur, delta, ''))

    # 2) Taxes for the period (clean total)
    if tax and tax > 0:
        cards.append(_kpi_card(_t('Taxes') + ' · ' + label,
                               _kpi_num(tax), cur, '', ''))

    # 3) Headcount / net payroll. Headcount derives from the roster when present
    #    (single source: payroll.json), else falls back to identity.headcount_payroll.
    _emps = (payroll or {}).get('employees') or []
    hc = len(_emps) if _emps else (identity or {}).get('headcount_payroll')
    if hc:
        sub = ''
        pn = (last.get('taxes') or {}).get('payroll_net')
        if pn:
            sub = _esc(_t('net payroll')) + ' ' + _kpi_num(pn) + ' ' + _esc(cur)
        _chip = _kpi_permit_chip(_emps)
        if _chip:
            sub = (sub + ' · ' if sub else '') + _chip
        cards.append(_kpi_card(_t('Headcount'),
                               _esc(str(hc)) + ' <small>' + _esc(_t('pers.')) + '</small>',
                               '', sub, ''))

    # 4) Annual pace + PKP-threshold headroom — lives in Context with the rest,
    #    so the whole strip is one uniform row (deadline moves up to the hero).
    yp = fin.get('yearly_pace_2026') or {}
    annual = (yp.get('estimated_annual_turnover_idr')
              or yp.get('estimated_annual_income') or yp.get('estimated_annual'))
    if annual:
        sub = ''
        thr = yp.get('pkp_threshold_idr')
        if thr:
            warn = bool(yp.get('pkp_warning'))
            key = 'approaching PKP threshold' if warn else 'under PKP threshold'
            sub = ('<span class="kpi-chip' + (' soon' if warn else '') + '">'
                   + _esc(_t(key)) + '</span> ' + _kpi_num(thr) + ' ' + _esc(cur))
        cards.append(_kpi_card(_t('Annual pace'), '~' + _kpi_num(annual), cur, sub, ''))

    if not cards:
        return ''
    cols = min(len(cards), 4)
    return ('<div class="kpi-row kpi-band" style="grid-template-columns:repeat('
            + str(cols) + ',minmax(0,1fr))">' + ''.join(cards) + '</div>')


_FWD_TERMINAL = ('paid', 'done', 'cancelled', 'auto_passed', 'sent')


def render_forward_strip(fin, jurisdiction='ru', today_iso=None):
    """Forward-looking companion to the KPI row: the nearest upcoming deadline
    (countdown) + the annual pace / threshold headroom. Reads the tax calendar
    and yearly_pace from state/financials.json. Cards appear only when data
    exists, so it degrades gracefully across jurisdictions."""
    if not fin:
        return ''
    from datetime import date
    if not today_iso:
        today_iso = date.today().isoformat()
    try:
        import _jurisdiction as _J
        _auth = _J.load_jurisdiction(jurisdiction).authorities
    except Exception:
        _auth = {}
    cur = _auth.get('currency_symbol') or '₽'
    cards = []

    # Card A — nearest upcoming deadline
    cal = fin.get('tax_calendar_2026') or []
    upcoming = sorted(
        [e for e in cal
         if str(e.get('date', '')) >= today_iso
         and (e.get('status') or '') not in _FWD_TERMINAL],
        key=lambda e: str(e.get('date', '')))
    if upcoming:
        ev = upcoming[0]
        d = str(ev.get('date', ''))
        try:
            n = (date.fromisoformat(d) - date.fromisoformat(today_iso)).days
        except Exception:
            n = None
        dd = (d[8:10] + '.' + d[5:7]) if len(d) >= 10 else d
        chip = ''
        if n is not None:
            soon = ' soon' if n <= 7 else ''
            chip = ('<span class="kpi-chip' + soon + '">'
                    + _esc(_t('in {} d.').format(n)) + '</span>')
        amt = ev.get('amount')
        sub = _esc((ev.get('what') or '')[:90])
        if amt:
            sub = _kpi_num(amt) + ' ' + _esc(cur) + ' · ' + sub
        cards.append('<div class="kpi-card kpi-fwd"><div class="kpi-k">'
                     + _esc(_t('Next deadline')) + '</div>'
                     '<div class="kpi-val">' + _esc(dd) + chip + '</div>'
                     '<div class="kpi-sub">' + sub + '</div></div>')

    # (Annual pace moved into the Context band in render_kpi_row.) This strip is
    # now the single nearest-deadline element, surfaced in the hero.
    if not cards:
        return ''
    return ('<div class="kpi-row kpi-fwd-row" style="grid-template-columns:repeat('
            + str(len(cards)) + ',minmax(0,1fr))">'
            + ''.join(cards) + '</div>')


def render_client_dashboard_v2(c, daemon_mail=None, daemon_anomalies=None):
    """Main function — client dashboard on top of mental_model."""
    import generate
    TODAY = generate.TODAY
    DIARY_INBOX = generate.DIARY_INBOX
    from _loaders import load_daemon_finkoper
    from _deadlines import collect_deadlines, collect_awaiting
    deadlines = collect_deadlines(TODAY)
    awaiting = collect_awaiting(TODAY)
    daemon_finkoper = load_daemon_finkoper(DIARY_INBOX, TODAY)

    mm = load_mental_models()
    # Analysis & recommendations zone — state-derived (no mental_model.md parsing).
    from _brief import (render_analysis_zone, render_client_questions,
                        build_client_analysis_from_state, ANALYSIS_CSS as _AN_CSS)
    import state_ops as _sop_an
    _an_data = build_client_analysis_from_state(c['id'], c.get('name_short'), _sop_an.state_read, TODAY)
    _an_zone = render_analysis_zone(_an_data, TODAY, last_change=None, esc=_esc, esca=_esca)
    _an_questions = render_client_questions(_an_data, esc=_esc)
    mm_client = _filter_mm_by_client(mm, c['id'])
    # by_client bundle (snapshot firm/in_progress/unclear, history, v2 sections) — all
    # assembled from state/*.json + history.jsonl inside load_mental_models().
    by_client = (mm.get('by_client') or {}).get(c['id'], {})
    snapshot = by_client.get('snapshot', {})
    history = by_client.get('history', [])

    h = calculate_health(c, today=TODAY,
                          daemon_finkoper=daemon_finkoper,
                          daemon_anomalies=daemon_anomalies,
                          deadlines=deadlines, awaiting=awaiting)
    health = h.get('color', 'grey')

    # Header
    n_tracks = len(mm_client['tracks'])
    n_aw = len([a for a in awaiting if a.get('client_id') == c['id']])
    n_gaps = len(mm_client['gaps'])
    time_bali = getattr(generate, 'TIME_BALI', '') or ''
    time_msk = getattr(generate, 'TIME_MSK', '') or ''
    time_line = ''
    if time_bali and time_msk:
        time_line = '<br>🕐 ' + _esc(time_bali) + ' WITA · ' + _esc(time_msk) + ' MSK'
    # Breadcrumb leads to the matching client-group list, not to overview.
    from _helpers import client_group as _client_group, _slugify_group as _slug_grp, _group_label as _grp_label
    _grp = _client_group(c)
    _grp_slug = _slug_grp(_grp)
    back_url = 'clients_' + _grp_slug + '.html'
    back_label = '← ' + _t('All clients') + ' · ' + _grp_label(_grp)
    # client tagline (UX): take business_description from state/regime if present
    _biz_desc = ''
    # Header badge = the SAME localised regime label shown on the client-list
    # snippet (c['regime'], built by _jurisdiction.render_regime_label). We no
    # longer concat the client-group name here — the breadcrumb above the title
    # already shows it. _is_ausn only drives the badge colour.
    _is_ausn = False
    # P2-fix 25.05.2026: DEPARTING/foreign_entities badges + team-meta
    _extra_badges = ''
    _team_meta = ''
    try:
        from _loaders import load_client_state_regime as _lcsr, load_client_state_identity as _lci
        _r = _lcsr(c['id'])
        if _r:
            _biz_desc = _r.get('business_description') or ''
            _rt = ((_r.get('primary') or {}).get('type') or '').strip()
            _is_ausn = (_rt == 'AUSN')
            _contour = _r.get('contour') or {}
            if _contour.get('type') == 'team':
                _leader = _contour.get('leader', '')
                _base = _contour.get('fresh_base_id', '')
                _bits = []
                if _leader:
                    _bits.append('🧑‍💼 ' + _leader)
                if _base:
                    _bits.append('1C:Fresh ' + _base)
                if _bits:
                    _team_meta = '<div class="client-team-meta" style="font-size:11px;color:#6b7280;margin-top:2px;">' + _esc(' · '.join(_bits)) + '</div>'
        _id = _lci(c['id'])
        if _id:
            _serv = _id.get('servicing_status') or {}
            _status = _serv.get('status', '')
            if _status == 'departing':
                _dep_to = _serv.get('departed_to', '')
                _extra_badges += ' <span class="badge" style="background:#fee2c2;color:#9a3412;border:1px solid #fdba74;">🚪 DEPARTING' + ((' → ' + _esc(_dep_to)) if _dep_to else '') + '</span>'
            elif _status == 'departed':
                _extra_badges += ' <span class="badge" style="background:#e5e7eb;color:#374151;border:1px solid #9ca3af;">🚪 DEPARTED</span>'
            elif _status == 'liquidating':
                _extra_badges += ' <span class="badge" style="background:#fecaca;color:#991b1b;border:1px solid #f87171;">⚠ LIQUIDATING</span>'
            elif _status == 'paused':
                _rv = _serv.get('review_date', '')
                _extra_badges += ' <span class="badge" style="background:#e0e7ff;color:#3730a3;border:1px solid #a5b4fc;">⏸ PAUSED' + ((' until ' + _esc(_rv)) if _rv else '') + '</span>'
            _fe = _id.get('foreign_entities') or []
            for _e in _fe:
                _country = _e.get('country', '')
                _st = _e.get('status', '')
                if _country and _st in ('frozen', 'active'):
                    _kik = ' ⚠CFC' if _e.get('kik_concern') else ''
                    _extra_badges += ' <span class="badge" style="background:#fef3c7;color:#92400e;border:1px solid #fcd34d;">🌍 ' + _esc(_country) + ' ' + _esc(_st) + _kik + '</span>'
    except Exception:
        pass
    _has_report = False
    try:
        import state_ops as _sops0
        _finx = _sops0.state_read(c['id'], 'financials.json')
        _has_report = bool(_finx and _finx.get('periods'))
    except Exception:
        _has_report = False
    _av_ini, _av_style = client_avatar(c['name_short'])
    # Full localised regime label, identical to the client-list snippet.
    _regime_full = (c.get('regime') or '').strip()
    _regime_badge_html = (
        ' <span class="badge ' + ('badge-ausn' if _is_ausn else 'badge-direct') + '">'
        + _esc(_regime_full) + '</span>'
    ) if _regime_full else ''
    head = (
        '<div class="breadcrumb">'
        '<a href="' + back_url + '">' + back_label + '</a>'
        '</div>'
        '<div class="client-topbar">'
        '<div class="ct-id">'
        '<span class="client-av health-' + health + '"' + _av_style + '>' + _esc(_av_ini) + '</span>'
        '<h1>'
        + _esc(c['name_short'])
        + _regime_badge_html
        + _extra_badges
        + '</h1>'
        + '</div>'
        '<div class="ct-act">'
        + '<div class="ct-btns">'
        + render_action_buttons(
            kind='client',
            entity_id=c['id'],
            entity_name=c['name_short'],
            prompt_text=_t('Review this client and propose today\'s priorities.'),
            context_text=(_t('Client') + ': ' + (c.get('name_short') or '')
                + (' — ' + _biz_desc if _biz_desc else '')),
        )
        + (('<a class="tm-btn tm-btn-outline tm-btn-sm" href="report_' + _esc(c['id']) + '.html" target="_blank" rel="noopener">\U0001F4C4 ' + _esc(_t('Client report')) + '</a>') if _has_report else '')
        + '</div>'
        + '</div>'
        + '</div>'
        + '<div class="client-desc">'
        + '<div class="client-desc-main">'
        + (('<div class="client-desc-text">' + _esc(_biz_desc) + '</div>') if _biz_desc else '')
        + _team_meta
        + '</div>'
        + '<span class="ct-meta">' + _t('updated') + ' ' + _format_date_ru(TODAY)
        + (time_line if time_line else '') + '</span>'
        + '</div>'
        + '<script>(function(){var b=document.querySelector(".client-topbar");if(!b)return;'
          'var f=function(){b.classList.toggle("stuck",(window.scrollY||document.documentElement.scrollTop||0)>6);};'
          'window.addEventListener("scroll",f,{passive:true});f();})();</script>'
    )

    req_card = render_client_requisites(c)
    snap = render_client_snapshot(snapshot)
    # R6/R9: shared tasks_lookup for risks and financial model
    _tasks_lookup = {}
    try:
        from _loaders import load_client_state_tasks
        _t_for_lookup = load_client_state_tasks(c['id']) or {}
        _tasks_lookup = {t.get('id'): t.get('title', '') for t in (_t_for_lookup.get('tasks') or [])}
    except Exception:
        _tasks_lookup = {}
    risks_html = ''
    try:
        from _loaders import load_client_state_risks
        _r = load_client_state_risks(c['id'])
        if _r:
            risks_html = render_client_risks(_r, tasks_lookup=_tasks_lookup,
                                             client_id=c['id'], today=TODAY,
                                             client_name=c.get('name_short') or '')
    except Exception:
        pass
    financials_html = ''
    counterparties_html = ''
    accounts_html = ''
    quick_access_html = ''
    payroll_html = ''
    real_estate_html = ''
    behavior_html = ''
    cheatsheet_html = ''
    kpi_html = ''
    fwd_html = ''
    try:
        cheatsheet_html = render_jurisdiction_cheatsheet(c.get('jurisdiction') or 'ru')
    except Exception:
        cheatsheet_html = ''
    try:
        from _loaders import (load_client_state_financials, load_client_state_counterparties,
                              load_client_state_accounts, load_client_state_behavior)
        # Payroll roster preload (shared by the headcount KPI and the roster panel).
        _pay = None
        try:
            from state_ops import state_read as _sr_pay, state_exists as _se_pay
            if _se_pay(c['id'], 'payroll.json'):
                _pay = _sr_pay(c['id'], 'payroll.json')
        except Exception:
            _pay = None
        _f = load_client_state_financials(c['id'])
        if _f:
            financials_html = render_client_financials(_f, tasks_lookup=_tasks_lookup, jurisdiction=c.get('jurisdiction') or 'ru', client_id=c['id'], today_d=TODAY, client_name=c.get('name_short') or '')
            try:
                from _loaders import load_client_state_identity as _lci_kpi
                _id_kpi = _lci_kpi(c['id'])
            except Exception:
                _id_kpi = None
            try:
                kpi_html = render_kpi_row(_f, _id_kpi, c.get('jurisdiction') or 'ru', payroll=_pay)
            except Exception:
                kpi_html = ''
            try:
                fwd_html = render_forward_strip(_f, c.get('jurisdiction') or 'ru', TODAY.isoformat() if hasattr(TODAY, 'isoformat') else str(TODAY))
            except Exception:
                fwd_html = ''
        _cp = load_client_state_counterparties(c['id'])
        if _cp:
            counterparties_html = render_client_counterparties(_cp, tasks_lookup=_tasks_lookup,
                                                               client_id=c['id'], today=TODAY,
                                                               client_name=c.get('name_short') or '')
        _acc = load_client_state_accounts(c['id'])
        if _acc:
            accounts_html = render_client_accounts(_acc)
            quick_access_html = render_client_quick_access(_acc)
        # P2 25.05.2026: real_estate (the client only)
        try:
            from state_ops import state_read, state_exists
            real_estate_html = ''
            if state_exists(c['id'], 'real_estate.json'):
                _re_data = state_read(c['id'], 'real_estate.json')
                if _re_data:
                    real_estate_html = render_client_real_estate(_re_data)
        except Exception:
            real_estate_html = ''

        # Payroll roster panel (reuses the preloaded _pay; slot from migration 0019).
        # Pass full tasks + risks so each row can open the entity-linked employee card.
        try:
            if _pay:
                _pay_tasks = []
                _pay_risks = []
                try:
                    from _loaders import load_client_state_tasks as _lct_pay
                    _pay_tasks = (_lct_pay(c['id']) or {}).get('tasks') or []
                except Exception:
                    _pay_tasks = []
                try:
                    from _loaders import load_client_state_risks as _lcr_pay
                    _pay_risks = (_lcr_pay(c['id']) or {}).get('risks') or []
                except Exception:
                    _pay_risks = []
                payroll_html = render_client_payroll_roster(
                    _pay, _f, tasks=_pay_tasks, risks=_pay_risks, client_id=c['id'],
                    client_name=(c.get('name_short') or c.get('name_full') or ''))
        except Exception:
            payroll_html = ''

        _beh = load_client_state_behavior(c['id'])
        if _beh:
            behavior_html = render_client_behavior(_beh)
    except Exception:
        pass
    # Client card = a per-client plan: the SAME plan rendering as the Plan page,
    # scoped to this client (horizon groups + clickable rows). Falls back to the
    # legacy tracks zone only if the client has no plan tasks.
    from _plan_today import render_client_plan
    _client_plan = render_client_plan(c['id'], TODAY)
    if _client_plan:
        tracks = ('<div class="section-title" id="all-tasks"><h2>' + _t('🎯 Active tracks') + '</h2></div>'
                  + _client_plan)
    else:
        tracks = render_tracks_zone(mm_client) if n_tracks else (
            '<div class="section-title" id="all-tasks"><h2>' + _t('🎯 Active tracks') + '</h2></div>'
            '<div class="side-list"><div class="empty">'
            + _t('Mental_model is empty or has no tracks') + '</div></div>'
        )
    awaitings = render_awaitings_zone(
        [a for a in awaiting if a.get('client_id') == c['id']]
    )
    gaps = render_gaps_zone(mm_client)
    side = '<section class="side-cols">' + awaitings + gaps + '</section>'
    hist = render_client_history(history)
    # v2 sections (Financial model, Calendar, Plan, Risks, Pattern, Links, Counterparties)
    v2_block = render_v2_block(by_client)

    # dictate button removed — header «Разобрать» (unified modal) is the one action
    global_mic = ''

    # Stage 1 sidebar: active item = team or direct based on the client's track
    sidebar_active = 'clients_' + _slug_grp(_client_group(c))
    title = c['name_short']
    return (
        '<!DOCTYPE html>\n<html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMTUuNSIgZmlsbD0iIzFGNEU3OSIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMTYiIHI9IjEyLjciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0I3OTI1NyIgc3Ryb2tlLXdpZHRoPSIxLjMiLz48dGV4dCB4PSIxNiIgeT0iMTciIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIiBmb250LWZhbWlseT0iQXJpYWwsSGVsdmV0aWNhLHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTQiIGZvbnQtd2VpZ2h0PSI3MDAiIGZpbGw9IiNmZmZmZmYiPkJLPC90ZXh0Pjwvc3ZnPg==">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>' + _esc(title) + '</title>'
        '<style>' + DESIGN_TOKENS_CSS + OVERVIEW_SPECIFIC_CSS + OVERVIEW_V2_CSS + REQ_CARD_CSS \
        + CLIENT_V2_EXTRA_CSS + PROMPT_MODAL_CSS  + SIDEBAR_CSS + V2_SECTIONS_CSS + TRACK_MODAL_CSS + _AN_CSS + QUICK_ACCESS_CSS + CHEATSHEET_CSS + KPI_ROW_CSS + ROSTER_CSS + '</style>'
        '</head><body>'
        '<div class="layout-shell">'
        + render_sidebar(active=sidebar_active)
        + '<main class="main-content">'
        + head + kpi_html + _an_zone + _an_questions
        + cheatsheet_html + quick_access_html + risks_html + tracks + financials_html + payroll_html + req_card + accounts_html + real_estate_html + counterparties_html + behavior_html + hist
        + '</main></div>'
        + PROMPT_MODAL_HTML + PROMPT_MODAL_JS
          + TRACK_MODAL_HTML + TRACK_MODAL_JS + QUICK_ACCESS_JS +
        '</body></html>'
    )


# ============================================================
# 🔗 Quick access (quick_access[] from state/accounts.json)
# Added by request 2026-06-14.
# ============================================================
ROSTER_CSS = """
.ros-totals { display:flex; align-items:flex-end; gap:14px; margin:36px 0 14px; padding:0 17px 0 0; }
.ros-tot-lead { flex:1 1 auto; min-width:0; display:flex; align-items:baseline; gap:10px; }
.ros-tot-title { font-size:var(--fs-h2); font-weight:600; margin:0; color:var(--text-primary,#15171C); }
.ros-tot-per { font-size:var(--fs-meta); color:var(--text-muted,#8A909C); font-variant-numeric:tabular-nums; }
.ros-totals .ros-stat-v { font-weight:600; }
.ros-val { flex:0 0 auto; min-width:82px; text-align:right; font-variant-numeric:tabular-nums;
           font-size:13.5px; color:var(--text-primary,#15171C); white-space:nowrap; }
.ros-wrap { display:flex; flex-direction:column; }
.ros-section { background:var(--bg-card,#fff);
               border:1px solid var(--border,#E8EAEE); border-radius:var(--radius-card,12px); overflow:hidden; }
.ros-row { display:flex; align-items:center; gap:14px; min-height:56px; padding:10px 16px;
           border-top:1px solid var(--border,#E8EAEE); border-left:2px solid transparent;
           transition:background 120ms; }
.ros-row:first-child { border-top:none; }
.ros-row:hover { background:var(--bg-subtle,#EEF1F4); }
.ros-rail-warn { border-left-color:var(--accent-yellow,#A8782B); }
.ros-rail-bad  { border-left-color:var(--accent-red,#C24A3D); }
.ros-hidden { display:none; }
.ros-section.ros-expanded .ros-hidden { display:flex; }
.ros-av { flex:0 0 32px; width:32px; height:32px; border-radius:50%; background:var(--bg-subtle,#EEF1F4);
          color:var(--text-secondary,#565B66); font-size:12px; font-weight:600; letter-spacing:.2px;
          display:inline-flex; align-items:center; justify-content:center; }
.ros-id { flex:1 1 auto; min-width:0; }
.ros-name-row { display:flex; align-items:center; gap:7px; flex-wrap:wrap; min-width:0; }
.ros-name { font-weight:550; color:var(--text-primary,#15171C); font-size:14px; }
.ros-pos { color:var(--text-muted,#8A909C); font-weight:400; font-size:12.5px; margin-top:2px;
           white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ros-stat { flex:0 0 auto; display:flex; flex-direction:column; align-items:flex-end; gap:2px; min-width:82px; }
.ros-stat-l { font-size:10px; font-weight:600; letter-spacing:.4px; text-transform:uppercase; color:var(--text-muted,#8A909C); }
.ros-stat-v { font-size:13.5px; font-variant-numeric:tabular-nums; color:var(--text-primary,#15171C); white-space:nowrap; }
.ros-dash { color:var(--border-strong,#D8DCE2); }
.ros-mchip, .ros-pchip { font-size:11px; padding:1px 8px; border-radius:20px; white-space:nowrap;
           background:var(--bg-subtle,#EEF1F4); color:var(--text-secondary,#565B66); }
.ros-mchip-flag { background:var(--yellow-bg,#F7F0E1); color:var(--accent-yellow,#A8782B); }
.ros-tag { font-size:11px; padding:1px 8px; border-radius:20px; white-space:nowrap;
           background:var(--accent-soft,#EAF1F7); color:var(--accent,#1F4E79); }
.ros-chip { }
.ros-pill { font-size:11.5px; font-weight:500; padding:2px 9px; border-radius:20px; white-space:nowrap; }
.ros-ok      { background:#E8F1EC; color:#2A6444; }
.ros-bad     { background:#F7ECEA; color:#97362B; }
.ros-warn    { background:#F6EEDD; color:#7A5A1F; }
.ros-neutral { background:var(--bg-subtle,#EEF1F4); color:var(--text-muted,#8A909C); }
.ros-chev { flex:0 0 16px; text-align:right; color:var(--border-strong,#D8DCE2); font-size:18px; font-weight:500; }
.ros-row:hover .ros-chev { color:var(--text-muted,#8A909C); }
.ros-more { align-self:flex-start; margin-top:10px; background:none; border:0; cursor:pointer;
            color:var(--accent,#1F4E79); font-size:13px; font-weight:500; padding:4px 2px; font-family:inherit; }
.ros-more:hover { text-decoration:underline; }
.ros-sum-ok   { color:var(--accent-green,#3E8E5E); }
.ros-sum-warn { color:var(--accent-yellow,#A8782B); }
.ros-sum-bad  { color:var(--accent-red,#C24A3D); }
"""


CHEATSHEET_CSS = """
.cs-card{border:1px solid #e6ebf0;border-radius:12px;background:#fff;margin-bottom:var(--space-lg,20px);}
.cs-summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;padding:13px 16px;font-size:14px;font-weight:600;color:#1F4E79;}
.cs-summary::-webkit-details-marker{display:none}
.cs-summary::before{content:'\\25B8';color:#9aa3ad;font-size:11px}
details.cs-card[open]>.cs-summary::before{content:'\\25BE'}
.cs-summary .ic{width:17px;height:17px;color:#B79257;}
.cs-body{padding:0 16px 14px;}
.cs-facts{display:flex;flex-wrap:wrap;gap:6px 18px;padding:4px 0 12px;border-bottom:1px solid #eef0f3;margin-bottom:10px;}
.cs-fact{font-size:12px;color:#3a4653;}
.cs-fl{color:#8a93a0;}
.cs-table{width:100%;border-collapse:collapse;font-size:12px;}
.cs-table th{text-align:left;color:#8a93a0;font-weight:600;padding:4px 8px;border-bottom:1px solid #eef0f3;font-size:11px;text-transform:uppercase;letter-spacing:.03em;}
.cs-table td{padding:5px 8px;border-bottom:1px solid #f3f5f7;vertical-align:top;}
.cs-table tr:last-child td{border-bottom:none;}
.cs-term{font-weight:600;color:#2a3744;white-space:nowrap;}
"""


def render_jurisdiction_cheatsheet(jurisdiction):
    """Inline reference for a client whose jurisdiction differs from the operator's
    home (ru): authority/portal/currency + the pack glossary (term -> operator-locale
    analogy). Collapsible; empty for ru clients so the RU book isn't cluttered."""
    juris = (jurisdiction or 'ru').strip().lower()
    if juris in ('', 'ru'):
        return ''
    try:
        import os as _os
        import _jurisdiction as _J
        from _config import LOCALE as _LOC
        from _icons import icon
        pack = _J.load_jurisdiction(juris)
    except Exception:
        return ''
    auth = pack.authorities or {}
    man = pack.manifest or {}
    jname = (man.get('name_i18n') or {}).get(_LOC) or man.get('name') or juris.upper()

    facts = []
    def _fact(label, val):
        if val:
            facts.append('<span class="cs-fact"><span class="cs-fl">' + _esc(_t(label))
                         + ':</span> ' + _esc(str(val)) + '</span>')
    _fs = auth.get('filing_systems') or []
    _fact('Tax authority', auth.get('tax_authority'))
    _fact('Portal', ', '.join(_fs) if isinstance(_fs, list) else _fs)
    _fact('Currency', auth.get('currency'))
    _fact('Social insurance', auth.get('social_authority'))
    facts_html = ('<div class="cs-facts">' + ''.join(facts) + '</div>') if facts else ''

    gloss_html = ''
    grel = man.get('glossary')
    if grel:
        try:
            text = open(_os.path.join(_J._PACKS_DIR, juris, grel), encoding='utf-8').read()
            data = []
            for ln in text.splitlines():
                ln = ln.strip()
                if not ln.startswith('|'):
                    continue
                cells = [c.strip() for c in ln.strip('|').split('|')]
                if len(cells) < 2:
                    continue
                if all(set(c) <= set('-: ') for c in cells):   # separator row
                    continue
                if cells[0].lower() == 'term':                  # header row
                    continue
                term = cells[0].replace('**', '').strip()
                analogy = (cells[2] if len(cells) >= 3 and cells[2] else cells[1]).replace('**', '').strip()
                if term:
                    data.append((term, analogy))
            if data:
                trs = ''.join('<tr><td class="cs-term">' + _esc(term) + '</td><td>'
                              + _esc(analogy) + '</td></tr>' for term, analogy in data)
                gloss_html = ('<table class="cs-table"><thead><tr><th>' + _esc(_t('Term'))
                              + '</th><th>' + _esc(_t('In plain terms')) + '</th></tr></thead>'
                              '<tbody>' + trs + '</tbody></table>')
        except Exception:
            gloss_html = ''

    if not (facts_html or gloss_html):
        return ''
    return ('<details class="cs-card"><summary class="cs-summary">' + icon('book-open')
            + ' ' + _esc(_t('Jurisdiction cheat sheet')) + ' · ' + _esc(jname)
            + '</summary><div class="cs-body">' + facts_html + gloss_html + '</div></details>')


QUICK_ACCESS_CSS = """
.qa-section{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-bottom:var(--space-lg,20px);align-items:start;}
.qa-tile{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:9px;transition:box-shadow .15s ease;}
.qa-tile:hover{box-shadow:0 3px 12px rgba(31,78,121,.08);}
.qa-tile.qa-off{opacity:.5;}
.qa-head{display:flex;align-items:flex-start;gap:10px;}
.qa-ic{width:34px;height:34px;border-radius:8px;background:#eef3fb;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:#1F4E79;}
.qa-ic .ic{width:18px;height:18px;}
.qa-tt{line-height:1.25;min-width:0;}
.qa-name{font-size:14px;font-weight:600;color:#1F4E79;}
.qa-go{margin-left:auto;text-decoration:none;font-size:13px;border:1px solid #cdd3db;border-radius:8px;padding:6px 11px;color:#1F4E79;white-space:nowrap;}
.qa-go:hover{background:#f4f7fc;}
.qa-cred{display:flex;align-items:center;gap:8px;font-size:13px;padding-top:9px;margin-top:9px;border-top:1px solid #eef0f3;}
.qa-cred + .qa-cred{border-top:none;padding-top:0;margin-top:7px;}
.qa-lbl{color:#6b7280;min-width:50px;}
.qa-val{font-family:ui-monospace,Menlo,Consolas,monospace;color:#1f2937;overflow-wrap:anywhere;}
.qa-btn{border:1px solid #cdd3db;background:#fff;border-radius:7px;padding:3px 9px;font-size:12px;color:#374151;cursor:pointer;}
.qa-btn:hover{background:#f4f7fc;}
.qa-cp{margin-left:auto;}
.qa-rev + .qa-cp{margin-left:6px;}
.qa-note{font-size:12.5px;color:#566070;line-height:1.5;overflow-wrap:anywhere;word-break:break-word;}
.qa-note.qa-clamp{display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;}
.qa-note.qa-expandable{cursor:pointer;}
.qa-note.qa-expandable:hover{color:#1F4E79;}
.qa-need{display:inline-block;font-size:11px;color:#9a6708;background:#faeeda;border-radius:6px;padding:1px 7px;margin-right:6px;}
.qa-status{display:inline-block;font-size:11px;font-weight:600;border-radius:20px;padding:2px 9px;margin-top:4px;align-self:flex-start;}
.qa-status.ok{color:#136c3a;background:#e6f4ec;}
.qa-status.wait{color:#9a6708;background:#faeeda;}
.qa-status.need{color:#9a3412;background:#fbe8e2;}
.qa-status.unknown{color:#5b6470;background:#eef0f3;}
"""

QUICK_ACCESS_JS = """
<script>
(function(){
  var DOTS='\\u2022\\u2022\\u2022\\u2022\\u2022\\u2022\\u2022\\u2022\\u2022\\u2022';
  document.querySelectorAll('.qa-rev').forEach(function(b){
    b.addEventListener('click',function(){
      var pw=b.parentNode.querySelector('.qa-pw');if(!pw)return;
      if(pw.dataset.shown==='1'){pw.textContent=DOTS;pw.dataset.shown='0';b.textContent='show';}
      else{pw.textContent=pw.dataset.pw;pw.dataset.shown='1';b.textContent='hide';}
    });
  });
  document.querySelectorAll('.qa-cp').forEach(function(b){
    b.addEventListener('click',function(){
      var v=b.getAttribute('data-v')||'';
      var t=document.createElement('textarea');t.value=v;document.body.appendChild(t);t.select();
      try{document.execCommand('copy');}catch(e){}document.body.removeChild(t);
      var old=b.textContent;b.textContent='\\u2713';setTimeout(function(){b.textContent=old;},900);
    });
  });
  document.querySelectorAll('.qa-note').forEach(function(n){
    if(n.scrollHeight-n.clientHeight<=1)return;
    n.classList.add('qa-expandable');
    n.addEventListener('click',function(){n.classList.toggle('qa-clamp');});
  });
})();
</script>
"""

# Service → semantic icon name (rendered as a line SVG; emoji would be stripped
# by the global sanitizer, leaving empty boxes). Keyed on the service slug — but a
# slug map is RU-centric and needs a code edit per new service. The structured way
# is `category` (assigned by the runtime per migrations/TASK_CLASSIFIER.md / 0006);
# the picker below prefers `category`, so a new service only needs a category, not
# a code change. The slug map stays as the fallback for entries without a category.
_QA_ICONS = {'prodamus':'acquiring','cloudpayments':'acquiring','ukassa':'acquiring',
             'bank':'bank_check','fns':'building','ofd':'kkt_check',
             'finkoper':'primary_collection','onec':'posting_1c','1c':'posting_1c',
             'acquiring':'acquiring','rosstat':'building',
             'assistant':'chat','mail':'email_action_required','email':'email_action_required',
             'tg':'chat','whatsapp':'chat','max':'chat',
             # Indonesian / newer services
             'gdrive':'brief','coretax':'building','edabu':'users','bpjs_tk':'users',
             'moka':'kkt_check','oss':'building'}

# Structured category → icon. The jurisdiction-neutral key the runtime sets; the
# picker prefers it over the slug, so a service in any jurisdiction renders a
# type-matched icon without a slug entry.
_QA_CAT_ICONS = {'bank':'bank_check','acquiring':'acquiring','pos':'kkt_check',
                 'ofd':'kkt_check','tax_authority':'building','social_insurance':'users',
                 'portal':'building','storage':'brief','mail':'email_action_required',
                 'messenger':'chat','accounting':'posting_1c','collection':'primary_collection',
                 'assistant':'chat'}


def _qa_icon_name(it):
    """Pick a type-matched icon: structured `category` first (jurisdiction-neutral,
    set by the runtime), then the service slug, then a neutral arrow. An invalid
    icon would fall back to 'dot' in icon(), so we resolve to a known name here."""
    cat = (it.get('category') or '').strip()
    if cat in _QA_CAT_ICONS:
        return _QA_CAT_ICONS[cat]
    return _QA_ICONS.get(it.get('service'), 'arrow')

def render_client_quick_access(acc):
    """Quick access — links/logins/passwords to client services from accounts.quick_access[]."""
    from _icons import icon
    if not acc:
        return ''
    items = acc.get('quick_access') or []
    if not items:
        return ''
    tiles = []
    for it in items:
        label = it.get('label') or it.get('service') or _t('Service')
        disabled = it.get('status') == 'disabled'
        ic = icon(_qa_icon_name(it))
        url = it.get('url')
        go = ''
        if url and not disabled:
            go = '<a class="qa-go" href="' + _esca(str(url)) + '" target="_blank" rel="noopener">' + _t('Open ↗') + '</a>'
        _QA_STATUS = {
            'connected': ('access ready', 'ok'), 'have': ('access ready', 'ok'),
            'ok': ('access ready', 'ok'), 'active': ('access ready', 'ok'),
            'client_holds': ('access with client', 'ok'),
            'after_first_billing': ('access after first payment', 'wait'),
            'pending': ('request access', 'need'), 'missing': ('request access', 'need'),
            'need': ('request access', 'need'),
            'unknown': ('set access status', 'unknown'),
        }
        # by_chat messengers (tg/whatsapp/max) have SESSION-LEVEL access only — one logged-in
        # operator account reaches every chat/channel by search. A per-chat quick_access entry is
        # a routing pointer, NOT a credentialed access point, so it carries no real cred_status:
        # suppress the access chip (no spurious «уточнить»). See connectors/_chat_collector.md.
        _svc = (it.get('service') or '').lower()
        _u = (it.get('url') or '').lower()
        _is_chat = _svc in ('tg', 'telegram', 'whatsapp', 'wa', 'max') or any(
            d in _u for d in ('telegram.org', 't.me', 'whatsapp.com', 'wa.me', 'max.ru'))
        _st = None if _is_chat else _QA_STATUS.get(it.get('cred_status'))
        status_badge = ('<div class="qa-status ' + _st[1] + '">' + _t(_st[0]) + '</div>') if _st else ''
        head = ('<div class="qa-head"><div class="qa-ic">' + ic + '</div>'
                '<div class="qa-tt"><div class="qa-name">' + _esc(str(label)) + '</div>'
                + status_badge + '</div>'
                + go + '</div>')
        creds = ''
        login = it.get('login')
        if login:
            creds += ('<div class="qa-cred"><span class="qa-lbl">' + _t('login') + '</span>'
                      '<span class="qa-val">' + _esc(str(login)) + '</span>'
                      '<button class="qa-btn qa-cp" data-v="' + _esca(str(login)) + '">' + _t('copy') + '</button></div>')
        pw = it.get('password')
        if pw:
            creds += ('<div class="qa-cred"><span class="qa-lbl">' + _t('password') + '</span>'
                      '<span class="qa-val qa-pw" data-pw="' + _esca(str(pw)) + '">••••••••••</span>'
                      '<button class="qa-btn qa-rev">' + _t('show') + '</button>'
                      '<button class="qa-btn qa-cp" data-v="' + _esca(str(pw)) + '">' + _t('copy') + '</button></div>')
        note = it.get('note') or ''
        note_html = ('<div class="qa-note qa-clamp">' + _esc(str(note)) + '</div>') if note else ''
        cls = ('qa-tile qa-off' if disabled else 'qa-tile') + ((' qa-st-' + _st[1]) if _st else '')
        tiles.append('<div class="' + cls + '">' + head + creds + note_html + '</div>')
    return (
        '<div class="section-title"><h2>' + _t('🔗 Quick access') + '</h2></div>'
        '<section class="qa-section">' + ''.join(tiles) + '</section>'
    )

