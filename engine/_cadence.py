"""Derived bookkeeping cadence — the tightest periodic obligation a client carries.

See docs/CADENCE.md. The bookkeeping conveyor (collect -> post -> close) has no legal
deadline of its own; its required frequency is the *tightest* downstream filing the client
must be ready for. This module derives that frequency from the pack-declared obligation
streams (jurisdictions/<code>/obligations.yaml) resolved AS-OF a period against the client's
structured state (regime / payroll roster / financials) — never from a stored flag, and never
from the narrative mental_model (a legal cadence floor is behaviour, and per the 0013 JSON-first
rule the engine reads structured state only).

Design:
  * The CORE is pure: resolve_bookkeeping_cadence(obligations, state, period) takes plain dicts
    and returns a cadence token (or None when undetermined). It does no file I/O, so it is fully
    unit-testable (tests/test_cadence.py).
  * resolve_for_client(client_id, period) is a thin I/O wrapper that loads the obligations and
    the client state via the existing loaders, then calls the core.

This module touches no rendering. Its consumers (the periods view, the lint, the task updater)
are wired separately and later.
"""

import datetime
import re

# Regular periodic cadences that can set a bookkeeping FLOOR, tightest first.
# `per_term` (PSN — paid on each patent's own term) and `event` (EFS-1 — on personnel
# events) are NOT regular bookkeeping drivers, so they never set the floor; they are
# excluded from this ranking on purpose (see the PSN example in obligations.yaml).
_PERIOD_RANK = {
    "monthly": 0,
    "quarterly": 1,
    "semester": 2,
    "annual": 3,
}


# ---------------------------------------------------------------------------
# Period parsing — a period STRING (as state records it) -> (start, end) dates.
# Recognised: "YYYY-MM" (month), "YYYY-Qn" (quarter), "YYYY-Hn" (half-year), "YYYY" (year).
# ---------------------------------------------------------------------------
def _last_day(year, month):
    if month == 12:
        return datetime.date(year, 12, 31)
    return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)


def period_bounds(period):
    """(start_date, end_date) for a period string, or None if unparseable.

    The END date is the moment the books must cover for that period — the anchor for every
    as-of check (a hire counts if it took effect on or before the period end, etc.).
    """
    if not period:
        return None
    p = str(period).strip().upper()

    m = re.fullmatch(r"(\d{4})-(\d{2})", p)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return (datetime.date(y, mo, 1), _last_day(y, mo))
        return None

    m = re.fullmatch(r"(\d{4})-Q([1-4])", p)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        start_mo = (q - 1) * 3 + 1
        return (datetime.date(y, start_mo, 1), _last_day(y, start_mo + 2))

    m = re.fullmatch(r"(\d{4})-H([12])", p)
    if m:
        y, h = int(m.group(1)), int(m.group(2))
        if h == 1:
            return (datetime.date(y, 1, 1), datetime.date(y, 6, 30))
        return (datetime.date(y, 7, 1), datetime.date(y, 12, 31))

    m = re.fullmatch(r"(\d{4})", p)
    if m:
        y = int(m.group(1))
        return (datetime.date(y, 1, 1), datetime.date(y, 12, 31))

    return None


def period_cadence(period):
    """The cadence a period STRING represents on its own: YYYY-MM -> monthly, YYYY-Qn -> quarterly,
    YYYY-Hn -> semester, bare YYYY -> annual. None if unparseable. This classifies the ROW's own
    period (for a rhythm chip); the client's REQUIRED cadence is resolve_bookkeeping_cadence."""
    p = str(period or "").strip().upper()
    if re.fullmatch(r"\d{4}-\d{2}", p):
        return "monthly"
    if re.fullmatch(r"\d{4}-Q[1-4]", p):
        return "quarterly"
    if re.fullmatch(r"\d{4}-H[12]", p):
        return "semester"
    if re.fullmatch(r"\d{4}", p):
        return "annual"
    return None


