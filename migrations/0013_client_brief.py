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
