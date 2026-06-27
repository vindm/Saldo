"""_plan_today.py — the "Plan — Today" page.

An actionable list of today's tasks grouped by category. A task row has exactly
one action: click it to open the track modal (where "Разобрать" hands it to the
runtime via the shared prompt modal). Per-row Discuss/Dictate buttons were
removed in the one-modal/one-button unification.
"""
import json
import os

from generate import (
    clients, TODAY,
    _esc, _esca,
    DESIGN_TOKENS_CSS, OVERVIEW_SPECIFIC_CSS, NEW_JS_FRAGMENT,
)
from _helpers import _format_date_ru, _translate_tech_terms, client_avatar
from _strings import t
from _status import status_pill as _status_pill, normalize_status
_t = t  # alias: several local helpers bind `t` to the task dict, shadowing the import
from _track_attrs import build_track_data_attrs, build_mm_tracks_index
from _overview_v2 import OVERVIEW_V2_CSS
from _overview_shared import render_header
from _sidebar import render_sidebar, SIDEBAR_CSS
from _css import PROMPT_MODAL_CSS, PROMPT_MODAL_HTML, PROMPT_MODAL_JS
from _mode_switch import MODE_SWITCH_HTML, MODE_SWITCH_CSS, MODE_SWITCH_JS, render_mode_switch
from _analytics_widgets import render_kpi_band, KPI_BAND_CSS
from _aggregator import aggregate_tasks
from _track_modal import TRACK_MODAL_CSS, TRACK_MODAL_HTML, TRACK_MODAL_JS
from _assistant_brief import render_assistant_rec_card, ASSISTANT_BRIEF_CSS
from _brief import ANALYSIS_CSS as _AN_CSS
from _plan_waves import (render_waves_page, render_waves_flat, horizon_counts,
                         _fmt_period, WAVES_CSS, WAVES_JS)


SCENARIO_RU = {
    'A': t('USN'), 'B': t('USN+Patent'), 'B+E': t('WB+Patent'),
    'C': t('video+self-employed'), 'D': t('rental'), 'E': t('WB'), 'F': t('AUSN'),
}


def _human_date(d):
    """Compact, locale-aware human date: '5 июля' (ru) / '5 July' (en). No weekday."""
    from _strings import MONTHS_GEN
    return f"{d.day} {MONTHS_GEN[d.month - 1]}"


def _format_due(t):
    """Due-date label for the task row — THE shared due badge (engine/_components),
    so the plan and the client hero render the exact same chip. One definition."""
    from _components import due_badge
    return due_badge(t.get('days_left'))


def _track_meta(t):
    """(label, kind) for the quiet regime/group token. kind: direct/team/ausn/sys."""
    track = t.get('track')
    if not track:
        return (_t('general'), 'sys')
    if track == 'team':
        return (_t('team'), 'team')
    cid = t.get('client_id')
    if cid:
        for c in clients:
            if c['id'] == cid:
                scn = c.get('scenario') or ''
                if scn == 'F':
                    return (_t('AUSN'), 'ausn')
                if scn:
                    return (_esc(SCENARIO_RU.get(scn, scn)), 'direct')
    return (_t('direct'), 'direct')


def _pill_for(t):
    """Filled pill — used in non-plan views (clients list, legend)."""
    label, kind = _track_meta(t)
    return f'<span class="pill pill-{kind}">{label}</span>'


SOURCE_LABEL = {
    'calendar': 'calendar',
    'monthly_check': 'monthly_check',
    'finkoper': 'finkoper',
    'request': 'request log',
    'track': 'mental_model',
    'update': 'updater',
    'tg': 'Telegram',
}



def _due_text(t):
    dl = t.get('days_left')
    due = t.get('due_date')
    if dl is None:
        return ''
    if dl < 0:
        return _t('overdue {}d').format(-dl)
    if dl == 0:
        return _t('today')
    if dl <= 3:
        if due:
            return _t('in {}d · {}').format(dl, _human_date(due))
        return _t('in {}d').format(dl)
    if due:
        return _t('{} · {}d').format(_human_date(due), dl)
    return _t('{}d').format(dl)


def _track_type_for(client_id):
    """team or direct by client_id."""
    try:
        from generate import clients
        for c in clients:
            if c.get('id') == client_id:
                return c.get('group', 'team')
    except Exception:
        pass
    return 'team'


