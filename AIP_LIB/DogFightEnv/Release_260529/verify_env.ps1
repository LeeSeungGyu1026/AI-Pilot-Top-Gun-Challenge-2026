# Verify the Release_260529 workspace without changing files, packages, or conda envs.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File verify_env.ps1
#   powershell -ExecutionPolicy Bypass -File verify_env.ps1 -BtDll AIP_BASE_target.dll

param(
    [string]$BtDll = "AIP_BASE_target.dll",
    [string]$RuleXml = "..\..\Rule_default.xml"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Resolve-CondaExe {
    $candidates = @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:LOCALAPPDATA\anaconda3\Scripts\conda.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    $fromPath = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    throw "conda.exe not found. Run setup_env.ps1 first."
}

function Resolve-CondaEnvPython([string]$CondaExe, [string]$EnvName) {
    $envList = & $CondaExe env list
    foreach ($line in $envList) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "\s+"
        if ($parts.Count -ge 2 -and $parts[0] -eq $EnvName) {
            $pathIndex = 1
            if ($parts[$pathIndex] -eq "*") {
                $pathIndex++
            }
            if ($parts.Count -le $pathIndex) {
                continue
            }

            $envPath = $parts[$pathIndex]
            $python = Join-Path $envPath "python.exe"
            if (Test-Path $python) {
                return (Resolve-Path $python).Path
            }
        }
    }
    throw "conda env '$EnvName' not found. Run setup_env.ps1 first."
}

$conda = Resolve-CondaExe
$py = Resolve-CondaEnvPython $conda "aip"
$resolvedRule = (Resolve-Path (Join-Path $Root $RuleXml)).Path
$resolvedDll = (Resolve-Path (Join-Path $Root $BtDll)).Path

Write-Host "[release] $Root"
Write-Host "[conda]   $conda"
Write-Host "[python]  $py"
Write-Host "[bt dll]  $resolvedDll"
Write-Host "[rule]    $resolvedRule"

$requiredFiles = @(
    "JSBSimAIPLib.dll",
    $BtDll,
    "Rule_forTraining.xml",
    "aircraft",
    "engine",
    "src\dogfight\ai\native_bt.py",
    "src\dogfight\ai\bt_rule_manager.py"
)

foreach ($item in $requiredFiles) {
    $path = Join-Path $Root $item
    if (-not (Test-Path $path)) {
        throw "Missing required Release_260529 asset: $path"
    }
}

& $py -c "import torch, ray, gymnasium, yaml, pymap3d; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('ray', ray.__version__); print('gymnasium', gymnasium.__version__); print('pymap3d OK')"

Push-Location $Root
try {
    & $py -c "import JSBSimWrapper; print('JSBSimWrapper OK')"

    & $py -m py_compile `
        run_unreal_inference.py `
        run_local_dogfight.py `
        train_rllib.py `
        train_curriculum.py `
        scripts\run_experiment.py `
        scripts\run_eval.py `
        student\my_submission.py

    $btProbe = @"
from pathlib import Path
import importlib.util

root = Path.cwd()
rule = Path(r"$resolvedRule")
bt_dll = r"$BtDll"

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

bt_rule_manager = load_module("bt_rule_manager", root / "src/dogfight/ai/bt_rule_manager.py")
native_bt = load_module("native_bt", root / "src/dogfight/ai/native_bt.py")

with bt_rule_manager.activate_rule_xml(rule, root):
    bt = native_bt.AIPilot(bt_dll)
    bt.CreateBehaviorTree(260529, 1)
    bt.Reset()
print("BT init OK:", bt_dll)
"@
    $btProbe | & $py -

    & $py scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run
}
finally {
    Pop-Location
}

Write-Host "[ok] Release_260529 environment verification completed."
