"""Anchor service_payment tasks to their BILLING QUARTER (type_specific.period).

The service fee is billed per quarter, but the quarter lived only in the human title
(«Контроль оплаты услуг — Q2 2026», «… 1кв 2026»), not in a structured field. So the
period view derived a misleading DUE month (Q2, due 20.07 → «июль») instead of the
quarter being billed, and the practice-level «Оплата услуг» lane on the Periods page
could not group by quarter. This migration extracts the billing quarter from the title
into `type_specific.period` ("YYYY-Qn") — the period becomes the source of truth.

Parentheticals are dropped first, so «… 1кв 2026 (4кв 2025 оплачено)» anchors to Q1
(the quarter being billed), not the paid-off aside. Idempotent: a task that already has
`type_specific.period` is untouched; a generic fee task with no quarter in its title is
left period-less. Schema-level — gate is `task_type==service_payment` + a quarter-token
shape; no client names, zero real data.

    tasks[].type_specific.period (service_payment, parsed from title) -> "YYYY-Qn"
"""
import re

ID = "0016"
DESCRIPTION = "tasks: anchor service_payment to its billing quarter (type_specific.period from title)"

_RX_Q = re.compile(r'\bQ([1-4])\s*(\d{4})', re.I)
_RX_KV = re.compile(r'\b([1-4])\s*кв\.?\s*(\d{4})', re.I)


def _quarter(title):
    base = re.sub(r'\([^)]*\)', '', title or '')  # drop «(4кв 2025 оплачено)» asides
    m = _RX_Q.search(base) or _RX_KV.search(base)
    return (m.group(2) + "-Q" + m.group(1)) if m else None


def up(api):
    def fix(client_id, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return False, ""
        changed = 0
        for tk in tasks:
            if not isinstance(tk, dict):
                continue
            if (tk.get("task_type") or "").strip() != "service_payment":
                continue
            ts = tk.get("type_specific")
            if not isinstance(ts, dict):
                ts = {}
            if ts.get("period"):
                continue
            q = _quarter(tk.get("title") or tk.get("what") or "")
            if not q:
                continue
            ts["period"] = q
            tk["type_specific"] = ts
            changed += 1
        if not changed:
            return False, ""
        return True, "anchored %d service_payment task(s) to billing quarter" % changed

    api.for_each_client("tasks.json", fix)


# ---------------------------------------------------------------------------
# AI-side surface (RUNTIME_PASS spec, added 2026-06-26). Optional; up() unchanged.
# This is the FIRST structured-field pass (period, not prose) and the first slice
# of the planned shared TASK CLASSIFIER (unifying 0014/0015/0016 — typing + period
# + routing by reading the task, per INSTRUCTIONS §0.4 / task-types.md). The
# deterministic up() anchors the period only when the QUARTER TOKEN is in the
# title; the tasks it leaves period-less are where the quarter must be INFERRED
# from context/next_action/date — a judgment, hence a runtime pass. period feeds
# only the Periods view/chip + the service-fee lane (render leaf), so it is safe
# for the runtime to write under the terminal-leaf invariant.
# ---------------------------------------------------------------------------

try:  # shared classifier prescreen lives in the engine (single source of truth)
    import _task_classifier as _tc   # guarded: a helper issue must never break discovery
except Exception:
    _tc = None


def preflight(api):
    """READ step -> shared task classifier (PERIOD dimension). One scan,
    one source of rules; see migrations/TASK_CLASSIFIER.md."""
    return _tc.period_candidates(api) if _tc else []


RUNTIME_PASS = {
    "intent": (
        "For each flagged service_payment task with no type_specific.period, INFER "
        "the billing quarter ('YYYY-Qn') from the title / context / next_action and "
        "the task's date when the evidence supports it (e.g. «оплата за прошлый "
        "квартал», a due date, «Q1 оплачен, ждём Q2»). If the quarter is genuinely "
        "indeterminate, LEAVE it period-less — never guess. Record provenance "
        "type_specific.period_source='runtime_inferred' so an inferred period is "
        "distinguishable from a title-parsed one. Terminal leaf: period only feeds "
        "the Periods view / service-fee lane."
    ),
    "scope": "tasks[].type_specific.period (task_type == service_payment)",
    "escalate": "on_anomaly",
    "guardrails": [
        "only set period on a service_payment task preflight flagged (no existing period)",
        "format strictly 'YYYY-Qn'; infer only from evidence, never fabricate",
        "mark type_specific.period_source='runtime_inferred' for auditability",
        "leave genuinely-indeterminate tasks period-less",
    ],
}

EXPECT = {
    "preflight_max": 20,
    "change_kinds": ["needs_period_inference"],
}

SCENARIO = [
    "On the Periods page, a service_payment task that was period-less now sits under "
    "its INFERRED quarter, carrying period_source='runtime_inferred'; a task with no "
    "quarter evidence is STILL period-less (not fabricated); the «Оплата услуг» lane "
    "groups by quarter correctly and the misleading derived due-month is gone.",
]
