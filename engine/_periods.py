# -*- coding: utf-8 -*-
"""_periods.py — "Periods" lens: the work viewed by reporting period.

Same content as the Plan / Calendar-List (the REAL expandable waves + shared
track rows), but grouped by REPORTING PERIOD ("close April" stays under April
even when its deadline slips into June). A view over state — writes nothing.
Complements the Plan (by horizon) and the Calendar (by due date).
"""
from generate import (
    DESIGN_TOKENS_CSS, OVERVIEW_SPECIFIC_CSS, NEW_JS_FRAGMENT, TODAY,
    _esc,
)
from _strings import t
from _sidebar import render_sidebar, SIDEBAR_CSS
from _overview_shared import render_header
from _overview_v2 import OVERVIEW_V2_CSS
from _aggregator import aggregate_tasks
from _css import PROMPT_MODAL_CSS, PROMPT_MODAL_HTML, PROMPT_MODAL_JS
from _track_modal import TRACK_MODAL_CSS, TRACK_MODAL_HTML, TRACK_MODAL_JS
from _mode_switch import MODE_SWITCH_CSS, MODE_SWITCH_JS, render_mode_switch
from _brief import ANALYSIS_CSS
import _plan_waves as PW
import _pipeline as P
import _cadence as _Cad

try:
    from _config import LOCALE as _LOC
except Exception:
    _LOC = 'ru'
_LOC = _LOC if _LOC in ('ru', 'en') else 'ru'

_DONE_STATUS = {'done', 'completed', 'cancelled', 'dropped', 'dismissed',
                'closed', 'resolved', 'deferred', 'paid'}

PERIODS_CSS = (
    '.page-title{font-size:19px;font-weight:600;color:var(--text-secondary);'
    'text-transform:uppercase;letter-spacing:.03em;margin:0 0 6px}'
    '.pp-sub{font-size:15px;color:var(--text-secondary);margin:0 0 var(--space-lg);max-width:62ch}'
    # ── per-period group: a period header + the real waves/tracks card ──
    '.pp-group{margin:0 0 16px;scroll-margin-top:16px}'
    '.pp-group-head{display:flex;align-items:center;gap:10px;margin:0 0 8px;padding:0 2px}'
    '.pp-group-head h3{font-size:14px;font-weight:700;text-transform:capitalize;'
    'letter-spacing:.01em;color:var(--text-primary);margin:0}'
    '.pp-cohort{font-size:12px;color:var(--accent-text);padding:2px 9px;background:var(--accent-soft);'
    'border:1px solid var(--accent-soft-border);border-radius:20px;font-weight:600}'
    '.pp-group.pp-over .pp-cohort{color:var(--accent-red);background:var(--red-bg);border-color:transparent}'
    '.pp-cad-band{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;'
    'color:var(--text-muted);margin:14px 0 8px;padding:0 2px}'
    '.pp-group .sec-card{margin-bottom:0}'
    '.pp-cycle-head{display:flex;align-items:center;gap:9px;font-weight:600;color:var(--text-secondary);'
    'text-transform:uppercase;letter-spacing:.06em;font-size:13px;margin:32px 0 20px}'
    '.pp-cycle-head::before{content:"";width:3px;height:13px;border-radius:2px;background:var(--gold)}'
    '.pp-juris-head{display:flex;align-items:center;gap:9px;font-weight:700;color:var(--text-secondary);'
    'text-transform:uppercase;letter-spacing:.05em;font-size:13px;margin:36px 0 20px}'
    '.pp-juris-head::before{content:"";width:3px;height:14px;border-radius:2px;background:var(--accent)}'
    # ── per-period vertical timeline of pipeline stages (waves + expected/empty) ──
    '.pp-tl{position:relative;padding:2px 2px 2px 0}'
    '.pp-tl-row{position:relative;display:flex;gap:14px;align-items:flex-start;padding:0 0 10px}'
    '.pp-tl-row:last-child{padding-bottom:0}'
    '.pp-tl-rail{position:relative;z-index:1;flex-shrink:0;width:16px;display:flex;'
    'justify-content:center;padding-top:14px}'
    '.pp-tl-row::after{content:"";position:absolute;left:7px;top:14px;width:2px;height:100%;'
    'background:var(--border);z-index:0}'
    '.pp-tl-row:last-child::after{display:none}'
    '.pp-tl-row.tl-last::after{display:none}'
    '.pp-tl-row.s-done::after{background:var(--accent-green)}'
    '.pp-tl-node{width:11px;height:11px;border-radius:50%;background:var(--bg-card);'
    'border:2px solid var(--border-strong)}'
    '.pp-tl-row.s-active .pp-tl-node{background:var(--accent);border-color:var(--accent)}'
    '.pp-tl-row.s-over .pp-tl-node{background:var(--accent-red);border-color:var(--accent-red)}'
    '.pp-tl-row.s-done .pp-tl-node{background:var(--accent-green);border-color:var(--accent-green)}'
    '.pp-tl-content{flex:1;min-width:0}'
    '.pp-tl-content .plan-item{border-bottom:none}'
    '.pp-tl-content .wave{border-bottom:none}'
    '.pp-stage-empty{display:flex;align-items:center;gap:10px;padding:8px var(--space-md) 8px 5px}'
    '.pp-stage-empty .wave-op{font-size:15px;font-weight:500;color:var(--text-muted)}'
    '.pp-stage-empty .wave-ic{color:var(--text-muted)}'
    # Periods filter is PERIOD-LEVEL: a shown period stays full — never hide the
    # individual waves/rows inside it, and the task-count banner doesn't apply.
    '.mode-banner{display:none}'
    'body.mode-team .pp-group .wave[data-track-type],body.mode-direct .pp-group .wave[data-track-type]{display:block!important}'
    'body.mode-team .pp-group .an-rec[data-track-type],body.mode-direct .pp-group .an-rec[data-track-type]{display:flex!important}'
    # Period is already the group header here — don't repeat it in every wave title.
    '.pp-group .wave-period{display:none}'
    '.pp-empty{padding:48px 24px;text-align:center;color:var(--text-muted);font-size:15px}'
)