def _parse_date(v):
    """Best-effort ISO date parse (YYYY-MM-DD / YYYY-MM / YYYY). None on failure."""
    if not v:
        return None
    s = str(v).strip()[:10]
    for fmt, pad in (("%Y-%m-%d", s), ("%Y-%m", s + "-01"), ("%Y", s + "-01-01")):
        try:
            return datetime.datetime.strptime(pad, "%Y-%m-%d").date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# As-of predicates — each reads structured state at the period boundary.
# ---------------------------------------------------------------------------
_START_KEYS = ("hired", "hire_date", "start", "since", "from", "effective")
_END_KEYS = ("terminated", "fired", "until", "end", "to", "dismissed")


def _regime_type(state):
    reg = (state or {}).get("regime") or {}
    primary = reg.get("primary") or {}
    return str(primary.get("type") or "").strip().upper()


def _employed_as_of(emp, period_end):
    """An employee record counts as employed for the period if it started on or before the
    period end and had not ended before it. A record with no dates is treated as employed
    (presence in the roster = employed)."""
    start = None
    for k in _START_KEYS:
        if emp.get(k):
            start = _parse_date(emp.get(k))
            if start:
                break
    end = None
    for k in _END_KEYS:
        if emp.get(k):
            end = _parse_date(emp.get(k))
            if end:
                break
    if start and start > period_end:
        return False
    if end and end < period_end:
        return False
    return True


def _has_employees_as_of(state, period_end):
    roster = ((state or {}).get("payroll") or {}).get("employees") or []
    if isinstance(roster, list) and any(
            isinstance(e, dict) and _employed_as_of(e, period_end) for e in roster):
        return True
    # Declaration fallback: the operator may assert staff (regime.has_employees, a PRIMARY fact)
    # before the structured roster is populated — that fact still sets a monthly floor. The
    # state_lint payroll check separately nags to fill the roster. (has_employees is therefore a
    # declaration, NOT a cache to retire; the roster reconciles to it.)
    reg = (state or {}).get("regime") or {}
    return reg.get("has_employees") is True


def _active_patent_as_of(state, start, end):
    """A patent is active for the period if its status is active and (when it carries dates)
    its term overlaps the period; date-less patents fall back to status alone."""
    reg = (state or {}).get("regime") or {}
    patents = reg.get("patents") or []
    if not isinstance(patents, list):
        return False
    for pt in patents:
        if not isinstance(pt, dict):
            continue
        status = str(pt.get("status") or "").strip().lower()
        if status and status != "active":
            continue
        pstart = _parse_date(pt.get("from") or pt.get("start") or pt.get("since"))
        pend = _parse_date(pt.get("to") or pt.get("until") or pt.get("end"))
        if pstart and pstart > end:
            continue
        if pend and pend < start:
            continue
        return True
    return False


def _turnover_to_date(state, period_end):
    """Sum of recorded turnover for the period_end's YEAR up to and including that period.
    Best-effort over financials.periods[]; None if nothing usable."""
    fin = (state or {}).get("financials") or {}
    periods = fin.get("periods") or []
    if not isinstance(periods, list):
        return None
    total = None
    for e in periods:
        if not isinstance(e, dict):
            continue
        b = period_bounds(e.get("period"))
        if not b:
            continue
        _, e_end = b
        if e_end.year != period_end.year or e_end > period_end:
            continue
        for k in ("turnover", "revenue", "income", "amount"):
            if isinstance(e.get(k), (int, float)):
                total = (total or 0) + e[k]
                break
    return total


def _vat_threshold(state, year):
    fin = (state or {}).get("financials") or {}
    for k in ("nds_threshold_%d" % year, "nds_threshold", "vat_threshold"):
        v = fin.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


def _vat_liable_as_of(state, start, end):
    rt = _regime_type(state)
    if rt == "OSNO":
        return True
    if rt == "USN":
        turnover = _turnover_to_date(state, end)
        threshold = _vat_threshold(state, end.year)
        if turnover is not None and threshold is not None:
            return turnover >= threshold
    return False


