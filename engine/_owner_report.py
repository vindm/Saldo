"""Owner-facing monthly one-pager.

A client-facing report the operator opens from the client card, prints to PDF and
sends. Standalone, print-styled, brand-themed; data-driven from state/financials
(latest period + turnover trend + upcoming deadlines). Operator-locale via t().

generate.py writes report_<id>.html next to the dashboards for every client that
has financial periods; the client card links to it. No data is invented — only the
client's own stored figures are shown.

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

    turnover = latest.get('turnover_idr')
    if turnover is None:
        turnover = latest.get('income_usn')
    period_for_label = latest.get('period')
    # AUSN keeps income per month under ausn_monthly{"YYYY-MM": {income_base, tax_ausn, …}}
    # rather than income_usn — fall back to the latest AUSN month so the report
    # shows the real turnover (and its month), not None.
    ausn = latest.get('ausn_monthly')
    ausn_last = None
    if isinstance(ausn, dict) and ausn:
        _mk = sorted(ausn.keys())[-1]
        ausn_last = ausn.get(_mk) or {}
        if turnover is None and ausn_last.get('income_base') is not None:
            turnover = ausn_last.get('income_base')
            period_for_label = _mk
    taxes = latest.get('taxes') or {}

    # tax lines + total
    cards, total = [], 0
    for k, v in taxes.items():
        # Only known, meaningful tax lines — skip meta/boolean flags and unknown
        # internal fields so the owner sees a clean, translated breakdown.
        if k not in _TAX_LINE or isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        lbl_key, note_key = _TAX_LINE[k]
        total += v
        cards.append('<div class="card"><div class="ct">' + _esc(t(lbl_key)) + '</div>'
                     + ('<div class="cd">' + _esc(t(note_key)) + '</div>' if note_key else '')
                     + '<div class="cv">' + _money(v) + ' ' + _esc(cur) + '</div></div>')
    # Honest taxes block. Only claim "paid ✓" when there are real tax lines;
    # otherwise state plainly that no payment was due — never "paid ✓ / 0".
    if cards:
        taxes_html = ('<h2>' + _esc(t('Taxes & contributions — paid')) + ' &#10003;</h2>'
                      + '<div class="cards">' + ''.join(cards) + '</div>'
                      + '<div class="total"><div class="tl">' + _esc(t('Total paid')) + '</div>'
                      + '<div class="tv">' + _money(total) + ' ' + _esc(cur) + '</div></div>')
    else:
        taxes_html = ('<h2>' + _esc(t('Taxes & contributions')) + '</h2>'
                      + '<div class="note">' + _esc(t('No tax payments were due this month.')) + '</div>')

    # trend bars (last 6 months)
    bars = ''
    tr = [(p.get('period'), p.get('turnover_idr') if p.get('turnover_idr') is not None else p.get('income_usn'))
          for p in months[-6:]]
    tr = [(pp, vv) for pp, vv in tr if isinstance(vv, (int, float))]
    if len(tr) >= 2:
        mx = max(vv for _, vv in tr) or 1
        cells = []
        for i, (pp, vv) in enumerate(tr):
            h = max(8, round(vv / mx * 92))
            cls = 'bar cur' if i == len(tr) - 1 else 'bar'
            cells.append('<div class="' + cls + '" style="height:' + str(h) + 'px"><span>' + _esc(_period_short(pp)) + '</span></div>')
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
        tlbl=_esc(t('Turnover this month')), tnum=_money(turnover) + ' ', cur=_esc(cur),
        scope=scope_html, bars=bars, taxesblock=taxes_html,
        payroll=payroll_html, nextblock=next_html,
        print_lbl=_esc(t('Print / Save PDF')),
        foot=_esc(t('Prepared by')) + ': ' + _esc(BRAND_NAME or '') + ' · ' + _esc(BRAND_TAGLINE or ''),
        title=_esc(t('Client report')) + ' — ' + _esc(cname),
    )


_CSS = """
@page{size:A4;margin:0;}
*{box-sizing:border-box;}
body{font-family:Arial,Helvetica,sans-serif;margin:0;color:#232a31;background:#eef0f3;}
.sheet{max-width:210mm;margin:14px auto;background:#fff;padding:20mm 16mm 16mm;box-shadow:0 2px 18px rgba(0,0,0,.1);}
.noprint{max-width:210mm;margin:14px auto 0;text-align:right;}
.pbtn{background:#1F4E79;color:#fff;border:none;border-radius:8px;padding:9px 16px;font-size:14px;cursor:pointer;}
.brandbar{display:flex;align-items:center;gap:12px;border-bottom:2px solid #B79257;padding-bottom:12px;}
.mono{font-family:Georgia,serif;font-size:20pt;color:#1F4E79;border:2.5px solid #B79257;width:46px;height:46px;line-height:42px;text-align:center;border-radius:6px;font-weight:700;}
.brandtext .bn{font-family:Georgia,serif;font-size:15pt;color:#1F4E79;font-weight:700;}
.brandtext .bt{font-size:8.5pt;letter-spacing:.08em;color:#8a93a0;text-transform:uppercase;}
.rhead{margin-left:auto;text-align:right;}
.rhead .rt{font-size:8.5pt;color:#8a93a0;text-transform:uppercase;letter-spacing:.06em;}
.rhead .rv{font-size:12pt;color:#1F4E79;font-weight:700;}
.title{margin:18px 0 2px;font-family:Georgia,serif;font-size:18pt;color:#1F4E79;}
.subtitle{color:#6b7785;font-size:10pt;}
.hero{display:flex;gap:18px;margin:18px 0;align-items:flex-end;background:#f7f9fb;border:1px solid #e6ebf0;border-radius:12px;padding:16px 18px;}
.hero-l{flex:1;}
.hero-lbl{font-size:9pt;color:#8a93a0;text-transform:uppercase;letter-spacing:.06em;}
.hero-num{font-family:Georgia,serif;font-size:27pt;color:#1F4E79;font-weight:700;line-height:1.1;}
.hero-num small{font-size:13pt;color:#B79257;}
.hero-scope{font-size:8.5pt;color:#8a93a0;margin-top:5px;}
.note{border:1px solid #e6ebf0;border-radius:9px;padding:11px 14px;color:#3a4653;font-size:10pt;background:#f7f9fb;}
.chart{display:flex;align-items:flex-end;gap:8px;height:104px;padding-bottom:16px;}
.bar{width:28px;border-radius:4px 4px 0 0;background:#cdd8e4;position:relative;}
.bar.cur{background:#1F4E79;}
.bar span{position:absolute;bottom:-15px;left:0;right:0;text-align:center;font-size:7.5pt;color:#8a93a0;}
h2{font-size:12pt;color:#1F4E79;margin:22px 0 9px;font-family:Georgia,serif;}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.card{border:1px solid #e6ebf0;border-left:3px solid #B79257;border-radius:9px;padding:10px 13px;}
.card .ct{font-weight:700;color:#2a3744;font-size:10.5pt;}
.card .cd{font-size:9pt;color:#6b7785;margin-top:1px;line-height:1.4;}
.card .cv{font-size:13pt;color:#1F4E79;font-weight:700;margin-top:5px;}
.total{display:flex;justify-content:space-between;align-items:center;background:#1F4E79;color:#fff;border-radius:9px;padding:12px 16px;margin-top:10px;}
.total .tl{font-size:10.5pt;}.total .tv{font-family:Georgia,serif;font-size:16pt;font-weight:700;}
.muted2{color:#8a93a0;font-size:9pt;margin-top:6px;}
.next{display:flex;gap:10px;}
.nx{flex:1;border:1px solid #e6ebf0;border-radius:9px;padding:10px 12px;}
.nx .nd{color:#B79257;font-weight:700;font-size:10pt;}
.nx .nt{font-size:9pt;color:#3a4653;margin-top:2px;line-height:1.4;}
.foot{margin-top:24px;border-top:1px solid #e6ebf0;padding-top:11px;color:#8a93a0;font-size:8.5pt;}
@media print{.noprint{display:none;}body{background:#fff;}.sheet{box-shadow:none;margin:0;}}
"""

_PAGE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>{title}</title><style>{css}</style></head><body>
<div class="noprint"><button class="pbtn" onclick="window.print()">{print_lbl}</button></div>
<div class="sheet">
<div class="brandbar"><div class="mono">{mono}</div><div class="brandtext"><div class="bn">{bn}</div><div class="bt">{bt}</div></div>
<div class="rhead"><div class="rt">{rt}</div><div class="rv">{period}</div></div></div>
<div class="title">{cname}</div><div class="subtitle">{subtitle}</div>
<div class="hero"><div class="hero-l"><div class="hero-lbl">{tlbl}</div><div class="hero-num">{tnum}<small>{cur}</small></div>{scope}</div>{bars}</div>
{taxesblock}{payroll}
{nextblock}
<div class="foot">{foot}</div>
</div></body></html>"""
