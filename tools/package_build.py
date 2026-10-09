"""Package the tested Linux renderer, exact source tree, three packs and auditions."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import platform
import subprocess
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
NAME='PRDE1_0.2.0_Linux_x86_64'
STAMP=1791504000  # Stable build-content timestamp: 2026-10-09 UTC.


def main():
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        raise ValueError('This convenience distribution targets Linux x86_64')
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    files={name:(ROOT/name).read_bytes() for name in tracked if name and not name.startswith('dist/')}
    if len([name for name in files if name.endswith('.prdepack')])!=3:
        raise ValueError('Expected exactly three tracked source packs')
    binary=ROOT/'build'/'prde1-render'
    files['build/prde1-render']=binary.read_bytes()
    for path in sorted((ROOT/'out'/'cc-auditions').glob('*.wav')):
        files['auditions/'+path.name]=path.read_bytes()
    if len([name for name in files if name.startswith('auditions/')])!=6:
        raise ValueError('Six verified auditions are required')
    version=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
    dependencies=subprocess.check_output(['ldd',str(binary)],text=True)
    source_tree=subprocess.check_output(['git','write-tree'],cwd=ROOT,text=True).strip()
    build_info={'version':'0.2.0','target':'Linux x86_64','builtOn':'Ubuntu 24.04',
        'compiler':version,'python':platform.python_version(),'sourceTreeBeforeDistribution':source_tree,
        'systemLibraries':dependencies,'schemaVersion':'1.0.0-dev.1','packCount':3,
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
                    info.mode=0o755 if name in ('run-demos.sh','build/prde1-render') else 0o644
                    archive.addfile(info,io.BytesIO(data))
    temporary.replace(output)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n')
    print(output,output.stat().st_size,'bytes',digest)


if __name__=='__main__':main()
