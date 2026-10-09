"""Render the six shipped arrangements and verify actual PCM repeat/seek identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


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
    for project in sorted((ROOT/'packs').glob('*.prdeproj')):
        pack=project.with_name(project.stem[:-2]+'.prdepack')
        before=hashlib.sha256(pack.read_bytes()).hexdigest()
        path=output/(project.stem+'.wav')
        report=render(pack,project,path)
        if report['conflicts'] or not 0<report['peak']<1:raise ValueError('Source demo export failed quality/coverage screen')
        data=pcm(path)
        with tempfile.TemporaryDirectory(prefix='prde1-cc-repeat-') as folder:
            repeated=Path(folder)/'repeated.wav';sought=Path(folder)/'sought.wav'
            render(pack,project,repeated)
            if repeated.read_bytes()!=path.read_bytes():raise ValueError('Non-repeatable source-pack render')
            render(pack,project,sought,123457)
            if pcm(sought)!=data[123457*6:]:raise ValueError('Source-pack seek differs from full-render slice')
        if hashlib.sha256(pack.read_bytes()).hexdigest()!=before:raise ValueError('Source pack modified during playback')
        report.update(project=project.name,pack=pack.name,packSha256=before,
                      wavSha256=hashlib.sha256(path.read_bytes()).hexdigest(),repeatByteIdentical=True,
                      seekFrame123457ExactSlice=True,packUnchanged=True,humanListening='not_performed')
        reports.append(report)
        print(project.name,report['eventCount'],'events',round(report['peakDbFS'],2),'dBFS; repeat/seek/hash passed',flush=True)
    if len(reports)!=6:raise ValueError('Expected exactly six arrangements')
    (output/'validation.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out'/'cc-auditions')
    main(parser.parse_args().output)
