# -*- coding: utf-8 -*-
"""_brief.py — the "Daily brief" zone on the home page. A PURE LENS over state.

Decision (2026-06-13): the brief is never stored (a view, not a store).
Everything comes from `state/*.json` + `history.jsonl` on every re-render. The
intelligence lives in the state upkeep done by the `mm_update` skill; this module
only ranks and formats.

The design strictly reuses the existing widgets (`aw-widget`/`aw-head`/`aw-row`/`aw-dl-badge`
from _analytics_widgets.ANALYTICS_CSS) — no hand-rolled markup or inline emoji.
The per-question recommendation = `type_specific.recommended`/`options` from the
open_question itself; until those exist we show `next_action` as a hypothesis + typical options.

Buttons use the shared copy-modal (data-prompt + PROMPT_MODAL_JS), not sendPrompt (file://).
Rows are clickable (track-card-clickable + data-track-*) and open the track modal —
the attributes are built by the passed make_attrs (build_track_data_attrs from _track_attrs).
"""
import os, glob, json
from datetime import date
from _helpers import track_stale_days  # R8
from _strings import t, tp

_PRIO = {'high': 0, 'normal': 1, 'low': 2}


def _to_date(s):
    try:
        y, m, d = map(int, str(s).split('T')[0].split('-')[:3])
        return date(y, m, d)
    except Exception:
        return None


def _age_days(created, today):
    d = _to_date(created)
    return (today - d).days if d else None


def _esc(s):
    return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _esca(s):
    return _esc(s).replace('"', '&quot;').replace("'", '&#39;')


def collect_brief(clients, state_read, today):
    decisions, questions, nearest = [], [], None
    overdue, due_today = [], []
    risks_red = 0
    for c in clients:
        cid = c['id']
        cname = c.get('name_short') or cid
        try:
            _rj = state_read(cid, 'risks.json') or {}
            risks_red += sum(1 for r in (_rj.get('risks') or []) if r.get('severity') == 'red')
        except Exception:
            pass
        try:
            t = state_read(cid, 'tasks.json') or {}
        except Exception:
            t = {}
        arr = t.get('tasks', []) if isinstance(t, dict) else (t or [])
        for tr in arr:
            if not isinstance(tr, dict):
                continue
            status = tr.get('status')
            # Deadlines (overdue / today / nearest) — from all OPEN tasks incl.
            # 'awaiting', matching the header's overdue count (active+awaiting).
            if status in ('active', 'awaiting', 'open'):
                dd = _to_date(tr.get('due_date'))
                if dd:
                    _it = (dd, cname, (tr.get('title') or '')[:60])
                    if dd < today:
                        overdue.append(_it)
                    elif dd == today:
                        due_today.append(_it)
                    elif nearest is None or dd < nearest[0]:
                        nearest = _it
            # Questions / decisions — only from actively-worked tasks.
            if status not in ('active', 'open'):
                continue
            tt = tr.get('task_type') or tr.get('type')
            if tt == 'open_question':
                a = tr.get('assist') or {}
                acts = a.get('actions') or None
                opts = ([{'label': x.get('label', ''), 'prompt': x.get('prompt', '')} for x in acts]
                        if acts else None)
                rec = None
                if acts:
                    for _i, x in enumerate(acts):
                        if x.get('recommended'):
                            rec = _i
                            break
                questions.append({
                    'id': tr.get('id', ''), 'client_id': cid, 'client': cname,
                    'text': tr.get('title') or '', 'priority': tr.get('priority', 'normal'),
                    'age': _age_days(tr.get('created_at'), today),
                    'hypothesis': a.get('hypothesis') or tr.get('next_action') or '',
                    'options': opts, 'recommended': rec,
                    'confidence': a.get('confidence'), 'updated_at': a.get('updated_at'),
                    'stale': track_stale_days(tr, today),
                })
            elif tr.get('assignee') == 'Operator' and tr.get('priority') == 'high':
                a = tr.get('assist') or {}
                decisions.append({
                    'id': tr.get('id', ''), 'client_id': cid, 'client': cname,
                    'title': tr.get('title') or '',
                    'next': a.get('hypothesis') or tr.get('next_action') or '',
                    'due': tr.get('due_date') or '', 'stale': track_stale_days(tr, today),
                })
    questions.sort(key=lambda q: (_PRIO.get(q['priority'], 1), 0 if q.get('stale') else 1, -(q['age'] or 0)))
    overdue.sort(key=lambda x: x[0])      # most overdue (oldest due) first
    due_today.sort(key=lambda x: x[1])
    return {'decisions': decisions, 'questions': questions, 'nearest': nearest,
            'overdue': overdue, 'due_today': due_today, 'risks_red': risks_red}


