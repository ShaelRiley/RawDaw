"""Offline diagnostics for curated, artist-supplied stems; no runtime use.

These estimates are review evidence, not proof of isolation or a listening pass.
No model is downloaded and no source bytes leave the machine.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks
from scipy.optimize import nnls

ANALYSIS_RATE = 16000
MAX_SOURCE_SECONDS = 600
MAX_SOURCE_BYTES = 256 * 1024 * 1024


def decode(path, rate=ANALYSIS_RATE, channels=1):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Absent or oversized source file")
    if rate not in (ANALYSIS_RATE, 48000) or channels not in (1, 2):
        raise ValueError("Unsupported preparation decode format")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "json", str(path)], check=True, capture_output=True, timeout=30)
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    if not math.isfinite(duration) or not 0 < duration <= MAX_SOURCE_SECONDS:
        raise ValueError("Source duration exceeds ten-minute preparation budget")
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", str(MAX_SOURCE_SECONDS + 1), "-ar", str(rate),
                             "-ac", str(channels), "-f", "f32le", "-"],
                            check=True, capture_output=True, timeout=120)
    data = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, channels).copy()
    if len(data) > MAX_SOURCE_SECONDS * rate or not np.isfinite(data).all() or not len(data):
        raise ValueError("Empty or non-finite source audio")
    return data[:, 0] if channels == 1 else data


def onsets(y, rate=ANALYSIS_RATE):
    hop, size = round(rate * .01), 1024
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(y, (size//2, size//2)), size)[::hop]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(size), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(spectrum * 10), axis=0)).mean(axis=1)
    peaks, _ = find_peaks(flux, distance=8, prominence=max(.007, float(np.percentile(flux, 65))*.7))
    return (peaks + 1) * hop / rate, flux


def pitch_frames(y, role, rate=ANALYSIS_RATE):
    size = 2048 if role == "lead" else 4096
    hop = 256
    lower, upper = ((110, 1100) if role == "lead" else (40, 300))
    low, high = int(rate/upper), min(size//2, math.ceil(rate/lower))
    frames = np.lib.stride_tricks.sliding_window_view(y, size)[::hop].astype(np.float64)
    frames -= frames.mean(axis=1, keepdims=True)
    rms = np.sqrt((frames**2).mean(axis=1))
    spectrum = np.fft.rfft(frames, n=size*2, axis=1)
    ac = np.fft.irfft(spectrum * spectrum.conj(), axis=1)[:, :high+2]
    squares = np.cumsum(frames**2, axis=1)
    squares = np.pad(squares, ((0,0),(1,0)))
    lag = np.arange(1, high+2)
    difference = squares[:, size-lag] + squares[:, size, None] - squares[:, lag] - 2*ac[:, 1:high+2]
    difference = np.maximum(0, difference)
    cmnd = difference * lag / np.maximum(1e-20, np.cumsum(difference, axis=1))
    output = []
    floor = max(.0007, float(rms.max()) * .012)
    for index, row in enumerate(cmnd):
        if rms[index] < floor:
            output.append(None); continue
        valleys, _ = find_peaks(-row[low-1:high])
        valleys = valleys + low-1
        good = valleys[row[valleys] < .2]
        chosen = int(good[0]) if len(good) else int(np.argmin(row[low-1:high])+low-1)
        error = float(row[chosen])
        if error > .28:
            output.append(None); continue
        tau = chosen+1.
        if 0 < chosen < len(row)-1:
            a,b,c = row[chosen-1:chosen+2]
            divisor = a-2*b+c
            if abs(divisor)>1e-12: tau += .5*(a-c)/divisor
        midi = 69 + 12*math.log2(rate/tau/440)
        output.append({"time":(index*hop+size/2)/rate,"midi":midi,"error":error,"rms":float(rms[index])})
    return output, hop/rate


def note_candidates(y, role):
    frames, step = pitch_frames(y, role)
    groups=[]; group=[]; last=None
    for frame in frames+[None]:
        note=round(frame["midi"]) if frame else None
        if note != last:
            if len(group)*step >= .13:
                values=np.array([x["midi"] for x in group])
                cents=float((np.median(values)-last)*100)
                spread=float(np.percentile(values,90)-np.percentile(values,10))*100
                if abs(cents)<=45 and spread<=55:
                    groups.append({"note":last,"start":group[0]["time"],"end":group[-1]["time"],
                                   "cents":round(cents,2),"spreadCents":round(spread,2),
                                   "error":float(np.median([x["error"] for x in group])),
                                   "rms":float(np.median([x["rms"] for x in group]))})
            group=[]; last=note
        if frame:group.append(frame)
    return sorted(groups,key=lambda x:(x["note"],x["error"],-min(x["end"]-x["start"],.6),-x["rms"],x["start"]))


def chord_spectrum(y, rate=ANALYSIS_RATE):
    """Harmonic-template fit. Preserve residual and ambiguity for review."""
    y=np.asarray(y,dtype=float); y-=y.mean()
    nfft=16384
    if len(y)>8192:y=y[:8192]
    spectrum=np.abs(np.fft.rfft(y*np.hanning(len(y)),n=nfft))
    frequencies=np.fft.rfftfreq(nfft,1/rate)
    bins=(frequencies>=70)&(frequencies<4200)
    f=frequencies[bins]
    templates=[]
    for note in range(40,85):
        fundamental=440*2**((note-69)/12)
        vector=np.zeros(len(f))
        for harmonic in range(1,13):
            center=fundamental*harmonic
            if center>4200:break
            width=max(3,center*.004)
            vector+=np.exp(-.5*((f-center)/width)**2)/harmonic**1.15
        templates.append(vector)
    matrix=np.array(templates).T
    target=spectrum[bins]
    coefficients,residual=nnls(matrix,target,maxiter=1500)
    chroma=np.zeros(12)
    for i,value in enumerate(coefficients):chroma[(i+40)%12]+=value
    chroma/=max(1e-20,chroma.max())
    ranked=sorted([(i+40,float(v)) for i,v in enumerate(coefficients)],key=lambda x:-x[1])
    return {"chroma":[round(float(x),3) for x in chroma],"notes":ranked[:8],
            "residual":float(residual/max(1e-20,np.linalg.norm(target)))}


def analyze(path, role):
    y=decode(path)
    attacks, _ = onsets(y)
    result={"file":str(path),"duration":len(y)/ANALYSIS_RATE,"onsets":attacks.tolist()}
    if role in ("lead","bass"):result["candidates"]=note_candidates(y,role)
    if role=="rhythm":
        result["candidates"]=[]
        for i,time in enumerate(attacks):
            next_time=attacks[i+1] if i+1<len(attacks) else len(y)/ANALYSIS_RATE
            duration=min(.48,next_time-time-.03)
            if duration<.13:continue
            start=round((time+.045)*ANALYSIS_RATE)
            evidence=chord_spectrum(y[start:start+round(duration*ANALYSIS_RATE)])
            result["candidates"].append({"start":float(time),"end":float(min(time+.6,next_time-.015)),**evidence})
    return result


def drum_candidates(path):
    y=decode(path); attacks,_=onsets(y); rows=[]
    for i,time in enumerate(attacks):
        following=float(attacks[i+1]) if i+1<len(attacks) else len(y)/ANALYSIS_RATE
        a=max(0,round((time-.018)*ANALYSIS_RATE))
        duration=min(.7,following-time-.015)
        if duration<.05:continue
        segment=y[a:a+round(min(.12,duration)*ANALYSIS_RATE)]
        spectrum=abs(np.fft.rfft(segment*np.hanning(len(segment)),n=8192))**2
        frequencies=np.fft.rfftfreq(8192,1/ANALYSIS_RATE)
        total=max(1e-20,float(spectrum.sum()))
        bands=[float(spectrum[(frequencies>=lo)&(frequencies<hi)].sum()/total) for lo,hi in [(0,180),(180,600),(600,3000),(3000,8000)]]
        mask=(frequencies>60)&(frequencies<450)
        low_peak=float(frequencies[mask][spectrum[mask].argmax()])
        tail=y[a:a+round(duration*ANALYSIS_RATE)]
        rows.append({"start":float(time),"end":float(time+duration),"bands":bands,
                     "lowPeakHz":low_peak,"rms":float(np.sqrt(np.mean(tail**2))),
                     "centroidHz":float((spectrum*frequencies).sum()/total),
                     "flatness":float(np.exp(np.log(spectrum+1e-20).mean())/(spectrum.mean()+1e-20))})
    return rows


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path);parser.add_argument("role",choices=["lead","bass","rhythm","drums"])
    parser.add_argument("output",type=Path)
    args=parser.parse_args();data=analyze(args.source,args.role)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(data,indent=2)+"\n")
    print(args.output, len(data.get("candidates",[])), "candidates")
