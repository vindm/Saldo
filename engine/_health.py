"""_health.py — compute a client's color status.

Extracted from generate.py as part of P3-11 (decomposition, 2026-05-17).
Sources (JSON-first, 2026-06-19): per-client state/*.json only —
  - state/financials.json.monthly_close (blocker)
  - aggregated deadlines from state (financials.tax_calendar_2026[] + tasks
    with a due_date), via _deadlines.collect_deadlines
  - aggregated "awaiting" from state (open tasks with an awaiting task_type),
    via _deadlines.collect_awaiting
  - daemon daily reports (finkoper / anomalies)
Returns (color, reasons[]). Used in overview and client_dashboard.

History:
  2026-05-25 — migrated monthly_check reads -> state/financials.json.monthly_close;
               removed dead sources-related code; removed client.blocker.
  2026-06-19 — JSON-first refactor: overdue/soon now derive from state-aggregated
               deadlines + awaiting (not the calendar / request-log registries).
               UKEP expiry dropped (no state source; it was an out-of-scope
               registry). The calendar_rows/ukep_rows/requests_rows parameters are
               kept for signature compatibility but are NO LONGER read.
"""
import os
from datetime import date, timedelta
from datetime import datetime as _dt
from _helpers import _short
import state_ops


def calculate_health(client, calendar_rows=None, ukep_rows=None, requests_rows=None,
                     today=None, daemon_finkoper=None, daemon_anomalies=None,
                     deadlines=None, awaiting=None):
    """{'color': red|yellow|green|grey, 'reasons': [...], 'score': int}.

    calendar_rows / ukep_rows / requests_rows are accepted for backward-compatible
    call sites but are ignored (JSON-first migration 2026-06-19). Deadlines and
    awaiting are derived from state; callers may pre-pass per-client slices via
    `deadlines` / `awaiting` to avoid re-reading state per client.
    """
    import generate
    TODAY = generate.TODAY
    DIARY_INBOX = generate.DIARY_INBOX
    if today is None:
        today = TODAY
    # Daemons: if not passed, try loading from disk. No files -> empty dicts.
    if daemon_finkoper is None or daemon_anomalies is None:
        from _loaders import load_daemon_finkoper, load_daemon_anomalies
        if daemon_finkoper is None:
            daemon_finkoper = load_daemon_finkoper(DIARY_INBOX, today)
        if daemon_anomalies is None:
            daemon_anomalies = load_daemon_anomalies(DIARY_INBOX, today)
    name_short = client.get('name_short', '')
    cid = client.get('id')
    # Source of truth for monthly_close is state/financials.json (migration 2026-05-25).
    mc = state_ops.state_read(cid, 'financials.json').get('monthly_close') or {}
    # State-derived deadlines + awaiting for THIS client (JSON-first 2026-06-19).
    # Deadlines for health come from STATE TRACKS only (kind='task'). tax_calendar
    # (kind='tax') is an external input that feeds track creation — it is NOT a
    # render/compute source, so it is excluded here (per the system's principles).
    from _deadlines import collect_deadlines, collect_awaiting
    if deadlines is None:
        deadlines = [r for r in collect_deadlines(today) if r['client_id'] == cid and r.get('kind') == 'task']
    else:
        deadlines = [r for r in deadlines if r['client_id'] == cid and r.get('kind') == 'task']
    if awaiting is None:
        awaiting = [r for r in collect_awaiting(today) if r['client_id'] == cid]
    else:
        awaiting = [r for r in awaiting if r['client_id'] == cid]
    red, yellow = [], []

    # Foreign-worker roster compliance (payroll.json, migration 0019). Mirrors
    # state_lint H3 so the avatar ring agrees with the lint: a BPJS `missing` or an
    # expired permit is RED; a permit within the pack's warn window is YELLOW.
    try:
        _roster = (state_ops.state_read(cid, 'payroll.json') or {}).get('employees') or []
    except Exception:
        _roster = []
    _permit_warn_days = None
    if _roster:
        try:
            import _jurisdiction as _J
            _jur = (state_ops.state_read(cid, 'regime.json') or {}).get('jurisdiction')
            _permit_warn_days = (((_J.load_jurisdiction(_jur).lint or {}).get('payroll')
                                  or {}).get('foreign_worker') or {}).get('permit_expiry_warn_days')
        except Exception:
            _permit_warn_days = None

    # RED
    if mc.get('blocker'):
        red.append(f"Monthly-close blocker: {_short(mc['blocker'], 50)}")
    # An OVERDUE active task makes the client red (operator decision 2026-06-26).
    # This keeps the colour honest against the card's «просрочено» badge, which is
    # derived from the very same task due-dates: a client can no longer read «в
    # норме» while carrying a past-due task. Mirrors the recommendations predicate
    # in _brief.build_client_analysis_from_state (same active statuses, questions
    # excluded), so the rail colour and the badge never disagree.
    from _deadlines import _parse_date as _pd
    _ACTIVE_TASK = ('active', 'open', 'in_progress', 'awaiting', 'awaiting_external')
    try:
        _client_tasks = (state_ops.state_read(cid, 'tasks.json') or {}).get('tasks') or []
    except Exception:
        _client_tasks = []
    for _tk in _client_tasks:
        if not isinstance(_tk, dict):
            continue
        if (_tk.get('status') or '') not in _ACTIVE_TASK:
            continue
        if _tk.get('task_type') == 'open_question':
            continue
        _dd = _pd(_tk.get('due_date'))
        if _dd is not None and _dd < today:
            red.append(f"Overdue task: {_short(_tk.get('title', ''), 50)}")
            break
    # Daemons: Finkoper overdues and high anomalies for today
    for it in daemon_finkoper.get('overdue', []):
        if it.get('client') == name_short:
            red.append(f"Finkoper task overdue: {_short(' | '.join(it.get('fields', [])), 60)}")
    for it in daemon_anomalies.get('high', []):
        if it.get('client') == name_short:
            red.append(f"Anomaly (high): {_short(it.get('text',''), 60)}")
    # Roster RED: a worker missing from a BPJS kas, or a permit already expired.
    for _emp in _roster:
        if not isinstance(_emp, dict):
            continue
        _who = _short(_emp.get('name') or _emp.get('id') or '?', 40)
        _bpjs = _emp.get('bpjs') or {}
        if (str(_bpjs.get('kesehatan')).lower() == 'missing'
                or str(_bpjs.get('ketenagakerjaan')).lower() == 'missing'):
            red.append(f"BPJS not registered: {_who}")
        _permit = _emp.get('permit') or {}
        for _pk in ('kitas_expires', 'rptka_expires'):
            _pdate = _pd(_permit.get(_pk))
            if _pdate is not None and _pdate < today:
                red.append(f"Work permit expired: {_who}")
                break

    if red:
        return {'color': 'red', 'reasons': red, 'score': min(100, 80 + 5*len(red))}

    # YELLOW
    # (Near-deadline tracks do NOT turn a client yellow on their own — matches the
    # original engine, which keyed yellow off calendar/request signals, not a
    # track's due_date.)
    # (Awaiting tasks do not drive yellow either — see the red note above.)
    # Daemons: Finkoper deadlines <=3 days, unread messages, medium anomalies
    for it in daemon_finkoper.get('soon', []):
        if it.get('client') == name_short:
            yellow.append(f"Finkoper deadline <=3d: {_short(' | '.join(it.get('fields', [])), 55)}")
    for it in daemon_finkoper.get('unread', []):
        if it.get('client') == name_short:
            yellow.append(f"Unread from client: {_short(' | '.join(it.get('fields', [])), 55)}")
    for it in daemon_anomalies.get('medium', []):
        if it.get('client') == name_short:
            yellow.append(f"Anomaly (medium): {_short(it.get('text',''), 55)}")
    # Roster YELLOW: a foreign worker's permit expiring within the pack's warn window.
    if _permit_warn_days:
        for _emp in _roster:
            if not isinstance(_emp, dict) or _emp.get('foreign_national') is not True:
                continue
            _who = _short(_emp.get('name') or _emp.get('id') or '?', 40)
            _permit = _emp.get('permit') or {}
            for _pk in ('kitas_expires', 'rptka_expires'):
                _pdate = _pd(_permit.get(_pk))
                if _pdate is not None and today <= _pdate <= today + timedelta(days=_permit_warn_days):
                    yellow.append(f"Work permit renewal soon: {_who}")
                    break

    if yellow:
        return {'color': 'yellow', 'reasons': yellow, 'score': min(79, 40 + 5*len(yellow))}

    # GREEN
    if not mc.get('blocker'):
        return {'color': 'green', 'reasons': [], 'score': 20}

    # GREY (reserved)
    return {'color': 'grey', 'reasons': [], 'score': 0}