def _brief_text(vm, today, fmt_date):
    ov, dt, nd = vm.get('overdue') or [], vm.get('due_today') or [], vm['nearest']
    qs, dec = vm['questions'], vm['decisions']
    parts = [fmt_date(today) + '.']
    # 1) Urgency — lead with overdue, then today, else reassure (honest, never
    #    "nothing urgent" while something is overdue).
    if ov:
        o = ov[0]
        parts.append(tp('overdue: {} (oldest — {}: {})',
                        'просрочено: {} (раньше всех — {}: {})').format(len(ov), o[1], o[2]))
    elif dt:
        d0 = dt[0]
        parts.append(tp('due today: {} ({})',
                        'срок сегодня: {} ({})').format(len(dt), d0[1]))
    else:
        parts.append(tp('nothing urgent today', 'срочного на сегодня нет'))
    # 2) Nearest upcoming deadline (after today)
    if nd:
        parts.append(tp('next due — {} {}',
                        'ближайший срок — {} {}').format(nd[1], nd[0].strftime('%d.%m')))
    # 3) What needs her / how many questions are open (specific counts, no false
    #    "can be closed" claim — the «Открытые вопросы» block below lists them).
    if dec:
        parts.append(tp('awaiting your decision: {}',
                        'ждут твоего решения: {}').format(len(dec)))
    if qs:
        parts.append(tp('open questions: {}',
                        'открытых вопросов: {}').format(len(qs)))
    if vm.get('risks_red'):
        parts.append(tp('red risks: {}', '🔴 рисков: {}').format(vm['risks_red']))
    return '; '.join(parts).replace('.;', '.', 1) + '.'


def _dl_badge(dd, today, esc):
    """Due-date badge in the aw-dl-badge style."""
    if not dd:
        return ''
    n = (dd - today).days
    if n < 0:
        cls, txt = 'dl-overdue', t('overdue {}d').format(-n)
    elif n == 0:
        cls, txt = 'dl-today', t('today')
    elif n <= 3:
        cls, txt = 'dl-soon', t('in {}d').format(n)
    elif n <= 7:
        cls, txt = 'dl-week', t('in {}d').format(n)
    else:
        cls, txt = 'dl-plan', dd.strftime('%d.%m')
    return f'<span class="aw-dl-badge {cls}">{esc(txt)}</span>'


def brief_lead_html(clients, state_read, plan_dir, today, fmt_date, esc=None):
    """Inner HTML for the "Today summary" lead. Prefers an AGENT-WRITTEN brief
    (journal/brief_<date>.md — composed by the mm_update daemon with full context
    over the whole dashboard); falls back to a deterministic, honest summary."""
    esc = esc or _esc
    import re as _re
    try:
        p = os.path.join(plan_dir, 'journal', 'brief_%s.md' % today.isoformat())
        if os.path.isfile(p):
            raw = open(p, encoding='utf-8').read().strip()
            if raw:
                html = esc(raw)
                html = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
                html = html.replace('\n', '<br>')
                return '<div class="aw-body brief-text">' + html + '</div>'
    except Exception:
        pass
    vm = collect_brief(clients, state_read, today)
    return '<div class="aw-body brief-text">' + esc(_brief_text(vm, today, fmt_date)) + '</div>'