def _cad_band_label(cad):
    """Localized sub-band header for a cadence within a cycle (Месяц / Квартал / Полугодие / Год)."""
    _L = {'monthly': ('Месяц', 'Monthly'), 'quarterly': ('Квартал', 'Quarterly'),
          'semester': ('Полугодие', 'Half-year'), 'annual': ('Год', 'Annual')}
    lab = _L.get(cad)
    if not lab:
        return ''
    return lab[0] if _LOC == 'ru' else lab[1]


def _fmt(p):
    return PW._fmt_period(p, _LOC)


def _plural_tasks(n):
    """Locale-correct task-count label: RU declension (1 задача / 2 задачи / 5 задач),
    EN simple plural."""
    if _LOC == 'ru':
        n10, n100 = n % 10, n % 100
        if n10 == 1 and n100 != 11:
            w = 'задача'
        elif 2 <= n10 <= 4 and not (12 <= n100 <= 14):
            w = 'задачи'
        else:
            w = 'задач'
        return str(n) + ' ' + w
    return str(n) + (' task' if n == 1 else ' tasks')


def _period_sort_key(p):
    """Chronological order. A month sorts to its month; an aggregating period sorts
    to the END of its span and AFTER the constituent months (sub-order 1=quarter,
    2=half-year), so May, June, Q2, H1 read in that order — never Q2 before May."""
    import re
    p = p or ''
    m = re.match(r'^(\d{4})-(\d{2})$', p)
    if m:
        return (int(m.group(1)), int(m.group(2)), 0)
    q = re.match(r'^(\d{4})-Q([1-4])$', p)
    if q:
        return (int(q.group(1)), int(q.group(2)) * 3, 1)   # quarter -> its END month
    h = re.match(r'^(\d{4})-H([12])$', p)
    if h:
        return (int(h.group(1)), int(h.group(2)) * 6, 2)   # half-year -> its END month
    return (9999, 99, 9)  # unknown / period-less last


