"""Prepare explicitly SYNTHETIC fixtures. This is NOT the AI song-pack builder.

No real recording is ingested, separated, transcribed, or claimed to have been
extracted. All synthesis/loop preparation happens here, before pack playback.
"""
from __future__ import annotations

import argparse
import io
import math
import random
import struct
import sys
import wave
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from prde1.contracts import RATE, SLOTS, VERSION, canonical_bytes
from prde1.music import diatonic
from prde1.pack import sha256
from prde1.project import save_project


def pcm_wave(values,channels=1):
    output=io.BytesIO()
    raw=bytearray(len(values)*3)
    for index,value in enumerate(values):
        number=max(-8388608,min(8388607,round(value*8388608)))&0xffffff
        raw[index*3:index*3+3]=number.to_bytes(3,"little")
    with wave.open(output,"wb") as stream:
        stream.setnchannels(channels); stream.setsampwidth(3); stream.setframerate(RATE); stream.writeframes(raw)
    return output.getvalue()


def note_audio(notes,duration=0.65,loop=False):
    frames=round(duration*RATE)
    values=[0.0]*frames
    for frame in range(48,frames):
        time=(frame-48)/RATE
        envelope=min(1,time/0.004)*min(1,(duration-time)/0.012)
        if not loop:
            envelope*=math.exp(-time*0.5)
        values[frame]=sum(math.sin(2*math.pi*440*2**((note-69)/12)*time)
                          +0.18*math.sin(4*math.pi*440*2**((note-69)/12)*time) for note in notes)*envelope*0.18/len(notes)
    marker=None
    if loop:
        start,end=4800,frames-1200
        # Offline circular crossfade; fixture QA can test marker continuity.
        crossfade=240
        for index in range(crossfade):
            weight=(index+1)/(crossfade+1)
            values[end-crossfade+index]=values[end-crossfade+index]*(1-weight)+values[start-crossfade+index]*weight
        marker={"startFrame":start,"endFrame":end,"validated":True}
    return pcm_wave(values),frames,marker


def drum_audio(identity):
    duration={"kick":0.35,"snare":0.25,"hat_closed":0.08,"hat_open":0.55,"tom_low":0.45,"tom_high":0.35,"crash":0.7}[identity]
    rng=random.Random(identity)
    frames=round(duration*RATE)
    values=[]
    for frame in range(frames):
        time=frame/RATE
        fade=min(1,(duration-time)/0.01)
        if identity=="kick":
            value=math.sin(2*math.pi*(48*time+15*(1-math.exp(-time*30))/30))*math.exp(-time*16)*0.55
        elif identity.startswith("tom"):
            value=(math.sin(2*math.pi*(90 if identity=="tom_low" else 135)*time)+rng.uniform(-0.1,0.1))*math.exp(-time*12)*0.25
        elif identity=="snare":
            value=rng.uniform(-1,1)*math.exp(-time*25)*0.30
        else:
            value=rng.uniform(-1,1)*math.exp(-time*(90 if identity=="hat_closed" else 12))*0.13
        values.append(value*fade)
    return pcm_wave(values),frames,None


def expression():
    return {"velocity":0.8,"attackMs":0,"playPercent":100,"changePercent":0,"variation":"none","locked":False,"lockExactPitch":False}


def event(identity,position,duration,kind,tone=0,register=60,sound=""):
    return {"id":identity,"beat":str(position),"duration":str(duration),"kind":kind,"enabled":True,
            "choice":{"tone":tone,"registerMidi":register,"exactMidi":None,"soundIdentity":sound},"expression":expression()}


def channel():
    return {"gainDb":-6,"pan":0,"muted":False,"eqPreset":"neutral","reverbOn":False,"delayOn":False,"inserts":[]}


def variable(value):
    result=[value&127]
    while value>>7:
        value>>=7; result.insert(0,(value&127)|128)
    return bytes(result)


def midi_drums(pattern,addresses,quarter_bpm=120):
    if not 20<=quarter_bpm<=300:
        raise ValueError("MIDI tempo outside preparation profile")
    tempo=round(60000000/quarter_bpm).to_bytes(3,"big")
    data=[(0,0,b"\xff\x51\x03"+tempo),(0,0,b"\xff\x58\x04\x04\x02\x18\x08")]
    from fractions import Fraction
    for hit in pattern["events"]:
        tick=round(Fraction(hit["beat"])*480)
        address=addresses[hit["choice"]["soundIdentity"]]
        data.extend([(tick,1,bytes([0x99,address,round(127*hit["expression"]["velocity"])])),(tick+60,0,bytes([0x89,address,0]))])
    data.append((1920,2,b"\xff\x2f\x00")); data.sort()
    track=bytearray(); previous=0
    for tick,_,message in data:
        track.extend(variable(tick-previous)); track.extend(message); previous=tick
    return b"MThd"+struct.pack(">IHHH",6,0,1,480)+b"MTrk"+struct.pack(">I",len(track))+track