def render_brief_zone(clients, state_read, plan_dir, today, fmt_date=None,
                      esc=None, esca=None, make_attrs=None,
                      sections=('brief', 'decisions', 'questions')):
    esc = esc or _esc
    esca = esca or _esca
    fmt_date = fmt_date or (lambda d: d.strftime('%d.%m.%Y'))
    vm = collect_brief(clients, state_read, today)

    # 1) Brief — a light lead line inside the widget card
    brief = (
        '<div class="aw-widget brief-lead">'
        '<div class="aw-head">' + t('🧭 Brief for today') + '</div>'
        + brief_lead_html(clients, state_read, plan_dir, today, fmt_date, esc) +
        '</div>'
    )

    # 2) Needs your decision
    dec = vm['decisions']
    if dec:
        rows = []
        for d in dec:
            attrs = make_attrs(d) if make_attrs else ''
            badge = _dl_badge(_to_date(d['due']), today, esc) or '<span class="brief-age">' + esc(t('decision')) + '</span>'
            _ds = (' \u00b7 \u23F3 ' + t('stale for {}d').format(d['stale'])) if d.get('stale') else ''
            sub = ('<div class="brief-sub">' + esc(d['next']) + _ds + '</div>') if (d['next'] or d.get('stale')) else ''
            rows.append(
                '<div class="aw-row track-card-clickable"' + attrs + '>' + badge +
                '<span class="aw-text">' + esc(d['client'] + ' — ' + d['title']) + sub + '</span></div>'
            )
        body = ''.join(rows)
    else:
        body = '<div class="aw-empty">' + t('Nothing urgent on you — all under control') + '</div>'
    decisions = (
        '<div class="aw-widget aw-decisions"><div class="aw-head">' + t('🚩 Needs your decision') + ' '
        '<span class="aw-count">' + str(len(dec)) + '</span></div>'
        '<div class="aw-body">' + body + '</div></div>'
    )

    # 3) Open questions — ONE block of the shared .an-rec question snippet (same as
    # the client dashboard). Needs-answer surfaced, the rest collapsed.
    _qs = vm['questions']
    _srt = sorted(_qs, key=lambda q: (_PRIO.get(q.get('priority', 'normal'), 1),
                                      -(q.get('stale') or 0), -(q.get('age') or 0)))
    # Surface the genuinely-needed (high-priority) questions; collapse the rest as
    # «наблюдения» — the same needs-answer-vs-observations split the client card uses.
    _high = [q for q in _srt if q.get('priority') == 'high']
    _shown = _high if _high else _srt[:3]
    _shown_ids = {id(q) for q in _shown}
    _remaining = [q for q in _srt if id(q) not in _shown_ids]

    def _q_item(q):
        # Map an aggregated open question onto the shared snippet item — the SAME
        # .an-rec row the client dashboard renders (one snippet everywhere). Acting
        # on a question happens in its modal (click), not via inline buttons.
        return {
            'title': (q.get('text') or '').strip(),
            'client': q.get('client') or '',
            'next_action': q.get('hypothesis') or '',
            'attrs': make_attrs(q) if make_attrs else '',
            'priority': q.get('priority', 'normal'),
            'due_days': None,
        }
    _shown_html = _render_task_rows([_q_item(q) for q in _shown], esc, kind='question')
    _more_html = (
        '<details class="an-bg"><summary>' + esc(t('observations'))
        + ' <span class="an-count">' + str(len(_remaining)) + '</span></summary>'
        + _render_task_rows([_q_item(q) for q in _remaining], esc, kind='question')
        + '</details>') if _remaining else ''
    questions = (
        '<div class="an-widget an-questions"><div class="an-head"><span class="an-title">'
        + esc(t('❓ Open questions')) + '</span><span class="an-count">' + str(len(_qs)) + '</span></div>'
        + _shown_html + _more_html + '</div>'
    ) if _qs else ''

    _parts = {'brief': brief, 'decisions': decisions, 'questions': questions}
    return '<section class="brief-zone">' + ''.join(_parts[s] for s in sections) + '</section>'

BRIEF_CSS = (
    ".brief-lead{}"
    ".brief-text{color:var(--text-primary);font-size:15px;line-height:1.6}"
    ".brief-sub{font-size:14px;color:var(--text-secondary);margin-top:2px;line-height:1.4}"
    ".brief-age{font-size:14px;padding:3px 10px;border-radius:6px;background:var(--bg-page);"
    "color:var(--text-muted);white-space:nowrap;flex-shrink:0;min-width:100px;text-align:center}"
    ".brief-q{padding:10px 0;border-bottom:1px solid var(--border)}"
    ".brief-q:last-child{border-bottom:none}"
    ".brief-q-head{margin-bottom:2px}"
    ".brief-hyp{font-size:14px;color:var(--text-muted);margin:2px 0 8px 108px;line-height:1.4}"
    ".brief-opts{display:flex;gap:6px;flex-wrap:wrap;margin-left:108px}"
    ".brief-opt{font-size:14px;padding:4px 11px;border:1px solid var(--border);background:var(--bg-card);"
    "color:var(--text-primary);border-radius:6px;cursor:pointer;font-family:inherit;transition:all 120ms}"
    ".brief-opt:hover{border-color:var(--accent-blue);color:var(--accent-blue)}"
    ".brief-opt.rec{border-color:var(--accent-blue);background:var(--blue-bg);color:var(--accent-blue)}"
    ".rec-tag{font-size:12px;margin-left:6px;color:var(--accent-blue)}"
    ".brief-opt-free{border:none;background:none;color:var(--text-secondary)}"
    ".brief-opt-free:hover{color:var(--accent-blue)}"
    ".brief-stale{font-size:14px;color:#8A6730;background:var(--yellow-bg);padding:1px 7px;border-radius:6px;white-space:nowrap}"
    ".aw-decisions{}"
    ".aw-decisions .aw-head{color:var(--accent-red)}"
    ".aw-decisions .aw-row{background:var(--red-bg);border-bottom:none;margin-bottom:6px}"
    ".aw-decisions .aw-row:hover{background:#F4CBC4}"
    ".aw-questions{}"
    ".aw-questions .aw-head{color:var(--text-primary)}"
    ".aw-questions-all{}"
    ".aw-questions-all>summary{cursor:pointer;list-style:none}"
    ".aw-questions-all>summary::-webkit-details-marker{display:none}"
    ".aw-questions-all .aw-head{color:var(--text-primary)}"
    ".qa-client{font-size:13px;font-weight:600;color:var(--text-secondary);margin:10px 0 3px;text-transform:uppercase;letter-spacing:.03em}"
    ".qa-client:first-child{margin-top:0}"
    ".qa-n{color:var(--text-muted);font-weight:500}"
    ".qa-row{padding:5px 0}"
    ".qa-more{margin-top:8px}"
    ".qa-more>summary{cursor:pointer;display:block;width:100%;text-align:center;padding:9px;color:var(--accent-blue);font-size:13px;font-weight:500;list-style:none;border-top:1px solid var(--border)}"
    ".qa-more>summary::-webkit-details-marker{display:none}"
    ".qa-more-body{margin-top:4px}"
)