_BLOCKER_TITLES = {}
_BLOCKER_TASKS = {}
_BLOCK_COUNTS = {}


def _index_blocker_titles(tasks):
    """Index the active task set so a blocked row can (a) name + link to its
    blocker, and (b) show «разблокирует N» — the reverse-dependency count. Keyed by
    both id and source_ref (the plan stores the real id in source_ref)."""
    _BLOCKER_TITLES.clear()
    _BLOCKER_TASKS.clear()
    _BLOCK_COUNTS.clear()
    for x in (tasks or []):
        ttl = x.get('what') or x.get('title') or ''
        for k in (x.get('id'), x.get('source_ref')):
            if k:
                if ttl:
                    _BLOCKER_TITLES[k] = ttl
                _BLOCKER_TASKS[k] = x
        for b in (x.get('blocked_by') or []):
            if b:
                _BLOCK_COUNTS[b] = _BLOCK_COUNTS.get(b, 0) + 1


def _attrs_for(task, mm_index=None):
    """data-track-* attribute string for a task (so a row/dep chip opens the
    canonical modal). Same construction the row uses for itself."""
    cid = task.get('client_id') or ''
    tid = (task.get('id') or task.get('source_ref') or '')[:60]
    full = None
    if mm_index is not None:
        full = mm_index.get((cid, tid)) or mm_index.get(('', tid))
    tfa = dict(task)
    tfa['source'] = SOURCE_LABEL.get(task.get('source', ''), task.get('source', ''))
    tfa['badge'] = _due_text(task)
    tfa['track_id'] = task.get('source_ref') or tfa.get('id')
    return build_track_data_attrs(tfa, _esca, today=TODAY, mm_track=full,
                                  track_type_for=_track_type_for)


def _render_task_row(t, mm_index=None, show_client_meta=True):
    """Build a snippet item from an aggregator task and render it with THE shared
    task snippet (engine/_brief.render_task_snippet). `show_client_meta` carries the
    «признаки клиента» (avatar + client line) — True on the cross-client Plan, False
    on a single client's card."""
    from _brief import render_task_snippet
    client_name = t.get('client_name', '')
    cid = t.get('client_id') or ''
    track_id = (t.get('id') or t.get('source_ref') or '')[:60]
    full_track = None
    if mm_index is not None:
        full_track = mm_index.get((cid, track_id)) or mm_index.get(('', track_id))

    # Status pill — hide the DEFAULT 'active' (pure noise); a still-«active» task
    # with an open blocker falls through with no pill, and the snippet derives the
    # «заблокировано» badge from the blocker. Rendered as the shared .an-status chip.
    status_html = ''
    _sp = _status_pill(t.get('status'))
    if _sp and normalize_status(t.get('status')) != 'active':
        _lab, _bg, _fg = _sp
        status_html = ('<span class="an-status" style="background:' + _bg + ';color:' + _fg + '">'
                       + _esc(_lab) + '</span>')

    data_attrs = _attrs_for(t, mm_index)

    # Third line = system hypothesis (assist lens), else next_action — same priority
    # the modal uses; replaced by the blocker chip when blocked.
    details = t.get('details') or {}
    next_text = details.get('next_action', '') or ''
    if next_text == '—':
        next_text = ''
    hypo_text = (t.get('assist') or {}).get('hypothesis') or ''
    inline_text = (hypo_text or next_text).replace('\n', ' ').strip()
    if len(inline_text) > 160:
        inline_text = inline_text[:160].rstrip() + '…'

    # Open blocker → name + link it (the snippet renders the «🔒 → <blocker>» chip).
    blocker_title = ''
    blocker_attrs = ''
    _bb = t.get('blocked_by') or (full_track or {}).get('blocked_by') or []
    for _b in _bb:
        _bt = _BLOCKER_TITLES.get(_b)
        if _bt:
            blocker_title = _translate_tech_terms(_bt)
            _bobj = _BLOCKER_TASKS.get(_b)
            blocker_attrs = _attrs_for(_bobj, mm_index) if _bobj else (' data-dep-id="' + _esca(_b) + '"')
            break

    # «разблокирует N» — reverse-dependency count keyed by this task's real id.
    unblocks = _BLOCK_COUNTS.get(t.get('source_ref')) or _BLOCK_COUNTS.get(t.get('id')) or 0

    # Reporting period of the row — EXPLICIT only (not the due-date fallback), so a
    # row never shows a misleading period. Plan/Calendar group purely by operation
    # (waves are period-less), so each row carries its own period chip.
    _ts = t.get('type_specific') or {}
    _per_raw = (t.get('period') or _ts.get('period') or _ts.get('quarter')
                or _ts.get('service_quarter') or '')
    period_label = _fmt_period(str(_per_raw)) if _per_raw else ''

    item = {
        'title': _translate_tech_terms(t.get('what', '')),
        'attrs': data_attrs,
        'priority': t.get('priority', 'normal'),
        'next_action': _translate_tech_terms(inline_text),
        'blocker_title': blocker_title,
        'blocker_attrs': blocker_attrs,
        'unblocks': unblocks,
        'due_days': t.get('days_left'),
        'status_html': status_html,
        'period': period_label,
    }
    if show_client_meta:
        item['client'] = client_name
        item['avatar'] = client_avatar(client_name)
    return render_task_snippet(item, _esc, kind='task')


