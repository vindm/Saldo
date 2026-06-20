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
