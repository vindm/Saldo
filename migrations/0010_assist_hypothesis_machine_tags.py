"""Strip machine annotations out of operator-facing `assist.hypothesis` (§0.1.a).

`assist.hypothesis` is now the one-line lens shown under EVERY track's title on
the Plan and inside the track modal (see `_plan_today.py`, `_track_modal.py`,
`connectors/mm_update/SKILL.md` §"assist"). §0.1.a forbids machine annotations in
operator-facing fields, but hypotheses written under the old system leaked daemon
tags and raw entity ids into what the operator reads:
  "…не давить (silence_check)."                      -> daemon tag, no operator meaning
  "…активного Кипр-трека (basalt_tax_i5) после…"    -> a raw track-id reference
  "…доступов от Полины (см. access_request);…"    -> a machine cross-reference
A view fix can't touch stored state — a migration is the only channel that reaches
the operator's real data (she pulls + runs it), so we actualize the stored text.

DELIBERATELY CONSERVATIVE — we remove a parenthetical ONLY when its content is a
machine token by SHAPE (a latin snake_case identifier) or a known engine daemon
name, optionally behind a "см./see" cross-ref prefix. We match by shape, never by
a literal client id — this file ships in the public repo and contains ZERO real
data. Inline source labels that carry operator meaning are PROTECTED and left for
a runtime prose rewrite (e.g. "Расхождение 8 (mental_model) vs 7 (state)" — here
the tokens distinguish two numbers, so blind removal would degrade the sentence).

Lossless / reversible: the original is preserved in `assist.hypothesis_legacy`
(mirroring 0007 `next_action_legacy`, 0008 `context_legacy`, 0009 `*_legacy`).
Idempotent: once cleaned there is no machine parenthetical left to match.
Schema-level — operates on the `assist.hypothesis` field, no client names.
"""
import re

ID = "0010"
DESCRIPTION = ("tasks: strip machine tags from operator-facing assist.hypothesis "
               "(daemon tags / raw track-ids / 'см. <id>' refs; original in assist.hypothesis_legacy)")

# Engine daemon / skill names — public engine vocabulary, safe to name here.
_DAEMON_VOCAB = {"silence_check", "mm_update", "signal_processor", "question_resolver"}

# Inline labels that carry operator meaning — never auto-stripped (need a prose
# rewrite by the runtime, not a mechanical removal).
_PROTECT = {"mental_model", "state"}

# A bare machine identifier: latin, lower-snake_case, at least one underscore
# (so a track-id like `basalt_tax_i5` or an entity ref like `access_request`
# matches by SHAPE, while a plain Cyrillic operator aside never does).
_ID_SHAPE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")

# Optional cross-reference prefix inside the parens: "см." / "см" / "see" / "cf.".
_REF_PREFIX = re.compile(r"^(?:см\.?|see|cf\.?)\s*", re.IGNORECASE)

# A single parenthetical group (no nested parens), with any leading whitespace so
# removal also takes the space that preceded the tag.
_PAREN = re.compile(r"\s*\(([^()]*)\)")


def _is_machine(inner):
    core = _REF_PREFIX.sub("", inner.strip()).strip()
    if core in _PROTECT:
        return False
    if core in _DAEMON_VOCAB:
        return True
    return bool(_ID_SHAPE.match(core))


def _clean(text):
    """Return cleaned hypothesis, or None if nothing changed."""
    if not isinstance(text, str) or not text:
        return None

    def repl(m):
        return "" if _is_machine(m.group(1)) else m.group(0)

    out = _PAREN.sub(repl, text)
    # Tidy up only when we actually removed something: collapse double spaces and
    # pull punctuation back against the preceding word.
    if out != text:
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r"[ \t]+([;,.])", r"\1", out)
        out = out.strip()
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
            assist = tk.get("assist")
            if not isinstance(assist, dict):
                continue
            new = _clean(assist.get("hypothesis"))
            if new is None:
                continue
            assist.setdefault("hypothesis_legacy", assist["hypothesis"])
            assist["hypothesis"] = new
            changed += 1
        if not changed:
            return False, ""
        return True, "cleaned machine tags in %d assist.hypothesis field(s)" % changed

    api.for_each_client("tasks.json", fix)


# ---------------------------------------------------------------------------
# AI-side surface (RUNTIME_PASS spec, added 2026-06-26). Optional; up() above is
# unchanged. The deterministic strip above PROTECTS parentheticals that carry
# operator meaning (mental_model / state and other source labels) and leaves them
# "for a runtime prose rewrite". preflight surfaces exactly those; RUNTIME_PASS
# rewrites them into clean operator Russian. See migrations/RUNTIME_PASS_SPEC.md.
# ---------------------------------------------------------------------------

def _residual_machine_label(text):
    """Parentheticals that SURVIVED the deterministic strip but still read as a
    machine token to the operator (a source label like (mental_model)/(state), or
    any latin-bearing aside). ADVISORY: the runtime rewrites the sentence; this
    just surfaces candidates. Pure-Cyrillic asides ((см. договор)) are not flagged."""
    base = _clean(text) or text
    if not isinstance(base, str) or not base:
        return []
    out = []
    for m in _PAREN.finditer(base):
        inner = m.group(1)
        if re.search(r"[A-Za-z][A-Za-z_]{2,}", inner):
            out.append(inner.strip())
    seen, ded = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); ded.append(x)
    return ded


def preflight(api):
    """READ step for `migrate.py next`. Read-only scan of assist.hypothesis for the
    meaningful machine-labelled parentheticals the deterministic strip left behind."""
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
            assist = tk.get("assist")
            if not isinstance(assist, dict):
                continue
            left = _residual_machine_label(assist.get("hypothesis"))
            if left:
                flags.append({
                    "client": cid,
                    "task": tk.get("id"),
                    "field": "assist.hypothesis",
                    "leftover": left,
                    "text": (_clean(assist.get("hypothesis")) or assist.get("hypothesis"))[:160],
                    "kind": "needs_prose_rewrite",
                })
                if len(flags) >= 50:
                    return flags
    return flags


RUNTIME_PASS = {
    "intent": (
        "Rewrite the assist.hypothesis lines preflight flagged so the meaning the "
        "machine label carried is expressed in clean operator Russian, with no "
        "(mental_model)/(state)/source-token parenthetical left. E.g. "
        "'Расхождение 8 (mental_model) vs 7 (state)' -> "
        "'Расхождение: по модели 8, в состоянии 7'. CONSERVATIVE: keep the numbers/"
        "facts, leave genuine non-machine asides, never touch identifiers or risk "
        "ids. Preserve the original in assist.hypothesis_legacy (mirroring up())."
    ),
    "scope": "tasks[].assist.hypothesis",
    "escalate": "on_anomaly",
    "guardrails": [
        "only modify a hypothesis preflight flagged",
        "preserve the original in assist.hypothesis_legacy",
        "keep every number / fact / id; rewrite only the machine-label phrasing",
        "leave genuine Cyrillic asides untouched",
    ],
}

EXPECT = {
    "preflight_max": 30,
    "change_kinds": ["needs_prose_rewrite"],
}

SCENARIO = [
    "Open the Plan / a track modal for a flagged client. Confirm the hypothesis "
    "lens reads as clean operator Russian, that no (mental_model)/(state)/machine "
    "parenthetical remains, that the distinction it carried is preserved in prose, "
    "and that assist.hypothesis_legacy kept the original.",
]
