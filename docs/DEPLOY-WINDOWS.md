# One-click update on the operator's Windows laptop

Goal: the operator (Irina) never opens a terminal. She double-clicks one desktop
icon and it pulls the latest engine, applies any pending data migrations,
regenerates the dashboards, and opens today's plan.

All the work is in `tools/update.py` (cross-platform). The Windows pieces are a
thin launcher (`tools/windows/update_saldo.bat`) and a one-time shortcut
installer (`tools/windows/install_shortcut.bat`). The `git pull` runs *inside*
`update.py`, not in the `.bat`, so the launcher never rewrites itself mid-run and
the freshly-pulled `migrate.py` / `generate.py` run as clean subprocesses.

## One-time setup (Dima, on her laptop)

1. The repo is already cloned and working (she pulls today via Git Bash), and
   `config/instance.yaml` points `data.dir` at her real data folder with
   `instance.locale: ru`. Nothing to change there.
2. Make sure **Python** and **Git** are callable from `cmd` (not only Git Bash):
   - In a `cmd` window: `py -3 --version` (or `python --version`) and `git --version`.
   - If Python is missing from PATH, reinstall Python with "Add python.exe to
     PATH" checked. Git installed with the default "from the command line too"
     option is already on PATH.
3. Double-click `tools\windows\install_shortcut.bat` once. It creates an
   **"Обновить Saldo"** icon on the Desktop. (Optional: right-click the icon →
   "Pin to taskbar".)

That's it. From now on she only uses the icon.

## Daily use (the operator)

Double-click **Обновить Saldo**. A window shows progress in Russian
("Скачиваю свежую версию → Применяю миграции → Пересобираю дашборды → Готово"),
the plan opens automatically, and the window stays open so she can read the
result (and screenshot it for Dima if anything looks off).

## What it does, in order

1. `git pull --ff-only` (best-effort: if offline, it keeps the current version
   and says so, then still rebuilds the dashboards).
2. ensures `pyyaml` is installed (no-op if it already is).
3. `engine/migrate.py up --apply` — applies pending state migrations. Every write
   is backed up + atomic + UTF-8-validated and recorded in
   `<data.dir>/journal/schema_migrations.json`; re-running is a no-op.
4. `engine/generate.py` — rebuilds the dashboards (prints `LINT OK`).
5. opens `<data.dir>/dashboards/plan_today.html`.

## Notes / gotchas

- **GitHub access**: the remote is SSH (`git@github.com:vindm/Saldo`). Since she
  already pulls in Git Bash, the key is set up; `cmd` uses the same key. If the
  key has a passphrase and no agent is running, the window may ask for it once.
- **Nothing is destructive**: migrations only reshape state with backups; the
  generator only writes derived `*.html`. `config/instance.yaml` and her data are
  never touched by `git pull` (both are git-ignored / outside the repo).
- **Advanced/testing flags** for `tools/update.py`: `--no-pull`, `--no-open`,
  `--no-pause`.
- **macOS/Linux**: the same `python3 tools/update.py` works; only the desktop
  shortcut is Windows-specific.
