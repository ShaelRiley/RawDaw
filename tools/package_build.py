"""Package the tested Linux renderer, exact source tree, catalog packs and auditions."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from prde1 import __version__
from source_catalog import recipes, projects
from assemble_build import CHUNK_BYTES
NAME='PRDE1_'+__version__+'_Linux_x86_64'
STAMP=1791504000  # Stable build-content timestamp: 2026-10-09 UTC.


def source_tree():
    # Exclude prior distributions so rebuilding does not include the old
    # archive's hash in its own input identity. Leave the real index untouched.
    records=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT).split(b'\0')
    records=[row for row in records if row and not row.split(b'\t',1)[1].startswith(b'dist/')]
    with tempfile.TemporaryDirectory(prefix='prde1-build-index-') as folder:
        environment=os.environ.copy();environment['GIT_INDEX_FILE']=folder+'/index'
        subprocess.run(['git','read-tree','--empty'],cwd=ROOT,env=environment,check=True)
        subprocess.run(['git','update-index','-z','--index-info'],cwd=ROOT,env=environment,
                       input=b'\0'.join(records)+b'\0',check=True)
        return subprocess.check_output(['git','write-tree'],cwd=ROOT,env=environment,text=True).strip()


def main():
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        raise ValueError('This convenience distribution targets Linux x86_64')
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    files={name:(ROOT/name).read_bytes() for name in tracked if name and not name.startswith('dist/')}
    expected_packs={'packs/'+recipe['packId']+'.prdepack' for recipe in recipes()}
    if {name for name in files if name.endswith('.prdepack')}!=expected_packs:
        raise ValueError('Tracked packs differ from the source catalog')
    binary=ROOT/'build'/'prde1-render'
    files['build/prde1-render']=binary.read_bytes()
    expected_auditions={project.stem+'.wav' for project in projects()}
    for path in sorted((ROOT/'out'/'source-auditions').glob('*.wav')):
        files['auditions/'+path.name]=path.read_bytes()
    if {name.removeprefix('auditions/') for name in files if name.startswith('auditions/')}!=expected_auditions:
        raise ValueError('Verified auditions differ from the source catalog')
    version=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
    dependencies=subprocess.check_output(['ldd',str(binary)],text=True)
    dependencies=re.sub(r'\s*\(0x[0-9a-fA-F]+\)','',dependencies)
    build_info={'version':__version__,'target':'Linux x86_64','builtOn':'Ubuntu 24.04',
        'compiler':version,'python':platform.python_version(),'sourceTreeBeforeDistribution':source_tree(),
        'systemLibraries':dependencies,'schemaVersion':'1.0.0-dev.1','packCount':len(expected_packs),
        'releaseStatus':'private development checkpoint; coverage-limited packs; listening gate open',
        'files':{name:{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)} for name,raw in sorted(files.items())}}
    files['BUILD_INFO.json']=(json.dumps(build_info,indent=2)+'\n').encode()
    output=ROOT/'dist'/(NAME+'.tar.gz');output.parent.mkdir(exist_ok=True)
    temporary=output.with_suffix('.partial')
    with temporary.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=STAMP,compresslevel=6) as compressed:
            with tarfile.open(fileobj=compressed,mode='w',format=tarfile.PAX_FORMAT) as archive:
                for name,data in sorted(files.items()):
                    info=tarfile.TarInfo(NAME+'/'+name);info.size=len(data);info.mtime=STAMP
                    info.mode=0o755 if name in ('run-demos.sh','run-prde1.sh','build/prde1-render') else 0o644
                    archive.addfile(info,io.BytesIO(data))
    temporary.replace(output)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n')
    parts=[]
    with output.open('rb') as source:
        while chunk:=source.read(CHUNK_BYTES):
            part=output.with_name(output.name+f'.part{len(parts)+1:02d}')
            part.write_bytes(chunk)
            parts.append({'file':part.name,'bytes':len(chunk),'sha256':hashlib.sha256(chunk).hexdigest()})
    manifest={'version':__version__,'archive':output.name,'bytes':output.stat().st_size,'sha256':digest,'parts':parts}
    (output.parent/(NAME+'.parts.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    print(output,output.stat().st_size,'bytes',digest)


if __name__=='__main__':main()
