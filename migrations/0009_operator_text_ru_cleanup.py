"""Clean stray English out of operator-facing task text (§0.1 / §0.1.a).

Some task `title`/`context`/`next_action` prose written under the old system
leaked English into what the operator (a Russian-speaking bookkeeper) reads:
"среди direct-клиентов", "Связан с risk R-…", completion markers "(done)".
§0.1.a now forbids this at the source, but the STORED text on the operator's
machine stays dirty until actualized — and a migration is the only channel that
reaches her real data (she pulls + runs it). A view fix can't touch state.

DELIBERATELY CONSERVATIVE — exact, grammar-correct, identifier-safe substrings
only. We do NOT do word-level swaps: that would corrupt identifiers and break
Russian case. In particular "risk" is rewritten ONLY in the phrase "risk R-"
(a reference to a risk entity, instrumental case «риском»), so risk IDs and
memory keys like `..._risk` / `client_risk` are never touched. Machine
annotations (`key=value`, `memory …`, bare `team_lead`) are intentionally left
alone here — they need prose rewriting (runtime, §0.1.a), not substitution.

Lossless / reversible: the original field is preserved in `<field>_legacy`
(mirroring 0007 `next_action_legacy`, 0008 `context_legacy`). Idempotent: the
replacements are no-ops once applied. Schema-level — operates on task fields,
no client names, no per-client logic.
"""

ID = "0009"
DESCRIPTION = ("tasks: clean stray English in operator-facing title/context/next_action "
               "(direct->прямой, 'risk R-'->'риском R-', '(done)'->'(готово)'; originals in *_legacy)")

# Ordered, exact substrings. More specific phrases first. Each is safe in any
# position: the 'risk R-' forms require a following " R-" so they never match a
# risk id or a `_risk` memory key; the '(done…' forms are parenthesis-bound.
_REPLACEMENTS = [
    ("среди direct-клиентов", "среди прямых клиентов"),
    ("direct-клиентов", "прямых клиентов"),
    ("direct-клиента", "прямого клиента"),
    ("direct-клиент", "прямой клиент"),
    ("Связан с risk R-", "Связан с риском R-"),
    ("связан с risk R-", "связан с риском R-"),
    ("Связанный risk R-", "Связанный риск R-"),
    ("связанный risk R-", "связанный риск R-"),
    ("Связана с risk R-", "Связана с риском R-"),
    ("связана с risk R-", "связана с риском R-"),
    ("См. risk R-", "См. риск R-"),
    ("см. risk R-", "см. риск R-"),
    ("(done)", "(готово)"),
    ("(DONE)", "(готово)"),
    ("(done ", "(готово "),
    ("(done,", "(готово,"),
    ("(DONE,", "(готово,"),
]

_FIELDS = ("title", "context", "next_action")


def _clean(text):
    """Return cleaned text, or None if nothing changed."""
    if not isinstance(text, str) or not text:
        return None
    out = text
    for old, new in _REPLACEMENTS:
        if old in out:
            out = out.replace(old, new)
    return out if out != text else None


def up(api):
    def fix(client_id, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return False, ""
        changed = 0
        for tk in tasks:
            if not isinstance(tk, dict):
                continue
            touched = False
            for fld in _FIELDS:
                new = _clean(tk.get(fld))
                if new is None:
                    continue
                tk.setdefault(fld + "_legacy", tk[fld])
                tk[fld] = new
                touched = True
            if touched:
                changed += 1
        if not changed:
            return False, ""
        return True, "cleaned operator-facing English in %d task(s)" % changed

    api.for_each_client("tasks.json", fix)