def _render_group(group_key, title, icon, color_cls, tasks, limit=None, mm_index=None):
    """One group block. If a limit is set and there are more tasks, the rest are hidden under details."""
    if not tasks:
        return (
            '<section class="group ' + color_cls + '">'
            '<div class="group-head">'
            '<span class="group-icon">' + icon + '</span>'
            '<h3>' + title + '</h3>'
            '<span class="group-count">0</span>'
            '</div>'
            '<div class="group-empty">' + t('— empty —') + '</div>'
            '</section>'
        )
    if limit and len(tasks) > limit:
        visible_html = ''.join(_render_task_row(t, mm_index) for t in tasks[:limit])
        hidden_html = ''.join(_render_task_row(t, mm_index) for t in tasks[limit:])
        hidden_n = len(tasks) - limit
        details_html = (
            '<details class="group-more-details">'
            '<summary>' + t('Show {} more').format(hidden_n) + ' ▾</summary>'
            + hidden_html +
            '</details>'
        )
        body_html = visible_html + details_html
    else:
        body_html = ''.join(_render_task_row(t, mm_index) for t in tasks)
    return (
        '<section class="group ' + color_cls + '">'
        '<div class="group-head">'
        '<span class="group-icon">' + icon + '</span>'
        '<h3>' + title + '</h3>'
        '<span class="group-count">' + str(len(tasks)) + '</span>'
        '</div>'
        + body_html +
        '</section>'
    )


