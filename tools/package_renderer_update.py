"""Ship a small, hashed renderer upgrade for a source checkout with existing packs.

This is an engine update, not a standalone all-content distribution. The normal
launcher and installer validate/restore it without requiring a local compiler.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import platform
import sys
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from prde1 import __version__


def main():
    if platform.system()!='Linux' or platform.machine()!='x86_64':raise ValueError('Linux x86_64 build required')
    name='PRDE1_'+__version__+'_Linux_x86_64';binary=(ROOT/'build/prde1-render').read_bytes()
    bound=dict(bytes=len(binary),sha256=hashlib.sha256(binary).hexdigest())
    source={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'native').glob('*')) if p.is_file()}
    info=dict(version=__version__,target='Linux x86_64',distribution='renderer upgrade for the source checkout; existing packs retained',
              nativeSourceSha256=source,files={'build/prde1-render':bound})
    payload={'BUILD_INFO.json':(json.dumps(info,indent=2)+'\n').encode(),'build/prde1-render':binary}
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',filename='',mtime=1791676800,compresslevel=9) as gz:
        with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as archive:
            for path,raw in sorted(payload.items()):
                member=tarfile.TarInfo(name+'/'+path);member.size=len(raw);member.mtime=1791676800
                member.mode=0o755 if path=='build/prde1-render' else 0o644
                archive.addfile(member,io.BytesIO(raw))
    raw=buffer.getvalue();digest=hashlib.sha256(raw).hexdigest();folder=ROOT/'dist';folder.mkdir(exist_ok=True)
    part=name+'.tar.gz.part01';(folder/part).write_bytes(raw)
    manifest=dict(version=__version__,archive=name+'.tar.gz',bytes=len(raw),sha256=digest,
                  parts=[dict(file=part,bytes=len(raw),sha256=digest)])
    (folder/(name+'.parts.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    (folder/(name+'.renderer.json')).write_text(json.dumps(dict(version=__version__,target='Linux x86_64',files=info['files']),indent=2)+'\n')
    (folder/(name+'.tar.gz.sha256')).write_text(digest+'  '+name+'.tar.gz\n')
    print(json.dumps(dict(version=__version__,upgradeBytes=len(raw),renderer=bound)))


if __name__=='__main__':main()
