"""Put genuine enumerated lists in task `context` on their own lines.

Some task `context` prose carries a multi-item list inline, e.g.
"...посчитать три вещи. 1) ... 2) ... 3) ...". Rendered, that collapses into one
run-on wall of text. The renderer now honours newlines (pre-wrap + newline-safe
stripIds in `_track_modal.py`), but the STORED text has no `\n`, so the data
itself must be actualized at the source — not just patched in the view.

This is content normalization, not a schema change, but it still ships as a
migration because that is the only channel that reaches an operator's real data
on her own machine (she pulls + runs it); a view fix alone never touches state.

DELIBERATELY CONSERVATIVE. Free prose is full of `N)` look-alikes that must NOT
be broken: parenthetical task ids `(i1)`, inline parenthetical lists
`(1)...(2)...`, and form numbers like `(форма 26.5-1)`. So we split ONLY when a
context contains a genuine *sequence* of BARE enumerators — `1)` AND `2)` (and
optionally `3) ...`), consecutive and starting at 1. A lone `1)` (e.g. a form
number) never qualifies. The `(N)` parenthetical form is left untouched.

Lossless / reversible: the original string is preserved in `context_legacy`
(mirroring 0005 `status_legacy` / 0007 `next_action_legacy`).

Idempotent: a context that already contains `\n` is skipped, so re-running
changes nothing. Schema-level — operates on `tasks[].context`, no client names,
no per-client logic.

    tasks[].context  "...три вещи. 1) a 2) b 3) c"
      -> "...три вещи.\n1) a\n2) b\n3) c"   (+ context_legacy: <original>)
"""

import re

ID = "0008"
DESCRIPTION = "tasks: break genuine inline enumerator lists in context onto newlines (original kept in context_legacy)"

# A BARE enumerator: digit 1-9 + ')' + whitespace, NOT preceded by a word char,
# '.', '-' or '(' . That negative lookbehind rejects '(1)', '26.5-1)', and any
# 'N)' glued to a letter/digit. Optional leading whitespace is consumed so it can
# be replaced by the newline.
_ENUM = re.compile(r"\s*(?<![\w.\-(])([1-9])\)\s")


def _normalize(text):
    """Return newline-split text, or None if `text` has no genuine list."""
    if not isinstance(text, str) or not text.strip():
        return None
    if "\n" in text:                     # already formatted -> idempotent skip
        return None
    nums = [int(m.group(1)) for m in _ENUM.finditer(text)]
    # genuine list = a sequence starting at 1 with >= 2 consecutive items
    if len(nums) < 2 or nums != list(range(1, len(nums) + 1)):
        return None
    out = _ENUM.sub(lambda m: "\n" + m.group(1) + ") ", text)
    out = out.strip()
    # sanity: must have actually introduced line breaks and not lost content
    if "\n" not in out:
        return None
    return out


def up(api):
    def fix(client_id, data):
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return False, ""
        changed = 0
        for tk in tasks:
            if not isinstance(tk, dict):
                continue
            new = _normalize(tk.get("context"))
            if new is None or new == tk.get("context"):
                continue
            tk.setdefault("context_legacy", tk["context"])
            tk["context"] = new
            changed += 1
        if not changed:
            return False, ""
        return True, "split inline enumerator list in context of %d task(s)" % changed

    api.for_each_client("tasks.json", fix)