def render_plan_today():
    """Main page function."""
    groups = aggregate_tasks(TODAY)
    _index_blocker_titles(groups['all'])
    # Index of mental_model tracks to enrich the task objects
    try:
        from _mental_model import load_mental_models as _lmm
        mm_index = build_mm_tracks_index(_lmm())
    except Exception:
        mm_index = {}

    n_total = len(groups['all'])

    head = render_header()
    title = t('Plan — Today')

    # Group blocks — the "work waves" view by horizon (a VIEW, no writes to state)
    assistant_card = render_assistant_rec_card(groups)
    blocks_html = render_waves_flat(
        groups['all'], lambda t: _render_task_row(t, mm_index), _esc,
        period_aware=False,
    )

    # Live counts for the All/Team/Direct switcher (was hardcoded 15/6/9).
    _ms_all = len(groups['all'])
    _ms_team = sum(1 for x in groups['all'] if _track_type_for(x.get('client_id')) == 'team')
    _ms_direct = sum(1 for x in groups['all'] if _track_type_for(x.get('client_id')) == 'direct')
    mode_switch_html = render_mode_switch(_ms_all, _ms_team, _ms_direct)

    # Honest buckets that match what the page actually shows. The old
    # near/planned/backlog split leaked a "backlog" count that mapped to no
    # visible section (dateless sub-tasks get absorbed into their operation
    # waves; far-future items render in the list with their dates). We now show
    # only what the reader can point at: total, the next-7-days slice, and "the
    # rest" (everything dated later + the Waiting lane).
    _near = horizon_counts(groups['all'])['near']
    _rest = n_total - _near
    # Page-header KPI band — the SAME component as overview / clients / client
    # cockpit. The leading «В работе» tile shares its label AND its number with
    # the overview band (both = aggregate_tasks(TODAY)['all']) — one definition,
    # one look. Horizon split (next-7 / later) stays as Plan-specific tiles.
    summary = render_kpi_band([
        {'num': n_total, 'label': t('Open items')},
        {'num': _near,   'label': t('Next 7 days'), 'tone': 'amber'},
        {'num': _rest,   'label': t('Later')},
    ])

    extra_css = (
        '.page-title{font-size:19px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.03em;margin:0 0 6px}'
        '.group{background:var(--bg-card);border:1px solid var(--border);'
        'border-radius:var(--radius-card);padding:0;margin-bottom:var(--space-md);'
        'border-left-width:3px}'
        '.group.g-red{border-left-color:var(--accent-red)}'
        '.group.g-amber{border-left-color:var(--accent-yellow)}'
        '.group.g-blue{border-left-color:var(--accent-blue)}'
        '.group.g-grey{border-left-color:var(--border)}'
        '.group-head{display:flex;align-items:center;gap:var(--space-sm);'
        'padding:12px var(--space-md);border-bottom:1px solid var(--border);'
        'background:var(--bg-page);border-radius:0 var(--radius-card) 0 0}'
        '.group-head h3{font-size:17px;font-weight:600;margin:0;flex:1}'
        '.group-icon{font-size:18px}'
        '.group-count{font-size:14px;color:var(--text-secondary);padding:2px 10px;'
        'background:var(--bg-card);border-radius:10px;border:1px solid var(--border);font-weight:500}'
        '.group-empty{padding:var(--space-md);text-align:center;color:var(--text-muted);'
        'font-size:15px}'
        '.group-more{padding:8px var(--space-md);text-align:center;color:var(--text-muted);'
        'font-size:14px;border-top:1px dashed var(--border)}'
        '.task-item{border-bottom:1px solid var(--border);cursor:pointer;'
        'transition:background var(--transition)}'
        '.task-item:last-child{border-bottom:none}'
        '.task-item:hover{background:var(--bg-page)}'
        '.task-row{display:grid;grid-template-columns:auto 1fr auto;gap:11px;'
        'align-items:center;padding:9px 14px}'
        '.task-avatar{width:30px;height:30px;border-radius:50%;flex-shrink:0;'
        'display:flex;align-items:center;justify-content:center;font-size:12px;'
        'font-weight:600;background:var(--bg-page);color:var(--text-muted)}'
        '.task-avatar.task-reg-direct{background:#E6F1FB;color:#185FA5}'
        '.task-avatar.task-reg-ausn{background:#FAEEDA;color:#854F0B}'
        '.task-avatar.task-reg-team{background:#F1EFE8;color:#5F5E5A}'
        '.task-avatar.task-reg-sys{background:#EEEDFE;color:#534AB7}'
        '.task-body{min-width:0;overflow:hidden}'
        '.task-what{color:var(--text-primary);font-size:15px;font-weight:600;'
        'line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
        '.task-sub{display:flex;align-items:baseline;gap:6px;margin-top:1px;min-width:0}'
        '.task-client{font-size:12.5px;color:var(--text-muted);white-space:nowrap;'
        'overflow:hidden;text-overflow:ellipsis}'
        '.task-reg{font-size:11.5px;color:#8a8980;white-space:nowrap;flex-shrink:0}'
        '.task-reg::before{content:"\\00b7 ";color:#c4c2ba}'
        '.task-next-inline{font-size:12.5px;color:var(--text-muted);margin-top:2px;'
        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
        '.task-dep{display:inline-flex;align-items:center;gap:5px;margin-top:4px;padding:4px 9px;'
        'background:transparent;border-radius:6px;font-size:12px;font-weight:500;color:#8A6730;cursor:pointer;max-width:100%;transition:background var(--transition)}'
        '.task-dep .dep-arrow{color:var(--text-muted);flex-shrink:0;white-space:nowrap}'
        '.task-dep:hover{background:var(--yellow-bg)}'
        # fixed columns so the status + due badges never jump between rows
        '.task-meta{display:grid;grid-template-columns:auto 96px;gap:8px;align-items:center;'
        'font-size:13px;flex-shrink:0;font-weight:500}'
        '.tm-cell{display:flex;justify-content:flex-end;min-width:0}'
        '.task-status{font-size:11.5px;padding:2px 8px;border-radius:9px;'
        'white-space:nowrap;font-weight:600;letter-spacing:.01em}'
        '.pill{font-size:15px;padding:2px 8px;border-radius:10px;font-weight:600;'
        'border:1px solid transparent;white-space:nowrap;letter-spacing:.02em}'
        '.pill-team{background:var(--bg-page);color:var(--text-secondary);'
        'border-color:var(--border)}'
        '.pill-direct{background:#E6F1FB;color:#0C447C;border-color:#B5D4F4}'
        '.pill-ausn{background:#FAEEDA;color:#633806;border-color:#FAC775}'
        '.pill-sys{background:#EEEDFE;color:#3C3489}'
        '.due-overdue{color:var(--accent-red);font-weight:600}'
        '.due-today{color:var(--accent-red);font-weight:600}'
        '.due-soon{color:#B8893A;font-weight:500}'
        '.due-plan{color:var(--text-secondary)}'
        '.group-more-details{border-top:1px dashed var(--border)}'
        '.group-more-details summary{padding:10px var(--space-md);cursor:pointer;'
        'font-size:15px;color:var(--accent-blue);background:var(--bg-page);'
        'list-style:none;text-align:center;font-weight:500}'
        '.group-more-details summary::-webkit-details-marker{display:none}'
        '.group-more-details summary:hover{background:var(--bg-card);color:var(--accent-blue)}'
        '.group-more-details[open] summary{border-bottom:1px solid var(--border)}'
    )

    return (
        '<!DOCTYPE html>\n<html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMTUuNSIgZmlsbD0iIzFGNEU3OSIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMTYiIHI9IjEyLjciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0I3OTI1NyIgc3Ryb2tlLXdpZHRoPSIxLjMiLz48dGV4dCB4PSIxNiIgeT0iMTciIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIiBmb250LWZhbWlseT0iQXJpYWwsSGVsdmV0aWNhLHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTQiIGZvbnQtd2VpZ2h0PSI3MDAiIGZpbGw9IiNmZmZmZmYiPtCY0JI8L3RleHQ+PC9zdmc+">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>' + _esc(title) + '</title>'
        '<style>' + DESIGN_TOKENS_CSS + OVERVIEW_SPECIFIC_CSS + OVERVIEW_V2_CSS
        + SIDEBAR_CSS + PROMPT_MODAL_CSS  + TRACK_MODAL_CSS + MODE_SWITCH_CSS + ASSISTANT_BRIEF_CSS + _AN_CSS + KPI_BAND_CSS + extra_css + WAVES_CSS + '</style>'
        '</head><body>'
        '<div class="layout-shell">'
        + render_sidebar(
            active='plan_today',
            counts={'plan_today': _near}
        )
        + '<main class="main-content">'
        + head
        + summary
        + mode_switch_html
        + blocks_html
        + '</main></div>'
                + PROMPT_MODAL_HTML  + TRACK_MODAL_HTML
        + NEW_JS_FRAGMENT + PROMPT_MODAL_JS  + TRACK_MODAL_JS + MODE_SWITCH_JS + WAVES_JS +
        '</body></html>'
    )


