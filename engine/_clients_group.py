"""_clients_group.py — generic "Clients — <group>" page with a card grid.

One renderer for every client group. The set of groups is derived from the
data (the per-client `group` field), so this single module replaces the old
group-specific _clients_team.py / _clients_direct.py pair.

render_clients_group(group_name, clients_in_group) builds one page; generate.py
calls it once per dynamic group and writes clients_<slug>.html.

Each card shows: name, regime/scenario, health, top track action, remaining
task count, and (if present) a small "profile" link. Clicking a card opens the
client dashboard.
"""
import os
from datetime import datetime as _dt

from generate import (
    clients, TODAY, DIARY_INBOX,
    _esc, _esca,
    load_daemon_finkoper, load_daemon_anomalies,
    calculate_health,
    DESIGN_TOKENS_CSS, OVERVIEW_SPECIFIC_CSS, NEW_JS_FRAGMENT, PLAN_DIR,
)
from _deadlines import collect_deadlines, collect_awaiting
from _helpers import (
    _format_date_ru, _translate_tech_terms,
    _slugify_group, _group_label, client_group, client_avatar,
)
from _strings import t, tp
from _icons import icon
from _components import due_badge
from _brief import build_client_analysis_from_state
from _overview_v2 import OVERVIEW_V2_CSS
from _analytics_widgets import render_kpi_band, KPI_BAND_CSS
from _sidebar import render_sidebar, SIDEBAR_CSS
from _css import PROMPT_MODAL_CSS, PROMPT_MODAL_HTML, PROMPT_MODAL_JS
from _onboarding import render_add_client_cta, ADD_CLIENT_CSS


def _plural_tasks(n):
    """Localized "N task(s)" label."""
    return t('{} task').format(n) if abs(n) == 1 else t('{} tasks').format(n)


def _client_profile_rel(c):
    """Relative path to a client's profile.md if it exists, else None.

    The engine does NOT parse profile.md — it only links to it. The file lives
    next to the client's state/ dir: <data>/<folder>/profile.md.
    """
    folder = c.get('folder') or os.path.join('clients', c.get('id', ''))
    abs_path = os.path.join(PLAN_DIR, folder, 'profile.md')
    if os.path.exists(abs_path):
        # Link relative to the dashboards/ output dir → into the data tree.
        # Kept as a best-effort relative hop; harmless if it 404s in a viewer.
        return os.path.relpath(abs_path, _DASHBOARD_DIR_FOR_LINKS())
    return None


def _DASHBOARD_DIR_FOR_LINKS():
    import generate
    return getattr(generate, 'OUT_DIR', '.')


def _scenario_short(c):
    """Short right-hand label on the card: regime, or scenario fallback."""
    regime = (c.get('regime') or '').strip()
    if regime:
        return regime[:30]
    scenario = (c.get('scenario') or '').strip()
    return scenario or ''


# Health reasons (_health.py) are built with English prefixes for a locale-neutral
# engine; on the operator-facing card the prefix must read in the operator's
# language (§0.1). Body text is already the operator's language.
_REASON_PREFIXES = [
    ('Monthly-close blocker:', 'Блокер закрытия месяца:'),
    ('Finkoper task overdue:', 'Finkoper — просрочено:'),
    ('Finkoper deadline <=3d:', 'Finkoper — срок ≤3 дн:'),
    ('Unread from client:', 'Непрочитано от клиента:'),
    ('Anomaly (high):', 'Аномалия:'),
    ('Anomaly (medium):', 'Аномалия:'),
]


def _localize_reason(s):
    """Translate the English health-reason prefix into the operator locale."""
    s = (s or '').strip()
    for en, ru in _REASON_PREFIXES:
        if s.startswith(en):
            return (tp(en, ru) + s[len(en):]).strip()
    return s


# Task types whose `amount` is a tax/contribution the client must PAY (a ПП the
# operator forms). Only these get a money chip, so the amount on a card always
# means one thing — «к уплате». Amounts on other task types mean something else
# (a fee for Irina's work, or money the client is RECEIVING) and would only
# confuse if shown the same way — that figure already lives in the task title.
_PAYMENT_TASK_TYPES = {'pp_to_form', 'tax_pp', 'pp_sign', 'sign_pay'}


