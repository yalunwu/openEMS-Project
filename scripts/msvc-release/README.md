Build the standard Windows ZIP from an x64 Visual Studio Developer PowerShell:

```powershell
.\scripts\build_windows_msvc.ps1 -Stage All -CudaArchitectures all -Jobs 4
```

The default workspace is `build/msvc-release`. Place a bootstrapped vcpkg
checkout in its `vcpkg` directory and standard CPython NuGet runtimes in
`tools/python-3.13/tools` and `tools/python-3.14/tools`. Visual Studio C++
Build Tools, its CMake/Ninja tools and the Windows SDK must be installed.

Individual `Dependencies`, `Native`, `Wheels` and `Package` stages can be
resumed. Dependencies use a shared manifest and release-only triplet so
configuring another component does not remove libraries from the install tree.
The binary cache is retained between runs. Packaging refuses to overwrite its
staging directory or archives. Use `package_windows_msvc.py --label <name>` for
a separate candidate; verification accepts the same `-Label`.
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
The wheel stage builds h5py against the same HDF5 headers/libraries and bundles
that runtime in both h5py wheels. Install these before CSXCAD/openEMS; a different
HDF5 wheel can conflict with the solver in the same Python process.
Archive names include the solver/meta-repository revisions, source digest and CUDA target
selection. BUILD-INFO.json and README.txt record the kernels actually embedded
in the solver DLL, including the PTX targets. Existing
release archives are never overwritten.

After packaging, verify the extracted ZIP with:

```powershell
.\scripts\verify_windows_msvc.ps1
```

This installs both wheel sets in fresh environments, requires HIP construction
and stepping, runs CPU/HIP and CSXCAD Python checks, tests plotting, and confirms
AppCSXCAD starts. Both Python versions run the unit and construction suites;
both also run the official Python notch-filter smoke test. Python 3.14 runs
all GPU engine regressions. Verification also checks both ZIP checksums, the
solver DLL hash and every recorded source-file hash. AppCSXCAD uses the Windows
Qt platform for its hidden OpenGL startup test; this does not validate visual rendering.
Run the native CTest suites before distributing as well.

The Windows HIP build uses CUDA; configure its headers/compiler in
openEMS/localConfig.cmake. The release helper defaults to `-CudaArchitectures all`:
native kernels for every architecture supported by the compiler, plus PTX for
forward compatibility. Use CUDA 12.x to retain Maxwell, Pascal (including the
Quadro P5000, SM 61) and Volta; CUDA 13 no longer compiles for these GPUs.
Packaging rejects an `all` build without Pascal kernels or PTX. A narrower
build can use, for example, `-CudaArchitectures '61;86'`. Local configuration
must not force a different architecture over the helper's selection.
Only hardware listed in the package's validation record has been runtime-tested.
CPU construction remains the default; use
`--engine=gpu --gpu-setup=gpu` or Python `engine='gpu', gpu_setup='gpu'` to require HIP setup.
Packages from modified source are labeled previews and include untracked,
non-ignored source files in the companion source ZIP.

`package_windows_msvc.py` accepts `--vcpkg-root`, `--h5py-wheels` and
`--validation-info` for an isolated build environment. Supply a JSON validation
record listing tested hardware/toolchains, checks and unavailable combinations.
The verifier accepts `-Python313` and `-Python314` when the base runtimes are
elsewhere. An unvalidated package is labeled as such.
