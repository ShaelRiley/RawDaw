"""Selection-only Governor. Inputs/outputs are metadata, never PCM buffers.

Probability outcomes are addressed by saved instance and event identity, not by
mutable playback RNG. Auditions and seek do not consume state. All adaptations
resolve at their actual trigger position; authored data is never overwritten.
"""
from __future__ import annotations

import hashlib
import math
from fractions import Fraction

from .contracts import ContractError, RATE, VERSION, validate
from .music import REGISTERS, QUALITIES, at, beat, chord_identity, diatonic, quarter_seconds, roman
from .project import validate_project

DECLICK_FRAMES=240
PRESETS=(
    ("pop_axis",(1,5,6,4)), ("pop_classic",(1,6,4,5)), ("minor_loop",(1,6,3,7)),
    ("home_return",(1,5,1,1)), ("modal_shuttle",(1,4,1,4)), ("long_cadence",(1,5,1,3,2,4,1,1)),
)


def context(project, position):
    tonality=at(project["tonalityMap"],position)
    chord=at(project["harmony"],position)["chord"]
    root,pitches,permitted=chord_identity(tonality["tonic"],tonality["mode"],chord)
    return chord,root,pitches,permitted


def _random(project, instance_id, event_id, purpose):
    data="|".join((project["variation"]["seed"],str(project["variation"]["revision"]),instance_id,event_id,purpose)).encode()
    return int.from_bytes(hashlib.sha256(data).digest()[:8],"big")/2**64


def _choose(pack,role,choice,chord_pitches,exact=False,variation=False):
    if exact:
        note=choice["exactMidi"]
        if note%12 not in chord_pitches:
            return None,"exact_pitch_conflict","Locked exact pitch is incompatible with the governing chord"
        sample=pack.mappings.get((role,note))
        if not sample:
            return None,"missing_sample",f"No prepared {role} note {note}"
        return sample,None,None
    tone=choice["tone"]
    if tone>=len(chord_pitches):
        return None,"tone_unavailable","Requested chord tone does not exist in this chord"
    permitted=set(chord_pitches) if variation else {chord_pitches[tone]}
    low,high=REGISTERS[role]
    candidates=[sample for key,sample in pack.mappings.items()
                if key[0]==role and low<=key[1]<=high and key[1]%12 in permitted]
    if not candidates:
        return None,"missing_sample",f"No prepared {role} asset for requested chord tone"
    candidates.sort(key=lambda sample:(abs(sample["pitches"][0]-choice["registerMidi"]),
                                     sample["lineage"]["transformationCost"],sample["pitches"][0],sample["id"]))
    return candidates[0],None,None


def vst_chord_notes(root, quality, inversion=0, base=60):
    """Event adapter only; not a plug-in host. One chord becomes constituent MIDI."""
    values=[base+root+interval for interval in QUALITIES[quality]]
    for index in range(inversion):
        values[index]+=12
    return sorted(values)


def _supported_mix(project):
    channels=[*project["mix"]["channels"].values(),project["mix"]["master"],
              *[lane["channel"] for lane in project["vocals"]],*[track["channel"] for track in project["pluginTracks"]]]
    for channel in channels:
        if channel["eqPreset"]!="neutral" or channel["reverbOn"] or channel["delayOn"]:
            raise ContractError("This core checkpoint cannot render EQ/reverb/delay; settings are preserved, not silently dropped")
        if any(not insert["bypassed"] for insert in channel["inserts"]):
            raise ContractError("Active VST effect insert cannot be rendered by this checkpoint; explicitly bypass it or use a future host")
    master=project["mix"]["master"]
    if master["pan"]!=0:
        raise ContractError("Master pan is not supported by this checkpoint")
    if any(lane["takes"] or lane["comp"] or lane["correction"]["on"] for lane in project["vocals"]):
        raise ContractError("Vocal media/correction is preserved by the contract but its renderer is not implemented yet")


