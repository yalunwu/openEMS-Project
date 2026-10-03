"""Package the MSVC install tree using the traditional openEMS ZIP layout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-root', type=Path, default=ROOT / 'build/msvc-release')
parser.add_argument('--vs-root', type=Path, required=True)
args = parser.parse_args()
build = args.build_root.resolve()
prefix = build / 'install'
deps = build / 'dependencies/x64-windows-release'
description = subprocess.check_output(
    ['git', '-C', str(ROOT / 'openEMS'), 'describe', '--tags', '--always', '--dirty'], text=True).strip()
stem = f'openEMS_x64_{description}_vulkan_msvc'
stage = build / 'pkgstage'
package = stage / 'openEMS'
if package.exists():
    raise SystemExit(f'Staging directory already exists: {package}')
package.mkdir(parents=True)
ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.pdb')

def copy_tree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)

for name in ('openEMS.exe', 'nf2ff.exe', 'sar_calc.exe', 'AppCSXCAD.exe'):
    if not (prefix / 'bin' / name).is_file():
        raise RuntimeError(f'Missing release executable: {name}')
copy_tree(prefix / 'bin', package)
copy_tree(prefix / 'include', package / 'include')
copy_tree(prefix / 'lib', package / 'lib')
for name in ('CSXCAD', 'openEMS'):
    copy_tree(prefix / 'share' / name / 'matlab', package / 'matlab')
copy_tree(ROOT / 'openEMS/matlab/Tutorials', package / 'matlab/Tutorials')
copy_tree(prefix / 'share/openEMS/resources', package / 'resources')
(package / 'CTB').mkdir()
for src in (ROOT / 'CTB').iterdir():
    if src.suffix in ('.m', '.txt'):
        shutil.copy2(src, package / 'CTB' / src.name)
(package / 'python').mkdir()
wheel_imports = build / 'wheel-imports'
for tag in ('cp313', 'cp314'):
    for name in ('csxcad', 'openems'):
        wheels = list((build / 'wheels').glob(f'{name}-*-{tag}-{tag}-win_amd64.whl'))
        if len(wheels) != 1:
            raise RuntimeError(f'Expected one {name} {tag} wheel, got {wheels}')
        shutil.copy2(wheels[0], package / 'python' / wheels[0].name)
        with zipfile.ZipFile(wheels[0]) as archive:
            for member in archive.namelist():
                if member.endswith('.pyd'):
                    archive.extract(member, wheel_imports / tag)
copy_tree(ROOT / 'openEMS/python/Tutorials', package / 'python/Tutorials')
copy_tree(ROOT / 'openEMS/python/Examples', package / 'python/Examples')
shutil.copy2(ROOT / 'scripts/msvc-release/smoke_test.py', package / 'python/smoke_test.py')
for name in ('CSXCAD', 'openEMS'):
    (package / 'python' / name).mkdir()
    for src in (ROOT / name / 'python' / name).glob('*.pxd'):
        shutil.copy2(src, package / 'python' / name / src.name)

plugin_roots = [deps / 'Qt6/plugins', deps / 'plugins', deps / 'tools/Qt6/plugins']
plugin_root = next((p for p in plugin_roots if (p / 'platforms/qwindows.dll').exists()), None)
if plugin_root is None:
    raise RuntimeError('The Qt Windows platform plugin is missing')
for category in ('platforms', 'styles', 'iconengines', 'imageformats'):
    if (plugin_root / category).exists():
        copy_tree(plugin_root / category, package / 'plugins' / category)
(package / 'qt.conf').write_text('[Paths]\nPlugins=plugins\n')

dumpbin = next((args.vs_root / 'VC/Tools/MSVC').glob('*/bin/Hostx64/x64/dumpbin.exe'))
runtime_dirs = list((args.vs_root / 'VC/Redist/MSVC').glob('*/x64/Microsoft.VC*.CRT'))
runtime_dirs += list((args.vs_root / 'VC/Redist/MSVC').glob('*/x64/Microsoft.VC*.OpenMP'))
search_dirs = [deps / 'bin', prefix / 'bin'] + runtime_dirs
system = Path(os.environ['SystemRoot']) / 'System32'
queue = list(package.rglob('*.exe')) + list(package.rglob('*.dll')) + list(wheel_imports.rglob('*.pyd'))
processed = set()
dependency_names = set()
while queue:
    binary = queue.pop()
    if binary in processed:
        continue
    processed.add(binary)
    output = subprocess.check_output([str(dumpbin), '/dependents', str(binary)], text=True)
    for name in re.findall(r'^\s{4}(\S+\.dll)\s*$', output, re.MULTILINE | re.IGNORECASE):
        dependency_names.add(name.lower())
        if name.lower().startswith(('python313', 'python314', 'api-ms-', 'ext-ms-')):
            continue
        target = package / name
        if target.exists():
            queue.append(target)
            continue
        source = next((p / name for p in search_dirs if (p / name).is_file()), None)
        if source:
            shutil.copy2(source, target)
            queue.append(target)
        elif not (system / name).is_file():
            raise RuntimeError(f'Unresolved DLL {name} imported by {binary}')

licenses = package / 'licenses'
licenses.mkdir()
for component in ('openEMS', 'CSXCAD', 'QCSXCAD', 'AppCSXCAD', 'fparser', 'CTB'):
    destination = licenses / component
    destination.mkdir()
    for src in (ROOT / component).iterdir():
        if src.is_file() and (src.name.upper().startswith(('COPYING', 'LICENSE')) or 'license' in src.name.lower()):
            shutil.copy2(src, destination / src.name)
for name in ('lgpl.txt', 'gpl.txt'):
    shutil.copy2(ROOT / 'fparser/docs' / name, licenses / 'fparser' / name)
for src in (deps / 'share').glob('*/copyright'):
    destination = licenses / 'third-party' / src.parent.name
    destination.mkdir(parents=True)
    shutil.copy2(src, destination / 'copyright')
shutil.copy2(build / 'dependencies/vcpkg/status', licenses / 'vcpkg-packages.txt')

(package / 'README.txt').write_text(f'''openEMS Windows x64 MSVC + Vulkan preview: {description}

Extract the entire openEMS folder. Add it to PATH to use openEMS.exe,
nf2ff.exe, sar_calc.exe and AppCSXCAD.exe. DLLs are beside the executables.

Python 3.13 or 3.14 (standard 64-bit CPython, installed separately):
  1. Open PowerShell in the extracted openEMS folder.
  2. Create an environment with your matching Python:
       py -3.14 -m venv .venv
  3. Install matching wheels (cp314 for 3.14, cp313 for 3.13):
       .venv\\Scripts\\python -m pip install (Get-ChildItem python\\csxcad-*-cp314-cp314-win_amd64.whl).FullName
       .venv\\Scripts\\python -m pip install (Get-ChildItem python\\openems-*-cp314-cp314-win_amd64.whl).FullName
  4. Tell Python where the DLLs are for this session:
       $env:CSXCAD_INSTALL_PATH = (Get-Location).Path
       $env:OPENEMS_INSTALL_PATH = $env:CSXCAD_INSTALL_PATH
  5. Check the installation:
       .venv\\Scripts\\python -c "import CSXCAD, openEMS; print(openEMS.openEMS())"
       .venv\\Scripts\\python python\\smoke_test.py

Python is not bundled. Use the wheels matching the Python version; MinGW
Python is not supported by these wheels. NumPy, Matplotlib and h5py are
installed by pip as package dependencies (internet access required).
Tutorials are in python\\Tutorials and matlab\\Tutorials.

Octave/Matlab:
  addpath('C:\\path\\to\\openEMS\\matlab')
  Add CTB to the search path for tutorials using the Circuit Toolbox.
  Octave/Matlab and its HDF5 helper setup are separate prerequisites.

GPU use: pass engine='vulkan' to FDTD.Run(), or --engine=vulkan to the
command-line solver. Install the GPU manufacturer's Vulkan driver.
The loader is bundled; a compatible GPU is needed only for GPU execution.
Check GPU execution with python\\smoke_test.py --engine vulkan.

This is a preview from modified source, not an official upstream release.
BUILD-INFO.json records the revisions and local changes. Distribute the
companion source ZIP with this package. Licenses are under licenses/.
Documentation: https://docs.openems.de
''', encoding='utf-8')
(package / 'python/README.txt').write_text('See ../README.txt for Python 3.13/3.14 wheel installation instructions.\n')
revisions = {}
components = ('', 'openEMS', 'CSXCAD', 'QCSXCAD', 'AppCSXCAD', 'fparser', 'CTB', 'hyp2mat')
for name in components:
    command = ['git', '-C', str(ROOT / name)]
    revisions[name or 'openEMS-Project'] = {
        'commit': subprocess.check_output(command + ['rev-parse', 'HEAD'], text=True).strip(),
        'diff': subprocess.check_output(command + ['diff', 'HEAD'], text=True),
    }
info = {'name': stem, 'compiler': 'MSVC x64', 'vulkan': True, 'python': ['3.13', '3.14'],
        'vtk_qt_quick': False,
        'revisions': revisions,
        'native_imports': sorted(dependency_names),
        'vcpkg_commit': subprocess.check_output(['git', '-C', str(build / 'vcpkg'), 'rev-parse', 'HEAD'], text=True).strip()}
(package / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
out = ROOT / 'build/release'
out.mkdir(exist_ok=True)
binary_zip = out / f'{stem}.zip'
with zipfile.ZipFile(binary_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
    for src in package.rglob('*'):
        if src.is_file():
            archive.write(src, src.relative_to(stage).as_posix())
source_zip = out / f'{stem}-source.zip'
with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
    archived = set()
    for name in components:
        base = ROOT / name
        files = subprocess.check_output(['git', '-C', str(base), 'ls-files', '-z']).decode().split('\0')
        for file in files:
            src = base / file
            if src.is_file():
                relative = src.relative_to(ROOT).as_posix()
                archive.write(src, 'openEMS-source/' + relative)
                archived.add(relative)
    for src in (ROOT / 'scripts').rglob('*'):
        if src.is_file() and src.relative_to(ROOT).as_posix() not in archived and '__pycache__' not in src.parts:
            archive.write(src, 'openEMS-source/' + src.relative_to(ROOT).as_posix())
    archive.write(package / 'BUILD-INFO.json', 'openEMS-source/BUILD-INFO.json')
    for src in (build / 'overlay-ports/vtk').rglob('*'):
        if src.is_file():
            archive.write(src, 'openEMS-source/release-dependency-overlay/vtk/' + src.relative_to(build / 'overlay-ports/vtk').as_posix())
checksums = []
for archive in (binary_zip, source_zip):
    with archive.open('rb') as stream:
        checksums.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {archive.name}')
(out / f'{stem}-SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n')
print(binary_zip)
print(source_zip)