def _amount_chip(c, rec):
    """Money chip («к уплате», jurisdiction currency) — only for payment tasks."""
    if (rec.get('task_type') or '') not in _PAYMENT_TASK_TYPES:
        return ''
    amount = rec.get('amount')
    try:
        if amount is None or float(amount) <= 0:
            return ''
    except (TypeError, ValueError):
        return ''
    from _owner_report import _money, _currency
    cur = _currency(c.get('jurisdiction'))
    return ('<span class="dc-amt" title="' + _esca(tp('amount to pay', 'сумма к уплате')) + '">'
            + icon('wallet') + ' ' + _esc(_money(amount)) + ' ' + _esc(cur) + '</span>')


def _render_group_card(c, color, rec, task_count, reasons):
    """A single client card — group-agnostic.

    Headline precedence:
      1. A flagged (red/yellow) client whose top task is NOT itself overdue
         leads with the health reason — otherwise, with no colour rail, the card
         would look calm while counting as «срочный». The «просрочено» badge
         already explains the overdue case, so we only fall back to the reason
         when the badge wouldn't.
      2. Otherwise the headline is the SAME #1 the client dashboard shows under
         «Главное на сегодня» (`recommendations[0]`), with the SAME `due_badge`,
         so snippet and dashboard never disagree on the task or its overdue state.
    """
    right_label = _scenario_short(c)
    _av_ini, _av_style = client_avatar(c["name_short"])
    head_html = (
        f'<div class="dc-name-row">'
        f'<span class="dc-av"{_av_style}>{_esc(_av_ini)}</span>'
        f'<span class="dc-name">{_esc(c["name_short"])}</span>'
        f'<span class="dc-regime">{_esc(right_label)}</span>'
        f'</div>'
    )

    _dd = rec.get('due_days') if rec else None
    rec_overdue = isinstance(_dd, int) and _dd < 0

    status_html = ''
    show_reason = bool(reasons) and not rec_overdue
    if show_reason:
        # Flagged, but the badge alone wouldn't show why (no overdue task).
        # State the reason plainly — quiet styling, no loud colour block.
        reason = _translate_tech_terms(_localize_reason(reasons[0]))
        action_html = (f'<div class="dc-action dc-reason">'
                       + icon('alert') + ' ' + _esc(reason) + '</div>')
        has_top = False
    elif rec:
        title = (rec.get('title') or '')[:90]
        action_html = f'<div class="dc-action">{_esc(_translate_tech_terms(title))}</div>'
        has_top = True
        bits = due_badge(rec.get('due_days')) + _amount_chip(c, rec)
        if bits:
            status_html = f'<div class="dc-status">{bits}</div>'
    elif color == 'green':
        action_html = '<div class="dc-action dc-action-calm">' + t('No urgent tasks or anomalies') + '</div>'
        has_top = False
    else:
        action_html = '<div class="dc-action dc-action-calm">' + t('No active tasks') + '</div>'
        has_top = False

    # Other open tasks beyond the headline. When the headline is a reason (not a
    # task), every task is still "more".
    if show_reason:
        remaining = task_count or 0
    elif has_top:
        remaining = max(0, (task_count or 0) - 1)
    else:
        remaining = 0
    meta_bits = []
    if remaining > 0:
        meta_bits.append('<span class="dc-more">+ ' + t('{} more').format(_plural_tasks(remaining)) + '</span>')
    profile_rel = _client_profile_rel(c)
    if profile_rel:
        meta_bits.append(
            '<span class="dc-profile" title="' + t('A prose profile.md exists for this client') + '">📄 ' + t('profile') + '</span>'
        )
    meta_html = f'<div class="dc-meta-row">{"".join(meta_bits)}</div>' if meta_bits else ''

    href = f'dashboard_{c["id"]}.html'
    return (
        f'<a href="{href}" class="dc-card dc-card-{color}">'
        + head_html + action_html + status_html + meta_html
        + '</a>'
    )


