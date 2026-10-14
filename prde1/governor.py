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
from .music import REGISTERS, QUALITIES, at, beat, chord_identity, quarter_seconds
from .project import arrangement_occurrences, validate_project
from .percussion import records as drum_records, sample as drum_sample

DECLICK_FRAMES=240
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
        low,high=REGISTERS[role]
        if not low<=note<=high:
            return None,"register_conflict","Locked pitch is outside the instrument register"
        sample=pack.sample_for((role,note))
        return sample,None,None
    tone=choice["tone"]
    tone%=len(chord_pitches)
    permitted=set(chord_pitches) if variation else {chord_pitches[tone]}
    low,high=REGISTERS[role]
    candidates=[note for note in range(low,high+1) if note%12 in permitted]
    candidates.sort(key=lambda note:(abs(note-choice["registerMidi"]),pack.coverage.cost((role,note)),note))
    return pack.sample_for((role,candidates[0])),None,None


def vst_chord_notes(root, quality, inversion=0, base=60):
    """Event adapter only; not a plug-in host. One chord becomes constituent MIDI."""
    from .coverage import chord_notes
    return [note+base-48 for note in chord_notes(root,quality,inversion)]


def _supported_mix(project):
    from .mixing import validate_supported_channel
    channels=[*project["mix"]["channels"].items(),('master',project["mix"]["master"]),
              *[(lane['id'],lane["channel"]) for lane in project["vocals"]],
              *[(track['id'],track["channel"]) for track in project["pluginTracks"]]]
    for name,channel in channels:
        validate_supported_channel(name,channel)
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
    from .mixing import processing_settings
    processing=processing_settings(project)
    if project["pluginTracks"] and not approve_altered:
        raise ContractError("VST host is not implemented. Plug-in tracks would be silent; an altered render requires explicit approval")
    end=beat(project["length"])
    frame=lambda position:round(quarter_seconds(position,project["tempoMap"])*RATE)
    end_frame=frame(end)
    if not 1<=end_frame<=86400000:
        raise ContractError("Render duration exceeds 30-minute profile")
    resolved=[]
    conflicts=[]
    warnings=[]
    reconstructed=set()
    if project["pluginTracks"]:
        warnings.append("Explicitly approved altered render: additional VST instruments are silent in this core checkpoint")
    boundary_beats=sorted({beat(item["beat"]) for name in ("harmony","tonalityMap") for item in project[name]})
    from .sequencer import effective_events
    for instance,pattern,cycle_end in arrangement_occurrences(project):
        role=pattern["role"]
        for authored in (trigger for source in pattern['events'] for trigger in effective_events(project,pack,instance,pattern,source)):
            if not authored["enabled"]:
                continue
            expression=authored["expression"]
            address=instance["id"]+":"+authored["id"]+(':flam' if authored.get('_subtrigger') else '')
            chance_id=authored.get('_chanceId',authored['id'])
            if _random(project,instance["id"],chance_id,"play")*100>=expression["playPercent"]:
                continue
            changed=(not expression["locked"] and _random(project,instance["id"],chance_id,"change")*100<expression["changePercent"])
            position=beat(instance["beat"])+beat(authored["beat"])
            duration=beat(authored["duration"])
            repeats=2 if changed and expression["variation"]=="double" else 1
            duration/=repeats
            if changed and expression["variation"]=="gate":
                duration/=2
            for repeat in range(repeats):
                trigger=position+repeat*beat(authored["duration"])/repeats
                if trigger>=cycle_end:
                    continue
                event_id=address+":"+str(repeat)
                chord,root,pitches,legal=context(project,trigger)
                sample=None
                issue=None
                message=None
                slot=None
                drum_address=None
                if role=="drums":
                    sound=authored["choice"]["soundIdentity"]
                    candidates=[(key,item) for key,item in drum_records(pack).items()
                                if item["status"]=="available" and item["soundIdentity"]==sound]
                    if not candidates:
                        issue,message="missing_drum",f"No prepared drum with sound identity {sound!r}; no slot-based substitution"
                    else:
                        sound_slot,record=candidates[0]
                        slot=record.get('mixSlot',sound_slot)
                        drum_address=record['midiAddress']
                        if record["pitchClass"]=="uncertain":
                            issue,message="uncertain_pitch","Pitched-extra classification requires review"
                        elif record["pitchClass"]=="pitched" and not {note%12 for note in record["pitches"]}.issubset(pitches):
                            issue,message="pitched_extra_conflict","Placed pitched hit conflicts with harmony; retained and withheld"
                        else:
                            sample=drum_sample(pack,sound_slot)
                elif role=="rhythm":
                    sample=pack.sample_for((role,root,chord["quality"],chord["inversion"]))
                else:
                    sample,issue,message=_choose(pack,role,authored["choice"],pitches,expression["lockExactPitch"])
                    if sample and changed and expression["variation"]=="nearby_note" and not expression["lockExactPitch"]:
                        low,high=REGISTERS[role]
                        alternatives=[note for note in range(low,high+1) if note%12 in pitches and note!=sample['pitches'][0]]
                        alternatives.sort(key=lambda note:(abs(note-sample['pitches'][0]),note))
                        if alternatives:
                            sample=pack.sample_for((role,alternatives[0]))
                if issue:
                    conflicts.append({"eventId":event_id,"code":issue,"message":message})
                    continue
                stop=min(cycle_end,trigger+duration)
                reason="loop_boundary" if cycle_end<end and trigger+duration>cycle_end else "gate"
                actual_pitches=sample["pitches"]
                if actual_pitches:
                    for boundary in boundary_beats:
                        if trigger<boundary<stop:
                            _,_,following,following_legal=context(project,boundary)
                            if not {note%12 for note in actual_pitches}.issubset(following):
                                stop=boundary
                                reason="harmonic_boundary"
                                break
                first,last=frame(trigger),frame(stop)
                if role!='drums' and not sample['loop'] and last>first+sample['frames']-sample['onsetFrame']:
                    sample=pack.coverage.sustain(sample)
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
                from .pulse import playback_velocity
                velocity=playback_velocity(project,trigger,expression["velocity"],grace=bool(authored.get('_subtrigger')))
                gain=velocity*10**((channel["gainDb"]+sample["gainDb"]+(group["gainDb"] if group and processing is None else 0))/20)
                pan=max(-1,min(1,channel["pan"]+(group["pan"] if group and processing is None else 0)))
                if gain>8:
                    raise ContractError("Combined channel/sample gain exceeds core headroom profile")
                if sample['id'].startswith('hybrid_'):reconstructed.add(sample['id'])
                resolved.append({"id":event_id,"sampleId":sample['id'],"startFrame":first,"endFrame":last,
                                 "polyphonic":pattern.get('sequencer',{}).get('entryMode')=='poly' and role in REGISTERS,
                                 "releaseFrames":min(DECLICK_FRAMES,last-first),"attackFrames":round(expression["attackMs"]*RATE/1000),
                                 "gain":gain,"pan":pan,"notePitches":actual_pitches,"role":role if role!="drums" else "drums."+slot,
                                 "noteVelocity":velocity,
                                 "endReason":reason})
                if drum_address is not None:resolved[-1]['drumMidiAddress']=drum_address
    resolved.sort(key=lambda event:(event["startFrame"],event["id"]))
    # Fixed monophonic lanes and explicit open/closed-hat choke group. No invented attacks.
    for index,event in enumerate(resolved):
        role=event["role"]
        group=role if role in ("lead","bass","rhythm") and not event['polyphonic'] else ("hats" if role in ("drums.hatClosed","drums.hatOpen") else None)
        if group:
            for following in resolved[index+1:]:
                if following["startFrame"]>=event["endFrame"]:
                    break
                next_group=following["role"] if following["role"] in ("lead","bass","rhythm") and not following['polyphonic'] else ("hats" if following["role"] in ("drums.hatClosed","drums.hatOpen") else None)
                if next_group==group:
                    event["endFrame"]=following["startFrame"]
                    event["releaseFrames"]=min(DECLICK_FRAMES,event["endFrame"]-event["startFrame"])
                    event["endReason"]="monophonic_retrigger" if group!="hats" else "hat_choke"
                    break
    # Same-position duplicates are preserved in authorship but only the deterministic last voice is active.
    resolved=[event for event in resolved if event["endFrame"]>event["startFrame"]]
    used={event['sampleId'] for event in resolved}
    assets=sorted((pack.samples[identity] for identity in used),key=lambda sample:sample['id'])
    indices={sample['id']:index for index,sample in enumerate(assets)}
    for event in resolved:event['assetIndex']=indices[event.pop('sampleId')];event.pop('polyphonic')
    if reconstructed:warnings.append(f"Sample bank: {len(reconstructed)} source-derived warped assets used; transformed PCM, not native source recordings")
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
    if processing is not None:plan['processing']=processing
    validate(plan,"prde1-events-v1.schema.json")
    return plan


def rank_progressions(pack,tonic,mode):
    """The same full bank used by the desktop; ranking never prepares audio."""
    from .progression_bank import ranked
    return ranked(pack,tonic,mode)