def make_fixture(output:Path,extras=1):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    files={}; samples=[]; mappings=[]
    source_hash=sha256(b"PRDE1 deterministic synthetic fixture recipe v0.1.0")
    def add(identity,role,pitches,audio,frames,loop=None,chord=None,articulation="single"):
        path=f"audio/{role}/{identity}.wav"; files[path]=audio
        sample={"id":identity,"role":role,"articulation":articulation,"path":path,"sha256":sha256(audio),"sampleRate":RATE,"bitsPerSample":24,
                "channels":1,"frames":frames,"onsetFrame":48 if pitches else 0,"gainDb":0,"pitches":pitches,"chord":chord,"loop":loop,
                "source":{"seconds":0,"quarterBeat":"0","durationSeconds":frames/RATE},
                "lineage":{"kind":"synthetic","sourceAsset":"generated:fixture","recipe":"tools/build_fixture.py; not source extraction","transformationCost":0},
                "quality":{"accepted":True,"confidence":1,"notes":"Synthetic mathematical identity; no human listening or source-quality claim"}}
        samples.append(sample)
        return identity
    for role,first in (("bass",36),("lead",60)):
        for offset in (0,2,4,5,7,9,11):
            note=first+offset
            audio,frames,loop=note_audio([note],loop=offset==0)
            identity=add(f"{role}_{note}",role,[note],audio,frames,loop)
            mappings.append({"role":role,"note":note,"root":None,"quality":None,"inversion":0,"sampleId":identity})
    for root,quality,notes in [(0,"major",[60,64,67]),(5,"major",[53,57,60]),(7,"major",[55,59,62]),
                               (9,"minor",[57,60,64]),(2,"minor",[50,53,57]),(4,"minor",[52,55,59])]:
        audio,frames,_=note_audio(notes,2.1)
        identity=add(f"chord_{root}_{quality}","rhythm",notes,audio,frames,chord={"root":root,"quality":quality,"inversion":0},articulation="whole-chord")
        mappings.append({"role":"rhythm","note":None,"root":root,"quality":quality,"inversion":0,"sampleId":identity})
    drum_records={}
    specs=[("kick","kick",36),("snare","snare",38),("hatClosed","hat_closed",42),("hatOpen","hat_open",46),
           ("tom1","tom_low",45),("tom2","tom_high",48),("extra1","crash",49),("extra2","tuned_C_stab",85)]
    for index,(slot,sound,address) in enumerate(specs):
        if index>=6+extras:
            drum_records[slot]={"status":"empty","reason":"Intentionally unused optional synthetic slot","sampleId":None,"displayName":"Unassigned",
                                "soundIdentity":"","midiAddress":None,"pitchClass":"unpitched","pitches":[]}
            continue
        pitches=[72] if slot=="extra2" else []
        audio,frames,loop=note_audio(pitches,0.2) if pitches else drum_audio(sound)
        identity=add("drum_"+sound,"drums",pitches,audio,frames,articulation=sound)
        drum_records[slot]={"status":"available","reason":"","sampleId":identity,"displayName":sound.replace("_"," ").title(),
                            "soundIdentity":sound,"midiAddress":address,"pitchClass":"pitched" if pitches else "unpitched","pitches":pitches}
    pattern={"id":"fixture_drums","role":"drums","length":"4","events":[],"provenance":{"sourceClip":"synthetic_groove_1","license":"MIT","changes":"Authored synthetic pattern; not transcribed"}}
    for index in range(8):
        from fractions import Fraction
        pattern["events"].append(event("hat_"+str(index),Fraction(index,2),"1/4","drum",sound="hat_closed"))
    for position in (0,2):pattern["events"].append(event("kick_"+str(position),position,"3/4","drum",sound="kick"))
    for position in (1,3):pattern["events"].append(event("snare_"+str(position),position,"1/2","drum",sound="snare"))
    if extras:pattern["events"].append(event("crash_0",0,"2","drum",sound="crash"))
    addresses={record["soundIdentity"]:record["midiAddress"] for record in drum_records.values() if record["status"]=="available"}
    files["clips/normalized/groove_1.json"]=canonical_bytes(pattern)
    files["clips/source-midi/groove_1.mid"]=midi_drums(pattern,addresses)
    files["clips/index.json"]=canonical_bytes([{"id":"synthetic_groove_1","role":"drums","origin":"synthetic_fixture","license":"MIT",
                    "attribution":"PRDE1 development fixture by Shael Riley","sourceHash":source_hash,
                    "normalizedPath":"clips/normalized/groove_1.json","midiPath":"clips/source-midi/groove_1.mid"}])
    files["analysis/harmony.json"]=canonical_bytes({"kind":"synthetic_fixture","quarterBpm":120,"meter":[4,4],"tonic":0,"mode":"major"})
    files["analysis/coverage.json"]=canonical_bytes({"profile":"synthetic-smoke-v1","sourceExtractionValidated":False,
                        "coveredNotes":{"bass":[36,38,40,41,43,45,47],"lead":[60,62,64,65,67,69,71]},"coveredChordRoots":[0,5,7,9,2,4]})
    files["presets/mix.json"]=canonical_bytes({"preset":"neutral","reverbOn":False,"delayOn":False})
    files["provenance.json"]=canonical_bytes({"kind":"synthetic_fixture","generator":"tools/build_fixture.py","license":"MIT","authorship":"Shael Riley"})
    files["qa/report.json"]=canonical_bytes({"sourceExtraction":"not_attempted","humanListening":"not_performed","syntheticPitchMetadata":"mathematically generated"})
    files["preview/audition.wav"]=note_audio([60,64,67],1.0)[0]
    def status(role):
        sample=next(item for item in samples if item["role"]==role)
        return {"status":"available","reason":"","sampleId":sample["id"],"displayName":"Synthetic "+role,"soundIdentity":"fixture_"+role,
                "midiAddress":None,"pitchClass":"pitched","pitches":sample["pitches"]}
    manifest={"schemaVersion":VERSION,"packId":f"synthetic_smoke_extras_{extras}",
              "builder":{"version":"synthetic-fixture-0.1.0","profileVersion":"core-v1-dev.1","modelVersion":"none"},
              "source":{"title":"SYNTHETIC developer fixture — not extracted audio","sha256":source_hash,"kind":"synthetic_fixture",
                        "rightsDeclaration":"Self-authored mathematical test signals and MIDI","license":"MIT","attribution":"Shael Riley"},
              "audio":{"sampleRate":RATE,"bitsPerSample":24,"tuningHz":440,"tuning":"12-TET"},
              "maps":{"harmony":"analysis/harmony.json","coverage":"analysis/coverage.json"},
              "instruments":{"lead":status("lead"),"rhythm":status("rhythm"),"bass":status("bass"),"drums":drum_records},
              "samples":samples,"mappings":mappings,"files":{path:sha256(raw) for path,raw in files.items()},
              "clips":{"index":"clips/index.json","libraryVersion":"synthetic-fixtures-0.1.0"},"channelPresets":"presets/mix.json",
              "provenance":"provenance.json","qa":"qa/report.json","preview":"preview/audition.wav",
              "validation":{"status":"complete","notes":"Complete only for the declared synthetic smoke inventory; not source or release validation"}}
    raw_manifest=canonical_bytes(manifest)
    files["manifest.json"]=raw_manifest
    pack_path=output/"synthetic.prdepack"
    with zipfile.ZipFile(pack_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(files):
            entry=zipfile.ZipInfo(path,(2026,1,1,0,0,0)); entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=(0o100644<<16); archive.writestr(entry,files[path])
    for name,tonic,mode,degrees in [("major",0,"major",[1,5,6,4]),("minor",9,"natural_minor",[1,6,3,7])]:
        patterns=[]; instances=[]
        for bar in range(4):
            for role in ("rhythm","bass","lead","drums"):
                if role=="drums":
                    import copy
                    part=copy.deepcopy(pattern); part["id"]=f"drums_{bar}"
                else:
                    events=([event("chord",0,4,"chord")] if role=="rhythm" else
                            [event("note_"+str(index),index,"3/4","note",tone=index%3 if role=="lead" else 0,register=64 if role=="lead" else 40) for index in range(4)])
                    part={"id":f"{role}_{bar}","role":role,"length":"4","events":events,
                          "provenance":{"sourceClip":"self-authored synthetic steps","license":"MIT","changes":"none"}}
                patterns.append(part); instances.append({"id":f"{role}_instance_{bar}","patternId":part["id"],"beat":str(bar*4),"linked":False})
        channels={role:channel() for role in ("lead","rhythm","bass","drums",*["drums."+slot for slot in SLOTS])}
        master=channel(); master["gainDb"]=0
        project={"formatVersion":VERSION,"projectId":"synthetic_"+name,"title":"SYNTHETIC "+name+" checkpoint audition",
                 "packReference":{"packId":manifest["packId"],"manifestSha256":sha256(raw_manifest)},"musicalRegistryVersion":"core-v1-dev.1",
                 "tempoMap":[{"beat":"0","quarterBpm":120}],"meterMap":[{"beat":"0","numerator":4,"denominator":4,"governorSegments":4}],
                 "tonalityMap":[{"beat":"0","tonic":tonic,"mode":mode}],"harmony":[{"beat":str(index*4),"chord":diatonic(tonic,mode,degree)} for index,degree in enumerate(degrees)],
                 "length":"16","patterns":patterns,"instances":instances,"variation":{"seed":"synthetic-repeatable-1","revision":0},
                 "mix":{"channels":channels,"master":master,"compressor":{"on":True,"thresholdDb":-12,"ratio":2,"attackMs":10,"releaseMs":150}},
                 "pluginTracks":[],"vocals":[{"id":"vocal_1","visible":True,"takes":[],"selectedTakeId":None,"comp":[],
                              "correction":{"on":False,"target":"key-mode"},"channel":channel()}],
                 "editorContext":{"selection":"rhythm_0","zoom":1,"scrollBeat":"0","lastAction":"Synthetic fixture created"},
                 "credits":[{"source":"self-authored synthetic test assets","license":"MIT","attribution":"Shael Riley","changes":"none"}]}
        save_project(output/(name+".prdeproj"),project)
    return pack_path


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True); parser.add_argument("--extras",type=int,choices=(0,1,2),default=1)
    options=parser.parse_args(); print(make_fixture(options.output,options.extras))