_EXTRA_CSS = """
.clients-head-left{min-width:0}
.clients-head-right{display:flex;flex-direction:column;align-items:flex-end;gap:8px;flex-shrink:0}
.clients-head-right .ct-meta{font-size:12px;color:var(--text-muted);text-align:right;line-height:1.5;white-space:nowrap}
.page-title{font-size:19px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.03em;margin:0 0 6px}
.page-count{display:inline-block;font-size:13px;font-weight:600;color:var(--text-secondary);
  background:var(--bg-subtle,rgba(0,0,0,0.05));border-radius:999px;padding:1px 9px;
  margin-left:8px;letter-spacing:0;text-transform:none;vertical-align:middle}
/* Container-aware grid: columns wrap on the available content width (which the
   fixed sidebar already narrows), so cards never overflow — no viewport media
   queries needed. */
.dc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
  gap:var(--space-md);margin:var(--space-md) 0}

.dc-card{position:relative;display:flex;flex-direction:column;gap:var(--space-sm);
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius-card);
  padding:var(--space-md);
  text-decoration:none;color:inherit;
  box-shadow:0 1px 3px rgba(0,0,0,0.04);
  transition:transform 150ms,box-shadow 150ms;
  min-height:124px;cursor:pointer}
.dc-card:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(0,0,0,0.08)}

.dc-name-row{display:flex;justify-content:space-between;align-items:center;gap:var(--space-sm)}
.dc-av{width:30px;height:30px;border-radius:50%;flex-shrink:0;display:flex;
  align-items:center;justify-content:center;font-size:12px;font-weight:600}
.dc-name{font-size:16px;font-weight:500;color:var(--text-primary);line-height:1.3;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;flex:1}
.dc-regime{font-size:13px;color:var(--text-muted);white-space:nowrap;flex-shrink:0}

.dc-action{font-size:15px;color:var(--text-primary);line-height:1.4}
.dc-action-calm{color:var(--text-muted)}
/* Flagged-but-no-task fallback: a quiet line, not a loud red block. The card's
   left rail already carries the colour. */
.dc-reason{display:flex;align-items:flex-start;gap:6px;color:var(--text-secondary)}
.dc-reason .ic{width:14px;height:14px;flex-shrink:0;margin-top:3px;color:var(--accent-red);opacity:.85}

.dc-meta-row{display:flex;gap:var(--space-md);margin-top:auto;padding-top:var(--space-xs);align-items:center}
.dc-more{font-size:13px;color:var(--text-muted)}
.dc-profile{font-size:13px;color:var(--text-secondary)}

/* Status row reuses the shared .due-badge (same component as the client
   dashboard's «Главное» rows), plus an optional amount chip. */
.dc-status{display:flex;flex-wrap:wrap;align-items:center;gap:8px var(--space-md)}
.dc-amt{display:inline-flex;align-items:center;gap:5px;font-size:13px;
  font-weight:600;color:var(--text-primary);white-space:nowrap;
  font-variant-numeric:tabular-nums}
.dc-amt .ic{width:13px;height:13px;opacity:.6}
"""


