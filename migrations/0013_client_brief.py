"""Add `brief.json` per client — the operator-facing situation-summary slot.

The client cockpit's hero shows a one-line situation brief — "the story of the
client right now". That narrative is authored by the runtime (mm_update) and must
live in STATE: the engine never parses `mental_model.md` for rendered content
(JSON-first, 2026-06-19). This migration creates the slot:

    state/brief.json = {
        "summary":       str,   # operator-facing situation brief (RU)
        "generated_for": str,   # ISO date the brief was generated for
    }

and BACKFILLS it from the summary the runtime ALREADY wrote into the client's
`mental_model.md` ```analysis``` block, so the brief renders immediately after the
upgrade. `mm_update` rewrites `brief.json` whenever state changes (nightly +
on-change) — no separate refresh job.

Idempotent: a client that already has a non-empty `brief.summary` is skipped.
Schema-level — keyed on file/field names; it reads each operator's OWN
`mental_model.md` at run time, so the migration file itself carries ZERO real
data and is safe in the public repo. Additive + behaviour-preserving: where no
summary exists, nothing is written and the hero falls back to the counts line.
Mirrors the additive pattern of 0004 (`jurisdiction`) / 0011 (`client_facing`).
"""

ID = "0013"
DESCRIPTION = ("create brief.json {summary, generated_for}, backfilled from the "
               "mental_model.md analysis summary (operator situation brief); "
               "mm_update refreshes it. Additive, behaviour-preserving.")


def up(api):
    # load_analysis_text parses the ```analysis``` JSON block out of mental_model.md
    # text — it is NOT the engine render path (that never touches the .md); here it
    # is used once, as a backfill source, exactly like a content migration.
    from _brief import load_analysis_text

    for cid in api.clients():
        existing = api._ops.state_read(cid, "brief.json")
        if isinstance(existing, dict) and (existing.get("summary") or "").strip():
            continue  # already has a brief — idempotent no-op

        md = api._ops.mental_model_read(cid) or ""
        an = load_analysis_text(md) if md else {}
        summary = (an.get("summary") or "").strip()
        if not summary:
            continue  # nothing to seed; mm_update fills it on the next run

        data = {"summary": summary, "generated_for": (an.get("updated_at") or "")}
        api._commit(cid, "brief.json", data,
                    "seed brief.summary from mental_model.md analysis")


# ---------------------------------------------------------------------------
# AI-side surface (RUNTIME_PASS spec, added 2026-06-26). Optional; up() unchanged.
# up() can only COPY a summary that already exists in mental_model.md — Python
# cannot author prose. The residue (a client with no analysis summary) would stay
# brief-less until the next mm_update collector run, leaving the cockpit hero on
# the bare counts line after an upgrade. preflight surfaces those clients;
# RUNTIME_PASS GENERATES the brief from state at migration time — the same thing
# mm_update does, but now, so no hero waits for the nightly cycle. The brief is a
# terminal leaf (it feeds only the cockpit-hero render), so the runtime may write
# it under the terminal-leaf invariant. See migrations/RUNTIME_PASS_SPEC.md.
# ---------------------------------------------------------------------------

def preflight(api):
    """READ step. Read-only: clients whose brief.summary is empty/missing — the
    residue up() could not seed (no analysis summary to copy)."""
    flags = []
    for cid in api.clients():
        brief = api.read(cid, "brief.json")
        summary = ""
        if isinstance(brief, dict):
            summary = (brief.get("summary") or "").strip()
        if not summary:
            flags.append({
                "client": cid,
                "field": "brief.summary",
                "kind": "needs_brief_generation",
            })
            if len(flags) >= 100:
                return flags
    return flags


RUNTIME_PASS = {
    "intent": (
        "For each flagged client with no brief, GENERATE the operator-facing "
        "situation brief — 'the story of the client right now' — by reading the "
        "client's state (regime / jurisdiction, open risks, active tracks, the "
        "current period, recent operator_decisions), exactly as mm_update would. "
        "Write brief.json {summary, generated_for: <migration date>}. Plain Russian, "
        "operator-facing (INSTRUCTIONS §0.1), HONEST — only what the state supports, "
        "no invented facts. If a client genuinely has no state to summarize, leave "
        "it brief-less (the hero falls back to the counts line)."
    ),
    "scope": "brief.json -> {summary, generated_for}",
    "escalate": "on_anomaly",
    "guardrails": [
        "only generate for a client preflight flagged (no existing brief.summary)",
        "the summary must be supported by the client's state — never fabricate",
        "operator-facing Russian; no machine tags / ids (INSTRUCTIONS §0.1)",
        "set generated_for to the migration run date; do not overwrite a non-empty brief",
    ],
}

EXPECT = {
    # A whole practice missing briefs is normal on a fresh instance, so the volume
    # bound is generous; the real escalation is a guardrail breach (can't summarize
    # honestly) or a scenario fail.
    "preflight_max": 100,
    "change_kinds": ["needs_brief_generation"],
}

SCENARIO = [
    "A client whose cockpit hero showed the bare counts line (no brief) now shows a "
    "real one-line situation brief generated from its state; a client that already "
    "had a brief is unchanged; no brief states a fact the client's state does not "
    "support.",
]
