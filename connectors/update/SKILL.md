# Update procedure — fetch a new engine version, migrate data, rebuild the dashboard

**Who runs this:** the runtime (Cowork / Claude) in a session with the operator
(Mom), when she clicks **"Обновить Saldo"** in the dashboard (the button copies
the trigger prompt below) or writes *«обнови систему Saldo»*. Not a developer
flow — Dima updates the engine with normal git.

> **Trigger prompt** the dashboard button copies (kept in sync with
> `engine/_updater.py → UPDATE_PROMPT_RU`):
>
> *«Обнови систему Saldo по workflow connectors/update/SKILL.md. Сначала проверь
> новую версию движка и сделай резервную копию, затем покажи мне, что именно
> изменится (новые версии, миграции данных), и ТОЛЬКО после моего «да» применяй
> обновление, миграцию и пересборку дашборда. После — проверь, что всё работает,
> и отчитайся.»*

## Context

The "is there a new version" check is **inline in the engine** — `generate.py`
does a `git fetch` + rev-list at render time (`engine/_updater.py`) and shows the
gold "Доступно обновление" item only when origin is ahead. So this file is only
the **apply** side: the guarded, pause-for-OK upgrade.

The actual pull → migrate → regenerate sequence already lives in
**`tools/update.py`** (the one-command updater, also behind the Windows
double-click shortcut). It runs fully automatic and does NOT pause. This flow
**reuses it** but adds a preview + approval gate before applying.

Paths:

```bash
REPO="…/saldo"                                            # the engine checkout
DATA_DIR="$(cd "$REPO/engine" && python3 -c 'from _config import DATA_DIR; print(DATA_DIR)')"
```

## Steps (pause-for-OK)

Steps 1–3 are backup-only / read-only and may run without asking. **Do NOT run
step 5 until the operator has said «да»** to the step-4 preview.

1. **Snapshot first** (restoreable rollback point):

   ```bash
   cd "$REPO" && python3 engine/snapshot.py pre-update
   ```

2. **Confirm the engine change** is a clean fast-forward and note what the new
   version brings (the headline already shown on the update page).

3. **Dry-run the migrations** (default is dry-run — writes nothing):

   ```bash
   python3 engine/migrate.py status --data-dir "$DATA_DIR"
   python3 engine/migrate.py up     --data-dir "$DATA_DIR"
   ```

4. **PAUSE — show the operator, in their configured locale, exactly what will change** and wait:
   the new version, the pending migrations and what each does to her data, and
   that a backup exists. Ask plainly, e.g. *«Готов применить. Изменится: … .
   Применяю? (да / нет)»*. **If she does not say «да», stop — nothing changed.**

5. **Apply — delegate to the one-command updater** (only after «да»). It pulls,
   runs `migrate up --apply`, and regenerates as fresh subprocesses on the
   just-pulled code:

   ```bash
   cd "$REPO" && python3 tools/update.py --no-open --no-pause
   ```

6. **Verify** (green exit is necessary but not sufficient — CLAUDE.md Invariant 0):

   ```bash
   python3 engine/state_lint.py              # expect LINT OK
   python3 engine/system_integrity_check.py  # expect ALL CLEAN
   ```

   Then **scenario-verify**: pick a representative client and confirm the runtime
   still reasons correctly after the migration (resolves the right jurisdiction
   pack, right rules, no stale artefacts). For a non-RU client, role-play one of
   `tests/runtime_scenarios/`.

7. **Report back in the operator's locale**, short and plain: the version she is on now, what
   changed for her, that a backup was made, and that the dashboard is rebuilt.
   Tell her to **refresh the dashboard tab** — that is the "relaunch" equivalent,
   nothing to restart. (The Claude desktop app's own "Relaunch to update" button,
   if lit, is Anthropic's app updater — separate from Saldo.)

## Rollback

```bash
cd "$REPO" && python3 engine/snapshot.py --list
python3 engine/snapshot.py --restore <pre-update-snapshot>   # try --dry-run first
```

Migrations are idempotent and every state write is backed up by `state_ops`, so
re-running is safe; the snapshot is the belt-and-braces restore point.