def render_clients_group(group_name, group_clients=None):
    """Render the clients page for one group.

    group_name   — raw group label (e.g. "team", "direct", "archive").
    group_clients — clients in this group; if None, derived from globals.
    """
    if group_clients is None:
        group_clients = [c for c in clients if client_group(c) == group_name]

    # Deadlines + awaiting feed the health computation below (per-client slices).
    deadlines = collect_deadlines(TODAY)
    awaiting = collect_awaiting(TODAY)
    daemon_finkoper = load_daemon_finkoper(DIARY_INBOX, TODAY)
    daemon_anomalies = load_daemon_anomalies(DIARY_INBOX, TODAY)

    # Health (for the colour rail/reason) + strict alphabetical order by name.
    # The card colour and the «N срочных» summary still signal urgency; the list
    # itself stays predictable (А→Я), independent of health.
    enriched = []
    for c in group_clients:
        h = calculate_health(c, today=TODAY,
                             daemon_finkoper=daemon_finkoper,
                             daemon_anomalies=daemon_anomalies,
                             deadlines=deadlines, awaiting=awaiting)
        color = h.get('color', 'grey')
        enriched.append((color, c, h.get('reasons') or []))
    enriched.sort(key=lambda x: x[1]['name_short'].lower())

    import state_ops as _sop
    cards_html = []
    health_counts = {'red': 0, 'yellow': 0, 'green': 0, 'grey': 0}
    for color, c, reasons in enriched:
        health_counts[color] = health_counts.get(color, 0) + 1

        # The headline mirrors the client dashboard's «Главное на сегодня» exactly:
        # same source (build_client_analysis_from_state), same sort, same badge.
        an = build_client_analysis_from_state(c['id'], c.get('name_short'),
                                              _sop.state_read, TODAY) or {}
        recs = an.get('recommendations') or []
        rec = recs[0] if recs else None
        task_count = an.get('task_count') or 0

        cards_html.append(_render_group_card(c, color, rec, task_count, reasons))

    grid_html = '<div class="dc-grid">' + ''.join(cards_html) + '</div>'

    # Page-header KPI band — the SAME component as overview / Plan / client
    # cockpit. Clients pages summarise by client HEALTH (red/amber/green); the
    # tiles carry the semantic value colours as signal, one metric look.
    health_summary = render_kpi_band([
        {'num': health_counts["red"],    'label': t('Urgent'), 'tone': 'red'},
        {'num': health_counts["yellow"], 'label': t('Soon'),   'tone': 'amber'},
        {'num': health_counts["green"],  'label': t('OK'),     'tone': 'green'},
    ])

    label = _group_label(group_name)
    slug = _slugify_group(group_name)
    active_key = 'clients_' + slug
    title = t('Clients — {}').format(label)

    # Time stamp mirrors the client page's «обновлён … 🕐 WITA · МСК» (ct-meta),
    # placed in the right column under the CTA. The big date <h1> is dropped on
    # the clients pages — the page title + summary already orient the operator,
    # and the relative badges («просрочено» / «через N дн») are implicitly today.
    import generate as _g
    _tb = getattr(_g, 'TIME_BALI', '') or ''
    _tm = getattr(_g, 'TIME_MSK', '') or ''
    _time_line = (('<br>🕐 ' + _esc(_tb) + ' WITA · ' + _esc(_tm) + ' ' + tp('MSK', 'МСК'))
                  if (_tb and _tm) else '')
    meta_html = ('<span class="ct-meta">' + t('updated') + ' '
                 + _esc(_format_date_ru(TODAY)) + _time_line + '</span>')
    return (
        '<!DOCTYPE html>\n<html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMTUuNSIgZmlsbD0iIzFGNEU3OSIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMTYiIHI9IjEyLjciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0I3OTI1NyIgc3Ryb2tlLXdpZHRoPSIxLjMiLz48dGV4dCB4PSIxNiIgeT0iMTciIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIiBmb250LWZhbWlseT0iQXJpYWwsSGVsdmV0aWNhLHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTQiIGZvbnQtd2VpZ2h0PSI3MDAiIGZpbGw9IiNmZmZmZmYiPtCY0JI8L3RleHQ+PC9zdmc+">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>' + _esc(title) + '</title>'
        '<style>' + DESIGN_TOKENS_CSS + OVERVIEW_SPECIFIC_CSS + OVERVIEW_V2_CSS
        + SIDEBAR_CSS + PROMPT_MODAL_CSS  + ADD_CLIENT_CSS + KPI_BAND_CSS + _EXTRA_CSS + '</style>'
        '</head><body>'
        '<div class="layout-shell">'
        + render_sidebar(active=active_key)
        + '<main class="main-content">'
        + '<div class="clients-head">'
        + '<div class="clients-head-left">'
        + '<h1 class="page-title">' + _esc(title)
        + ' <span class="page-count">' + str(len(group_clients)) + '</span></h1>'
        + health_summary
        + '</div>'
        + '<div class="clients-head-right">'
        + render_add_client_cta(group=group_name, group_label=label)
        + meta_html
        + '</div>'
        + '</div>'
        + grid_html
        + '</main></div>'
        + PROMPT_MODAL_HTML 
        + NEW_JS_FRAGMENT + PROMPT_MODAL_JS  +
        '</body></html>'
    )
