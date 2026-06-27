"""Owner-facing monthly one-pager.

A client-facing report the operator opens from the client card, prints to PDF and
sends. Standalone, print-styled, brand-themed; data-driven from state/financials
(latest period + turnover trend + upcoming deadlines). Operator-locale via t().

generate.py writes report_<id>.html next to the dashboards for every client that
has financial periods; the client card links to it. No data is invented — only the
client's own stored figures are shown.

Design + aesthetic rules live in docs/DESIGN-SYSTEM.md → "Client one-pager": a
calm financial *statement* (hairline tax rows, not card grids; serif tabular
figures; flat navy fills + a single gold accent), in the client brand (navy/gold)
per policies/brand-and-tone.md. Edit the look here (_CSS/_PAGE) and regenerate;
never hand-edit a generated report_*.html.

Graceful empty states are load-bearing (a just-onboarded client has no data yet):
no turnover on file → a quiet italic caption, never a lone "—"; no tax lines →
the honest "no payment was due" note, never "paid ✓ / 0". Turnover source order:
turnover_idr → income_usn → income_ausn → ausn_monthly[latest].income_base.

Client-facing boundary: the subtitle reads `regime.client_facing.summary` (operator
authored, client-clean) — NOT `regime.business_description`, which is internal
operator prose (ticket numbers, credit codes, open uncertainties). When
`client_facing.summary` is null the subtitle is *derived* from structured fields
(regime label + main activity + start year), which leaks nothing. The taxes block
is honest: it claims "paid" only when there are real tax lines, otherwise it states
plainly that no payment was due. See migration 0011 + policies/INSTRUCTIONS.md.
"""
import os
from _strings import t, LOCALE
from _config import BRAND_NAME, BRAND_TAGLINE, BRAND_MONOGRAM
from _helpers import _esc

# tax field -> (label key, plain-note key). Unknown fields are humanized.
_TAX_LINE = {
    'pp55_final_0p5':        ('Final tax 0.5% (PP55)', 'Main tax: 0.5% of turnover'),
    'final_pph':            ('Final tax 0.5%', 'Main tax: 0.5% of turnover'),
    'pph21':                ('Payroll income tax (PPh 21)', 'Income tax on salaries'),
    'pph4_2_rent':          ('Rent withholding', 'Tax on rent paid'),
    'pph23':                ('Services withholding (PPh 23)', 'Tax withheld on services'),
    'bpjs_tk':              ('Social insurance (BPJS)', 'Employee social contributions'),
    'bpjs':                 ('Social insurance (BPJS)', 'Employee social contributions'),
    'pph_final_construction': ('Construction final tax', 'Final tax on construction'),
    'usn_advance':          ('USN advance', 'Simplified-tax advance'),
    'one_pct_overage':      ('1% surplus', '1% over the threshold'),
    'fixed_insurance_paid': ('Fixed contributions', 'Fixed insurance contributions'),
}
_NON_TAX = {'payroll_net', 'payroll_net_idr'}

_MONTHS = {
    'ru': ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль',
           'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December'],
}
_MONTHS_SHORT = {
    'ru': ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'],
    'en': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
}


def _loc():
    return LOCALE if LOCALE in ('ru', 'en') else 'ru'


def _money(v):
    if v is None:
        return '—'
    try:
        return '{:,.0f}'.format(float(v)).replace(',', ' ')
    except Exception:
        return str(v)


def _money_short(v):
    """Compact figure for in-chart labels: 4.7M / 720K / 540. Locale-neutral
    suffixes so it stays correct under any jurisdiction's currency."""
    try:
        n = float(v)
    except Exception:
        return ''
    a = abs(n)
    if a >= 1_000_000:
        s = '{:.1f}M'.format(n / 1_000_000)
    elif a >= 1_000:
        s = '{:.0f}K'.format(n / 1_000)
    else:
        s = '{:.0f}'.format(n)
    return s.replace('.0M', 'M')


def _period_label(p):
    s = str(p or '')
    if len(s) == 7 and s[4] == '-':
        try:
            return _MONTHS[_loc()][int(s[5:7]) - 1] + ' ' + s[:4]
        except Exception:
            return s
    return s