# === Narrative layer: "Analysis and recommendations" (synthesis, not fact) ===
# Stored as a fenced ```analysis {JSON} ``` block in mental_model.md (system-wide/client).
# Written/refreshed by mm_update; rendering is read-only; marks "stale" if its date < last movement.
import re as _re_an


def load_analysis_text(txt):
    """Extracts {updated_at, summary, recommendations[]} from the ```analysis block in the text. {} if missing/broken."""
    m = _re_an.search(r"```analysis\s*\n(.*?)\n```", txt or "", _re_an.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1)) or {}
    except Exception:
        return {}


def build_client_analysis_from_state(client_id, client_name, state_read, today):
    """State-derived view for one client, SPLIT by task_type.

    A `task_type == 'open_question'` item is an unknown to resolve, not an action
    the operator performs — so it goes to a separate `questions` list, never into
    `recommendations`. Recommendations are REAL tasks (top 3 by priority/due).
    Every row carries the track data-attrs so a click opens the real task/question
    modal (identical to the Plan). Returns {} when there is nothing active.
    """
    try:
        tdata = state_read(client_id, 'tasks.json') or {}
    except Exception:
        tdata = {}
    tasks = tdata.get('tasks', []) if isinstance(tdata, dict) else (tdata or [])
    _ACTIVE = ('active', 'open', 'in_progress', 'awaiting', 'awaiting_external')
    active = [tr for tr in tasks if isinstance(tr, dict) and tr.get('status') in _ACTIVE]
    if not active:
        return {}
    real = [tr for tr in active if tr.get('task_type') != 'open_question']
    questions = [tr for tr in active if tr.get('task_type') == 'open_question']
    # Triage questions: a question earns queue space only if it fills a required
    # field (resolves_when) OR is high/normal priority. Low-priority items with no
    # resolves_when are speculative observations (e.g. auto-derived from analysis) →
    # collapsed + UNCOUNTED, so they never inflate the attention queue.
    def _needs_answer(tr):
        return bool(tr.get('resolves_when')) or tr.get('priority') in ('high', 'normal')
    q_needed = [tr for tr in questions if _needs_answer(tr)]
    q_bg = [tr for tr in questions if not _needs_answer(tr)]

    # data-track-* attrs so a row opens the canonical task/question modal.
    try:
        from _track_attrs import build_track_data_attrs as _bda
    except Exception:
        _bda = None

    def _attrs(tr):
        if not _bda:
            return ''
        try:
            return _bda(dict(tr, client_id=client_id), _esca, today=today)
        except Exception:
            return ''

    def _prio(tr):
        return _PRIO.get(tr.get('priority', 'normal'), 1)

    # summary — tasks and (only the needs-answer) questions, counted SEPARATELY.
    # The single nearest deadline is NOT computed here: it lives once, in the
    # Context strip, sourced from the tax calendar (the authoritative deadline
    # source). Computing a second "nearest" from task due-dates produced a
    # contradictory, less-urgent date — so it's removed.
    nt, nq = len(real), len(q_needed)
    bits = []
    if nt:
        bits.append(str(nt) + ' ' + t('tasks in flight'))
    if nq:
        bits.append(str(nq) + ' ' + t('open questions'))
    counts = ' · '.join(bits)
    if counts:
        counts += '.'
    # Operator situation brief — authored by mm_update and stored in state
    # (state/brief.json); the engine never reads mental_model.md. Falls back to
    # the plain counts line when the brief is absent.
    try:
        _brief_state = state_read(client_id, 'brief.json') or {}
    except Exception:
        _brief_state = {}
    ai_summary = ((_brief_state.get('summary') or '').strip()
                  if isinstance(_brief_state, dict) else '')
    summary = ai_summary or counts

    # How many tasks each task UNBLOCKS — a real dependency (others' blocked_by
    # point at it), not prose. A prerequisite that gates other work must be done
    # first, so it ranks ahead of them regardless of its own priority/due.
    _dep_count = {}
    for _t in tasks:
        for _b in (_t.get('blocked_by') or []):
            if _b:
                _dep_count[_b] = _dep_count.get(_b, 0) + 1

    # Lookup + "is it still open" + "the open blocker" — for the blocked marker.
    from _status import normalize_status as _ns
    _DONE = ('done', 'paid', 'cancelled', 'dropped', 'deferred')
    _by_id = {tr.get('id'): tr for tr in tasks if isinstance(tr, dict) and tr.get('id')}
    _open = lambda tr: _ns(tr.get('status', '')) not in _DONE

    def _blocker_of(tr):
        for b in (tr.get('blocked_by') or []):
            bt = _by_id.get(b)
            if bt and _open(bt):
                return bt          # first still-open blocker
        return None

    def _row(tr):
        # third line = the system's hypothesis (assist lens), else next_action —
        # SAME priority the plan rows use. Replaced by the blocker when blocked.
        na = ((tr.get('assist') or {}).get('hypothesis') or tr.get('next_action') or '').strip()
        dd = _to_date(tr.get('due_date'))
        _blk = _blocker_of(tr)
        return {
            'priority': tr.get('priority', 'normal'),
            'title': tr.get('title') or '',
            'due': dd.strftime('%d.%m') if dd else '',
            'due_days': ((dd - today).days if dd else None),
            'amount': (tr.get('amount')
                       if tr.get('amount') is not None
                       else (tr.get('type_specific') or {}).get('amount')),
            'task_type': tr.get('task_type'),
            'next_action': na,
            'unblocks': _dep_count.get(tr.get('id'), 0),
            'blocker_title': (_blk.get('title') or '') if _blk else '',
            'blocker_attrs': _attrs(_blk) if _blk else '',
            'attrs': _attrs(tr),
        }

    # SIMPLE deadline order (intuitive, transparent). Blocked tasks are NOT hidden
    # or reordered — they keep their urgency slot, get a clear «🔒 blocked» marker,
    # and link straight to the blocker so the operator can jump to what unblocks them.
    real_open = [tr for tr in tasks if isinstance(tr, dict)
                 and tr.get('task_type') != 'open_question' and _open(tr)]

    def _due_key(tr):
        dd = _to_date(tr.get('due_date'))
        return ((dd - today).days if dd else 10 ** 9, _prio(tr))
    _qsort = lambda L: sorted(L, key=lambda x: (_prio(x), _to_date(x.get('due_date')) or date.max))
    recs = [_row(tr) for tr in sorted(real_open, key=_due_key)[:3]]
    qrows = [_row(tr) for tr in _qsort(q_needed)]
    qbg_rows = [_row(tr) for tr in _qsort(q_bg)]
    return {'updated_at': today.isoformat(), 'summary': summary, 'counts': counts,
            'recommendations': recs, 'questions': qrows, 'questions_bg': qbg_rows,
            'task_count': nt, 'question_count': nq, 'bg_count': len(q_bg)}


