"""Install only the hashed native renderer from this checkout's verified build."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from prde1 import __version__
from prde1.contracts import read_json
from tools.assemble_build import assemble


def install(manifest_path,destination):
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
        binary=contents[name+'/build/prde1-render'];expected=info['files']['build/prde1-render']
        if len(binary)!=expected['bytes'] or hashlib.sha256(binary).hexdigest()!=expected['sha256']:raise ValueError('Native renderer hash mismatch')
        if binary[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(binary[18:20],'little')!=62:raise ValueError('Renderer is not a Linux x86_64 ELF')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True);temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,suffix='.partial',delete=False) as output:
            temporary=Path(output.name);output.write(binary);output.flush();os.fsync(output.fileno())
        temporary.chmod(0o755);temporary.replace(destination);temporary=None
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return destination


if __name__=='__main__':
    print(install(ROOT/'dist'/('PRDE1_'+__version__+'_Linux_x86_64.parts.json'),ROOT/'build/prde1-render'),'verified and installed')
