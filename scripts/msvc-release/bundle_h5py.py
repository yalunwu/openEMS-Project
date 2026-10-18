"""Bundle the matching HDF5 runtime in source-built Windows h5py wheels."""
import argparse
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import zipfile


def bundle(wheel, destination, deps, vs_root):
    dumpbin = next((vs_root / 'VC/Tools/MSVC').glob('*/bin/Hostx64/x64/dumpbin.exe'))
    runtime = list((vs_root / 'VC/Redist/MSVC').glob('*/x64/Microsoft.VC*.CRT'))
    search = [deps / 'bin'] + runtime
    system = Path(os.environ['SystemRoot']) / 'System32'
    with zipfile.ZipFile(wheel) as archive:
        files = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
    # dumpbin needs files, so inspect the original installed extensions and the
    # dependency DLLs in a dedicated temporary directory beside the new wheel.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='h5py-imports-', dir=destination) as temporary:
        root = Path(temporary)
        queue = []
        for name, data in files.items():
            if name.endswith('.pyd'):
                binary = root / name
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_bytes(data)
                queue.append(binary)
        copied = set()
        while queue:
            binary = queue.pop()
            output = subprocess.check_output([str(dumpbin), '/dependents', str(binary)], text=True)
            for name in re.findall(r'^\s{4}(\S+\.dll)\s*$', output, re.MULTILINE | re.IGNORECASE):
                key = name.lower()
                if key in copied or key.startswith(('python3', 'api-ms-', 'ext-ms-')):
                    continue
                source = next((directory / name for directory in search if (directory / name).is_file()), None)
                if source:
                    copied.add(key)
                    files['h5py/' + name] = source.read_bytes()
                    queue.append(source)
                elif not (system / name).is_file():
                    raise RuntimeError(f'Unresolved h5py dependency {name} in {binary}')
    info = next(name.split('/')[0] for name in files if name.endswith('.dist-info/METADATA'))
    # Include the license of each vcpkg package contributing a bundled DLL.
    for listing in (deps.parent / 'vcpkg/info').glob('*.list'):
        entries = listing.read_text().splitlines()
        if not any(Path(entry).name.lower() in copied and '/bin/' in entry for entry in entries):
            continue
        for entry in entries:
            if entry.endswith('/copyright'):
                source = deps.parent / entry
                files[f'{info}/licenses/runtime/{source.parent.name}/copyright'] = source.read_bytes()
    record = info + '/RECORD'
    rows = []
    for name, data in sorted(files.items()):
        if name != record:
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            rows.append((name, 'sha256=' + digest, str(len(data))))
    rows.append((record, '', ''))
    stream = io.StringIO(newline='')
    csv.writer(stream, lineterminator='\n').writerows(rows)
    files[record] = stream.getvalue().encode()
    target = destination / wheel.name
    if target.exists():
        raise FileExistsError(target)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    print(f'{target}: bundled {", ".join(sorted(copied))}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deps', type=Path, required=True)
    parser.add_argument('--vs-root', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    wheels = sorted(args.wheel_dir.glob('h5py-*-win_amd64.whl'))
    if not wheels:
        raise RuntimeError('No source-built h5py wheels found')
    for wheel in wheels:
        bundle(wheel, args.output, args.deps, args.vs_root)