def applies_as_of(token, state, period):
    """Resolve an obligation's `applies_when` predicate against state, as of `period`.
    Unknown tokens resolve False (a pack predicate the engine does not know stays inert)."""
    bounds = period_bounds(period)
    if not bounds:
        return False
    start, end = bounds
    rt = _regime_type(state)
    if token == "regime_usn":
        return rt == "USN"
    if token == "regime_ausn":
        return rt == "AUSN"
    if token == "regime_osno":
        return rt == "OSNO"
    if token == "has_employees":
        return _has_employees_as_of(state, end)
    if token == "has_active_patent":
        return _active_patent_as_of(state, start, end)
    if token == "vat_liable":
        return _vat_liable_as_of(state, start, end)
    return False


# ---------------------------------------------------------------------------
# Cadence resolution.
# ---------------------------------------------------------------------------
def min_period(cadences):
    """The tightest (shortest-period) cadence among the given tokens, or None.
    Only regular periodic cadences participate; per_term / event / unknowns are ignored."""
    ranked = [(_PERIOD_RANK[c], c) for c in cadences if c in _PERIOD_RANK]
    if not ranked:
        return None
    return min(ranked)[1]


def delivery_cadence(value):
    """Map a free-text source-doc delivery frequency (behavior.json `bank_statement_frequency`)
    to a regular cadence token, or None when it is not a regular cadence (`on_request`,
    `before_reporting`, blank, unknown). Delivery is client LOGISTICS — a separate fact from the
    derived work cadence — but it must stay answerable to it (see `is_delivery_looser`)."""
    s = str(value or "").strip().lower()
    if not s:
        return None
    if "month" in s or "месяч" in s:
        return "monthly"
    if "quart" in s or "кварт" in s:
        return "quarterly"
    if "semest" in s or "half" in s or "полугод" in s:
        return "semester"
    if "annual" in s or "year" in s or "год" in s:
        return "annual"
    return None


def is_delivery_looser(delivery, required):
    """True if `delivery` is LOOSER (longer period) than `required` — the client sends documents
    less often than the books must be done, so the period cannot be posted on time. Both must be
    regular cadences; otherwise (unknown delivery / undetermined requirement) returns False — the
    lint stays silent when it cannot judge."""
    if delivery not in _PERIOD_RANK or required not in _PERIOD_RANK:
        return False
    return _PERIOD_RANK[delivery] > _PERIOD_RANK[required]


def active_streams_as_of(obligations, state, period):
    """[(obligation_code, cadence), ...] for streams that apply to the client as of `period`."""
    out = []
    for code, obl in (obligations or {}).items():
        if not isinstance(obl, dict):
            continue
        if applies_as_of(obl.get("applies_when"), state, period):
            out.append((code, obl.get("cadence")))
    return out


def resolve_bookkeeping_cadence(obligations, state, period):
    """PURE CORE. The derived bookkeeping cadence token for a client in a period, or None when
    undetermined (no applicable regular-periodic obligation — caller surfaces it, never assumes
    monthly). `obligations` is the pack obligations dict; `state` is
    {regime, payroll, financials}; `period` is a period string ("YYYY-MM" / "YYYY-Qn" / ...)."""
    streams = active_streams_as_of(obligations, state, period)
    return min_period([c for _, c in streams])


# ---------------------------------------------------------------------------
# Thin I/O wrapper — loads obligations + client state, then calls the pure core.
# Not unit-tested (it does file I/O); the logic it delegates to is.
# ---------------------------------------------------------------------------
def resolve_for_client(client_id, period):
    """Convenience: resolve the bookkeeping cadence for a real client + period."""
    import _jurisdiction as _J
    import _plan_waves as _PW
    import state_ops as _S

    juris = _PW._client_jurisdiction(client_id)
    obligations = _J.load_jurisdiction(juris).obligations

    def _read(name):
        try:
            if _S.state_exists(client_id, name):
                return _S.state_read(client_id, name) or {}
        except Exception:
            pass
        return {}

    state = {
        "regime": _read("regime.json"),
        "payroll": _read("payroll.json"),
        "financials": _read("financials.json"),
    }
    return resolve_bookkeeping_cadence(obligations, state, period)
