"""Restore a verified distribution from bounded transport parts, atomically."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prde1 import __version__

CHUNK_BYTES = 8 * 1024 * 1024


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('Invalid distribution filename')
    return value


def assemble(manifest_path, output=None):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    name = safe_name(manifest['archive'])
    parts = manifest['parts']
    if not 1 <= len(parts) <= 64 or not 0 < manifest['bytes'] <= 64 * CHUNK_BYTES:
        raise ValueError('Distribution exceeds assembly budget')
    names = [safe_name(part['file']) for part in parts]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate distribution part')
    if any(type(part['bytes']) is not int or not 0 < part['bytes'] <= CHUNK_BYTES for part in parts):
        raise ValueError('Invalid distribution part length')
    if sum(part['bytes'] for part in parts) != manifest['bytes']:
        raise ValueError('Distribution part lengths do not add up')
    destination = Path(output) if output else manifest_path.parent / name
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='prde1-assembly-', suffix='.partial', delete=False) as stream:
            temporary = Path(stream.name)
            archive_hash = hashlib.sha256()
            for part in parts:
                digest = hashlib.sha256()
                count = 0
                with (manifest_path.parent / part['file']).open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        count += len(chunk)
                        if count > part['bytes']:
                            raise ValueError('Distribution part exceeds declared length')
                        digest.update(chunk)
                        archive_hash.update(chunk)
                        stream.write(chunk)
                if count != part['bytes'] or digest.hexdigest() != part['sha256']:
                    raise ValueError('Distribution part hash/length mismatch: ' + part['file'])
            if archive_hash.hexdigest() != manifest['sha256']:
                raise ValueError('Assembled archive hash mismatch')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
        temporary = None
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'dist' / ('PRDE1_' + __version__ + '_Linux_x86_64.parts.json'))
    args = parser.parse_args()
    print(assemble(args.manifest), 'verified and ready to extract')
