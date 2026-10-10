"""Render the catalog's source arrangements and verify actual PCM repeat/seek identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from source_catalog import projects, pack_for_project


def render(pack,project,output,seek=0):
    args=['python3','-m','prde1','render',str(pack),str(project),str(output)]
    if seek:args+=['--seek-frame',str(seek)]
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,check=True)
    return json.loads(result.stdout)


def pcm(path):
    with wave.open(str(path),'rb') as stream:
        if (stream.getnchannels(),stream.getsampwidth(),stream.getframerate())!=(2,3,48000):
            raise ValueError('Incorrect rendered audio format')
        return stream.readframes(stream.getnframes())


def main(output):
    output.mkdir(parents=True,exist_ok=True)
    reports=[]
    expected=projects()
    if set(expected)!=set((ROOT/'packs').glob('*.prdeproj')):
        raise ValueError('Source catalog differs from available arrangements')
    for project in sorted(expected):
        pack=pack_for_project(project)
        before=hashlib.sha256(pack.read_bytes()).hexdigest()
        path=output/(project.stem+'.wav')
        report=render(pack,project,path)
        if report['conflicts'] or not 0<report['peak']<1:raise ValueError('Source demo export failed quality/coverage screen')
        data=pcm(path)
        seek=report['frames']*3//4 if report['frames']>=120*48000 else 123457
        with tempfile.TemporaryDirectory(prefix='prde1-cc-repeat-') as folder:
            repeated=Path(folder)/'repeated.wav';sought=Path(folder)/'sought.wav'
            render(pack,project,repeated)
            if repeated.read_bytes()!=path.read_bytes():raise ValueError('Non-repeatable source-pack render')
            render(pack,project,sought,seek)
            if pcm(sought)!=data[seek*6:]:raise ValueError('Source-pack seek differs from full-render slice')
        if hashlib.sha256(pack.read_bytes()).hexdigest()!=before:raise ValueError('Source pack modified during playback')
        report.update(project=project.name,pack=pack.name,packSha256=before,
                      wavSha256=hashlib.sha256(path.read_bytes()).hexdigest(),repeatByteIdentical=True,
                      verifiedSeekFrame=seek,seekExactSlice=True,packUnchanged=True,humanListening='not_performed')
        reports.append(report)
        print(project.name,report['eventCount'],'events',round(report['peakDbFS'],2),'dBFS; repeat/seek/hash passed',flush=True)
    if len(reports)!=len(expected):raise ValueError('Missing verified source arrangement')
    (output/'validation.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out'/'source-auditions')
    main(parser.parse_args().output)
