@echo off
rem One-time setup (run once by Dima): puts an "Обновить Saldo" icon on the
rem Desktop that points at update_saldo.bat. After this, the operator only ever
rem double-clicks that icon.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_shortcut.ps1"
echo.
pause