_PR_CLS = {"high": "an-pr-high", "normal": "an-pr-normal", "low": "an-pr-low"}


def ref_chip(title, attrs, esc, glyph='&#128274;'):
    """THE clickable track-reference chip — the Plan's «🔒 → blocker» pattern,
    extracted so every track reference reuses ONE markup: blockers on the Plan, and
    risk-linked tasks / tax-calendar tasks / counterparty tasks on the client
    dashboard. `attrs` is the data-track-* string from build_track_data_attrs — when
    present the chip is a `track-card-clickable` that opens the canonical modal; when
    absent (a stale / unresolved ref) it degrades to a non-clickable `.an-dep-static`
    label. `glyph` is the optional leading icon (the lock 🔒 for a blocker); pass ''
    for none — the trailing → already signals the chip navigates."""
    lead = ('<span class="an-dep-arrow">' + glyph + '</span> ') if glyph else ''
    if attrs:
        return ('<div class="an-dep track-card-clickable"' + attrs + '>' + lead
                + esc(title) + '<span class="an-dep-go">&rarr;</span></div>')
    return '<div class="an-dep an-dep-static">' + lead + esc(title) + '</div>'


def render_task_snippet(r, esc, kind='task'):
    """THE one task-row snippet, used everywhere — overview «Сводка», client
    «Сводка», the Plan and the per-client plan ("Активные треки"). A
    `track-card-clickable` carrying canonical data-track-* attrs, so a click opens
    the REAL task/question modal. Keyboard-activable.

    The ONLY per-surface difference is the «признаки клиента» (avatar + client
    line): present on cross-client lists, omitted on a single client's card. That
    is driven purely by whether the item carries `avatar` / `client` — the caller
    decides, the snippet does not branch on the surface.

    Item keys: title, attrs, avatar=(initials, style) | None, client, priority,
    next_action, blocker_title, blocker_attrs, unblocks, due_days,
    status_html (pre-rendered chip; if absent an «заблокировано» badge is derived
    from an open blocker), kind."""
    pcls = _PR_CLS.get(r.get("priority", "normal"), "an-pr-normal")
    na = (r.get("next_action") or "").strip()
    sub = ('<div class="an-why">' + esc(na) + '</div>') if na else ""
    # THE shared due badge (engine/_components.due_badge) — defined once, reused.
    from _components import due_badge
    due_chip = due_badge(r.get('due_days'))
    unb = r.get('unblocks') or 0
    unb_chip = ('<span class="an-unblocks">' + esc(t('unblocks {}').format(unb)) + '</span>') if unb else ""
    # Reporting period of THIS row — rendered INLINE, muted, right after the title
    # (not a badge: the chip row is already busy). On the Plan/Calendar waves are
    # grouped purely by operation (periods collapsed), so the row carries its own
    # period; the caller sets `period` only there, so other surfaces are unaffected.
    per_inline = ('<span class="an-period-inline">· ' + esc(r.get('period')) + '</span>') if r.get('period') else ""
    # Dependency: rendered like the track-modal's «Зависит от» — «🔒 → <blocker>»,
    # clickable (its own track-card-clickable) so the operator jumps straight to the
    # blocker. Replaces the hypothesis line when blocked.
    blk_html = ""
    if r.get("blocker_title"):
        blk_html = ref_chip(r["blocker_title"], r.get("blocker_attrs") or "", esc)
    # Status chip: an explicit pre-rendered chip (the Plan passes its «ждём» /
    # «заблокирован» pill) wins; otherwise derive «заблокировано» from an open
    # blocker so the Сводка rows still read as blocked.
    status_chip = r.get("status_html") or ""
    if not status_chip and r.get("blocker_title"):
        status_chip = '<span class="an-blocked">' + esc(t('blocked')) + '</span>'
    # Marker: a client avatar when given (cross-client lists), else the priority
    # ring / ? mark. Omitting the avatar IS how a single client's card drops it.
    _av = r.get('avatar')
    if _av:
        _ini, _avst = _av
        marker = '<span class="an-av"' + (_avst or '') + '>' + esc(_ini) + '</span>'
    elif kind == 'question':
        marker = '<span class="an-q" aria-hidden="true">?</span>'
    else:
        marker = '<span class="an-check ' + pcls + '" aria-hidden="true"></span>'
    return (
        '<div class="an-rec track-card-clickable" role="button" tabindex="0"' + (r.get('attrs') or '')
        + " onkeydown=\"if(event.key==='Enter'||event.key===' '){event.preventDefault();this.click();}\">"
        + marker
        + '<div class="an-rec-body"><div class="an-rec-title">'
        + '<span class="an-rec-title-text">' + esc(r.get("title", "")) + '</span>' + per_inline + '</div>'
        + (('<div class="an-client">' + esc(r.get("client")) + '</div>') if r.get("client") else "")
        + (blk_html if r.get("blocker_title") else sub) + '</div>'
        + status_chip + unb_chip + due_chip
        + '<span class="an-go">&rarr;</span>'
        '</div>')