def _period_short(p):
    s = str(p or '')
    if len(s) == 7 and s[4] == '-':
        try:
            return _MONTHS_SHORT[_loc()][int(s[5:7]) - 1]
        except Exception:
            return s
    return s


def _currency(jurisdiction):
    try:
        import _jurisdiction as _J
        return (_J.load_jurisdiction((jurisdiction or 'ru').strip().lower()).authorities or {}).get('currency_symbol') or '₽'
    except Exception:
        return '₽'


def _derive_subtitle(regime, identity, jurisdiction):
    """A client-clean subtitle built only from structured fields — never from the
    internal `business_description` prose. Shape: "<regime> · <main activity> · с <year>".
    Any piece that is missing is simply omitted; an empty result is fine.
    """
    regime = regime or {}
    identity = identity or {}
    parts = []

    # Regime token, client-friendly and localized (e.g. "УСН 6%"). The client knows
    # their regime by its short name + rate, not the operator's object distinction
    # ("Доходы" vs "Доходы−Расходы"), so we localize the type via t() and append the
    # rate. If t() has no entry (a non-RU jurisdiction), fall back to the pack's
    # regime label so this stays multi-jurisdiction-correct and never RF-assumes.
    prim = regime.get('primary') or {}
    rtype = prim.get('type')
    rate = prim.get('rate')
    if rtype:
        loc = t(rtype)
        if loc and loc != rtype:
            parts.append(loc + (' ' + str(rate) + '%' if rate is not None else ''))
        else:
            try:
                import _jurisdiction as _J
                pack = _J.load_jurisdiction((jurisdiction or 'ru').strip().lower())
                lbl = (_J.render_regime_label(pack, prim, regime.get('patents') or []) or '').strip()
                parts.append(lbl or (str(rtype) + (' ' + str(rate) + '%' if rate is not None else '')))
            except Exception:
                parts.append(str(rtype) + (' ' + str(rate) + '%' if rate is not None else ''))

    # Main activity (client-friendly name only — no codes).
    okved = (identity.get('okved') or {}).get('main') or {}
    act = okved.get('name')
    if act and str(act).strip():
        parts.append(str(act).strip())

    # Start year.
    yr = identity.get('reg_started_year')
    if not yr:
        rd = str(identity.get('reg_date') or '')
        yr = rd[:4] if len(rd) >= 4 and rd[:4].isdigit() else None
    if yr:
        parts.append(t('since') + ' ' + str(yr))

    return ' · '.join(parts)


