# Reproducible environment setup for the DogFightEnv RL workspace.
# Re-runnable: skips steps that are already done.
#
# Usage:  powershell -ExecutionPolicy Bypass -File setup_env.ps1 [-Cpu]
#   -Cpu : install CPU-only PyTorch instead of the CUDA 12.6 build.

param([switch]$Cpu)

$ErrorActionPreference = "Stop"
$conda = "$env:LOCALAPPDATA\miniconda3\Scripts\conda.exe"
$envPy = "$env:LOCALAPPDATA\miniconda3\envs\aip\python.exe"

# 1) Miniconda (user scope)
if (-not (Test-Path $conda)) {
    Write-Host "[1/4] Installing Miniconda3 (user scope) via winget..."
    winget install -e --id Anaconda.Miniconda3 --scope user --accept-package-agreements --accept-source-agreements --silent
    & $conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
    & $conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
    & $conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2
} else {
    Write-Host "[1/4] Miniconda already installed."
}

# 2) Python 3.11 env named 'aip' (matches the competition manual)
if (-not (Test-Path $envPy)) {
    Write-Host "[2/4] Creating conda env 'aip' (python 3.11)..."
    & $conda create -n aip python=3.11 -y
} else {
    Write-Host "[2/4] Conda env 'aip' already exists."
}

# 3) PyTorch (CUDA build by default; requirements.txt only pins >=2.3,<3.0)
Write-Host "[3/4] Installing PyTorch..."
if ($Cpu) {
    & $envPy -m pip install "torch>=2.3,<3.0"
} else {
    & $envPy -m pip install "torch>=2.3,<3.0" --index-url https://download.pytorch.org/whl/cu126
}

# 4) Remaining dependencies
Write-Host "[4/5] Installing requirements.txt..."
& $envPy -m pip install -r "$PSScriptRoot\requirements.txt"

# 5) Debug CRT runtime for the provided simulation DLLs.
# JSBSimAIPLib.dll / AIP_BASE*.dll are DEBUG builds: they import msvcp140d.dll,
# vcruntime140d.dll, vcruntime140_1d.dll, ucrtbased.dll. These only ship with
# Visual Studio (Build Tools + C++ workload), not with the normal VC++ redist.
if (-not (Test-Path "$PSScriptRoot\ucrtbased.dll")) {
    Write-Host "[5/5] Deploying debug CRT DLLs next to the simulation DLLs..."
    $debugCrtDir = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Redist\MSVC\*\debug_nonredist\x64\Microsoft.VC143.DebugCRT" -ErrorAction SilentlyContinue | Select-Object -First 1
    $ucrtbased = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\ucrt\ucrtbased.dll" -ErrorAction SilentlyContinue | Select-Object -Last 1
    if (-not $debugCrtDir -or -not $ucrtbased) {
        Write-Host "  Debug CRT not found - installing VS 2022 Build Tools (C++ workload, ~10 min)..."
        winget install -e --id Microsoft.VisualStudio.2022.BuildTools --accept-package-agreements --accept-source-agreements --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
        $debugCrtDir = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Redist\MSVC\*\debug_nonredist\x64\Microsoft.VC143.DebugCRT" | Select-Object -First 1
        $ucrtbased = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\ucrt\ucrtbased.dll" | Select-Object -Last 1
    }
    Copy-Item "$($debugCrtDir.FullName)\msvcp140d.dll", "$($debugCrtDir.FullName)\vcruntime140d.dll", "$($debugCrtDir.FullName)\vcruntime140_1d.dll" $PSScriptRoot
    Copy-Item $ucrtbased.FullName $PSScriptRoot
} else {
    Write-Host "[5/5] Debug CRT DLLs already present."
}

Write-Host ""
Write-Host "Done. Smoke check:"
& $envPy -c "import torch, ray, gymnasium, yaml; print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); print('ray', ray.__version__)"
Push-Location $PSScriptRoot
& $envPy -c "import JSBSimWrapper; print('JSBSimWrapper OK')"
Pop-Location
