param(
    [string]$BuildRoot = '',
    [ValidateSet('Dependencies', 'Native', 'Wheels', 'Package', 'All')]
    [string]$Stage = 'All',
    [int]$Jobs = 4
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not $BuildRoot) { $BuildRoot = Join-Path $projectRoot 'build/msvc-release' }
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
$vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
$vsRoot = & $vswhere -all -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsRoot) { throw 'Visual Studio C++ Build Tools are required.' }
& "$vsRoot/Common7/Tools/Launch-VsDevShell.ps1" -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
$cmake = "$vsRoot/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
$ninja = "$vsRoot/Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe"
$vcpkgRoot = Join-Path $BuildRoot 'vcpkg'
$prefix = Join-Path $BuildRoot 'install'
$deps = Join-Path $BuildRoot 'dependencies'
$triplet = 'x64-windows-release'
$env:VCPKG_MAX_CONCURRENCY = "$Jobs"
$env:VCPKG_DISABLE_METRICS = '1'
$env:VCPKG_ROOT = $vcpkgRoot
$env:VCPKG_VISUAL_STUDIO_PATH = $vsRoot
$env:VCPKG_BINARY_SOURCES = "clear;files,$BuildRoot/binary-cache,readwrite"
New-Item -ItemType Directory -Force "$BuildRoot/binary-cache", $prefix | Out-Null
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
if ($Stage -in @('Dependencies', 'All')) {
    # AppCSXCAD uses Qt Widgets. VTK's Qt Quick/QML module is not needed.
    $overlay = Join-Path $BuildRoot 'overlay-ports'
    New-Item -ItemType Directory -Force "$overlay/vtk" | Out-Null
    Copy-Item "$vcpkgRoot/ports/vtk/*" "$overlay/vtk" -Recurse -Force
    $vtkManifest = Get-Content "$overlay/vtk/vcpkg.json" -Raw | ConvertFrom-Json
    $vtkManifest.features.qt.dependencies = @($vtkManifest.features.qt.dependencies | Where-Object { $_ -ne 'qtdeclarative' })
    $vtkManifest | ConvertTo-Json -Depth 30 | Set-Content "$overlay/vtk/vcpkg.json"
    $vtkPort = Get-Content "$overlay/vtk/portfile.cmake" -Raw
    $vtkPort = $vtkPort.Replace('vcpkg_cmake_configure(', "list(APPEND VTK_FEATURE_OPTIONS -DVTK_MODULE_ENABLE_VTK_GUISupportQtQuick=NO)`nvcpkg_cmake_configure(")
    Set-Content "$overlay/vtk/portfile.cmake" -Value $vtkPort -NoNewline
    Invoke-Checked "$vcpkgRoot/vcpkg.exe" @('install', "--x-manifest-root=$PSScriptRoot/msvc-release", "--x-install-root=$deps", "--overlay-triplets=$PSScriptRoot/msvc-release/triplets", "--overlay-ports=$overlay", "--triplet=$triplet", "--host-triplet=$triplet")
}
if ($Stage -in @('Native', 'All')) {
    foreach ($component in @('fparser', 'CSXCAD', 'openEMS', 'QCSXCAD', 'AppCSXCAD')) {
        $componentBuild = Join-Path $BuildRoot "native/$component"
        $options = @('-S', "$projectRoot/$component", '-B', $componentBuild,
            '-UCSXCAD_INCLUDE_DIR', '-UQCSXCAD_INCLUDE_DIR',
            '-G', 'Ninja', "-DCMAKE_MAKE_PROGRAM=$ninja", '-DCMAKE_BUILD_TYPE=Release',
            "-DCMAKE_INSTALL_PREFIX=$prefix", '-DCMAKE_WINDOWS_EXPORT_ALL_SYMBOLS=ON',
            "-DCMAKE_PREFIX_PATH=$prefix",
            "-DFPARSER_ROOT_DIR=$prefix", "-DCSXCAD_ROOT_DIR=$prefix", "-DQCSXCAD_ROOT_DIR=$prefix",
            "-DCMAKE_TOOLCHAIN_FILE=$vcpkgRoot/scripts/buildsystems/vcpkg.cmake",
            '-DVCPKG_MANIFEST_MODE=OFF', "-DVCPKG_INSTALLED_DIR=$deps",
            "-DVCPKG_OVERLAY_TRIPLETS=$PSScriptRoot/msvc-release/triplets",
            "-DVCPKG_TARGET_TRIPLET=$triplet", "-DVCPKG_HOST_TRIPLET=$triplet")
        if ($component -eq 'openEMS') { $options += '-DENABLE_VULKAN=ON' }
        if ($component -eq 'CSXCAD') { $options += '-DCSXCAD_BUILD_TESTS=ON' }
        Invoke-Checked $cmake $options
        Invoke-Checked $cmake @('--build', $componentBuild, '--parallel', "$Jobs")
        Invoke-Checked $cmake @('--install', $componentBuild)
    }
}
if ($Stage -in @('Wheels', 'All')) {
    $env:CSXCAD_INSTALL_PATH = $prefix
    $env:OPENEMS_INSTALL_PATH = $prefix
    foreach ($version in @('3.13', '3.14')) {
        $python = Join-Path $BuildRoot "tools/python-$version/tools/python.exe"
        $venv = Join-Path $BuildRoot "wheel-venv-$version"
        Invoke-Checked $python @('-m', 'venv', $venv)
        $python = Join-Path $venv 'Scripts/python.exe'
        Invoke-Checked $python @('-m', 'pip', 'install', 'cython', 'setuptools', 'setuptools-scm', 'wheel', 'numpy', 'h5py', 'matplotlib')
        foreach ($component in @('CSXCAD', 'openEMS')) {
            Invoke-Checked $python @('-m', 'pip', 'wheel', "$projectRoot/$component/python", '--no-deps', '--no-build-isolation', '-w', "$BuildRoot/wheels")
            if ($component -eq 'CSXCAD') {
                $tag = 'cp' + $version.Replace('.', '')
                $wheel = Get-ChildItem "$BuildRoot/wheels" -Filter "csxcad-*-$tag-$tag-win_amd64.whl" | Sort-Object LastWriteTime | Select-Object -Last 1
                Invoke-Checked $python @('-m', 'pip', 'install', '--force-reinstall', '--no-deps', $wheel.FullName)
            }
        }
    }
}
if ($Stage -in @('Package', 'All')) {
    $python = Join-Path $BuildRoot 'tools/python-3.14/tools/python.exe'
    Invoke-Checked $python @("$PSScriptRoot/package_windows_msvc.py", '--build-root', $BuildRoot, '--vs-root', $vsRoot)
}