def build_owner_report(client_id, financials, identity=None, regime=None, jurisdiction='ru'):
    periods = (financials or {}).get('periods') or []
    months = [p for p in periods if (p.get('period_type') or '') == 'month']
    latest = months[-1] if months else (periods[-1] if periods else None)
    if not latest:
        return ''
    cur = _currency(jurisdiction)
    name = (identity or {}).get('name', {})
    cname = (name.get('short') or name.get('full') or client_id) if isinstance(name, dict) else (name or client_id)
    # Client-facing subtitle: operator-authored client copy if present, else a
    # derived structured line. NEVER the internal `business_description` prose.
    cf = (regime or {}).get('client_facing') or {}
    subtitle = (cf.get('summary') or '').strip() or _derive_subtitle(regime, identity, jurisdiction)
    turnover_scope = (cf.get('turnover_scope') or '').strip()

    def _turnover_of(p):
        for f in ('turnover_idr', 'income_usn', 'income_ausn'):
            if p.get(f) is not None:
                return p.get(f)
        return None

    turnover = _turnover_of(latest)
    period_for_label = latest.get('period')
    # AUSN may also keep income per month under ausn_monthly{"YYYY-MM": {income_base,…}}
    # rather than a flat field — fall back to the latest AUSN month so the report
    # shows the real turnover (and its month), not None.
    ausn = latest.get('ausn_monthly')
    if isinstance(ausn, dict) and ausn:
        _mk = sorted(ausn.keys())[-1]
        _al = ausn.get(_mk) or {}
        if turnover is None and _al.get('income_base') is not None:
            turnover = _al.get('income_base')
            period_for_label = _mk
    taxes = latest.get('taxes') or {}

    # Turnover hero figure. When no turnover is on file yet (a common onboarding
    # state — e.g. a just-signed client), a lone "—" reads as broken, so show a
    # plain italic caption instead of a giant dash.
    if turnover is None:
        heronum_html = '<div class="hero-empty">' + _esc(t('No turnover recorded yet')) + '</div>'
    else:
        heronum_html = ('<div class="hero-num num">' + _money(turnover)
                        + ' <small>' + _esc(cur) + '</small></div>')

    # Tax lines as a clean statement (label + note on the left, amount right),
    # which keeps an even rhythm for any number of lines — one or six — and never
    # leaves a lonely half-width card.
    rows, total = [], 0
    for k, v in taxes.items():
        # Only known, meaningful tax lines — skip meta/boolean flags and unknown
        # internal fields so the owner sees a clean, translated breakdown.
        if k not in _TAX_LINE or isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        lbl_key, note_key = _TAX_LINE[k]
        total += v
        rows.append('<div class="trow"><div class="tr-l"><div class="tr-t">' + _esc(t(lbl_key)) + '</div>'
                    + ('<div class="tr-d">' + _esc(t(note_key)) + '</div>' if note_key else '')
                    + '</div><div class="tr-v num">' + _money(v) + ' ' + _esc(cur) + '</div></div>')
    # Honest taxes block. Only claim "paid ✓" when there are real tax lines;
    # otherwise state plainly that no payment was due — never "paid ✓ / 0".
    if rows:
        taxes_html = ('<h2>' + _esc(t('Taxes & contributions — paid')) + ' &#10003;</h2>'
                      + '<div class="tlist">' + ''.join(rows) + '</div>'
                      + '<div class="total"><span class="tl">' + _esc(t('Total paid')) + '</span>'
                      + '<span class="tv num">' + _money(total) + ' <b>' + _esc(cur) + '</b></span></div>')
    else:
        taxes_html = ('<h2>' + _esc(t('Taxes & contributions')) + '</h2>'
                      + '<div class="note">' + _esc(t('No tax payments were due this month.')) + '</div>')

    # trend bars (last 6 months) — compact, sits in the hero beside the figure.
    bars = ''
    tr = [(p.get('period'), _turnover_of(p)) for p in months[-6:]]
    tr = [(pp, vv) for pp, vv in tr if isinstance(vv, (int, float))]
    if len(tr) >= 2:
        mx = max(vv for _, vv in tr) or 1
        cells = []
        for i, (pp, vv) in enumerate(tr):
            h = max(12, round(vv / mx * 90))
            cls = 'bar cur' if i == len(tr) - 1 else 'bar'
            cells.append('<div class="barwrap"><div class="' + cls + '" style="height:' + str(h) + 'px"></div>'
                         + '<div class="blbl">' + _esc(_period_short(pp)) + '</div></div>')
        bars = '<div class="chart">' + ''.join(cells) + '</div>'

    # upcoming deadlines
    import datetime as _dt
    today = _dt.date.today().isoformat()
    cal = sorted((financials or {}).get('tax_calendar_2026') or [], key=lambda e: e.get('date', ''))
    # Client view: hide internal/background items (e.g. long-term recovery deadlines
    # the client never acts on). These are operator tracking, not client commitments.
    _HIDE_STATUS = {'long_term_background'}
    upc = [e for e in cal
           if e.get('date', '') >= today and (e.get('status') or '') not in _HIDE_STATUS][:3]
    next_html = ''
    if upc:
        nx = []
        for e in upc:
            nx.append('<div class="nx"><div class="nd">' + _esc(e.get('date', '')) + '</div>'
                      '<div class="nt">' + _esc(e.get('what', '')) + '</div></div>')
        next_html = '<h2>' + _esc(t("What's next")) + '</h2><div class="next">' + ''.join(nx) + '</div>'

    payroll = taxes.get('payroll_net') or latest.get('payroll_net_idr')
    payroll_html = ''
    if payroll:
        payroll_html = ('<div class="muted2">' + _esc(t('Salaries paid; net payroll')) + ': '
                        + _money(payroll) + ' ' + _esc(cur) + '.</div>')

    scope_html = ('<div class="hero-scope">' + _esc(turnover_scope) + '</div>') if turnover_scope else ''

    return _PAGE.format(
        css=_CSS, mono=_esc(BRAND_MONOGRAM or 'IV'), bn=_esc(BRAND_NAME or ''), bt=_esc(BRAND_TAGLINE or ''),
        rt=_esc(t('Client report')), period=_esc(_period_label(period_for_label)),
        cname=_esc(cname), subtitle=_esc(subtitle),
        tlbl=_esc(t('Turnover this month')), heronum=heronum_html,
        scope=scope_html, bars=bars, taxesblock=taxes_html,
        payroll=payroll_html, nextblock=next_html,
        print_lbl=_esc(t('Print / Save PDF')),
        foot=_esc(t('Prepared by')) + ': ' + _esc(BRAND_NAME or '') + ' · ' + _esc(BRAND_TAGLINE or ''),
        title=_esc(t('Client report')) + ' — ' + _esc(cname),
    )


