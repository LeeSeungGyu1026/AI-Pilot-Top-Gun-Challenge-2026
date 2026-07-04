$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "C:\Users\GYU\AppData\Local\miniconda3\envs\aip\python.exe"
$Experiment = Join-Path $Root "experiments\codex_ic_s3_v12_level_rear_gunnery_v1.yaml"
$RunDir = Join-Path $Root "artifacts\watch\codex_v12_level_rear_gunnery_v1"
$LogPath = Join-Path $RunDir "codex_train.log"
$ErrPath = Join-Path $RunDir "codex_train.err.log"
$ExitPath = Join-Path $RunDir "codex_train.exit"
$PidPath = Join-Path $RunDir "codex_run.pid"
$StartedPath = Join-Path $RunDir "codex_started.txt"

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
Get-Date -Format o | Set-Content -Encoding UTF8 -Path $StartedPath
Remove-Item -Force -ErrorAction SilentlyContinue $ExitPath

$WrapperPath = Join-Path $RunDir "codex_wrapper.ps1"
@"
`$ErrorActionPreference = 'Continue'
`$env:PYTHONUTF8 = '1'
`$env:PYTHONIOENCODING = 'utf-8'
`$pyDir = Split-Path -Parent '$Python'
if (Test-Path `$pyDir) { `$env:Path = "`$pyDir;`$pyDir\Scripts;`$env:Path" }
Set-Location -LiteralPath '$Root'
`$cmd = @'
python scripts\run_experiment.py experiments\codex_ic_s3_v12_level_rear_gunnery_v1.yaml
'@
Invoke-Expression `$cmd *> '$LogPath'
`$code = `$LASTEXITCODE
if (`$null -eq `$code) { `$code = 0 }
Set-Content -LiteralPath '$ExitPath' -Value `$code -Encoding ascii
"@ | Set-Content -Encoding UTF8 -Path $WrapperPath

$Process = Start-Process -FilePath "powershell.exe" `
  -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $WrapperPath) `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -PassThru

$Process.Id | Set-Content -Encoding UTF8 -Path $PidPath
Write-Host "codex_v12_pid=$($Process.Id)"
Write-Host "codex_v12_rundir=$RunDir"
