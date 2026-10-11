"""Install only the hashed native renderer from this checkout's verified build."""
from __future__ import annotations

import hashlib
import argparse
import json
import os
import platform
import re
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from prde1 import __version__
from prde1.contracts import read_json
from tools.assemble_build import assemble


def install(manifest_path,destination,expected=None):
    if platform.system()!='Linux' or platform.machine()!='x86_64':raise ValueError('Build the native renderer locally on this architecture')
    manifest=json.loads(Path(manifest_path).read_text())
    name='PRDE1_'+__version__+'_Linux_x86_64'
    if manifest['archive']!=name+'.tar.gz' or manifest['version']!=__version__:raise ValueError('Distribution version does not match this checkout')
    archive_path=assemble(manifest_path)
    with tarfile.open(archive_path,'r:gz') as archive:
        wanted={name+'/BUILD_INFO.json':4*1024*1024,name+'/build/prde1-render':16*1024*1024};contents={};count=0;total=0
        for member in archive:
            count+=1;total+=member.size
            if count>4096 or total>256*1024*1024:raise ValueError('Distribution contents exceed installation budget')
            if member.name in wanted:
                if member.name in contents or not member.isfile() or not 0<member.size<=wanted[member.name]:raise ValueError('Invalid distribution member: '+member.name)
                with archive.extractfile(member) as stream:contents[member.name]=stream.read(wanted[member.name]+1)
        if set(contents)!=set(wanted):raise ValueError('Distribution is missing native build metadata/renderer')
        info=read_json(contents[name+'/BUILD_INFO.json'])
        if info['version']!=__version__:raise ValueError('Build metadata version mismatch')
        binary=contents[name+'/build/prde1-render'];bound=info['files']['build/prde1-render']
        if len(binary)!=bound['bytes'] or hashlib.sha256(binary).hexdigest()!=bound['sha256']:raise ValueError('Native renderer hash mismatch')
        if expected is not None and bound!=expected:raise ValueError('Renderer identity does not match this checkout')
        if binary[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(binary[18:20],'little')!=62:raise ValueError('Renderer is not a Linux x86_64 ELF')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True);temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,suffix='.partial',delete=False) as output:
            temporary=Path(output.name);output.write(binary);output.flush();os.fsync(output.fileno())
        temporary.chmod(0o755);temporary.replace(destination);temporary=None
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return destination


def ensure(manifest_path,destination,identity_path):
    """Keep a matching binary offline; replace an older executable atomically."""
    identity_path=Path(identity_path)
    if identity_path.stat().st_size>4*1024*1024:raise ValueError('Renderer identity metadata is too large')
    info=read_json(identity_path.read_bytes())
    if info['version']!=__version__:raise ValueError('Renderer identity version does not match this checkout')
    expected=info['files']['build/prde1-render']
    if (type(expected['bytes']) is not int or not 20<=expected['bytes']<=16*1024*1024
            or not isinstance(expected['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',expected['sha256'])):
        raise ValueError('Invalid renderer identity')
    destination=Path(destination)
    if (destination.is_file() and not destination.is_symlink() and os.access(destination,os.X_OK)
            and destination.stat().st_size==expected['bytes']
            and hashlib.sha256(destination.read_bytes()).hexdigest()==expected['sha256']):
        return destination,False
    if not Path(manifest_path).is_file():raise ValueError('Renderer needs rebuilding: run make all or restore the compiled distribution')
    return install(manifest_path,destination,expected),True


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ensure',action='store_true',help='Verify the installed renderer and upgrade it if necessary')
    args=parser.parse_args()
    name='PRDE1_'+__version__+'_Linux_x86_64'
    manifest=ROOT/'dist'/(name+'.parts.json');destination=ROOT/'build/prde1-render'
    if args.ensure:
        identity=ROOT/'dist'/(name+'.renderer.json')
        if not identity.is_file():identity=ROOT/'BUILD_INFO.json'
        path,updated=ensure(manifest,destination,identity)
        if updated:print(path,'verified and installed')
    else:
        print(install(manifest,destination),'verified and installed')
