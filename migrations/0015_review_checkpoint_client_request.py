"""Re-type a review_checkpoint that is RESOLVED BY ASKING THE CLIENT as client_followup.

`review_checkpoint` is a process marker (a control point), not an operation. When
the checkpoint's resolving action is a question to the client / their manager
(«уточнить у …», «спросить у …», «запросить у …»), the task IS a client request —
«Запрос у клиента» — and should batch into that bucket, not float as a stray row on
the Plan/Calendar. The substance lives in `next_action` / `context` (e.g. «30.06
уточнить у Анастасии статус подписания договора»), while the title reads as a
control («Контроль: подписан ли договор») and carries no request signal, so the
engine cannot infer it from the title alone.

This migration actualizes state at the source: a `review_checkpoint` whose
`next_action`/`context` matches the ask-the-client shape is re-typed to
`client_followup`; the original is preserved in `task_type_legacy` (lossless /
reversible). Pairs with INSTRUCTIONS §0.4 (type by the action, not the framing) and
with `client_followup` being a standing «Запрос у клиента» bucket.

Idempotent: a task already typed `client_followup` is untouched. Schema-level — the
gate is `task_type == review_checkpoint` + an ask-the-client verb shape; no client
names, no per-client logic; the file carries zero real data.

    tasks[].task_type (review_checkpoint, asks the client) -> 'client_followup'
        (+ task_type_legacy: <original>)
"""
import re

ID = "0015"
DESCRIPTION = "tasks: type ask-the-client review_checkpoint as client_followup (original kept in task_type_legacy)"

# Resolving action is a question to someone — «уточнить/спросить/запросить/узнать у …».
_ASK_RX = re.compile(r'(уточнить|спросить|запросить|узнать)\s+у\s', re.I)


def up(api):
    def fix(client_id, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return False, ""
        changed = 0
        for tk in tasks:
            if not isinstance(tk, dict):
                continue
            if (tk.get("task_type") or "").strip() != "review_checkpoint":
                continue
            blob = " ".join(str(tk.get(k) or "") for k in ("next_action", "context", "title", "what"))
            if not _ASK_RX.search(blob):
                continue
            tk.setdefault("task_type_legacy", tk.get("task_type"))
            tk["task_type"] = "client_followup"
            changed += 1
        if not changed:
            return False, ""
        return True, "re-typed %d ask-the-client checkpoint(s) to client_followup" % changed

    api.for_each_client("tasks.json", fix)


# ---------------------------------------------------------------------------
# AI-side surface (RUNTIME_PASS spec, added 2026-06-26). Optional; up() unchanged.
# A slice of the shared TASK CLASSIFIER (migrations/TASK_CLASSIFIER.md). up() keys
# on the strict «(уточнить|спросить|запросить|узнать) у» verb; preflight surfaces
# checkpoints resolved by the client but phrased without it (e.g. «ждём ответа от
# клиента», «нужно подтверждение от …») for the runtime to classify.
# ---------------------------------------------------------------------------

try:  # shared classifier prescreen lives in the engine (single source of truth)
    import _task_classifier as _tc   # guarded: a helper issue must never break discovery
except Exception:
    _tc = None


def preflight(api):
    """READ step -> shared task classifier (RE-TYPE (ask-the-client) dimension). One scan,
    one source of rules; see migrations/TASK_CLASSIFIER.md."""
    return _tc.retype_candidates(api) if _tc else []


RUNTIME_PASS = {
    "intent": (
        "For each flagged review_checkpoint, decide per task-types.md / INSTRUCTIONS "
        "§0.4 whether its resolving action is a question to / a wait on the client or "
        "their manager. If yes, re-type to client_followup (it batches into «Запрос у "
        "клиента») and preserve task_type_legacy. If the checkpoint is resolved by us "
        "(an internal control), LEAVE it as review_checkpoint. See "
        "migrations/TASK_CLASSIFIER.md."
    ),
    "scope": "tasks[].task_type",
    "escalate": "on_anomaly",
    "guardrails": [
        "only re-type a task preflight flagged",
        "preserve the original in task_type_legacy",
        "leave it as review_checkpoint if it is resolved internally, not by the client",
        "change only the type; keep every fact / id",
    ],
}

EXPECT = {
    "preflight_max": 20,
    "change_kinds": ["needs_task_classification"],
}

SCENARIO = [
    "A checkpoint resolved by the client but phrased without «уточнить у …» (e.g. "
    "«ждём ответа от клиента») now batches into «Запрос у клиента» with "
    "task_type_legacy kept; an internal control checkpoint was NOT re-typed.",
]
