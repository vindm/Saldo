# Migrations

When an engine change reshapes **state** (renames a field, moves a fact to a
single source, drops a duplicated key), the data on every practice's machine
must be reshaped to match. Each such engine change ships a **migration** here so
every user can apply it deterministically to their own data.

Migrations are written against the **schema** (field names), never against
specific clients. A migration says "wherever key X exists, do Y"; the runner
applies it to whatever clients the local `clients_index.json` lists. It behaves
identically for 3 clients or 50, whatever they are named. **No client names,
paths, or per-client business logic belong in a migration** (engine invariant).

## For a practice operator (running migrations on your data)

> On a Windows laptop, the operator does **not** run these by hand — a single
> desktop icon does pull + migrate + regenerate + open. See
> [`docs/DEPLOY-WINDOWS.md`](../docs/DEPLOY-WINDOWS.md). The commands below are the
> equivalent manual flow (what the icon automates).

This is the text flow to hand to Cowork after pulling the latest engine:

```bash
# 1. See what is pending against YOUR data (read-only, writes nothing):
python3 engine/migrate.py status

# 2. Preview exactly what would change (dry-run, still writes nothing):
python3 engine/migrate.py up

# 3. Apply. Every write is backed up + atomic + UTF-8 validated by state_ops,
#    and recorded in <data.dir>/journal/schema_migrations.json:
python3 engine/migrate.py up --apply

# 4. Verify:
python3 engine/state_lint.py
```

Migrations are **idempotent**: re-running an already-applied migration changes
nothing. The ledger (`journal/schema_migrations.json`) lives with your data, so
the runner always knows what you have already applied.

`--data-dir PATH` targets a specific data directory (handy for testing a
migration against a copy before touching live data).

## For an engine developer (writing a migration)

Create `migrations/NNNN_slug.py` (zero-padded, next number) exposing:

```python
ID = "0003"
DESCRIPTION = "one line, schema-level, no client names"

def up(api):
    # high-level helper for a straight rename:
    api.rename_key("identity.json", "old_key", "new_key", on_conflict="append")

    # or the escape hatch for anything non-trivial:
    def fix(client_id, data):
        if "foo" not in data:
            return False, ""
        data["bar"] = transform(data.pop("foo"))
        return True, "foo -> bar (reshaped)"
    api.for_each_client("regime.json", fix)
```

The `api` object (see `engine/migrate.py`) is the only way migrations touch
state, so backup / atomic-write / UTF-8 / history-logging / dry-run are enforced
centrally. `on_conflict="append"` is free-text safe (joins with ` | `);
`on_conflict="skip"` (default) leaves a client untouched and warns when both the
old and new keys already hold values, so nothing is silently clobbered.

Ship the migration **in the same change** as the engine code that needs it; per
the project rule, an engine change that touches data is incomplete without its
migration.

## Current migrations

- `0001_reg_date_note.py` — identity: `reg_date_uncertainty` → `reg_date_note`.
- `0002_bank_statement_note.py` — behavior: `bank_statement_frequency_note` →
  `bank_statement_notes` (free-text note only; the distinct `*_frequency` and
  `*_trigger` value fields are left alone).
- `0003_track_event_ts.py` — tasks: optional `ts` (timestamp) on track history
  events; additive, no back-fill.
- `0004_regime_jurisdiction.py` — regime: add `jurisdiction` (default `ru`) where
  absent; additive, behaviour-preserving (Phase 2 multi-jurisdiction).
- `0005_normalize_task_status.py` — tasks: collapse free-form track `status` to the
  canonical vocabulary (`engine/_status.py`); the original is preserved in
  `status_legacy`. Pairs with the display-time normalizer + the `state_lint`
  `status_noncanon` check.
- `0006_quick_access_map.py` — quick_access: normalize `cred_status` (`na` →
  derived) + backfill the RU service map; idempotent.
- `0007_terminal_task_next_action.py` — tasks: clear stale `next_action` on
  terminal tasks (done/archived/cancelled); original kept in `next_action_legacy`.
  Pairs with the render-side guard in `_track_attrs.py` + the `stale_next_action`
  lint check.
- `0008_context_enumerator_newlines.py` — tasks: break a genuine inline
  enumerator list (`1) … 2) … 3) …`) in `context` onto separate lines; original
  kept in `context_legacy`. Conservative — only fires on a real sequence starting
  at 1 with ≥2 bare items, so `(i1)`, `(1)…(2)…` and form numbers are left alone.
  Pairs with the render-side `white-space:pre-wrap` + newline-safe `stripIds` in
  `_track_modal.py` and the §0.3 authoring rule in `policies/INSTRUCTIONS.md`.
- `0009_operator_text_ru_cleanup.py` — tasks: clean stray English in
  operator-facing `title`/`context`/`next_action` (`direct`→`прямой`, `risk R-`→
  `риском R-`, `(done)`→`(готово)`); originals in `*_legacy`. Conservative — exact,
  grammar-correct, identifier-safe substrings only, so risk-ids/memory-keys are
  left alone. Pairs with the §0.1.a rule in `policies/INSTRUCTIONS.md`.
- `0010_assist_hypothesis_machine_tags.py` — tasks: strip machine annotations
  (daemon tags, raw snake_case track-ids, `см./see <id>` cross-refs) from
  operator-facing `assist.hypothesis`; original kept in `assist.hypothesis_legacy`.
  Matched by SHAPE, never a literal client id (zero real data). Conservative —
  meaningful inline source labels (e.g. `(mental_model)` vs `(state)`) are
  protected. Pairs with the extended §0.1.a rule + the render change making
  `assist.hypothesis` the per-row lens (`_plan_today.py` / `_track_modal.py`).
- `0011_regime_client_facing.py` — regime: add optional `client_facing`
  `{summary, turnover_scope}` where absent. Additive, behaviour-preserving (null =
  the report derives a clean line). Opens the only client-facing prose slot so the
  client one-pager stops borrowing the internal `business_description`. Pairs with
  the rework of `engine/_owner_report.py` and the §0.1.b authoring rule in
  `policies/INSTRUCTIONS.md`.
- `0012_chat_quick_access_no_cred_status.py` — accounts.quick_access: remove the
  stale `cred_status` from `by_chat` messenger entries (tg/whatsapp/max — access is
  session-level, not a per-chat credential, so the chip was spurious). Idempotent;
  behaviour-preserving with the render change (`_client_dashboard_v2.py →
  render_client_quick_access` already suppresses the chip for messenger entries).
- `0013_client_brief.py` — create `state/brief.json` `{summary, generated_for}`,
  backfilled from the `mental_model.md` ```analysis``` summary (the operator
  situation brief shown in the client-cockpit hero); `mm_update` refreshes it
  nightly + on-change. Additive, behaviour-preserving (no summary → the hero falls
  back to the counts line). Mirrors the additive pattern of 0004 / 0011.

## Known follow-ups needing a content decision (not yet migrations)

These came out of the 2026-06-21 audit but are **not** mechanical synonyms, so
they need a human decision before a migration can be written:

- **Duplicated fact**: the 1C base number lives both in
  `regime.contour.fresh_base_id` (structured, canonical) and inline in the
  `accounting_system_note` prose. De-duping means editing free-text — decide the
  desired note wording first.
- **patents**: `patents` (array), `patents_2026` (object),
  `patents_not_applicable_note` / `patents_unresolved_note` (notes) are *different
  things*, not synonyms — needs a canonical model, not a rename.
- **KKT/OFD**: `kkt_mode`, `kkt_status`, `kkt_status_note`, `ofd_note` are
  distinct fields — same caveat.
