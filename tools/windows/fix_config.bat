@echo off
rem ============================================================================
rem  Saldo - fix the config so dashboards build from HER data (not the demo).
rem  Use when the plan shows example clients (Aurora/Cobalt/...) instead of the
rem  real ones. It finds the old config\instance.yaml, copies it into the new
rem  C:\Saldo clone REWRITING any relative data.dir to an absolute path, then
rem  rebuilds. You can also drag the old instance.yaml onto this .bat.
rem ============================================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Saldo - fix config

set "REPO=C:\Saldo\Saldo-engine"
if not exist "%REPO%\engine\generate.py" set "REPO=%~dp0..\.."
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

rem 0) Get the latest engine first (C:\Saldo pulls cleanly - no OneDrive lock),
rem    so port_config.py / update.py are present even on an older clone.
echo Getting the latest engine ...
git -C "%REPO%" pull --ff-only < nul
echo.

rem 1) Old config: from a dragged-in path (%1) or the likely old locations.
set "OLDCFG=%~1"
if not defined OLDCFG (
  for %%P in (
    "%USERPROFILE%\Documents\Saldo\Saldo-engine\config\instance.yaml"
    "%USERPROFILE%\OneDrive\Documents\Saldo\Saldo-engine\config\instance.yaml"
    "%OneDrive%\Documents\Saldo\Saldo-engine\config\instance.yaml"
  ) do if not defined OLDCFG if exist "%%~P" set "OLDCFG=%%~P"
)

if not defined OLDCFG (
  echo [!] Could not find your old instance.yaml automatically.
  echo     Drag your old config\instance.yaml onto this .bat, or run:
  echo         "%~f0" "C:\path\to\old\config\instance.yaml"
  echo.
  pause
  exit /b 1
)

echo Using old config: !OLDCFG!
echo Porting into %REPO%\config\instance.yaml (relative data paths -^> absolute) ...
%PY% "%REPO%\tools\port_config.py" "!OLDCFG!" "%REPO%\config\instance.yaml" --force || (echo [!] Port failed. & pause & exit /b 1)

echo.
echo Rebuilding dashboards from YOUR data (no pull) ...
echo.
%PY% "%REPO%\tools\update.py" --no-pull --no-pause

echo.
echo ============================================================================
echo  Check the lines above point to YOUR data folder, NOT ...\instances\example.
echo  If they do, you are all set - use the Desktop icon from now on.
echo ============================================================================
pause
