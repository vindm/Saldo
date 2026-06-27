"""Normalize task_type on service-fee-control rows to service_payment.

«Контроль оплаты услуг» / «Проверить оплату услуг …» is the practice's OWN
service-fee receivable — one reusable operation (`service_payment`). In state some
of these tasks were typed by INTERACTION MODE instead of by operation:
`client_followup` (active chase) or `awaiting_external` (postfactum wait). On the
Plan that scattered them into the «Запрос у клиента» / generic buckets instead of
batching with the rest of the service-payment work.

This migration actualizes state at the source: a task whose title denotes the
service-payment operation AND whose current type is a mode/generic token is
re-typed to `service_payment`; the original is preserved in `task_type_legacy`
(lossless / reversible, mirroring 0007's `next_action_legacy`).

The view already DERIVES `service_payment` from this same title shape for generic
types (engine/_plan_waves._OP_KEYWORDS) — so for those this only makes the STORED
type match what the engine shows; for the mode types it aligns them too. Pairs
with the `_op_canonical` guard (operation beats mode-type) and INSTRUCTIONS §0.4.

Idempotent: a task already typed `service_payment` is untouched. Schema-level —
matched by the title SHAPE («оплат… услуг»), no client names, no per-client logic;
the file carries zero real data.

    tasks[].task_type (service-fee row, mode/generic) -> 'service_payment'
        (+ task_type_legacy: <original>)
"""
import re

ID = "0014"
DESCRIPTION = "tasks: type service-fee-control rows as service_payment (original kept in task_type_legacy)"

# The service-fee operation in the title — mirrors the service_payment keyword in
# engine/_plan_waves._OP_KEYWORDS, narrowed to the unambiguous «услуг» phrasing so
# it can't catch a supplier payment.
_SERVICE_FEE_RX = re.compile(r'оплат\w*\s+услуг|service\s+payment|client\s+payment', re.I)

# Types that describe interaction MODE / generic status, not the operation — only
# these are re-typed. A task already carrying a real operation type is left alone.
_MODE_OR_GENERIC = {"client_followup", "client_action", "awaiting_external",
                    "awaiting_external_then_action", "other"}


def up(api):
    def fix(client_id, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return False, ""
        changed = 0
        for tk in tasks:
            if not isinstance(tk, dict):
                continue
            tt = (tk.get("task_type") or "").strip()
            if tt == "service_payment" or tt not in _MODE_OR_GENERIC:
                continue
            title = (tk.get("title") or tk.get("what") or "")
            if not _SERVICE_FEE_RX.search(title):
                continue
            tk.setdefault("task_type_legacy", tt)
            tk["task_type"] = "service_payment"
            changed += 1
        if not changed:
            return False, ""
        return True, "re-typed %d service-fee task(s) to service_payment" % changed

    api.for_each_client("tasks.json", fix)


# ---------------------------------------------------------------------------
# AI-side surface (RUNTIME_PASS spec, added 2026-06-26). Optional; up() unchanged.
# A slice of the shared TASK CLASSIFIER (migrations/TASK_CLASSIFIER.md). up() keys
# on the strict «оплат… услуг» adjacency; preflight surfaces service-fee tasks
# phrased beyond it (e.g. «оплата ЗА услуги», reversed order, a synonym) for the
# runtime to classify per task-types.md / INSTRUCTIONS §0.4.
# ---------------------------------------------------------------------------

try:  # shared classifier prescreen lives in the engine (single source of truth)
    import _task_classifier as _tc   # guarded: a helper issue must never break discovery
except Exception:
    _tc = None


def preflight(api):
    """READ step -> shared task classifier (TYPE dimension). One scan,
    one source of rules; see migrations/TASK_CLASSIFIER.md."""
    return _tc.type_candidates(api) if _tc else []


RUNTIME_PASS = {
    "intent": (
        "For each flagged task, decide per task-types.md / INSTRUCTIONS §0.4 whether "
        "it is really the practice's OWN service-fee receivable (service_payment) — "
        "as opposed to a supplier / bank / tax payment. If yes and clear, re-type to "
        "service_payment and preserve task_type_legacy. If it could be a non-fee "
        "payment, LEAVE it. See migrations/TASK_CLASSIFIER.md."
    ),
    "scope": "tasks[].task_type",
    "escalate": "on_anomaly",
    "guardrails": [
        "only re-type a task preflight flagged",
        "preserve the original in task_type_legacy",
        "leave it if the fee-vs-other-payment call is not clear",
        "change only the type; keep every fact / id / amount",
    ],
}

EXPECT = {
    "preflight_max": 20,
    "change_kinds": ["needs_task_classification"],
}

SCENARIO = [
    "A service-fee task that up() missed (e.g. «оплата за услуги», reversed order) "
    "now batches in the «Оплата услуг клиентом» wave with task_type_legacy kept; a "
    "supplier/tax payment with similar words was NOT re-typed; no real operation "
    "type was overwritten.",
]
