# Recovery runbook

What to do when client state looks wrong, corrupted, or was changed by mistake.
This is the operator's safety net — you do **not** need a developer to recover.

There are two independent backup layers, both local to the operator's machine.

## Layer 1 — per-write `.bak_` backups (automatic, fine-grained)

Every write through `engine/state_ops.py` first saves a timestamped copy of the
file next to it (`<file>.bak_<timestamp>`) before replacing it. So the previous
version of any single state file is always one step back.

**Restore one file:**

1. Find the backups for the file, e.g. for a client's tasks:
   `ls clients/<id>/state/tasks.json.bak_*`
2. Pick the most recent one from *before* the bad change (the timestamp is in the name).
3. Copy it over the live file:
   `cp clients/<id>/state/tasks.json.bak_20260622_0930 clients/<id>/state/tasks.json`
4. Re-validate and re-render:
   `python3 engine/state_lint.py && python3 engine/generate.py`

`.bak_` files are rotated by `engine/rotate_baks.py` so they don't pile up — keep
that in mind if you're recovering something old; that's what Layer 2 is for.

## Layer 2 — full snapshots (manual, whole-system)

`engine/snapshot.py` archives all text/code/state (`.md .py .json .jsonl .txt`,
excluding secrets and backups) into `Archive/snapshots/brain_<timestamp>_<label>.tar.gz`.
Take one before any risky operation (a migration, a bulk edit, a schema change).

**Create a snapshot (do this before migrations):**

```
python3 engine/snapshot.py before_migration
```

**List snapshots:**

```
python3 engine/snapshot.py --list
```

**Preview a restore (changes nothing):**

```
python3 engine/snapshot.py --restore brain_20260622_0930_before_migration.tar.gz --dry-run
```

**Restore:**

```
python3 engine/snapshot.py --restore brain_20260622_0930_before_migration.tar.gz
```

`<snap>` can be a bare filename (looked up in `Archive/snapshots/`) or a full path.
Restore **overwrites files in place** and is guarded against unsafe paths. It does
**not** delete files created after the snapshot — so if a bad change *added* files,
remove those by hand after restoring.

## If state is corrupted (NUL bytes / broken JSON / bad UTF-8)

1. Run the integrity check to see exactly which files are affected:
   `python3 engine/system_integrity_check.py`
2. Recover each flagged file from its most recent good `.bak_` (Layer 1), or restore
   the last good snapshot (Layer 2) if the damage is widespread.
3. Re-run `state_lint.py`, then `system_integrity_check.py`, and confirm both are clean
   before regenerating dashboards.

## Before a migration (recommended habit)

1. `python3 engine/snapshot.py before_migration`
2. Run the migration's instructions.
3. `python3 engine/state_lint.py` and `python3 engine/system_integrity_check.py` — both clean.
4. If anything is wrong, restore the `before_migration` snapshot and stop.
