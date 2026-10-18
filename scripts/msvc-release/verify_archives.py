"""Check a Windows binary/source release against its recorded SHA-256 hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--build-info', type=Path, required=True)
args = parser.parse_args()
info = json.loads(args.build_info.read_text())
stem = info['name']
checksums = {}
for line in (args.directory / (stem + '-SHA256SUMS.txt')).read_text().splitlines():
    digest, name = line.split('  ', 1)
    checksums[name] = digest
for name in (stem + '.zip', stem + '-source.zip'):
    with (args.directory / name).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == checksums[name], f'Archive checksum differs: {name}'
with zipfile.ZipFile(args.directory / (stem + '.zip')) as archive:
    assert archive.testzip() is None, 'Binary archive has corrupt entries'
    embedded = json.loads(archive.read('openEMS/BUILD-INFO.json'))
    assert embedded == info, 'Binary build record differs'
    assert hashlib.sha256(archive.read('openEMS/openEMS.dll')).hexdigest() == info['solver_dll_sha256'], 'Solver DLL checksum differs'
with zipfile.ZipFile(args.directory / (stem + '-source.zip')) as archive:
    assert archive.testzip() is None, 'Source archive has corrupt entries'
    for name, expected in info['source_files'].items():
        assert hashlib.sha256(archive.read('openEMS-source/' + name)).hexdigest() == expected, f'Source checksum differs: {name}'
    embedded = json.loads(archive.read('openEMS-source/BUILD-INFO.json'))
    assert embedded == info, 'Source build record differs'
assert hashlib.sha256(json.dumps(info['source_files'], sort_keys=True).encode()).hexdigest() == info['source_sha256'], 'Source manifest checksum differs'
print(f'PASS release archive checksums, solver DLL and {len(info["source_files"])} source files')