def resolve(project, pack, *, approve_altered=False):
    validate_project(project)
    reference=project["packReference"]
    if reference!={"packId":pack.manifest["packId"],"manifestSha256":pack.manifest_hash}:
        raise ContractError("Exact pack identity/version does not match saved project")
    _supported_mix(project)
    if project["pluginTracks"] and not approve_altered:
        raise ContractError("VST host is not implemented. Plug-in tracks would be silent; an altered render requires explicit approval")
    end=beat(project["length"])
    frame=lambda position:round(quarter_seconds(position,project["tempoMap"])*RATE)
    end_frame=frame(end)
    if not 1<=end_frame<=86400000:
        raise ContractError("Render duration exceeds 30-minute profile")
    assets=sorted(pack.samples.values(),key=lambda sample:sample["id"])
    indices={sample["id"]:index for index,sample in enumerate(assets)}
    resolved=[]
    conflicts=[]
    warnings=list(pack.warnings)
    if project["pluginTracks"]:
        warnings.append("Explicitly approved altered render: additional VST instruments are silent in this core checkpoint")
    boundary_beats=sorted({beat(item["beat"]) for name in ("harmony","tonalityMap") for item in project[name]})
    patterns={pattern["id"]:pattern for pattern in project["patterns"]}
    for instance in project["instances"]:
        pattern=patterns[instance["patternId"]]
        role=pattern["role"]
        for authored in pattern["events"]:
            if not authored["enabled"]:
                continue
            expression=authored["expression"]
            address=instance["id"]+":"+authored["id"]
            if _random(project,instance["id"],authored["id"],"play")*100>=expression["playPercent"]:
                continue
            changed=(not expression["locked"] and _random(project,instance["id"],authored["id"],"change")*100<expression["changePercent"])
            position=beat(instance["beat"])+beat(authored["beat"])
            duration=beat(authored["duration"])
            repeats=2 if changed and expression["variation"]=="double" else 1
            duration/=repeats
            if changed and expression["variation"]=="gate":
                duration/=2
            for repeat in range(repeats):
                trigger=position+repeat*beat(authored["duration"])/repeats
                if trigger>=end:
                    continue
                event_id=address+":"+str(repeat)
                chord,root,pitches,legal=context(project,trigger)
                sample=None
                issue=None
                message=None
                slot=None
                if role=="drums":
                    sound=authored["choice"]["soundIdentity"]
                    candidates=[(key,item) for key,item in pack.manifest["instruments"]["drums"].items()
                                if item["status"]=="available" and item["soundIdentity"]==sound]
                    if not candidates:
                        issue,message="missing_drum",f"No prepared drum with sound identity {sound!r}; no slot-based substitution"
                    else:
                        slot,record=candidates[0]
                        if record["pitchClass"]=="uncertain":
                            issue,message="uncertain_pitch","Pitched-extra classification requires review"
                        elif record["pitchClass"]=="pitched" and (not legal or not {note%12 for note in record["pitches"]}.issubset(pitches)):
                            issue,message="pitched_extra_conflict","Placed pitched hit conflicts with harmony; retained and withheld"
                        else:
                            sample=pack.samples[record["sampleId"]]
                elif pack.manifest["instruments"][role]["status"]!="available":
                    issue,message="missing_role",f"{role} unavailable: {pack.manifest['instruments'][role]['reason']}"
                elif not legal:
                    issue,message="harmony_conflict",f"Exact authored {roman(chord)} is outside the declared mode; preserved without reinterpretation"
                elif role=="rhythm":
                    sample=pack.mappings.get((role,root,chord["quality"],chord["inversion"]))
                    if not sample:
                        issue,message="missing_chord",f"No prepared whole chord for {roman(chord)} (root {root}, {chord['quality']})"
                else:
                    sample,issue,message=_choose(pack,role,authored["choice"],pitches,expression["lockExactPitch"])
                    if sample and changed and expression["variation"]=="nearby_note" and not expression["lockExactPitch"]:
                        # Try a covered neighbor; unavailable substitutions retain the legal authored choice.
                        alternatives=[asset for key,asset in pack.mappings.items() if key[0]==role
                                      and key[1]%12 in pitches and asset["id"]!=sample["id"]]
                        alternatives.sort(key=lambda asset:(abs(asset["pitches"][0]-sample["pitches"][0]),asset["id"]))
                        if alternatives:
                            sample=alternatives[0]
                if issue:
                    conflicts.append({"eventId":event_id,"code":issue,"message":message})
                    continue
                stop=min(end,trigger+duration)
                reason="gate"
                actual_pitches=sample["pitches"]
                if actual_pitches:
                    for boundary in boundary_beats:
                        if trigger<boundary<stop:
                            _,_,following,following_legal=context(project,boundary)
                            if not following_legal or not {note%12 for note in actual_pitches}.issubset(following):
                                stop=boundary
                                reason="harmonic_boundary"
                                break
                first,last=frame(trigger),frame(stop)
                if not sample["loop"] and last>first+sample["frames"]-sample["onsetFrame"]:
                    last=first+sample["frames"]-sample["onsetFrame"]
                    reason="natural_limit"
                    warnings.append(f"{event_id}: gate exceeds prepared sample duration; natural limit used")
                if last<=first:
                    continue
                channel=project["mix"]["channels"][role if role!="drums" else "drums."+slot]
                group=project["mix"]["channels"]["drums"] if role=="drums" else None
                if channel["muted"] or (group and group["muted"]) or project["mix"]["master"]["muted"]:
                    continue
                gain=expression["velocity"]*10**((channel["gainDb"]+sample["gainDb"]+(group["gainDb"] if group else 0))/20)
                pan=max(-1,min(1,channel["pan"]+(group["pan"] if group else 0)))
                if gain>8:
                    raise ContractError("Combined channel/sample gain exceeds core headroom profile")
                resolved.append({"id":event_id,"assetIndex":indices[sample["id"]],"startFrame":first,"endFrame":last,
                                 "releaseFrames":min(DECLICK_FRAMES,last-first),"attackFrames":round(expression["attackMs"]*RATE/1000),
                                 "gain":gain,"pan":pan,"notePitches":actual_pitches,"role":role if role!="drums" else "drums."+slot,
                                 "endReason":reason})
    resolved.sort(key=lambda event:(event["startFrame"],event["id"]))
    # Fixed monophonic lanes and explicit open/closed-hat choke group. No invented attacks.
    for index,event in enumerate(resolved):
        role=event["role"]
        group=role if role in ("lead","bass","rhythm") else ("hats" if role in ("drums.hatClosed","drums.hatOpen") else None)
        if group:
            for following in resolved[index+1:]:
                if following["startFrame"]>=event["endFrame"]:
                    break
                next_group=following["role"] if following["role"] in ("lead","bass","rhythm") else ("hats" if following["role"] in ("drums.hatClosed","drums.hatOpen") else None)
                if next_group==group:
                    event["endFrame"]=following["startFrame"]
                    event["releaseFrames"]=min(DECLICK_FRAMES,event["endFrame"]-event["startFrame"])
                    event["endReason"]="monophonic_retrigger" if group!="hats" else "hat_choke"
                    break
    # Same-position duplicates are preserved in authorship but only the deterministic last voice is active.
    resolved=[event for event in resolved if event["endFrame"]>event["startFrame"]]
    endpoints=sorted([(event["startFrame"],1) for event in resolved]+[(event["endFrame"],-1) for event in resolved])
    voices=peak=0
    for _,delta in endpoints:
        voices+=delta
        peak=max(peak,voices)
    if peak>64:
        raise ContractError("Arrangement exceeds 64-voice budget; no silent voice stealing")
    plan={"formatVersion":VERSION,"sampleRate":RATE,"endFrame":end_frame,
          "assets":[{"id":sample["id"],"path":sample["path"],"channels":sample["channels"],"frames":sample["frames"],
                     "onsetFrame":sample["onsetFrame"],"loopStart":sample["loop"]["startFrame"] if sample["loop"] else 0,
                     "loopEnd":sample["loop"]["endFrame"] if sample["loop"] else 0} for sample in assets],
          "events":resolved,"conflicts":conflicts,"warnings":sorted(set(warnings)),
          "compressor":project["mix"]["compressor"],"masterGain":10**(project["mix"]["master"]["gainDb"]/20),"peakCeilingDb":-0.1}
    validate(plan,"prde1-events-v1.schema.json")
    return plan