_CSS = """
@page{size:A4;margin:0;}
*{box-sizing:border-box;}
:root{--navy:#1F4E79;--navy-d:#163a5b;--gold:#B79257;--gold-d:#9a7a40;
  --ink:#2a333d;--muted:#6d7782;--faint:#9aa4af;--line:#e8ecf1;--hair:#eef1f5;
  --tint:#f8fafc;--bg:#edf0f4;}
html,body{margin:0;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  color:var(--ink);background:var(--bg);-webkit-font-smoothing:antialiased;line-height:1.5;
  font-feature-settings:"tnum" 1,"lnum" 1;}
.serif{font-family:Georgia,"Times New Roman",serif;}
.num{font-family:Georgia,"Times New Roman",serif;font-feature-settings:"tnum" 1,"lnum" 1;}

.sheet{max-width:210mm;margin:24px auto;background:#fff;padding:26mm 24mm 22mm;
  box-shadow:0 10px 44px rgba(20,40,70,.13);position:relative;}
.sheet::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;
  background:linear-gradient(90deg,var(--navy) 0,var(--navy) 70%,var(--gold) 70%,var(--gold) 100%);}

.noprint{max-width:210mm;margin:20px auto 0;text-align:right;}
.pbtn{background:var(--navy);color:#fff;border:none;border-radius:7px;padding:10px 18px;
  font-size:13px;font-weight:600;letter-spacing:.01em;cursor:pointer;}
.pbtn:hover{background:var(--navy-d);}

/* header */
.brandbar{display:flex;align-items:center;gap:14px;}
.mono{font-family:Georgia,serif;font-size:18pt;color:var(--navy);border:1.5px solid var(--gold);
  width:46px;height:46px;line-height:43px;text-align:center;border-radius:7px;font-weight:700;}
.brandtext .bn{font-family:Georgia,serif;font-size:14pt;color:var(--navy);font-weight:700;line-height:1.15;}
.brandtext .bt{font-size:7.5pt;letter-spacing:.16em;color:var(--faint);text-transform:uppercase;margin-top:4px;}
.rhead{margin-left:auto;text-align:right;}
.rhead .rt{font-size:7.5pt;color:var(--faint);text-transform:uppercase;letter-spacing:.16em;}
.rhead .rv{font-family:Georgia,serif;font-size:12.5pt;color:var(--navy);font-weight:700;margin-top:4px;}

/* client */
.client{margin-top:30px;padding-bottom:22px;border-bottom:1px solid var(--line);}
.cname{margin:0;font-family:Georgia,serif;font-size:21pt;color:var(--navy);font-weight:700;
  letter-spacing:-.01em;line-height:1.12;}
.subtitle{color:var(--muted);font-size:9.5pt;line-height:1.55;margin-top:8px;max-width:62ch;}

/* hero */
.hero{display:flex;align-items:flex-end;gap:26px;margin:26px 0 0;
  background:var(--tint);border:1px solid var(--line);border-radius:12px;padding:24px 28px;}
.hero-l{flex:1;}
.hero-lbl{font-size:8pt;color:var(--muted);text-transform:uppercase;letter-spacing:.15em;font-weight:600;}
.hero-num{font-size:31pt;color:var(--navy);font-weight:700;line-height:1.04;margin-top:11px;}
.hero-num small{font-size:14pt;color:var(--gold);font-weight:700;}
.hero-empty{font-size:11.5pt;color:var(--faint);font-style:italic;margin-top:13px;}
.hero-scope{font-size:8pt;color:var(--faint);margin-top:10px;}

/* chart in hero */
.chart{display:flex;align-items:flex-end;gap:10px;height:104px;}
.barwrap{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;}
.bar{width:22px;border-radius:3px 3px 0 0;background:#ccd6e2;}
.bar.cur{background:var(--navy);}
.blbl{font-size:7pt;color:var(--faint);margin-top:8px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;}

/* section heading */
h2{font-size:11pt;color:var(--navy);margin:32px 0 6px;font-family:Georgia,serif;font-weight:700;}

/* taxes statement */
.tlist{margin-top:6px;}
.trow{display:flex;justify-content:space-between;align-items:baseline;gap:20px;
  padding:13px 2px;border-bottom:1px solid var(--hair);}
.trow:first-child{border-top:1px solid var(--hair);}
.tr-t{font-size:10.5pt;color:var(--ink);font-weight:600;}
.tr-d{font-size:8.5pt;color:var(--muted);margin-top:3px;}
.tr-v{font-size:12pt;color:var(--navy);font-weight:700;white-space:nowrap;}
.total{display:flex;justify-content:space-between;align-items:center;
  background:var(--navy);color:#fff;border-radius:10px;padding:15px 20px;margin-top:18px;}
.total .tl{font-size:9pt;text-transform:uppercase;letter-spacing:.13em;color:#cdd9e6;font-weight:600;}
.total .tv{font-size:15pt;font-weight:700;color:#fff;}
.total .tv b{color:#e7d3aa;font-weight:700;}

.note{border:1px solid var(--line);border-radius:10px;padding:14px 16px;color:#4a5660;font-size:10pt;
  background:var(--tint);margin-top:6px;}
.muted2{color:var(--muted);font-size:8.5pt;margin-top:13px;}

/* what's next */
.next{display:grid;grid-template-columns:repeat(auto-fit,minmax(0,1fr));gap:14px;margin-top:6px;}
.nx{border:1px solid var(--line);border-radius:10px;padding:14px 16px;}
.nx .nd{color:var(--gold-d);font-weight:700;font-size:9pt;font-feature-settings:"tnum" 1;}
.nx .nt{font-size:9pt;color:#4a5660;margin-top:6px;line-height:1.5;}

.foot{margin-top:34px;border-top:1px solid var(--line);padding-top:14px;color:var(--faint);font-size:7.5pt;letter-spacing:.02em;}

@media print{.noprint{display:none;}body{background:#fff;}
  .sheet{box-shadow:none;margin:0;}
  .total,.pbtn,.bar.cur,.sheet::before{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
"""

_PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>{title}</title><style>{css}</style></head><body>
<div class="noprint"><button class="pbtn" onclick="window.print()">{print_lbl}</button></div>
<div class="sheet">
<header class="brandbar"><div class="mono">{mono}</div><div class="brandtext"><div class="bn">{bn}</div><div class="bt">{bt}</div></div>
<div class="rhead"><div class="rt">{rt}</div><div class="rv">{period}</div></div></header>
<div class="client"><h1 class="cname">{cname}</h1><div class="subtitle">{subtitle}</div></div>
<section class="hero"><div class="hero-l"><div class="hero-lbl">{tlbl}</div>{heronum}{scope}</div>{bars}</section>
{taxesblock}{payroll}
{nextblock}
<footer class="foot">{foot}</footer>
</div></body></html>"""
