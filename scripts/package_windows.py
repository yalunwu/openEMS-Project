"""Assemble a portable ZIP from the local MinGW build (no compiler bundled)."""
import hashlib
import json
import os
from datetime import date
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MINGW = Path(sys.prefix)
OUT = ROOT / 'build' / 'release'
NAME = f'openEMS-windows-x64-vulkan-{date.today().isoformat()}-preview'
PKG = OUT / NAME
if PKG.exists():
    raise SystemExit(f'Staging folder already exists: {PKG}')
PKG.mkdir(parents=True)

def copy_tree(src, dst, ignore=None):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)

ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.pdb')
copy_tree(ROOT / 'build/install/bin', PKG / 'bin', ignore)
copy_tree(ROOT / 'build/install/share', PKG / 'share', ignore)
copy_tree(ROOT / 'build/install/include', PKG / 'include', ignore)
copy_tree(ROOT / 'build/install/lib', PKG / 'lib', ignore)
shutil.copy2(MINGW / 'bin/python.exe', PKG / 'bin/python.exe')
stdlib = MINGW / 'lib/python3.14'
copy_tree(stdlib, PKG / 'lib/python3.14', shutil.ignore_patterns(
    '__pycache__', '*.pyc', 'site-packages', 'test', 'tests', 'idlelib',
    'tkinter', 'turtledemo', 'ensurepip', 'config-3.14', '_tkinter*'))
site = PKG / 'lib/python3.14/site-packages'
site.mkdir()
packages = ('numpy', 'h5py', 'matplotlib', 'mpl_toolkits', 'contourpy',
            'cycler', 'dateutil', 'fontTools', 'kiwisolver', 'packaging',
            'PIL', 'pyparsing', 'six.py', 'pylab.py')
for name in packages:
    src = stdlib / 'site-packages' / name
    if src.is_dir():
        copy_tree(src, site / name, ignore)
    else:
        shutil.copy2(src, site / name)
for src in (stdlib / 'site-packages').glob('*.dist-info'):
    if not src.name.lower().startswith(('pip-', 'setuptools-', 'cython-', 'distlib-')):
        copy_tree(src, site / src.name, ignore)
for name in ('CSXCAD', 'openEMS'):
    copy_tree(ROOT / 'build/python' / name, site / name, ignore)
(site / 'sitecustomize.py').write_text('''import os
from pathlib import Path
_root = Path(__file__).resolve().parents[3]
_dll_handles = [os.add_dll_directory(str(_root / "bin"))]
os.environ["CSXCAD_INSTALL_PATH"] = str(_root / "bin")
os.environ["OPENEMS_INSTALL_PATH"] = str(_root / "bin")
''', encoding='utf-8')

# Resolve every native extension as well as the executables; Python and Qt
# plugins can have dependencies that are not imported by openEMS.exe.
queue = list(PKG.rglob('*.exe')) + list(PKG.rglob('*.dll')) + list(PKG.rglob('*.pyd'))
seen = set()
system = Path(os.environ['SystemRoot']) / 'System32'
while queue:
    binary = queue.pop()
    if binary in seen:
        continue
    seen.add(binary)
    result = subprocess.run([str(MINGW / 'bin/objdump.exe'), '-p', str(binary)],
                            capture_output=True, text=True, check=True)
    for dep in re.findall(r'DLL Name:\s*(\S+)', result.stdout):
        target = PKG / 'bin' / dep
        if target.exists():
            queue.append(target)
        elif (MINGW / 'bin' / dep).exists():
            shutil.copy2(MINGW / 'bin' / dep, target)
            queue.append(target)
        elif not (system / dep).exists() and not dep.lower().startswith(('api-ms-', 'ext-ms-')):
            raise RuntimeError(f'Unresolved dependency {dep} in {binary}')

copy_tree(ROOT / 'openEMS/python/Tutorials', PKG / 'examples/Tutorials', ignore)
copy_tree(ROOT / 'openEMS/python/Examples', PKG / 'examples/Examples', ignore)
copy_tree(MINGW / 'share/licenses', PKG / 'licenses/third-party', ignore)
for name in ('openEMS', 'CSXCAD', 'fparser', 'CTB'):
    dest = PKG / 'licenses' / name
    dest.mkdir(parents=True)
    for pattern in ('COPYING*', 'LICENSE*', '*license*'):
        for src in (ROOT / name).glob(pattern):
            if src.is_file():
                shutil.copy2(src, dest / src.name)

