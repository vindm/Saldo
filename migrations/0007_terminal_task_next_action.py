"""Clear the stored `next_action` on terminal (done/archived/cancelled) tasks.

A closed task has no "next action", yet a stale value often lingered in state
(e.g. a task closed because the data arrived, while `next_action` still read
"request the NPWP"). The dashboard now suppresses it at render time
(`_track_attrs.py`), but the STORED field stays inconsistent. This migration
actualizes state at the source so the data itself is correct, not just the view.

For every client task whose status normalizes to a terminal token
(`done` / `archived` / `cancelled`), a non-empty `next_action` (and
`next_action_full`) is blanked, the original preserved in `next_action_legacy`
(lossless / reversible, mirroring 0005's `status_legacy`).

Idempotent: a terminal task that already has an empty next_action is untouched,
so re-running changes nothing. Schema-level — no client names, no per-client
logic; the terminal test uses the engine's canonical status normalizer.

    tasks[].next_action (terminal task) -> ''   (+ next_action_legacy: <original>)
"""

ID = "0007"
DESCRIPTION = "tasks: clear stale next_action on terminal tasks (original kept in next_action_legacy)"

_TERMINAL = ("done", "archived", "cancelled")


def up(api):
    from _status import normalize_status

    def fix(client_id, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return False, ""
        changed = 0
        for tk in tasks:
            if not isinstance(tk, dict):
                continue
            if normalize_status(tk.get("status") or "") not in _TERMINAL:
                continue
            na = tk.get("next_action") or tk.get("next_action_full") or ""
            if not na:
                continue
            tk.setdefault("next_action_legacy", na)
            if tk.get("next_action"):
                tk["next_action"] = ""
            if tk.get("next_action_full"):
                tk["next_action_full"] = ""
            changed += 1
        if not changed:
            return False, ""
        return True, "cleared next_action on %d terminal task(s)" % changed

    api.for_each_client("tasks.json", fix)