# ── Reusable per-client plan block ───────────────────────────────────────────
# The SAME plan rendering as the Plan page, scoped to one client (for the client
# card). For a single client no multi-client waves form, so it reads as the
# client's tasks grouped by horizon (Горит/Неделя/Бэклог) with clickable rows.
# Self-contained (own <style>/<script>) so callers drop it in without wiring CSS.
PLAN_BLOCK_CSS = (
    '.group{background:var(--bg-card);border:1px solid var(--border);'
    'border-radius:var(--radius-card);padding:0;margin-bottom:var(--space-md);border-left-width:3px}'
    '.group.g-red{border-left-color:var(--accent-red)}'
    '.group.g-amber{border-left-color:var(--accent-yellow)}'
    '.group.g-blue{border-left-color:var(--accent-blue)}'
    '.group.g-grey{border-left-color:var(--border)}'
    '.group-head{display:flex;align-items:center;gap:var(--space-sm);'
    'padding:10px var(--space-md);border-bottom:1px solid var(--border);background:var(--bg-page)}'
    '.group-head h3{font-size:16px;font-weight:600;margin:0;flex:1}'
    '.group-icon{font-size:17px}'
    '.group-count{font-size:13px;color:var(--text-secondary);padding:2px 9px;'
    'background:var(--bg-card);border-radius:10px;border:1px solid var(--border);font-weight:500}'
    '.task-item{border-bottom:1px solid var(--border);cursor:pointer;transition:background var(--transition)}'
    '.task-item:last-child{border-bottom:none}'
    '.task-item:hover{background:var(--bg-page)}'
    '.task-row{display:grid;grid-template-columns:auto 1fr auto;gap:11px;'
    'align-items:center;padding:9px 14px}'
    '.task-avatar{width:30px;height:30px;border-radius:50%;flex-shrink:0;'
    'display:flex;align-items:center;justify-content:center;font-size:12px;'
    'font-weight:600;background:var(--bg-page);color:var(--text-muted)}'
    '.task-avatar.task-reg-direct{background:#E6F1FB;color:#185FA5}'
    '.task-avatar.task-reg-ausn{background:#FAEEDA;color:#854F0B}'
    '.task-avatar.task-reg-team{background:#F1EFE8;color:#5F5E5A}'
    '.task-avatar.task-reg-sys{background:#EEEDFE;color:#534AB7}'
    '.task-body{min-width:0;overflow:hidden}'
    '.task-what{color:var(--text-primary);font-size:15px;font-weight:600;'
    'line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
    '.task-sub{display:flex;align-items:baseline;gap:6px;margin-top:1px;min-width:0}'
    '.task-client{font-size:12.5px;color:var(--text-muted);white-space:nowrap;'
    'overflow:hidden;text-overflow:ellipsis}'
    '.task-reg{font-size:11.5px;color:#8a8980;white-space:nowrap;flex-shrink:0}'
    '.task-reg::before{content:"\\00b7 ";color:#c4c2ba}'
    '.task-next-inline{font-size:12.5px;color:var(--text-muted);margin-top:2px;'
    'white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
    '.task-dep{display:inline-flex;align-items:center;gap:5px;margin-top:4px;padding:4px 9px;'
    'background:transparent;border-radius:6px;font-size:12px;font-weight:500;color:#8A6730;cursor:pointer;max-width:100%;transition:background var(--transition)}'
    '.task-dep .dep-arrow{color:var(--text-muted);flex-shrink:0;white-space:nowrap}'
    '.task-dep:hover{background:var(--yellow-bg)}'
    '.task-meta{display:grid;grid-template-columns:auto 96px;gap:8px;align-items:center;font-size:13px;flex-shrink:0;font-weight:500}'
    '.tm-cell{display:flex;justify-content:flex-end;min-width:0}'
    '.task-status{font-size:11.5px;padding:2px 8px;border-radius:9px;white-space:nowrap;font-weight:600;letter-spacing:.01em}'
    '.pill{font-size:14px;padding:2px 8px;border-radius:10px;font-weight:600;border:1px solid transparent;white-space:nowrap}'
    '.pill-team{background:var(--bg-page);color:var(--text-secondary);border-color:var(--border)}'
    '.pill-direct{background:#E6F1FB;color:#0C447C;border-color:#B5D4F4}'
    '.pill-ausn{background:#FAEEDA;color:#633806;border-color:#FAC775}'
    '.pill-sys{background:#EEEDFE;color:#3C3489}'
    '.due-overdue,.due-today{color:var(--accent-red);font-weight:600}'
    '.due-soon{color:#B8893A;font-weight:500}'
    '.due-plan{color:var(--text-secondary)}'
)


def render_client_plan(client_id, today=None):
    """Self-contained per-client plan block (style+html+script) or '' if no tasks."""
    from _plan_waves import WAVES_CSS, WAVES_JS, render_waves_flat
    t_today = today or TODAY
    groups = aggregate_tasks(t_today)
    _index_blocker_titles(groups['all'])
    ctasks = [x for x in groups['all'] if x.get('client_id') == client_id]
    if not ctasks:
        return ''
    try:
        from _mental_model import load_mental_models as _lmm
        mm_index = build_mm_tracks_index(_lmm())
    except Exception:
        mm_index = {}
    html = render_waves_flat(
        ctasks, lambda x: _render_task_row(x, mm_index, show_client_meta=False), _esc,
        period_aware=False)
    if not html:
        return ''
    # WAVES_JS already carries its own <script>…</script> tags — don't double-wrap
    # (nested <script> tags break the handler, so client-card waves wouldn't toggle).
    return '<style>' + _AN_CSS + PLAN_BLOCK_CSS + WAVES_CSS + '</style>' + html + WAVES_JS