(PKG / 'python.cmd').write_text('@echo off\nsetlocal\nset "PYTHONHOME=%~dp0"\nset "PYTHONPATH="\nset "PYTHONNOUSERSITE=1"\nset "PATH=%~dp0bin;%SystemRoot%\\System32;%SystemRoot%"\n"%~dp0bin\\python.exe" %*\nexit /b %errorlevel%\n')
(PKG / 'examples/smoke_test.py').write_text('''from pathlib import Path
import uuid
import gc
import os
import shutil
import gc
import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
csx = ContinuousStructure()
grid = csx.GetGrid()
grid.SetDeltaUnit(1e-3)
for axis in "xyz":
    grid.SetLines(axis, np.linspace(-10, 10, 11))
fdtd = openEMS(NrTS=10)
fdtd.SetCSX(csx)
fdtd.SetGaussExcite(1e9, 0.5e9)
fdtd.SetBoundaryCond(["PEC"] * 6)
fdtd.AddLumpedPort(1, 50, [-2, -2, -2], [2, 2, 2], 'z', 1)
original = Path.cwd()
directory = Path.cwd() / ("openEMS-smoke-" + uuid.uuid4().hex)
directory.mkdir()
try:
    result = fdtd.Run(str(Path(directory) / "simulation"), engine="multithreaded", numThreads=2)
    assert result in (None, 0), result
finally:
    del fdtd
    gc.collect()
    os.chdir(original)
    shutil.rmtree(directory)
print("PASS: packaged Python bindings and CPU simulation")
''')
(PKG / 'README.txt').write_text('''openEMS Windows x64 Vulkan preview - 2026-10-03

Extract the entire folder to a writable location. Open a command prompt
in this folder, then run:

  python.cmd examples\\smoke_test.py
  python.cmd examples\\Tutorials\\MSL_NotchFilter.py
  python.cmd C:\\path\\to\\your_simulation.py

Python 3.14 (MinGW), NumPy, h5py and Matplotlib are bundled. Use python.cmd;
these native bindings do not work with a separately installed CPython.
The smoke test runs a tiny CPU simulation and should print PASS.
Examples using AppCSXCAD geometry viewing need that application separately;
AppCSXCAD, SciPy, pip and a compiler are not included.

Command-line solver: bin\\openEMS.exe <simulation.xml>
Vulkan: use engine='vulkan' in fdtd.Run(). A compatible GPU and its
Vulkan driver are needed. CPU simulation does not require a Vulkan GPU.
GPU behavior depends on the model and device; this is a preview build.

Octave/Matlab: add both share\\openEMS\\matlab and share\\CSXCAD\\matlab
to the search path, and add bin to PATH for that session. Octave/Matlab
and its HDF5 helper setup are separate prerequisites.

Licenses are in licenses/. BUILD-INFO.json identifies the source revisions.
Distribute the companion source ZIP alongside this binary package.
Third-party dependency source/build recipes are provided by MSYS2:
https://github.com/msys2/MINGW-packages
Documentation: https://docs.openems.de
''', encoding='utf-8')

versions = {}
for name in ('', 'openEMS', 'CSXCAD', 'fparser', 'CTB', 'QCSXCAD', 'AppCSXCAD', 'hyp2mat'):
    path = ROOT / name
    versions[name or 'openEMS-Project'] = {
        'commit': subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip(),
        'status': subprocess.check_output(['git', '-C', str(path), 'status', '--short', '--untracked-files=no'], text=True).strip()}
(PKG / 'BUILD-INFO.json').write_text(json.dumps({
    'name': NAME, 'python': sys.version, 'vulkan': True, 'gui': False,
    'revisions': versions}, indent=2), encoding='utf-8')

source_zip = OUT / f'{NAME}-source.zip'
with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in ('', 'openEMS', 'CSXCAD', 'fparser', 'CTB', 'QCSXCAD', 'AppCSXCAD', 'hyp2mat'):
        base = ROOT / name
        files = subprocess.check_output(['git', '-C', str(base), 'ls-files', '-z']).decode().split('\0')
        for file in files:
            src = base / file
            if src.is_file():
                archive.write(src, 'openEMS-source/' + src.relative_to(ROOT).as_posix())
    archive.write(Path(__file__), 'openEMS-source/scripts/package_windows.py')
    archive.write(PKG / 'BUILD-INFO.json', 'openEMS-source/BUILD-INFO.json')
print(f'Staged: {PKG}', flush=True)
print(f'Source: {source_zip}', flush=True)
subprocess.run(['cmd.exe', '/d', '/c', 'python.cmd', 'examples\\smoke_test.py'],
               cwd=PKG, check=True)
binary_zip = OUT / f'{NAME}.zip'
with zipfile.ZipFile(binary_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
    for src in PKG.rglob('*'):
        if src.is_file():
            archive.write(src, src.relative_to(OUT).as_posix())
checksums = []
for archive in (binary_zip, source_zip):
    with archive.open('rb') as stream:
        checksums.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {archive.name}')
(OUT / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n')
print(f'Release: {binary_zip}', flush=True)
