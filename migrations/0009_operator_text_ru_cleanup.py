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


# ---------------------------------------------------------------------------
# AI-side surface (RUNTIME_PASS spec, added 2026-06-26). All optional - up()
# above is unchanged. preflight is READ-ONLY and deterministic (no model); it
# surfaces the residual English the conservative substitution list deliberately
# LEFT for a runtime prose rewrite (see the module docstring). RUNTIME_PASS and
# SCENARIO are DATA the migration-runtime skill consumes - see
# migrations/RUNTIME_PASS_SPEC.md and connectors/migration_runtime/SKILL.md.
# ---------------------------------------------------------------------------
import re


def _residual_english(text):
    """Runs of >=2 CONSECUTIVE English words in operator-facing text - the
    signature of leftover prose, as opposed to a lone proper noun, product name,
    file extension or domain (PDF, Finkoper, tbank.ru), which legitimately stay
    Latin in clean Russian. HIGH-PRECISION sampler: favours false negatives. The
    RUNTIME_PASS does the actual judgment (it can tell a person's name from a
    stray phrase, so even a flagged 'Anna Nazarova' is safe to surface)."""
    base = _clean(text) or text
    if not isinstance(base, str) or not base:
        return []
    out, run = [], []

    def flush():
        # a run is leftover PROSE only if it is >=2 words AND not all proper-cased
        # (a lowercase function word like "by"/"not"/"draft" is the tell)
        if len(run) >= 2 and any(w.islower() for w in run):
            out.append(" ".join(run))
        run.clear()

    for tok in base.split():
        core = tok.strip(".,;:!?()[]{}«»\"'`—–-")
        if (re.fullmatch(r"[A-Za-z]{2,}", core)
                and not any(c in tok for c in "_/@.0123456789`")):
            run.append(core)
        else:
            flush()
    flush()
    seen, ded = set(), []
    for r in out:
        if r not in seen:
            seen.add(r); ded.append(r)
    return ded

def preflight(api):
    """READ step for `migrate.py next`. Read-only scan of operator-facing task
    fields for residual English the deterministic up() does not cover. Returns
    advisory flags for the RUNTIME_PASS judgment rewrite."""
    flags = []
    for cid in api.clients():
        data = api.read(cid, "tasks.json")
        if not isinstance(data, dict):
            continue
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            continue
        for tk in tasks:
            if not isinstance(tk, dict):
                continue
            for fld in _FIELDS:
                left = _residual_english(tk.get(fld))
                if left:
                    flags.append({
                        "client": cid,
                        "task": tk.get("id"),
                        "field": fld,
                        "leftover": left,
                        "text": (_clean(tk.get(fld)) or tk.get(fld))[:160],
                        "kind": "needs_prose_rewrite",
                    })
                    if len(flags) >= 50:  # bounded - this is a sampler, not a report
                        return flags
    return flags


RUNTIME_PASS = {
    "intent": (
        "Rewrite the residual English preflight flagged in operator-facing task "
        "title/context/next_action into clean Russian. CONSERVATIVE: leave "
        "identifiers, risk ids (R-...), memory keys and machine annotations "
        "(snake_case, key=value) untouched - those are a separate structured "
        "concern, not prose. Preserve each original in <field>_legacy (mirroring "
        "up()). Terminal leaf: nothing downstream reads these fields as input."
    ),
    "scope": "tasks[].title, tasks[].context, tasks[].next_action",
    # Autonomy by default: apply without asking when the result is inside EXPECT.
    # Escalate to the operator only on an anomaly / a guardrail breach / a scenario
    # fail. ("always" would force a pause every time - not used here.)
    "escalate": "on_anomaly",
    # Per-write guardrails the runtime enforces while rewriting; a proposed write
    # that breaks one is NOT made - it is surfaced as an anomaly instead.
    "guardrails": [
        "only modify a field that preflight flagged",
        "preserve the original in <field>_legacy",
        "never touch identifiers, risk ids (R-...), amounts, or machine annotations",
        "keep active-jurisdiction terms (id: 'kode billing', 'NTPN') - not English",
    ],
}

# The 'normal application' envelope. The engine compares preflight against this
# and the runtime applies autonomously while the result stays inside it; outside
# (e.g. a flood of flags, or a flag kind we did not expect) is the 'something
# really unexpected' case that escalates to the operator instead of auto-applying.
EXPECT = {
    "preflight_max": 40,                  # real data shows a handful; 40 is generous
    "change_kinds": ["needs_prose_rewrite"],
}

SCENARIO = [
    "Open the Plan / a track modal for a client preflight flagged. Confirm the "
    "operator-facing task text now reads as clean Russian with no stray English "
    "words, that risk ids / identifiers / machine annotations are intact, that "
    "each rewritten field kept its <field>_legacy original, and that task "
    "routing (wave / type) is unchanged.",
]