def _render_task_rows(items, esc, kind='task'):
    """Render a list of items with the shared snippet."""
    return ''.join(render_task_snippet(r, esc, kind=kind) for r in items)


def render_analysis_zone(analysis, today, last_change=None, esc=None, esca=None):
    """"Analysis & recommendations": situation summary + the top REAL tasks
    (clickable through to the real task). Questions live in their own section."""
    esc = esc or _esc; esca = esca or _esca
    if not analysis or not (analysis.get("summary") or analysis.get("recommendations")):
        return ""
    upd_d = _to_date(analysis.get("updated_at") or "")
    stale = bool(upd_d and last_change and last_change > upd_d)
    upd_txt = (t("updated {}").format(upd_d.strftime("%d.%m")) if upd_d else t("date ?"))
    stale_pill = ' <span class="an-stale">' + esc(t("stale — refresh")) + '</span>' if stale else ""
    rows = _render_task_rows(analysis.get("recommendations") or [], esc, kind='task')
    # "show all" → scrolls to the full operations list (#all-tasks)
    more = ('<a class="an-more" href="#all-tasks">' + esc(t('Show all tasks')) + ' &rarr;</a>') if rows else ""
    recs_html = ('<div class="an-recs-label">' + esc(t("Top for today")) + '</div>' + rows + more) if rows else ""
    summary = analysis.get("summary", "")
    counts = analysis.get("counts", "")
    summ = ('<p class="an-summary">' + esc(summary) + '</p>') if summary else ""
    # counts as a small secondary line, only when the hero summary is the AI brief
    counts_line = ('<div class="an-counts">' + esc(counts) + '</div>') if (counts and counts != summary) else ""
    return (
        '<div class="an-widget">'
        '<div class="an-head"><span class="an-title">' + esc(t('🧠 Analysis and recommendations')) + '</span>'
        '<span class="an-meta">' + esc(upd_txt) + ' · ' + esc(t('judgment, not fact')) + stale_pill + '</span></div>'
        + summ + counts_line + recs_html + '</div>'
    )


