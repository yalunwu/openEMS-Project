param([string]$BuildRoot = '',[string]$Label = '',[string]$Python313 = '',[string]$Python314 = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not $BuildRoot) { $BuildRoot = Join-Path $projectRoot 'build/msvc-release' }
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
$suffix = if ($Label) { "-$Label" } else { '' }
if ($Label -and $Label -notmatch '^[A-Za-z0-9-]+$') { throw 'Invalid package label' }
$stage = Join-Path $BuildRoot "pkgstage$suffix/openEMS"
$buildInfo = Get-Content "$stage/BUILD-INFO.json" -Raw | ConvertFrom-Json
$archive = Join-Path $projectRoot "build/release/$($buildInfo.name).zip"
$verify = Join-Path $BuildRoot "extracted verification$suffix"
if (Test-Path $verify) { throw "Verification directory already exists: $verify" }
Expand-Archive -LiteralPath $archive -DestinationPath $verify
$pkg = Join-Path $verify 'openEMS'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
$env:CSXCAD_INSTALL_PATH = $pkg
$env:OPENEMS_INSTALL_PATH = $pkg
$env:PYTHONPATH = ''
$env:PYTHONHOME = ''
$env:PYTHONNOUSERSITE = '1'
$env:MPLBACKEND = 'Agg'
$env:TEMP = Join-Path $BuildRoot 'tmp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
$env:QT_PLUGIN_PATH = ''
$env:QT_QPA_PLATFORM_PLUGIN_PATH = ''
$env:PATH = "$pkg;$env:SystemRoot/System32;$env:SystemRoot"
foreach ($executable in @('openEMS.exe', 'nf2ff.exe', 'sar_calc.exe')) {
    & "$pkg/$executable"
    if ($LASTEXITCODE -notin @(0, 1, -1)) { throw "$executable startup failed: $LASTEXITCODE" }
}
$geometryTests = Join-Path $verify 'csxcad-tests'
New-Item -ItemType Directory -Force $geometryTests | Out-Null
Copy-Item "$projectRoot/CSXCAD/python/tests/test_*.py" $geometryTests
Copy-Item "$projectRoot/CSXCAD/python/tests/sphere.stl", "$projectRoot/CSXCAD/python/tests/sphere.ply" $geometryTests
foreach ($version in @('3.13', '3.14')) {
    $python = Join-Path $BuildRoot "tools/python-$version/tools/python.exe"
    if ($version -eq '3.13' -and $Python313) { $python = $Python313 }
    if ($version -eq '3.14' -and $Python314) { $python = $Python314 }
    $venv = Join-Path $BuildRoot "verify-python-$version$suffix"
    if (Test-Path -LiteralPath $venv) { throw "Verification environment already exists: $venv" }
    Invoke-Checked $python @('-m', 'venv', $venv)
    $python = Join-Path $venv 'Scripts/python.exe'
    $tag = 'cp' + $version.Replace('.', '')
    foreach ($component in @('h5py', 'csxcad', 'openems')) {
        $wheel = Get-ChildItem "$pkg/python" -Filter "$component-*-$tag-$tag-win_amd64.whl"
        Invoke-Checked $python @('-m', 'pip', 'install', $wheel.FullName)
    }
    Push-Location $verify
    try {
        Invoke-Checked $python @('-c', 'import h5py; print(h5py.version.info)')
        Invoke-Checked $python @("$pkg/python/smoke_test.py")
        Invoke-Checked $python @("$pkg/python/smoke_test.py", '--engine', 'gpu')
        Invoke-Checked $python @("$projectRoot/openEMS/.github/smoketests/python/MSL_NotchFilter.py")
        Write-Output "PASS: official Python smoke test $version"
        Invoke-Checked $python @('-m', 'unittest', 'discover', '-s', $geometryTests, '-p', 'test_*.py')
        Invoke-Checked $python @('-m', 'unittest', 'discover', '-s', "$projectRoot/openEMS/python/Tests", '-p', 'test_*.py')
        Invoke-Checked $python @("$projectRoot/openEMS/python/Tests/GPU_Setup.py", '--require-backend', 'HIP')
        Invoke-Checked $python @('-c', 'import h5py, matplotlib.pyplot as plt; from pathlib import Path; p=Path("plot-check.png"); plt.plot([0,1],[0,1]); plt.savefig(p); assert p.stat().st_size>0; p.unlink(); print("PASS: plotting and HDF5 imports")')
    } finally { Pop-Location }
}
$python = Join-Path $BuildRoot "verify-python-3.14$suffix/Scripts/python.exe"
Invoke-Checked $python @("$PSScriptRoot/msvc-release/verify_archives.py", '--directory', "$projectRoot/build/release", '--build-info', "$stage/BUILD-INFO.json")
$testRoot = Join-Path $verify 'tests'
New-Item -ItemType Directory -Force $testRoot | Out-Null
Copy-Item "$projectRoot/openEMS/python/Tests/GPU_Engine.py" "$testRoot/GPU_Engine.py"
Push-Location $testRoot
try {
    Invoke-Checked $python @("$testRoot/GPU_Engine.py", '--require-backend', 'HIP')
} finally { Pop-Location }
$env:PATH = "$pkg;$env:SystemRoot/System32;$env:SystemRoot"
$env:QT_QPA_PLATFORM = 'windows'
$app = Start-Process -FilePath "$pkg/AppCSXCAD.exe" -WorkingDirectory $pkg -WindowStyle Hidden -PassThru -RedirectStandardOutput "$BuildRoot/appcsxcad-stdout.log" -RedirectStandardError "$BuildRoot/appcsxcad-stderr.log"
if ($app.WaitForExit(8000)) { throw "AppCSXCAD exited during startup with code $($app.ExitCode)" }
$app.Kill()
$app.WaitForExit()
$appLog = Get-Content "$BuildRoot/appcsxcad-stderr.log" -Raw -ErrorAction SilentlyContinue
if ($appLog -match 'Could not find the Qt platform plugin|no Qt platform plugin could be initialized') { throw $appLog }
'PASS: extracted package, both CPython versions, strict HIP construction, CPU/HIP comparisons and AppCSXCAD startup'