PERIODS_BOARD_CSS = (
    ".pp-viewtoggle{display:inline-flex;border:0.5px solid var(--border-strong);border-radius:8px;overflow:hidden;margin:0 0 18px;font-size:13px}"
    ".pp-viewtoggle .vt{border:0;background:transparent;color:var(--text-secondary);padding:6px 16px;cursor:pointer;font:inherit}"
    ".pp-viewtoggle .vt + .vt{border-left:0.5px solid var(--border)}"
    ".pp-viewtoggle .vt.on{background:#1F4E79;color:#fff;font-weight:600}"
    ".pp-lane{display:flex;align-items:flex-start;gap:18px;padding:13px 0;border-bottom:0.5px solid var(--border)}"
    ".pp-lane .lname{width:170px;flex:none;font-size:13px;font-weight:600;color:var(--text-primary);line-height:1.25;padding-top:9px}"
    ".pp-lcards{display:flex;flex-wrap:wrap;gap:8px;align-items:center}"
    ".pp-lcard{display:flex;align-items:center;gap:10px;border:0.5px solid var(--border);border-radius:12px;padding:9px 13px;min-width:150px;background:#fff;text-decoration:none;cursor:pointer}"
    ".pp-lcard:hover{border-color:var(--border-strong)}"
    ".pp-ldot{width:9px;height:9px;border-radius:50%;flex:none}"
    ".pp-lcard .ltext{display:flex;flex-direction:column}"
    ".pp-lcard .lp{font-size:13px;font-weight:500;color:var(--text-primary);line-height:1.2}"
    ".pp-lcard .lm{font-size:11px;margin-top:1px;color:var(--text-secondary)}"
    ".pp-lclosed{display:flex;align-items:center;gap:6px;padding:9px 4px;color:var(--text-muted);font-size:12px}"
)

PERIODS_BOARD_JS = (
    "<script>(function(){"
    "function setView(v){var tl=document.getElementById('pp-timeline'),bd=document.getElementById('pp-board');"
    "if(!tl||!bd)return;tl.style.display=v==='board'?'none':'';bd.style.display=v==='board'?'':'none';"
    "[].forEach.call(document.querySelectorAll('.pp-viewtoggle .vt'),function(b){b.classList.toggle('on',b.getAttribute('data-view')===v);});}"
    "document.addEventListener('click',function(e){"
    "var vt=e.target.closest('.pp-viewtoggle .vt');if(vt){setView(vt.getAttribute('data-view'));return;}"
    "var cell=e.target.closest('.pp-lcard');if(cell&&cell.getAttribute('data-period')){var per=cell.getAttribute('data-period');setView('timeline');"
    "var g=document.querySelector('.pp-group[data-period=\"'+per+'\"]');if(g)g.scrollIntoView({behavior:'smooth',block:'center'});}"
    "});})();</script>"
)

