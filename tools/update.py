#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""update.py - one-command updater for an operator's machine.

Does the whole "пулл -> миграции -> дашборды -> открыть" sequence so the operator
never touches a terminal: pull the latest engine from GitHub, apply any pending
state migrations to their data dir, regenerate the dashboards, and open today's
plan. Cross-platform; on Windows it is launched by tools/windows/update_saldo.bat
(itself behind a desktop shortcut), so the operator just double-clicks an icon.

Design note: the git pull happens HERE (in Python), not in the .bat. The .bat is
then a thin, stable launcher that never rewrites itself mid-run, and migrate.py /
generate.py are executed as fresh subprocesses that read the just-pulled code.

Flags (for testing / advanced use):
    --no-pull   skip git pull        --no-open   don't open the browser
    --no-pause  don't wait for Enter at the end
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(REPO, "engine")

# Print UTF-8 even if the Windows console code page is legacy.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Locale-aware messages (operator-facing surface follows instance.locale).
try:
    sys.path.insert(0, ENGINE)
    from _config import LOCALE as _LOCALE
except Exception:
    _LOCALE = "en"


def say(en, ru):
    print(ru if _LOCALE == "ru" else en, flush=True)


def run(argv, label_en, label_ru):
    say("- " + label_en + " ...", "- " + label_ru + " ...")
    try:
        r = subprocess.run(argv, cwd=REPO)
        return r.returncode == 0
    except Exception as e:
        print("  " + str(e), flush=True)
        return False


def main():
    args = set(sys.argv[1:])
    py = sys.executable or "python"
    say("=== Updating Saldo ===", "=== Обновление Saldo ===")

    # 1. Pull the latest engine (best-effort: offline -> keep working with what we have).
    if "--no-pull" not in args:
        if not run(["git", "-C", REPO, "pull", "--ff-only"],
                   "Downloading the latest version", "Скачиваю свежую версию"):
            say("  (could not update from GitHub - continuing with the current version)",
                "  (не получилось обновиться с GitHub - продолжаю на текущей версии)")

    # 2. Make sure the one dependency is present (no-op if already installed).
    subprocess.run([py, "-m", "pip", "install", "--quiet", "pyyaml"],
                   cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3. Apply pending data migrations (backup + atomic + ledger handled by migrate.py).
    ok_mig = run([py, os.path.join(ENGINE, "migrate.py"), "up", "--apply"],
                 "Applying data migrations", "Применяю миграции данных")

    # 4. Regenerate the dashboards from state.
    ok_gen = run([py, os.path.join(ENGINE, "generate.py")],
                 "Rebuilding the dashboards", "Пересобираю дашборды")

    # 5. Open today's plan.
    opened = False
    if "--no-open" not in args and ok_gen:
        try:
            from _config import DASHBOARD_DIR
            page = os.path.join(DASHBOARD_DIR, "plan_today.html")
            if os.path.exists(page):
                if sys.platform.startswith("win"):
                    os.startfile(page)  # noqa
                elif sys.platform == "darwin":
                    subprocess.run(["open", page])
                else:
                    subprocess.run(["xdg-open", page])
                opened = True
        except Exception:
            pass

    print(flush=True)
    if ok_gen:
        say("Done - dashboards are up to date." + ("" if opened else " Open plan_today.html to view."),
            "Готово - дашборды обновлены." + ("" if opened else " Откройте plan_today.html."))
    else:
        say("Something went wrong above. Send this window to Dima.",
            "Что-то пошло не так выше. Покажите это окно Диме.")

    if "--no-pause" not in args:
        try:
            input(("\nPress Enter to close..." if _LOCALE != "ru"
                   else "\nНажмите Enter, чтобы закрыть..."))
        except EOFError:
            pass
    return 0 if (ok_gen and ok_mig) else 1


if __name__ == "__main__":
    raise SystemExit(main())