def render_client_questions(analysis, esc=None):
    """Open-questions section. Split: needs-answer (counted, surfaced) vs
    background observations (collapsed, UNCOUNTED) — speculative items that fill
    no required field don't inflate the attention queue."""
    esc = esc or _esc
    analysis = analysis or {}
    needed = analysis.get("questions") or []
    bg = analysis.get("questions_bg") or []
    if not needed and not bg:
        return ""
    head = ('<div class="an-head"><span class="an-title">' + esc(t('❓ Open questions'))
            + '</span><span class="an-count">' + str(len(needed)) + '</span></div>')
    body = _render_task_rows(needed, esc, kind='question')
    bg_html = ''
    if bg:
        bg_html = ('<details class="an-bg"><summary>' + esc(t('observations'))
                   + ' <span class="an-count">' + str(len(bg)) + '</span></summary>'
                   + _render_task_rows(bg, esc, kind='question') + '</details>')
    return '<div class="an-widget an-questions">' + head + body + bg_html + '</div>'


ANALYSIS_CSS = (
    ".an-widget{background:var(--bg-card);border:1px solid var(--border);"
    "border-radius:var(--radius-card);padding:16px 20px;margin-bottom:14px;box-shadow:none}"
    ".an-head{display:flex;justify-content:space-between;align-items:baseline;gap:var(--space-sm);"
    "margin-bottom:var(--space-sm);flex-wrap:wrap}"
    ".an-title{font-size:16px;font-weight:600;color:var(--text-primary)}"
    ".an-meta{font-size:14px;color:var(--text-muted)}"
    ".an-stale{color:var(--accent-red);font-weight:600}"
    ".an-summary{font-size:15px;line-height:1.6;color:var(--text-primary);margin:0 0 var(--space-md)}"
    ".an-recs-label{font-size:13px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;margin:14px 0 2px}"
    ".an-count{font-size:13px;color:var(--text-muted);font-weight:500}"
    # AI brief is the main summary; the counts sit under it as a quiet line
    # cap the measure (~72ch) so the brief prose doesn't run edge-to-edge across
    # the card — long lines hurt readability; this keeps a comfortable line length.
    ".an-summary{font-size:15px;line-height:1.6;color:var(--text-primary);margin:0 0 6px;max-width:880px}"
    ".an-counts{font-size:13px;color:var(--text-muted);margin:0 0 var(--space-md);max-width:880px}"
    # 'show all tasks' → scrolls to the operations list
    ".an-more{display:inline-block;margin-top:12px;font-size:13.5px;font-weight:500;color:var(--accent);cursor:pointer}"
    ".an-more:hover{color:var(--accent-text)}"
    # Clickable task / question row — opens the canonical modal (track-card-clickable).
    ".an-rec{display:flex;align-items:center;gap:13px;padding:12px;margin:0 -12px;"
    "border-top:1px solid var(--border);cursor:pointer;border-radius:8px;transition:background var(--transition)}"
    ".an-rec:hover{background:var(--bg-page)}"
    ".an-rec:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}"
    # status marker — a ring; colour encodes priority (real tasks)
    ".an-check{flex-shrink:0;width:18px;height:18px;border-radius:50%;border:2px solid var(--text-muted);box-sizing:border-box}"
    ".an-check.an-pr-high{border-color:var(--accent-red)}"
    ".an-check.an-pr-normal{border-color:var(--accent-blue)}"
    ".an-check.an-pr-low{border-color:var(--border-strong)}"
    # question marker — a '?' chip (distinct from a task)
    ".an-q{flex-shrink:0;width:18px;height:18px;border-radius:50%;background:var(--bg-subtle);"
    "color:var(--text-muted);font-size:12px;font-weight:700;display:inline-flex;align-items:center;justify-content:center}"
    # client avatar marker (cross-client rows) — same look as the plan avatars
    ".an-av{flex-shrink:0;width:30px;height:30px;border-radius:50%;display:inline-flex;"
    "align-items:center;justify-content:center;font-size:12px;font-weight:600;border:1px solid var(--border)}"
    ".an-rec-body{flex:1;min-width:0}"
    ".an-rec-title{font-size:15px;font-weight:600;color:var(--text-primary);"
    "display:flex;align-items:baseline;gap:6px;min-width:0}"
    ".an-rec-title-text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}"
    # period inline next to the title (Plan/Calendar period-less waves) — muted, light
    # weight, never clipped (the title text ellipsizes, the period stays).
    ".an-period-inline{flex:none;font-size:13px;font-weight:400;color:var(--text-muted);white-space:nowrap}"
    ".an-client{font-size:12.5px;color:var(--text-muted);margin-top:2px}"
    ".an-why{font-size:13px;color:var(--text-secondary);margin-top:3px;line-height:1.45;"
    "overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
    # dependency box — mirrors the track-modal's «Зависимости» (yellow, 🔒→link),
    # clickable to jump to the blocker. Replaces the hypothesis line when blocked.
    # background stays transparent until the row (or the chip) is hovered — keeps
    # the snippet calm; the padding is always reserved so nothing reflows on hover.
    # margin-left:-10px cancels the chip's own left padding so its lock/text align
    # to the title's left edge; the padding still gives the hover background room.
    ".an-dep{display:inline-flex;align-items:center;gap:6px;margin:-2px 0 0 -10px;padding:5px 10px;"
    "background:transparent;border-radius:6px;font-size:12.5px;color:#8A6730;"
    "font-weight:500;cursor:pointer;max-width:100%;transition:background var(--transition)}"
    ".an-dep .an-dep-arrow{color:var(--text-muted);flex-shrink:0;white-space:nowrap}"
    # trailing go-arrow on the right — signals the chip is a link even without hover
    ".an-dep .an-dep-go{padding-left:8px;color:var(--text-muted);flex-shrink:0}"
    # background appears only on the dep's OWN hover — signals it is separately
    # clickable (jumps to the blocker), distinct from clicking the whole row.
    ".an-dep:hover{background:var(--yellow-bg)}"
    ".an-dep:hover .an-dep-go{color:var(--accent)}"
    # a reference whose target task could not be resolved (stale id): same look,
    # but not clickable and no hover affordance.
    ".an-dep-static{cursor:default}"
    ".an-dep-static:hover{background:transparent}"
    # 'заблокировано' — status chip for a row whose blocker is still open
    ".an-blocked{flex-shrink:0;font-size:12px;font-weight:600;color:#854F0B;"
    "background:#FAEEDA;border-radius:6px;padding:3px 9px;white-space:nowrap}"
    # generic status chip (Plan passes «ждём»/«заблокирован»/… with inline colours)
    ".an-status{flex-shrink:0;font-size:12px;font-weight:600;border-radius:6px;"
    "padding:3px 9px;white-space:nowrap}"
    # (due date uses the shared .due-badge from DESIGN_TOKENS_CSS — no local copy)
    # 'unblocks N' — marks a prerequisite that gates other tasks (why it's first)
    ".an-unblocks{flex-shrink:0;font-size:12px;font-weight:600;color:var(--gold);"
    "background:var(--gold-soft);border-radius:6px;padding:3px 9px;white-space:nowrap}"
    ".an-go{flex-shrink:0;font-size:15px;color:var(--text-muted);opacity:.5;transition:opacity var(--transition)}"
    ".an-rec:hover .an-go{opacity:1;color:var(--accent)}"
    ".an-questions{margin-bottom:14px}"
    ".an-bg{margin-top:6px}"
    ".an-bg>summary{cursor:pointer;list-style:none;font-size:13px;color:var(--text-muted);font-weight:500;padding:7px 0}"
    ".an-bg>summary::-webkit-details-marker{display:none}"
    ".an-bg>summary::before{content:'\\25B8 ';color:var(--text-muted);font-size:11px}"
    ".an-bg[open]>summary::before{content:'\\25BE '}"
)


def latest_history_change(plan_dir):
    """Date of the last movement in history.jsonl across all clients (to mark "stale"). None if none."""
    import glob
    latest = None
    for hp in (glob.glob(os.path.join(plan_dir, '*', 'state', 'history.jsonl'))
               + glob.glob(os.path.join(plan_dir, '*', '*', 'state', 'history.jsonl'))):
        try:
            lines = open(hp, encoding="utf-8").read().strip().splitlines()
        except Exception:
            continue
        for ln in lines[-3:]:
            try:
                d = _to_date(json.loads(ln).get("ts"))
            except Exception:
                d = None
            if d and (latest is None or d > latest):
                latest = d
    return latest
