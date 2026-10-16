Build the standard Windows ZIP from an x64 Visual Studio Developer PowerShell:

```powershell
.\scripts\build_windows_msvc.ps1 -Stage All -Jobs 4
```

The default workspace is `build/msvc-release`. Place a bootstrapped vcpkg
checkout in its `vcpkg` directory and standard CPython NuGet runtimes in
`tools/python-3.13/tools` and `tools/python-3.14/tools`. Visual Studio C++
Build Tools, its CMake/Ninja tools and the Windows SDK must be installed.

Individual `Dependencies`, `Native`, `Wheels` and `Package` stages can be
resumed. Dependencies use a shared manifest and release-only triplet so
configuring another component does not remove libraries from the install tree.
The binary cache is retained between runs. Remove the old `pkgstage` directory
before repeating the packaging stage; the script refuses to overwrite it.
Wheel builds use isolated staging directories and a short temporary path so
failed builds can be retried within Windows path limits.
The dependency stage generates a VTK overlay from the pinned vcpkg checkout,
disables its unused Qt Quick module and omits Qt Declarative. AppCSXCAD uses
Qt Widgets; SVG support is retained for Qt icons.

The package has an `openEMS` root folder, executables/DLLs at its root, merged
MATLAB scripts, CTB scripts, AppCSXCAD/Qt plugins and Python 3.13/3.14 wheels.
Python itself is not bundled. Package assembly checks transitive DLL imports
of executables, plugins and wheel extensions, copies runtime libraries and
licenses, and emits a matching source ZIP and SHA-256 checksums in `build/release`.
Archive names include the solver and meta-repository revisions. Existing
release archives are never overwritten.

After packaging, verify the extracted ZIP with:

```powershell
.\scripts\verify_windows_msvc.ps1
```

This installs both wheel sets in fresh environments, requires HIP construction
and stepping, runs CPU/HIP and CSXCAD Python checks, tests plotting, and confirms
AppCSXCAD starts. Both Python versions run the unit and construction suites;
both also run the official Python notch-filter smoke test. Python 3.14 runs
all GPU engine regressions.
Run the native CTest suites before distributing as well.

The Windows HIP build uses CUDA; configure its headers/compiler and target
architecture in openEMS/localConfig.cmake. The current local release targets
NVIDIA SM 86. CPU construction remains the default; use
`--engine=gpu --gpu-setup=gpu` or Python `engine='gpu', gpu_setup='gpu'` to require HIP setup.
Packages from modified source are labeled previews and include untracked,
non-ignored source files in the companion source ZIP.