def rank_progressions(pack,tonic,mode):
    """Initial coverage ranking; no claim that these six fixtures form a large catalog."""
    result=[]
    for name,degrees in PRESETS:
        missing=[role+":unavailable" for role in ("lead","rhythm","bass") if pack.manifest["instruments"][role]["status"]!="available"]
        costs=[]
        for degree in degrees:
            chord=diatonic(tonic,mode,degree)
            root,pitches,legal=chord_identity(tonic,mode,chord)
            sample=pack.mappings.get(("rhythm",root,chord["quality"],0))
            if not sample or not legal:
                missing.append("rhythm:"+roman(chord))
            else:
                costs.append(sample["lineage"]["transformationCost"])
            for role in ("lead","bass"):
                for pitch in pitches:
                    candidates=[sample for key,sample in pack.mappings.items() if key[0]==role and key[1]%12==pitch]
                    if not candidates:
                        missing.append(role+":"+str(pitch))
                    else:
                        costs.append(min(sample["lineage"]["transformationCost"] for sample in candidates))
        result.append({"id":name,"degrees":list(degrees),"display":[roman(diatonic(tonic,mode,degree)) for degree in degrees],
                       "playable":not missing,"missing":missing,"worstPreparationCost":max(costs,default=0),
                       "averagePreparationCost":sum(costs)/max(1,len(costs)),
                       "explanation":"All required prepared targets covered" if not missing else "Explicit prepared-sample gaps"})
    return sorted(result,key=lambda item:(len(item["missing"]),item["worstPreparationCost"],item["averagePreparationCost"],item["id"]))
