"""Normalize free-form track statuses in tasks.json to the canonical vocabulary.

Track statuses had drifted into free text that encoded specifics into the token
itself (``blocked_by_anastasia``, ``scheduled_calc_by_fact``,
``client_notified_08.06_pays_self``) — not scalable and not localizable. The
engine now defines a small canonical status set (``engine/_status.py``) and the
dashboard normalizes for display; this migration aligns the STORED value so state
is canonical at the source. The pre-migration value is preserved per task in
``status_legacy`` (lossless and reversible), and ``state_lint`` flags any status
that is still non-canonical.

    tasks[].status: <free-form> -> <canonical>   (+ status_legacy: <original>)

Idempotent: a task whose status is already canonical is left untouched, so
re-running changes nothing. Schema-level — no client names, no per-client logic.
"""

ID = "0005"
DESCRIPTION = "tasks: normalize track status to canonical vocabulary (original kept in status_legacy)"


def up(api):
    # Imported inside up(): the runner puts engine/ on sys.path before running.
    from _status import CANON_LABEL, normalize_status

    def fix(client_id, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return False, ""
        changed = 0
        seen = []
        for t in tasks:
            st = t.get("status")
            if st and st not in CANON_LABEL:
                canon = normalize_status(st)
                t.setdefault("status_legacy", st)
                t["status"] = canon
                changed += 1
                pair = "%s->%s" % (st, canon)
                if pair not in seen:
                    seen.append(pair)
        if not changed:
            return False, ""
        return True, "normalized %d task status(es): %s" % (changed, ", ".join(seen))

    api.for_each_client("tasks.json", fix)
