"""_track_attrs.py — single function that assembles data-track-* attributes for a track card.

One source of truth for the track modal: the plan pages (today/week/month),
the overview, and the client dashboard all use this function. Previously each one
assembled them by hand and the attribute set drifted — the modal showed different content.

Reference baseline was in _overview_v2.py (24 attributes); the plan only had 13 of them.
"""
import json
import os
from datetime import datetime
from _strings import t
from _status import normalize_status, status_label as _status_label

# Name-collision guard: build_track_data_attrs() takes a param named `t` (the
# track dict). Alias the localization helper to `_t` so it stays reachable
# inside that scope. Use _t(...) for display wraps everywhere in this module.
_t = t


# task_type token -> a clean English label that is ALSO a key in the _strings.py
# t() catalog, so the chip localizes with the rest of the chrome. No emoji here
# (the UI uses monochrome icons; t() would strip them anyway). Unknown tokens
# fall back to a humanized form ("foo_bar" -> "foo bar") routed through t().
_TASK_TYPE_LABEL = {
    'bank_check': 'bank check',
    'kudir_posting': 'KUDIR posting',
    'pp_to_form': 'prepare payment order',
    'awaiting_external': 'waiting externally',
    'client_followup': 'client follow-up',
    'regime_question': 'regime question',
    'open_question': 'open question',
    'investigation': 'investigation',
    'regulatory_action': 'regulatory',
    'regulatory_watch': 'regulatory monitoring',
    'infrastructure': 'infrastructure',
    'regular_check': 'routine check',
    'recovery_period': 'period recovery',
    'other': '·',
    'month_close': 'month close',
    'month_audit': 'month audit',
    'kkt_check': 'cash register check',
    'finkoper_recurring': 'recurring task',
    'primary_collection': 'source documents collection',
    'team_conversation_required': 'conversation with the team',
    'technical_1c': 'technical in 1C',
    'ausn_reconciliation': 'AUSN reconciliation',
    'regulatory_monitoring': 'regulatory monitoring',
    'balance_reconciliation': 'balance reconciliation',
    'long_term_parallel': 'long-term track',
    'awaiting_external_then_action': 'wait externally, then act',
    'multi_step_preparation': 'multi-step preparation',
    'client_action': 'client action',
    'email_action_required': 'reply to email',
    'access_request': 'access request',
    'ausn_markup_review': 'AUSN markup review',
    'ndfl_register': 'NDFL register',
    'ens_reconciliation': 'ENS reconciliation',
    'acquiring_reconciliation': 'acquiring reconciliation',
    'extraction': 'data export',
    'regulatory': 'regulatory',
    'period_close': 'period close',
    'strategic_decision': 'strategic decision',
    'client_departure': 'client departure',
    'sz_checks_reconciliation': 'self-employed receipts reconciliation',
    'preparation': 'preparation',
    'ausn_bank_marking': 'AUSN bank marking',
    'documentation': 'documentation',
    'monitoring': 'monitoring',
    'ausn_monthly': 'AUSN monthly',
    'coretax_billing': 'Coretax billing',
    'pp_sign': 'sign payment order',
    'service_payment': 'client service payment',
    'turnover_collection': 'turnover collection',
    'control': 'control',
    'reconciliation': 'reconciliation',
    'review_checkpoint': 'review checkpoint',
    'tax_calc': 'tax calc',
    'tax_reconciliation': 'tax reconciliation',
    # Indonesia (id pack) task types. English canonical phrases here; operator-locale
    # rendering comes from _strings UI (ru), so a non-RU client's chips still read in
    # the operator's language — see INSTRUCTIONS.md §0.1.
    'inputs_collection': 'source documents collection',
    'compute_final_pph': 'compute final tax 0.5%',
    'payroll': 'payroll',
    'payroll_pph21_bpjs': 'payroll: income tax + contributions',
    'withholding_unifikasi': 'withholding (rent/services)',
    'tax_pay': 'tax payment',
    'record_ntpn': 'record payment receipt',
    'spt_masa': 'monthly tax return',
    'monthly_close_pt': 'month close',
    'monthly_close': 'month close',
    'withholding': 'withholding',
    'annual_spt_badan': 'annual tax return',
    'note': 'note',
    'data_request': 'data request',
}


def _format_due_str(due_raw, today):
    """data-track-due text for the track modal. Uses THE shared due_label so the
    modal shows the exact same wording as the card/hero/plan for the same task."""
    if not due_raw or not today:
        return ''
    try:
        dobj = datetime.strptime(str(due_raw)[:10], '%Y-%m-%d').date()
        from _components import due_label
        return due_label((dobj - today).days)
    except Exception:
        return str(due_raw)[:10]


