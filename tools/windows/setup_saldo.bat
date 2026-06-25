@echo off
rem ============================================================================
rem  Saldo bootstrap - send THIS file to the operator via Telegram and have her
rem  double-click it. It does NOT touch the old (locked) copy under Documents:
rem  it clones a FRESH copy into C:\Saldo (outside OneDrive, so no file-lock
rem  failures), carries over her config, makes the Desktop icon, and runs the
rem  first update. After this she only ever uses the "Update Saldo" icon.
rem
rem  Delivery note: Telegram sends .bat as a file. On first run Windows may show
rem  "Windows protected your PC" -> click "More info" -> "Run anyway" (or right-
rem  click the file -> Properties -> Unblock before running).
rem ============================================================================
setlocal EnableDelayedExpansion
title Saldo setup

set "DEST=C:\Saldo"
set "REPO=%DEST%\Saldo-engine"
rem HTTPS (matches how this laptop already pulls; no SSH key needed - cached
rem GitHub credentials are reused). For SSH instead: git@github.com:vindm/Saldo.git
set "URL=https://github.com/vindm/Saldo.git"

where git >nul 2>nul || (echo [!] Git not found. Install Git for Windows, then run this again. & pause & exit /b 1)
where py  >nul 2>nul && (set "PY=py -3") || (set "PY=python")

echo === Setting up Saldo at %REPO% (outside OneDrive) ===
echo.

if exist "%REPO%\.git" (
  echo A copy already exists at %REPO% - it will just be updated.
) else (
  if not exist "%DEST%" mkdir "%DEST%"
  if exist "%REPO%" rd /s /q "%REPO%"
  echo Cloning a fresh copy - this can take a minute. You may be asked to sign in to GitHub once.
  git clone "%URL%" "%REPO%" || (echo [!] Clone failed - check internet / GitHub access. & pause & exit /b 1)
)

rem Carry over the existing config. Look in the likely old locations (plain
rem Documents AND OneDrive-redirected Documents). port_config.py rewrites any
rem RELATIVE data.dir to absolute so the data still resolves from the new location;
rem it won't overwrite a config that's already there.
set "OLDCFG="
for %%P in (
  "%USERPROFILE%\Documents\Saldo\Saldo-engine\config\instance.yaml"
  "%USERPROFILE%\OneDrive\Documents\Saldo\Saldo-engine\config\instance.yaml"
  "%OneDrive%\Documents\Saldo\Saldo-engine\config\instance.yaml"
) do if not defined OLDCFG if exist "%%~P" set "OLDCFG=%%~P"

if defined OLDCFG (
  echo Porting your config from "!OLDCFG!" ...
  %PY% "%REPO%\tools\port_config.py" "!OLDCFG!" "%REPO%\config\instance.yaml"
) else (
  echo [!] Could not find your previous config automatically.
)

if not exist "%REPO%\config\instance.yaml" (
  echo.
  echo [!] No config\instance.yaml yet - the update will STOP rather than build the
  echo     demo. Find your old instance.yaml and run, in this window:
  echo         %PY% "%REPO%\tools\port_config.py" "PATH\TO\OLD\config\instance.yaml" "%REPO%\config\instance.yaml"
  echo     (or copy it in and set data.dir + locale: ru). Ask Dima if unsure.
  echo.
)

echo Creating the Desktop icon ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\tools\windows\install_shortcut.ps1"

echo.
echo Running the first update (pull + migrations + dashboards) ...
echo.
%PY% "%REPO%\tools\update.py" --no-pause

echo.
echo ============================================================================
echo  Done. From now on just use the Desktop icon to update.
echo  The old folder under Documents can be deleted later (after pausing OneDrive).
echo ============================================================================
pause