def render_periods():
    today = TODAY
    all_tasks = aggregate_tasks(today).get('all', [])

    # ORIGINAL grouping, preserved: JURISDICTION -> CYCLE -> reporting PERIOD. Only the
    # VIEW inside each period changes (real waves + tracks instead of the stage stepper).
    # Period-anchored pipeline tasks only — same scope/idea as the original page.
    by = {}
    for tk in all_tasks:
        op = PW._op_canonical(tk)
        if not (isinstance(op, str) and op.startswith('stage:')):
            continue
        juris = PW._client_jurisdiction(tk.get('client_id')) or 'ru'
        code, _, per = op[len('stage:'):].partition('|')
        cyc = P.cycle_of_stage(code, juris) or 'monthly_close'
        by.setdefault(juris, {}).setdefault(cyc, {}).setdefault(per or '', []).append(tk)

    # Reuse the Plan's REAL wave + track-row components (same indexes the Plan builds).
    from _plan_today import _render_task_row, _index_blocker_titles, _track_type_for
    _index_blocker_titles(all_tasks)
    try:
        from _mental_model import load_mental_models as _lmm
        from _track_attrs import build_mm_tracks_index
        _mm_index = build_mm_tracks_index(_lmm())
    except Exception:
        _mm_index = {}

    def _plan_row(tk):
        return _render_task_row(tk, _mm_index)
    PW._RENDER_ROW = _plan_row

    def _period_timeline(juris, cyc_code, per, tasks):
        # The pipeline's OWN stage order (from the jurisdiction pack) is the timeline:
        # each stage is a node, present stages render the real wave, stages with no
        # work yet render a dimmed «expected» placeholder. Vertical connector links them.
        stages = P.stages(juris, cycle=cyc_code)
        waves, singles = PW.cluster_tasks(tasks)
        wmap = {}
        for members in waves:
            tok = PW._op_canonical(members[0])
            if isinstance(tok, str) and tok.startswith('stage:'):
                wmap.setdefault(tok[len('stage:'):].split('|')[0], members)
        rows = []
        for sdef in stages:
            code = sdef['code']
            members = wmap.pop(code, None)
            if members:
                openc = sum(1 for m in members if (m.get('status') or '').lower() not in _DONE_STATUS)
                over = any((m.get('days_left') is not None and m['days_left'] < 0) for m in members)
                stt = 'done' if openc == 0 else ('over' if over else 'active')
                content = '<div class="plan-item">' + PW._render_wave(members, _esc, 'per') + '</div>'
            else:
                stt = 'none'
                from _icons import icon as _icon
                _ica = P.stage_attr(code, juris, 'icon')
                _ic = _icon(_ica) if _ica else _icon(code)
                content = ('<div class="pp-stage-empty"><span class="wave-chevron"></span>'
                           '<span class="wave-op"><span class="wave-ic">' + _ic + '</span>'
                           + _esc(P.stage_title(code, _LOC, juris)) + '</span></div>')
            rows.append('<div class="pp-tl-row s-' + stt + '">'
                        '<span class="pp-tl-rail"><span class="pp-tl-node"></span></span>'
                        '<div class="pp-tl-content">' + content + '</div></div>')
        # any waves/singles NOT matched to a stage of this cycle (defensive) — append as active
        for members in wmap.values():
            rows.append('<div class="pp-tl-row s-active"><span class="pp-tl-rail"><span class="pp-tl-node"></span></span>'
                        '<div class="pp-tl-content"><div class="plan-item">' + PW._render_wave(members, _esc, 'per') + '</div></div></div>')
        for x in singles:
            rows.append('<div class="pp-tl-row s-active"><span class="pp-tl-rail"><span class="pp-tl-node"></span></span>'
                        '<div class="pp-tl-content"><div class="plan-item plan-single">' + _plan_row(x) + '</div></div></div>')
        return '<section class="sec-card"><div class="pp-tl">' + ''.join(rows) + '</div></section>'

    def _juris_name(juris):
        try:
            import _jurisdiction as _J
            mani = _J.load_jurisdiction(juris).manifest
            return (mani.get('name_i18n') or {}).get(_LOC) or mani.get('name') or juris.upper()
        except Exception:
            return juris.upper()

    def _period_group(juris, cyc_code, per, tasks):
        over = any((tk.get('days_left') is not None and tk['days_left'] < 0) for tk in tasks)
        label = _fmt(per) if per else t('No period')
        gcls = 'pp-group' + (' pp-over' if over else '')
        trks = {_track_type_for(tk.get('client_id')) for tk in tasks}
        ht = '1' if 'team' in trks else '0'
        hd = '1' if 'direct' in trks else '0'
        return ('<div class="' + gcls + '" data-period="' + _esc(per) + '" '
                'data-has-team="' + ht + '" data-has-direct="' + hd + '">'
                '<div class="pp-group-head"><h3>' + _esc(label) + '</h3>'
                '<span class="pp-cohort">' + _esc(_plural_tasks(len(tasks))) + '</span></div>'
                + _period_timeline(juris, cyc_code, per, tasks) + '</div>')

    def _cycle_title(c):
        return (c.get('title') or {}).get(_LOC) or (c.get('title') or {}).get('en') or c['code']

    def _juris_render(juris):
        # cycle bands (primary stays headerless, like the original single pipeline),
        # then its reporting periods CHRONOLOGICALLY, each with its waves + tracks.
        out = []
        cyc_map = by.get(juris, {})
        for c in P.cycles(juris):
            pmap = cyc_map.get(c['code'])
            if not pmap:
                continue
            # Label EVERY cycle (incl. the primary one) so the first section is never an
            # unnamed block and a period repeated across cycles reads unambiguously.
            out.append('<h3 class="pp-cycle-head">' + _esc(_cycle_title(c)) + '</h3>')
            _pers = sorted(pmap.keys(), key=_period_sort_key)
            _ORDER = ['monthly', 'quarterly', 'semester', 'annual']
            _cad_of = {pp: (_Cad.period_cadence(pp) or '') for pp in _pers}
            _bands = [b for b in _ORDER if any(_cad_of[pp] == b for pp in _pers)]
            _unknown = [pp for pp in _pers if _cad_of[pp] not in _ORDER]
            # Cadence sub-bands ONLY when the cycle spans more than one cadence: a monthly-only
            # cycle stays flat; a mixed one (months + a quarter/half-year batch, or the tax
            # umbrella's quarter/half/year) splits into Месяц / Квартал / Полугодие / Год bands.
            if len(_bands) + (1 if _unknown else 0) > 1:
                for _b in _ORDER:
                    _members = [pp for pp in _pers if _cad_of[pp] == _b]
                    if not _members:
                        continue
                    out.append('<h4 class="pp-cad-band">' + _esc(_cad_band_label(_b)) + '</h4>')
                    for per in _members:
                        out.append(_period_group(juris, c['code'], per, pmap[per]))
                for per in _unknown:
                    out.append(_period_group(juris, c['code'], per, pmap[per]))
            else:
                for per in _pers:
                    out.append(_period_group(juris, c['code'], per, pmap[per]))
        return ''.join(out)

    def _board_render():
        order = (['ru'] if by.get('ru') else []) + sorted(j for j in by if j != 'ru')
        lanes = []
        for juris in order:
            cyc_map = by.get(juris, {})
            for c in P.cycles(juris):
                pmap = cyc_map.get(c['code'])
                if not pmap:
                    continue
                lab = _cycle_title(c) + ('' if juris == 'ru' else ' · ' + _juris_name(juris))
                lanes.append((lab, pmap))
        if not lanes:
            return ''
        _DOT = {'over': '#A32D2D', 'soon': '#BA7517', 'act': '#1F4E79', 'up': '#888780'}

        def _card(per, tasks):
            openc = sum(1 for tk in tasks if (tk.get('status') or '').lower() not in _DONE_STATUS)
            over = any((tk.get('days_left') is not None and tk['days_left'] < 0) for tk in tasks)
            dl = [tk['days_left'] for tk in tasks if tk.get('days_left') is not None and tk['days_left'] >= 0]
            mind = min(dl) if dl else None
            cnt = _plural_tasks(openc)
            if over:
                st, rank, tail = 'over', -1, ('просрочено' if _LOC == 'ru' else 'overdue')
            elif mind is not None and mind <= 7:
                st, rank, tail = 'soon', mind, (('через ' + str(mind) + ' дн') if _LOC == 'ru' else ('in ' + str(mind) + 'd'))
            elif mind is not None:
                st, rank, tail = 'act', mind, (('через ' + str(mind) + ' дн') if _LOC == 'ru' else ('in ' + str(mind) + 'd'))
            else:
                st, rank, tail = 'up', 99999, ''
            meta = cnt + (' · ' + tail if tail else '')
            html = ('<a class="pp-lcard" data-period="' + _esc(per) + '">'
                    '<span class="pp-ldot" style="background:' + _DOT[st] + '"></span>'
                    '<span class="ltext"><span class="lp">' + _esc(_fmt(per)) + '</span>'
                    '<span class="lm"' + (' style="color:#A32D2D"' if st == 'over' else '') + '>' + meta + '</span></span></a>')
            return rank, html

        out = []
        for lab, pmap in lanes:
            cards, closed = [], 0
            for per, tasks in pmap.items():
                openc = sum(1 for tk in tasks if (tk.get('status') or '').lower() not in _DONE_STATUS)
                if openc == 0:
                    closed += 1
                else:
                    cards.append(_card(per, tasks))
            cards.sort(key=lambda x: x[0])
            inner = ''.join(h for _, h in cards)
            if closed:
                inner += ('<span class="pp-lclosed">✓ ' + str(closed)
                          + (' закрыто' if _LOC == 'ru' else ' closed') + '</span>')
            if not inner:
                continue
            out.append('<div class="pp-lane"><div class="lname">' + _esc(lab)
                       + '</div><div class="pp-lcards">' + inner + '</div></div>')
        return ''.join(out)

    # RU first with no jurisdiction header (the default practice); other
    # jurisdictions follow under a labelled band so their cycles never blend in.
    blocks = []
    if by.get('ru'):
        blocks.append(_juris_render('ru'))
    for juris in sorted(j for j in by if j != 'ru'):
        blocks.append('<h2 class="pp-juris-head">' + _esc(_juris_name(juris)) + '</h2>'
                      + _juris_render(juris))

    body = ''.join(blocks) if blocks else '<div class="pp-empty">' + t('No monthly-cycle tasks.') + '</div>'

    # Mode switch with REAL counts over the displayed (pipeline) tasks, so the
    # filter banner reads correctly instead of an empty "Показано of".
    _disp = [tk for cm in by.values() for pm in cm.values() for ts in pm.values() for tk in ts]
    _n_all = len(_disp)
    _n_team = sum(1 for tk in _disp if _track_type_for(tk.get('client_id')) == 'team')
    _n_direct = sum(1 for tk in _disp if _track_type_for(tk.get('client_id')) == 'direct')
    mode_html = render_mode_switch(_n_all, _n_team, _n_direct)

    # The generic mode-switch hides individual rows/waves; on a grouped page that
    # leaves behind empty period cards + cycle/jurisdiction headers. This re-runs
    # after every filter change and collapses any group/header with nothing visible.
    pp_filter_js = (
        '<script>(function(){'
        'function sectionHasVisible(h,jurisOnly){var n=h.nextElementSibling;'
        'while(n){if(n.classList.contains("pp-juris-head"))break;'
        'if(!jurisOnly&&n.classList.contains("pp-cycle-head"))break;'
        'if(n.classList.contains("pp-group")&&n.style.display!=="none")return true;'
        'n=n.nextElementSibling;}return false;}'
        'function refilter(){'
        'var m=document.body.classList.contains("mode-team")?"team":(document.body.classList.contains("mode-direct")?"direct":"all");'
        '[].forEach.call(document.querySelectorAll(".pp-group"),function(g){'
        'g.style.display=(m==="all"||g.getAttribute("data-has-"+m)==="1")?"":"none";});'
        '[].forEach.call(document.querySelectorAll(".pp-cycle-head,.pp-juris-head"),function(h){'
        'h.style.display=sectionHasVisible(h,h.classList.contains("pp-juris-head"))?"":"none";});}'
        'document.addEventListener("click",function(e){'
        'if(e.target.closest(".mode-btn,.mode-banner-clear"))setTimeout(refilter,0);});'
        'if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",function(){setTimeout(refilter,0);});'
        'else setTimeout(refilter,0);})();</script>')
    head = render_header()
    _board_html = _board_render()
    _tl = '\u0422\u0430\u0439\u043c\u043b\u0430\u0439\u043d' if _LOC == 'ru' else 'Timeline'
    _bd = '\u0414\u043e\u0441\u043a\u0430' if _LOC == 'ru' else 'Board'
    _view_toggle = ('<div class="pp-viewtoggle">'
                    '<button class="vt on" data-view="timeline">' + _tl + '</button>'
                    '<button class="vt" data-view="board">' + _bd + '</button></div>') if _board_html else ''
    title = t('Periods')
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>' + _esc(title) + '</title>'
        '<style>' + DESIGN_TOKENS_CSS + OVERVIEW_SPECIFIC_CSS + OVERVIEW_V2_CSS + SIDEBAR_CSS
        + PROMPT_MODAL_CSS + TRACK_MODAL_CSS + MODE_SWITCH_CSS + PW.WAVES_CSS + ANALYSIS_CSS + PERIODS_CSS + PERIODS_BOARD_CSS + '</style>'
        '</head><body><div class="layout-shell">'
        + render_sidebar(active='periods')
        + '<main class="main-content">' + head
        + '<h1 class="page-title">' + title + '</h1>'
        + '<div class="pp-sub">' + t('Work grouped by cycle, with its waves and tasks.') + '</div>'
        + mode_html
        + _view_toggle
        + '<div id="pp-timeline">' + body + '</div>'
        + '<div id="pp-board" style="display:none">' + _board_html + '</div>'
        + '</main></div>'
        + PROMPT_MODAL_HTML + TRACK_MODAL_HTML
        + NEW_JS_FRAGMENT + PROMPT_MODAL_JS + TRACK_MODAL_JS + MODE_SWITCH_JS + PW.WAVES_JS + pp_filter_js + PERIODS_BOARD_JS
        + '</body></html>'
    )