def build_mm_tracks_index(mm):
    """Builds an index (client_id, track_id) -> full_track from mental_model.tracks.

    Handles different ID fields (track_id or id) and both keys without client_id
    (in case of global uniqueness).
    """
    idx = {}
    if not mm:
        return idx
    for tr in (mm.get('tracks') or []):
        cid = tr.get('client_id') or ''
        for key in ('track_id', 'id'):
            tid = tr.get(key)
            if tid:
                idx[(cid, tid)] = tr
                idx[('', tid)] = tr  # fallback by bare ID
    return idx


from _helpers import track_stale_days  # R8


def _resolution_render(status_canon, blocked_by):
    """Render-time approximation of resolution_mode (policies/resolution-model.md).
    The precise auto/needs split is the SWEEP's job; the render shows the operator
    axis only: is this task WAITING (blocked/awaiting external) or does it NEED YOU.
    Terminal -> 'done'. Cheap: status + blocked_by, no lint/theta at render."""
    if status_canon in ('done', 'archived', 'cancelled'):
        return 'done'
    if status_canon in ('blocked', 'deferred') or str(status_canon).startswith('await') or blocked_by:
        return 'wait_external'
    return 'needs_operator'


def build_track_data_attrs(
    t,
    esca,
    today=None,
    mm_track=None,
    tg_for=None,
    track_type_for=None,
    blocked_titles=None,
    status_label='',
    badge_override=None,
    translate_fn=None,
):
    """Assembles the data-track-* attribute string (25 of them) for a track card.

    Args:
        t: dict with track fields or a task object from the aggregator. Fields may be:
           id / track_id, client_id, client_name, title / what,
           status, priority, task_type/type, owner/assignee, labels/anchors,
           blocked_by, type_specific, comments, history / _history,
           context / context_full, next_action / next_action_full,
           reply_draft, due_date, source, source_ref, details, badge.
        esca: callable(str) -> HTML-attribute-escaped str.
        today: date (for due-date calculation).
        mm_track: optional full track from mental_model (to enrich t if it is lightweight).
        tg_for: callable(client_id) -> tg-username (without @).
        track_type_for: callable(client_id) -> 'team' / 'direct'.
        blocked_titles: dict track_id -> title (to resolve blocked_by -> titles).
        status_label: human-readable status label for data-track-status (if any).
        badge_override: if passed — used instead of the computed due date.

    Returns:
        a string like ' data-track-id="..." data-track-... ...' (with a leading space),
        ready to insert into <div ...>.
    """
    # Merge the lightweight t with the full track (if any)
    base = dict(mm_track or {})
    for k, v in (t or {}).items():
        if v not in (None, '', [], {}):
            base[k] = v

    track_id = (
        base.get('track_id') or base.get('id')
        or (t.get('source_ref') if t else '') or ''
    )
    client_id = base.get('client_id') or ''

    # state-task as the single source of truth for the modal.
    # If we have client_id and track_id — load the canonical task from state
    # and use its fields as the base. This way the modal is identical wherever it is opened
    # (plan/overview/client dashboard/analytics widget).
    if client_id and track_id:
        try:
            import state_ops as _state_ops
            _state_tasks = _state_ops.state_read(client_id, 'tasks.json')
            if isinstance(_state_tasks, dict):
                # A single track = one canonical task in state, however a view names the id.
                # Match by track_id OR by source_ref (the plan stores the real id in source_ref,
                # while id holds a synthetic tr_<cid>_<id>_<title>). This way any view
                # (overview/dashboard/plan) renders the same track from one source.
                _cand = {track_id, base.get('source_ref') or ''}
                _cand.discard('')
                for _st in (_state_tasks.get('tasks') or []):
                    if _st.get('id') in _cand:
                        # state-task fields take PRIORITY over the passed ones — they are canonical
                        for _k, _v in _st.items():
                            if _v not in (None, '', [], {}):
                                base[_k] = _v
                        break
        except Exception:
            pass
    client_name = base.get('client_name') or ''
    # fallback resolution of the name from clients_index by client_id (on the client
    # dashboard tr may arrive without client_name — it is global for the page).
    if not client_name and client_id:
        try:
            import json as _json
            from pathlib import Path as _Path
            _idx_path = _Path(os.path.dirname(os.path.abspath(__file__))) / 'clients_index.json'
            if _idx_path.exists():
                for _e in _json.loads(_idx_path.read_text(encoding='utf-8')):
                    if _e.get('id') == client_id:
                        client_name = _e.get('name_short') or ''
                        break
        except Exception:
            pass
    title = base.get('title') or base.get('what') or ''

    status_raw = base.get('status') or ''
    # Normalize the free-form status to a canonical, localizable token for the
    # chip (specifics like "blocked_by_anastasia" collapse to "blocked"; the
    # detail lives in context/history, not in the status enum).
    status_canon = normalize_status(status_raw)
    status_disp = _status_label(status_raw)
    priority = base.get('priority') or 'normal'
    task_type_raw = base.get('task_type') or base.get('type') or ''
    # Localize the chip: known token -> catalog label, unknown -> humanized; both
    # routed through t() so it renders Russian under ru like the rest of the chrome.
    task_type_ru = _t(_TASK_TYPE_LABEL.get(task_type_raw) or task_type_raw.replace('_', ' ')) if task_type_raw else ''
    assignee = base.get('owner') or base.get('assignee') or ''
    labels = base.get('labels') or base.get('anchors') or []
    blocked_by = base.get('blocked_by') or []
    type_specific = base.get('type_specific') or {}
    comments = base.get('comments') or []
    history_list = base.get('history') or (t.get('_history') if t else None) or []

    assist = base.get('assist') or {}
    _stale = track_stale_days(base, today) if today else None
    context = base.get('context_full') or base.get('context') or ''
    next_action = base.get('next_action_full') or base.get('next_action') or ''
    # translate_fn — optional normalization (e.g. _translate_tech_terms).
    # Applied uniformly — no divergence between overview/plan/dashboard.
    if translate_fn:
        try:
            if context:
                context = translate_fn(context)
            if next_action:
                next_action = translate_fn(next_action)
        except Exception:
            pass
    if not next_action and t:
        nxt = (t.get('details') or {}).get('next_action') or ''  # cross-file details-dict key (see _aggregator.py, _plan_today.py)
        if nxt and nxt != '—':
            next_action = nxt
    # A closed/terminal task has no "next action" — suppress any stale value so the
    # modal/plan never shows an outdated next step on a done task (render-side guard;
    # the stored field is also normalized at the source by migration 0007).
    if status_canon in ('done', 'archived', 'cancelled'):
        next_action = ''
    reply_draft = base.get('reply_draft') or ''

    due_raw = base.get('due_date') or ''
    due_str = _format_due_str(due_raw, today)
    # unified badge calculation — if there is no explicit override, use the order:
    # badge_override -> t['badge'] -> due-date format -> status label.
    # The client dashboard passes badge_override='routine' for dateless tracks,
    # the plan passes nothing. Unify: if there is no due and no override — 'routine' for
    # active, 'waiting' for awaiting, 'closed' for done.
    if badge_override is not None and badge_override != '':
        badge_text = badge_override
    else:
        badge_text = (t.get('badge') if t else None) or due_str
        if not badge_text:
            _status_map = {'active': _t('routine'), 'awaiting': _t('waiting'),
                           'awaiting_external': _t('waiting'), 'done': _t('closed'),
                           'dropped': _t('dropped')}
            badge_text = _status_map.get(status_raw, '')

    # source — take the canonical one from the state-task (source); do not append
    # source_ref if it == track_id (that is just a duplicate of the canonical id, not extra info).
    source = base.get('source') or ''
    src_ref = (t.get('source_ref') if t else None) or base.get('source_ref') or ''
    if src_ref and src_ref != track_id and src_ref not in source:
        source_text = source + ' · ' + src_ref if source else src_ref
    else:
        source_text = source

    bb_titles = []
    # resolve blocked_by titles uniformly — via state/tasks.json of the same
    # client. The passed blocked_titles is used only if it contains a
    # MEANINGFUL title (not equal to the id itself and not empty).
    _bt_cache = None
    for bid in blocked_by:
        passed = (blocked_titles or {}).get(bid, '')
        # passed is considered meaningful only if it is non-empty AND not equal to the id
        ttitle = passed if (passed and passed != bid) else ''
        if not ttitle and client_id:
            if _bt_cache is None:
                try:
                    import state_ops as _sops2
                    _bt_cache = {t.get('id'): t.get('title', '')
                                 for t in (_sops2.state_read(client_id, 'tasks.json').get('tasks') or [])}
                except Exception:
                    _bt_cache = {}
            ttitle = _bt_cache.get(bid, '')
        if not ttitle:
            ttitle = bid
        bb_titles.append({'id': bid, 'title': ttitle})

    # Reverse dependency — the tasks THIS one blocks ("Блокирует"): same-client
    # tasks whose blocked_by names this track. The inverse of blocked_by, resolved
    # from the same state/tasks.json. Skip terminal blockers (a done/cancelled task
    # is no longer being held up). Self-references are dropped.
    blocks_titles = []
    if client_id:
        _self_ids = {x for x in (track_id, base.get('id'), base.get('source_ref')) if x}
        try:
            from _status import normalize_status as _nstat
        except Exception:
            _nstat = lambda s: (s or '').strip().lower()
        _terminal = {'done', 'cancelled', 'archived', 'dropped', 'deferred'}
        if _bt_cache is None:
            try:
                import state_ops as _sops3
                _all_tasks = (_sops3.state_read(client_id, 'tasks.json').get('tasks') or [])
            except Exception:
                _all_tasks = []
        else:
            try:
                import state_ops as _sops3
                _all_tasks = (_sops3.state_read(client_id, 'tasks.json').get('tasks') or [])
            except Exception:
                _all_tasks = []
        for _ot in _all_tasks:
            if _nstat(_ot.get('status')) in _terminal:
                continue
            _obb = _ot.get('blocked_by') or []
            if _self_ids & set(_obb):
                _oid = _ot.get('id')
                if _oid in _self_ids:
                    continue
                blocks_titles.append({'id': _oid, 'title': _ot.get('title') or _oid})

    # assemble details here uniformly (track/status/context/next_action) instead of
    # trusting the passed t['details'] (which has different formats from plan and dashboard).
    # NOTE: the dict keys below ('track'/'status'/'context'/'next_action') are
    # cross-file LOGIC KEYS — _aggregator.py writes them and _plan_today.py reads them.
    # If passed details exist — merge them on top for additional fields.
    _passed_details = (t.get('details') if t else None) or {}
    details = {
        'track': track_id,
        'status': status_raw or '—',
        'context': context or '—',
        'next_action': next_action or '—',
    }
    # Additional fields from the passed details (Assignee, Amount, Related, etc.)
    for _dk, _dv in _passed_details.items():
        if _dk not in details and _dv not in (None, '', '—'):
            details[_dk] = _dv
    details_json_s = json.dumps(details, ensure_ascii=False)

    tg = ''
    if tg_for and client_id:
        try:
            tg = tg_for(client_id) or ''
        except Exception:
            tg = ''
    track_type_v = ''
    if track_type_for and client_id:
        try:
            track_type_v = track_type_for(client_id) or ''
        except Exception:
            track_type_v = ''

    # Resolve payroll-line employee names from the client's roster AT RENDER TIME
    # (entity-linking: the stored line keeps only employee_id; name/position is derived).
    # Review cockpit: derive per-line + run-level review signals AT RENDER TIME from the
    # client's roster (names), the PRIOR month's run (Δ), and the period aggregate (parity
    # localization). All in the rendered copy — the stored line keeps only its calc fields.
    _ts_render = type_specific
    try:
        if isinstance(type_specific, dict) and type_specific.get('payroll_lines') and client_id:
            import state_ops as _so, copy as _cp
            _ts_render = _cp.deepcopy(type_specific)
            _lines = _ts_render.get('payroll_lines') or []
            # roster: id -> {name, position}
            _einfo = {e.get('id'): e for e in
                      ((_so.state_read(client_id, 'payroll.json') or {}).get('employees') or [])
                      if isinstance(e, dict) and e.get('id')}
            # prior masa run: id -> gross
            def _prev_masa(m):
                try:
                    y, mm = str(m).split('-'); mm = int(mm) - 1
                    return ("%d-12" % (int(y) - 1)) if mm == 0 else ("%s-%02d" % (y, mm))
                except Exception:
                    return None
            _pm = _prev_masa(type_specific.get('period'))
            _prior = {}
            if _pm:
                for _tk in ((_so.state_read(client_id, 'tasks.json') or {}).get('tasks') or []):
                    _ts2 = _tk.get('type_specific') or {}
                    if str(_tk.get('task_type', '')).startswith('payroll') and _ts2.get('period') == _pm:
                        for _l2 in (_ts2.get('payroll_lines') or []):
                            if isinstance(_l2, dict) and _l2.get('employee_id'):
                                _prior[_l2['employee_id']] = _l2.get('gross')
            # period aggregate (incumbent benchmark)
            _per_pph = None
            for _p in ((_so.state_read(client_id, 'financials.json') or {}).get('periods') or []):
                if isinstance(_p, dict) and _p.get('period') == type_specific.get('period'):
                    _per_pph = (_p.get('taxes') or {}).get('pph21')
            _TH = 1000000
            _sum = 0; _nflag = _nchg = 0; _has_thr = False; _bpjs_gap = False
            for _ln in _lines:
                if not isinstance(_ln, dict):
                    continue
                _e = _einfo.get(_ln.get('employee_id'))
                if _e:
                    _ln['name'] = _e.get('name'); _ln['position'] = _e.get('position')
                _g = _ln.get('gross') or 0; _sum += (_ln.get('pph') or 0)
                _pv = _prior.get(_ln.get('employee_id'))
                _delta = None if _pv is None else (_g - (_pv or 0))
                _isnew = bool(_prior) and (_ln.get('employee_id') not in _prior)
                if _ln.get('thr'):
                    _has_thr = True
                _kk = (_ln.get('bpjs') or {}).get('ketenagakerjaan')
                if _kk in (None, '') or str(_kk).lower() == 'missing':
                    _bpjs_gap = True
                _flag = _isnew or (_delta is not None and abs(_delta) >= _TH)
                if _flag:
                    _nflag += 1
                if _isnew or (_delta not in (None, 0)):
                    _nchg += 1
                _ln['_review'] = {'delta': _delta, 'is_new': _isnew, 'flag': _flag}
            _gap = (_sum - _per_pph) if _per_pph is not None else None
            _ts_render['_summary'] = {'n': len(_lines), 'sum_pph': _sum, 'period_pph': _per_pph,
                'gap': _gap, 'n_flag': _nflag, 'n_change': _nchg, 'thr': _has_thr, 'bpjs_gap': _bpjs_gap}
    except Exception:
        _ts_render = type_specific

    parts = [
        ' data-track-id="' + esca(track_id) + '"',
        ' data-track-client-id="' + esca(client_id) + '"',
        ' data-track-client-name="' + esca(client_name) + '"',
        ' data-track-title="' + esca(title) + '"',
        ' data-track-status="' + esca(status_label) + '"',
        ' data-track-status-raw="' + esca(status_raw) + '"',
        ' data-track-status-disp="' + esca(status_disp) + '"',
        ' data-track-status-canon="' + esca(status_canon) + '"',
        ' data-track-resolution="' + esca(_resolution_render(status_canon, blocked_by)) + '"',
        ' data-track-confidence="' + esca(((assist or {}).get('confidence') or '')) + '"',
        ' data-track-badge="' + esca(badge_text) + '"',
        ' data-track-context="' + esca(context) + '"',
        ' data-track-next="' + esca(next_action) + '"',
        ' data-track-reply="' + esca(reply_draft) + '"',
        ' data-track-tg="' + esca(tg) + '"',
        ' data-track-type="' + esca(track_type_v) + '"',
        ' data-track-task-type="' + esca(task_type_ru) + '"',
        ' data-track-priority="' + esca(priority) + '"',
        ' data-track-assignee="' + esca(assignee) + '"',
        ' data-track-due="' + esca(due_str) + '"',
        ' data-track-due-raw="' + esca(str(due_raw)) + '"',
        ' data-track-source="' + esca(source_text) + '"',
        ' data-track-blocked-by-json="' + esca(json.dumps(bb_titles, ensure_ascii=False)) + '"',
        ' data-track-blocks-json="' + esca(json.dumps(blocks_titles, ensure_ascii=False)) + '"',
        ' data-track-labels-json="' + esca(json.dumps(list(labels), ensure_ascii=False)) + '"',
        ' data-track-type-specific-json="' + esca(json.dumps(_ts_render, ensure_ascii=False)) + '"',
        ' data-track-comments-json="' + esca(json.dumps(comments, ensure_ascii=False)) + '"',
        ' data-track-details-json="' + esca(details_json_s) + '"',
        ' data-track-history-json="' + esca(json.dumps(history_list, ensure_ascii=False) if history_list else '') + '"',
        ' data-track-assist-json="' + esca(json.dumps(assist, ensure_ascii=False) if assist else '') + '"',
        ' data-track-stale="' + (str(_stale) if _stale is not None else '') + '"',
    ]
    return ''.join(parts)
