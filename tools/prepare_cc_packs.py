"""Repeatable preparation of three curated CC songs from verified artist stems.

This bounded prototype is not the public AI builder skill or a general mixed-song
separator. It consumes saved crop/pitch decisions, checks source hashes, and
pre-renders any listed variants before the music runtime sees them.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import math
import shutil
import subprocess
import sys
import wave
import zipfile
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prde1.contracts import RATE, VERSION, SLOTS, canonical_bytes
from prde1.music import MODES, QUALITIES
from prde1.pack import Pack, sha256
from prde1.project import save_project, validate_project
from source_analysis import decode, pitch_frames, chord_spectrum, MAX_SOURCE_BYTES
from build_fixture import channel, event, midi_drums

ROOT = Path(__file__).resolve().parent.parent
PROFILE = "curated-cc-stems-0.2.0"


def pcm24(audio):
    audio=np.asarray(audio)
    if audio.ndim==1:audio=audio[:,None]
    if audio.ndim!=2 or audio.shape[1] not in (1,2) or not 1<=len(audio)<=30*RATE:
        raise ValueError("Audio dimensions exceed preparation profile")
    if not np.isfinite(audio).all() or np.max(np.abs(audio))>=1:
        raise ValueError("Non-finite/clipping prepared audio")
    words=np.rint(audio*8388608).astype(np.int32).reshape(-1)
    if np.min(words)<-8388608 or np.max(words)>8388607:
        raise ValueError("PCM quantization would overflow")
    raw=np.stack([words&255,(words>>8)&255,(words>>16)&255],axis=1).astype(np.uint8).tobytes()
    output=io.BytesIO()
    with wave.open(output,"wb") as stream:
        stream.setnchannels(audio.shape[1]);stream.setsampwidth(3);stream.setframerate(RATE);stream.writeframes(raw)
    return output.getvalue()


def clean(audio, peak=.42, fade_in_ms=2, fade_out_ms=8):
    audio=np.asarray(audio,dtype=np.float64).copy()
    audio-=audio.mean(axis=0,keepdims=True)
    source_peak=float(np.max(np.abs(audio)))
    if source_peak<1e-5:raise ValueError("Silent crop")
    gain=min(4.,peak/source_peak)
    audio*=gain
    fade_in=min(len(audio)//4,round(fade_in_ms*RATE/1000))
    fade_out=min(len(audio)//4,round(fade_out_ms*RATE/1000))
    audio[:fade_in]*=np.linspace(0,1,fade_in)[:,None]
    audio[-fade_out:]*=np.linspace(1,0,fade_out)[:,None]
    return audio,{"dcRemoval":True,"gainCalibrationDb":20*math.log10(gain),
                  "boundaryFadeInMs":fade_in*1000/RATE,"boundaryFadeOutMs":fade_out*1000/RATE,
                  "sourcePeak":source_peak,"peak":float(np.max(np.abs(audio)))}


def offline_shift(audio, semitones, vocal=False):
    if abs(semitones)>3.25:raise ValueError("Variant exceeds 3.25-semitone prototype budget")
    # Padding avoids sacrificing the original crop to the preparation processor's
    # analysis window. This is never imported into prde1/governor.py or the engine.
    padded=np.pad(audio,((RATE//8,RATE//8),(0,0))).astype("<f4")
    recipe=f"rubberband=tempo=1:pitch={2**(semitones/12):.12g}:pitchq=quality:channels=together"
    if vocal:recipe+=":formant=preserved"
    result=subprocess.run(["ffmpeg","-v","error","-f","f32le","-ar",str(RATE),"-ac",str(audio.shape[1]),
                           "-i","-","-af",recipe,"-f","f32le","-"],input=padded.tobytes(),capture_output=True,check=True,timeout=60)
    output=np.frombuffer(result.stdout,dtype="<f4").reshape(-1,audio.shape[1]).copy()
    if len(output)<len(audio)+RATE//8:raise ValueError("Truncated pitch-preparation result")
    return output[RATE//8:RATE//8+len(audio)],recipe


def pitch_check(audio, role, expected):
    mono=resample_poly(audio.mean(axis=1),1,3)
    if len(mono)<(2048 if role=="lead" else 4096):raise ValueError("Crop too short for pitch diagnostics")
    frames,_=pitch_frames(mono,role)
    values=[f["midi"] for f in frames if f and f["error"]<.25]
    if len(values)<3:raise ValueError("No stable prepared fundamental")
    median=float(np.median(values)); cents=(median-expected)*100
    spread=float(np.percentile(values,90)-np.percentile(values,10))*100
    if abs(cents)>45 or spread>70:raise ValueError(f"Pitch diagnostic rejected note {expected}: {cents:.1f} cents; spread {spread:.1f}")
    return {"medianMidi":median,"centsFromTarget":cents,"spreadCents":spread,"voicedFrames":len(values)}


def harmonic_check(audio, spec):
    evidence=chord_spectrum(resample_poly(audio.mean(axis=1),1,3)[720:])
    expected={(spec["chord"]["root"]+interval)%12 for interval in QUALITIES[spec["chord"]["quality"]]}
    chroma=evidence["chroma"]
    if min(chroma[pc] for pc in expected)<.18 or max(chroma[pc] for pc in set(range(12))-expected)>.25 or evidence["residual"]>.8:
        raise ValueError("Whole-chord diagnostic disagrees with saved identity: "+spec["id"])
    evidence["expectedPitchClasses"]=sorted(expected)
    evidence["interpretation"]="Passed bounded spectral screen; voicing/isolation/listening validation remains open"
    return evidence


def degree_chord(root, quality, inversion, tonic, mode):
    pcs=[(tonic+x)%12 for x in MODES[mode]]
    if root not in pcs:raise ValueError("Authored demonstration chord outside declared mode")
    return {"degree":pcs.index(root)+1,"alteration":0,"quality":quality,"inversion":inversion}


def make_project(manifest, manifest_hash, spec, clip, name):
    tonic,mode=spec["tonic"],spec["mode"]
    mappings=manifest["mappings"]
    patterns=[];instances=[];harmony=[]
    for bar,request in enumerate(spec["chords"]):
        root,quality,inversion=request
        tones=[(root+x)%12 for x in QUALITIES[quality]]
        harmony.append({"beat":str(bar*4),"chord":degree_chord(root,quality,inversion,tonic,mode)})
        for role in ("rhythm","bass","lead","drums"):
            if role=="drums":
                part=copy.deepcopy(clip);part["id"]=f"drums_{bar}"
                # These extra accents are newly authored, not misreported as
                # part of the source groove's estimated transcription.
                for slot,position in (("extra1","0"),("extra2","5/2")):
                    definition=manifest["instruments"]["drums"][slot]
                    if definition["status"]=="available" and (bar==0 or name=="b"):
                        accent=event(f"authored_{slot}",position,"1/4","drum",sound=definition["soundIdentity"])
                        accent["expression"]["velocity"]=.48
                        part["events"].append(accent)
                part["provenance"]["changes"]+="; newly authored extra-slot accents are explicitly separate from the source transcription"
            else:
                if role=="rhythm":events=[event(f"strum_{i}",str(Fraction(i,2)),"3/8","chord") for i in range(8)]
                else:
                    available=[i for i,pc in enumerate(tones) if any(m["role"]==role and m["note"]%12==pc for m in mappings)]
                    if not available:raise ValueError("No legal pitched material for demonstration")
                    events=[]
                    for i in range(8 if role=="lead" else 4):
                        tone=available[(i+bar)%len(available)] if role=="lead" else available[0]
                        e=event(f"note_{i}",str(Fraction(i,2) if role=="lead" else Fraction(i)),"3/8" if role=="lead" else "3/4","note",tone=tone,register=65 if role=="lead" else 36)
                        e["expression"]["velocity"]=(.65,.82,.72,.9)[i%4]
                        if name=="b" and i:
                            e["expression"].update(playPercent=90,changePercent=25,variation="nearby_note")
                        events.append(e)
                part={"id":f"{role}_{bar}","role":role,"length":"4","events":events,
                      "provenance":{"sourceClip":"PRDE1 authored demonstration","license":"MIT",
                                    "changes":"New performance using the prepared CC source bank"}}
            patterns.append(part);instances.append({"id":f"{role}_instance_{bar}","patternId":part["id"],"beat":str(bar*4),"linked":False})
    channels={role:channel() for role in ("lead","rhythm","bass","drums",*["drums."+slot for slot in SLOTS])}
    for role,gain in {"lead":-8,"rhythm":-10,"bass":-7,"drums":-8}.items():channels[role]["gainDb"]=gain
    master=channel();master["gainDb"]=0
    return {"formatVersion":VERSION,"projectId":manifest["packId"]+"_"+name,"title":manifest["source"]["title"]+" — new "+mode+" arrangement",
            "packReference":{"packId":manifest["packId"],"manifestSha256":manifest_hash},"musicalRegistryVersion":"core-v1-dev.1",
            "tempoMap":[{"beat":"0","quarterBpm":spec["bpm"]}],
            "meterMap":[{"beat":"0","numerator":4,"denominator":4,"governorSegments":spec.get("segments",4)}],
            "tonalityMap":[{"beat":"0","tonic":tonic,"mode":mode}],"harmony":harmony,"length":"16",
            "patterns":patterns,"instances":instances,"variation":{"seed":manifest["packId"]+"-curated-demo","revision":0},
            "mix":{"channels":channels,"master":master,"compressor":{"on":True,"thresholdDb":-12,"ratio":2,"attackMs":10,"releaseMs":150}},
            "pluginTracks":[],"vocals":[{"id":"vocal_1","visible":True,"takes":[],"selectedTakeId":None,"comp":[],
                "correction":{"on":False,"target":"key-mode"},"channel":channel()}],
            "editorContext":{"selection":"rhythm_0","zoom":1,"scrollBeat":"0","lastAction":"Curated source demonstration created"},
            "credits":[{"source":manifest["source"]["title"],"license":manifest["source"]["license"],
                "attribution":manifest["source"]["attribution"],"changes":"Cropped/cleaned artist stems; listed offline note variants; new arrangement"}]}


def prepare(recipe, source_root, output, work):
    if not shutil.which("ffmpeg"):raise ValueError("Blocked ingest: FFmpeg is required")
    output.mkdir(parents=True,exist_ok=True);work.mkdir(parents=True,exist_ok=True)
    inputs={}
    for key,asset in recipe["inputs"].items():
        relative=Path(asset["path"])
        if relative.is_absolute() or ".." in relative.parts:raise ValueError("Unsafe source path")
        path=source_root/relative
        if not path.is_file() or path.stat().st_size>MAX_SOURCE_BYTES or path.stat().st_size!=asset["bytes"] or sha256(path.read_bytes())!=asset["sha256"]:
            raise ValueError("Blocked ingest: absent/changed authorized source "+key)
        inputs[key]=path
    ffmpeg=subprocess.check_output(["ffmpeg","-version"],text=True).splitlines()[0]
    files={};samples=[];mappings=[];audit=[];native={};decoded={}
    def add(spec,audio,lineage,extra_qa=None):
        role=spec["role"];identity=spec["id"]
        clean_audio,cleanup=clean(audio,peak=spec.get("peak",.42),fade_in_ms=spec.get("fadeInMs",2),fade_out_ms=spec.get("fadeOutMs",8))
        qa={"id":identity,"cleanup":cleanup,"source":spec.get("source"),"decision":spec.get("decision","Saved curated crop and musical estimate")}
        if role in ("lead","bass"):qa["pitch"]=pitch_check(clean_audio,role,spec["pitches"][0])
        if role=="rhythm":qa["harmonicFit"]=harmonic_check(clean_audio,spec)
        if extra_qa:qa.update(extra_qa)
        raw=pcm24(clean_audio);path=f"audio/{role}/{identity}.wav";files[path]=raw
        position=spec.get("source",{}).get("start",0)
        sample={"id":identity,"role":role,"articulation":spec.get("articulation","whole-chord" if role=="rhythm" else "single"),
            "path":path,"sha256":sha256(raw),"sampleRate":RATE,"bitsPerSample":24,"channels":clean_audio.shape[1],
            "frames":len(clean_audio),"onsetFrame":min(spec.get("onsetFrame",96),len(clean_audio)-1),"gainDb":0,
            "pitches":spec["pitches"],"chord":spec.get("chord"),"loop":None,
            "source":{"seconds":position,"quarterBeat":str(Fraction(position*recipe["bpm"]/60).limit_denominator(960)),"durationSeconds":len(clean_audio)/RATE},
            "lineage":lineage,"quality":{"accepted":True,"confidence":spec.get("confidence",.75),
                "notes":"Accepted for automated prototype profile; source pitch/identity estimates and residual bleed require listening review. No sustain loop."}}
        samples.append(sample);audit.append(qa)
        if role in ("lead","bass"):
            mappings.append({"role":role,"note":spec["pitches"][0],"root":None,"quality":None,"inversion":0,"sampleId":identity})
        elif role=="rhythm":
            mappings.append({"role":role,"note":None,**spec["chord"],"sampleId":identity})
        return clean_audio
    for spec in recipe["crops"]:
        source=spec["source"];key=source["input"]
        if key not in decoded:decoded[key]=decode(inputs[key],rate=RATE,channels=2)
        start,end=round(source["start"]*RATE),round(source["end"]*RATE)
        if not 0<=start<end<=len(decoded[key]) or end-start>30*RATE:raise ValueError("Crop outside source")
        audio=decoded[key][start:end].copy()
        raw=audio.astype("<f4").tobytes()
        (work/(spec["id"]+"_unmodified.f32")).write_bytes(raw)
        lineage={"kind":"native","sourceAsset":key+":"+recipe["inputs"][key]["sha256"],
                 "recipe":"Source crop; DC removal, bounded gain calibration and boundary fades. "+spec.get("decision",""),"transformationCost":0}
        if spec.get("filter"):
            # Explicit preparation-only separation of a source cymbal from its
            # overlapping low drum; never a runtime EQ or new sound generator.
            if spec["filter"]!="highpass=frequency=1800":raise ValueError("Unknown cleanup filter")
            result=subprocess.run(["ffmpeg","-v","error","-f","f32le","-ar",str(RATE),"-ac","2","-i","-",
                                   "-af",spec["filter"],"-f","f32le","-"],input=audio.astype("<f4").tobytes(),capture_output=True,check=True,timeout=60)
            audio=np.frombuffer(result.stdout,dtype="<f4").reshape(-1,2).copy()
            lineage.update(kind="pre-rendered",transformationCost=.25,recipe=lineage["recipe"]+"; "+spec["filter"])
        native[spec["id"]]=(spec,add(spec,audio,lineage,{"unmodifiedCropSha256":sha256(raw)}))
    for variant in recipe["variants"]:
        base,audio=native[variant["base"]]
        spec=copy.deepcopy(base);spec["id"]=variant["id"];spec["pitches"]=[variant["note"]]
        cents=next(q["pitch"]["centsFromTarget"] for q in audit if q["id"]==base["id"])
        semitones=variant["note"]-base["pitches"][0]-cents/100
        audio,processor=offline_shift(audio,semitones,vocal=recipe.get("vocalLead",False) and spec["role"]=="lead")
        add(spec,audio,{"kind":"pre-rendered","sourceAsset":base["id"],"recipe":processor+f"; shift {semitones:.6f} semitones; original duration retained",
                       "transformationCost":round(abs(semitones),6)}, {"variantOf":base["id"],"semitones":semitones})
    def record(sample_id,label,sound,slot=None,address=None):
        sample=next(s for s in samples if s["id"]==sample_id)
        return {"status":"available","reason":"","sampleId":sample_id,"displayName":label,"soundIdentity":sound,
                "midiAddress":address,"pitchClass":"unpitched" if slot else "pitched","pitches":sample["pitches"]}
    instruments={role:record(next(s["id"] for s in samples if s["role"]==role),recipe["roleLabels"][role],recipe["packId"]+"_"+role) for role in ("lead","rhythm","bass")}
    drums={}
    for slot in SLOTS:
        definition=recipe["drums"][slot]
        if definition.get("sampleId"):
            drums[slot]=record(definition["sampleId"],definition["label"],definition["soundIdentity"],slot,definition["midiAddress"])
        else:
            drums[slot]={"status":"empty" if slot.startswith("extra") else "unavailable","reason":definition["reason"],
                         "sampleId":None,"displayName":"Unassigned" if slot.startswith("extra") else "Unavailable",
                         "soundIdentity":"","midiAddress":None,"pitchClass":"unpitched","pitches":[]}
    instruments["drums"]=drums
    clip=recipe["clip"]
    files["clips/normalized/source_groove.json"]=canonical_bytes(clip)
    addresses={v["soundIdentity"]:v["midiAddress"] for v in drums.values() if v["status"]=="available"}
    files["clips/source-midi/source_groove.mid"]=midi_drums(clip,addresses,recipe["bpm"])
    files["clips/index.json"]=canonical_bytes([{"id":clip["id"],"role":"drums","origin":"audio-derived estimated transcription, saved curated assignments",
        "license":recipe["license"],"attribution":recipe["attribution"],"sourceHash":recipe["inputs"]["drums"]["sha256"],
        "normalizedPath":"clips/normalized/source_groove.json","midiPath":"clips/source-midi/source_groove.mid"}])
    files["analysis/harmony.json"]=canonical_bytes(recipe["analysis"])
    files["analysis/coverage.json"]=canonical_bytes({"profile":PROFILE,"notes":{role:sorted(m["note"] for m in mappings if m["role"]==role) for role in ("lead","bass")},
        "chords":[{k:m[k] for k in ("root","quality","inversion")} for m in mappings if m["role"]=="rhythm"],
        "unavailableSlots":{slot:v["reason"] for slot,v in drums.items() if v["status"]=="unavailable"},
        "fullTonalMapVerified":False,"humanListening":"not_performed","sustainLoops":0})
    files["presets/mix.json"]=canonical_bytes({"preset":"dry prototype","masterReverbOn":False,"masterDelayOn":False})
    files["provenance.json"]=canonical_bytes({"sourcePage":recipe["sourcePage"],"license":recipe["license"],"licenseUrl":recipe["licenseUrl"],
        "attribution":recipe["attribution"],"ingredients":recipe["inputs"],"licenseEvidence":recipe["licenseEvidence"],
        "separation":"Artist-provided stems from this song, plus the credited upstream vocal in Where You Are Now; no learned separation model",
        "recipeSha256":sha256(canonical_bytes(recipe)),"ffmpeg":ffmpeg,"numpy":np.__version__,
        "scipy":__import__('scipy').__version__,"corrections":"Saved crop, note/chord and drum identity selections in recipes/cc-songs.json",
        "sourceTimeConvention":"Per-ingredient decoded seconds. Stem-to-master offsets/rearrangements are not claimed to be verified.",
        "changes":"Crops, DC removal, boundary fades, bounded gain calibration; individually documented preparation-only filters/pitch variants"})
    files["qa/report.json"]=canonical_bytes({"profile":PROFILE,"structuralValidation":"actual PRDE1 loader", "assets":audit,
        "humanListening":"not_performed","isolation":"Artist stems; possible baked effects/residual percussion bleed; provisional percussion labels",
        "releaseQualityGate":"open","loops":"None; natural sample limits are reported during playback", "syntheticAssets":0})
    preview=next(s for s in samples if s["role"]=="rhythm");files["preview/audition.wav"]=files[preview["path"]]
    files["ATTRIBUTION.json"]=canonical_bytes({"attribution":recipe["attribution"],
        "licenseUrl":recipe["licenseUrl"],"sourcePage":recipe["sourcePage"],
        "changes":"Cropped/cleaned source stems; listed pre-rendered note variants; estimated drum MIDI.",
        "endorsement":"No artist endorsement implied."})
    manifest={"schemaVersion":VERSION,"packId":recipe["packId"],"builder":{"version":"curated-stem-preparation-0.2.0","profileVersion":PROFILE,"modelVersion":"none — artist stems"},
        "source":{"title":recipe["title"],"sha256":recipe["inputs"]["mix"]["sha256"],"kind":"authorized_recording",
                  "rightsDeclaration":"Selected under user's authorization; primary artist source pages list CC BY 3.0. Credits/license and modifications retained.",
                  "license":recipe["license"],"attribution":recipe["attribution"]},
        "audio":{"sampleRate":RATE,"bitsPerSample":24,"tuningHz":440,"tuning":"12-TET"},
        "maps":{"harmony":"analysis/harmony.json","coverage":"analysis/coverage.json"},"instruments":instruments,"samples":samples,"mappings":mappings,
        "files":{path:sha256(data) for path,data in files.items()},"clips":{"index":"clips/index.json","libraryVersion":"curated-source-grooves-0.2.0"},
        "channelPresets":"presets/mix.json","provenance":"provenance.json","qa":"qa/report.json","preview":"preview/audition.wav",
        "validation":{"status":"coverage-limited","notes":"Useful pitched bank and two playable demo arrangements; unverified kit slots explicitly unavailable; listening/full source-analysis gate open"}}
    raw_manifest=canonical_bytes(manifest);files["manifest.json"]=raw_manifest
    pack_path=output/(recipe["packId"]+".prdepack")
    temporary=pack_path.with_suffix(".partial")
    with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(files):
            entry=zipfile.ZipInfo(path,(2026,10,9,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16
            archive.writestr(entry,files[path])
    with Pack(temporary):pass
    projects=[]
    for index,spec in enumerate(recipe["demonstrations"]):
        project=make_project(manifest,sha256(raw_manifest),spec,clip,"ab"[index])
        validate_project(project)
        projects.append((output/(recipe["packId"]+"_"+"ab"[index]+".prdeproj"),project))
    temporary.replace(pack_path)
    for project_path,project in projects:save_project(project_path,project)
    (work/"asset-audit.json").write_bytes(canonical_bytes(audit))
    print(pack_path,len(samples),"source-derived assets; coverage-limited",flush=True)
    return pack_path


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources",type=Path,required=True);parser.add_argument("--output",type=Path,default=ROOT/"packs")
    parser.add_argument("--work",type=Path,default=ROOT/"out"/"source-preparation")
    parser.add_argument("--only",choices=["reach_out","where_you_are_now","auld_lang_syne_bossa"])
    args=parser.parse_args();recipes=json.loads((ROOT/"recipes"/"cc-songs.json").read_text())
    for recipe in recipes:
        if not args.only or recipe["packId"]==args.only:prepare(recipe,args.sources,args.output,args.work/recipe["packId"])
