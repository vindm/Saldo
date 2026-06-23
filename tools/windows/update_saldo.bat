@echo off
rem Saldo one-click updater (Windows). Behind a desktop shortcut, the operator
rem just double-clicks. All real work happens in tools/update.py (git pull +
rem migrations + regenerate + open). This file stays tiny so it never changes
rem under its own feet during the pull.
chcp 65001 >nul
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% "%~dp0..\update.py" --no-pause
echo.
pause
