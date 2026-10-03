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
The dependency stage generates a VTK overlay from the pinned vcpkg checkout,
disables its unused Qt Quick module and omits Qt Declarative. AppCSXCAD uses
Qt Widgets; SVG support is retained for Qt icons.

The package has an `openEMS` root folder, executables/DLLs at its root, merged
MATLAB scripts, CTB scripts, AppCSXCAD/Qt plugins and Python 3.13/3.14 wheels.
Python itself is not bundled. Package assembly checks transitive DLL imports
of executables, plugins and wheel extensions, copies runtime libraries and
licenses, and emits a matching source ZIP and SHA-256 checksums in `build/release`.

After packaging, verify the extracted ZIP with:

```powershell
.\scripts\verify_windows_msvc.ps1
```

This installs both wheel sets in fresh environments, runs CPU/Vulkan checks
and the CSXCAD Python tests, checks plotting, and confirms AppCSXCAD starts.
Run the native CTest suites before distributing as well.
