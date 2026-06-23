$ErrorActionPreference = "Stop"
$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$target  = Join-Path $here "update_saldo.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk     = Join-Path $desktop "Обновить Saldo.lnk"
$ws = New-Object -ComObject WScript.Shell
$s  = $ws.CreateShortcut($lnk)
$s.TargetPath       = $target
$s.WorkingDirectory = $here
$s.IconLocation     = "shell32.dll,238"
$s.Description       = "Обновить Saldo: свежая версия, миграции, дашборды"
$s.Save()
Write-Host ("Ярлык создан на рабочем столе: " + $lnk)
