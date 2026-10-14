"""Full session envelope, transactional manifests, and explicit copy semantics."""
from __future__ import annotations

import copy
import math
import uuid
from fractions import Fraction
from pathlib import Path

from .contracts import ContractError, ROLES, SLOTS, atomic_json, read_json, validate
from .music import MODES, QUALITIES, beat


def instance_length(instance: dict, pattern: dict) -> Fraction:
    """Arrangement span; the editable source pattern keeps its original cycle."""
    return beat(instance.get('playbackLength', pattern['length']))


def check_arrangement_space(project, role, start, length, exclude=''):
    """Protect occupied material, including trimmed/repeated clip spans."""
    start=beat(str(start));length=beat(str(length));stop=start+length
    if length<=0 or stop>beat(project['length']):
        raise ContractError('Clip must fit inside the song')
    cycle=project.get('trackLoops',{}).get(role)
    if cycle and not beat(cycle['startBeat'])<=start<stop<=beat(cycle['endBeat']):
        raise ContractError('Clip must fit the track loop source cycle; turn track looping off to extend the arrangement')
    patterns={p['id']:p for p in project['patterns']}
    for occurrence in project['instances']:
        if occurrence['id']==exclude:continue
        pattern=patterns[occurrence['patternId']];other=beat(occurrence['beat'])
        if pattern['role']==role and max(start,other)<min(stop,other+instance_length(occurrence,pattern)):
            raise ContractError('Clip would overlap existing material on this track')


def arrangement_spans(project):
    """Saved clips and track-loop ghosts as (source, pattern, start, span, cycle)."""
    patterns={p['id']:p for p in project['patterns']};song_end=beat(project['length'])
    for source in project['instances']:
        pattern=patterns[source['patternId']]
        start=beat(source['beat']);length=instance_length(source,pattern)
        track=project.get('trackLoops',{}).get(pattern['role'])
        period=beat(track['endBeat'])-beat(track['startBeat']) if track else None
        cycle=0
        while start<song_end:
            yield source,pattern,start,min(length,song_end-start),cycle
            if period is None:break
            start+=period;cycle+=1


def arrangement_occurrences(project):
    """Expand musical loops without saving duplicate patterns or consuming RNG.

    IDs at the first placement remain unchanged. Later cycle addresses depend
    only on saved identity and repeat number, so extending a loop retains the
    realization of every preceding repeat. The caller validates the project
    first; the project budget bounds this iterator to 100,000 source cycles.
    """
    song_end=beat(project['length'])
    for source,pattern,start,length,track_repeat in arrangement_spans(project):
        period=beat(pattern['length']);clip_end=start+length
        track=project.get('trackLoops',{}).get(pattern['role'])
        offset=Fraction(0);clip_repeat=0
        while start+offset<clip_end:
            occurrence=dict(source,beat=str(start+offset))
            suffix=(f':track_{track_repeat}' if track_repeat else '')+(f':loop_{clip_repeat}' if clip_repeat else '')
            occurrence['id']=source['id']+suffix
            # A clip loop bounds each pattern cycle. A whole-track loop bounds
            # the track cycle, preserving authored holds across shorter source
            # clip ends. Legacy one-shots preserve their existing gates.
            if 'playbackLength' in source:
                limit=min(clip_end,start+offset+period)
            elif track:
                track_period=beat(track['endBeat'])-beat(track['startBeat'])
                limit=min(song_end,beat(track['endBeat'])+track_repeat*track_period)
            else:limit=song_end
            yield occurrence,pattern,limit
            offset+=period;clip_repeat+=1


def validate_project(project: dict) -> None:
    validate(project, "prde1-project-v1.schema.json")
    end = beat(project["length"])
    initial_phase=beat(project.get('rhythmicPulse',{}).get('phaseBeat','0'))
    first_meter=project['meterMap'][0]
    if initial_phase>=Fraction(4*first_meter['numerator'],first_meter['denominator']):
        raise ContractError('Pulse audition phase must fit the first measure')
    if not end:
        raise ContractError("Empty song length")
    for name in ("tempoMap", "meterMap", "tonalityMap", "harmony"):
        positions = [beat(entry["beat"]) for entry in project[name]]
        if positions[0] != 0 or any(right<=left for left,right in zip(positions,positions[1:])) or positions[-1] >= end:
            raise ContractError(f"{name} must start at zero and have distinct sorted positions inside song")
    for entry in project["tonalityMap"]:
        if entry["mode"] not in MODES:
            raise ContractError("Unsupported mode registry version/entry")
    for entry in project["harmony"]:
        chord=entry["chord"]
        if chord["inversion"]>=len(QUALITIES[chord["quality"]]):
            raise ContractError("Impossible chord inversion")
    for previous, current in zip(project["meterMap"],project["meterMap"][1:]):
        offset=initial_phase if beat(previous['beat'])==0 else Fraction(0)
        if (beat(current["beat"])-beat(previous["beat"])+offset)/Fraction(4*previous["numerator"],previous["denominator"]) % 1:
            raise ContractError("Meter changes must align to a preceding bar boundary")
    patterns={}
    for pattern in project["patterns"]:
        from .sequencer import validate_pattern
        validate_pattern(pattern)
        if pattern["id"] in patterns or not beat(pattern["length"]):
            raise ContractError("Duplicate or empty pattern")
        patterns[pattern["id"]]=pattern
        ids=set()
        expected={"lead":"note","bass":"note","rhythm":"chord","drums":"drum"}[pattern["role"]]
        for event in pattern["events"]:
            if event["id"] in ids or event["kind"]!=expected or beat(event["beat"])>=beat(pattern["length"]) or not beat(event["duration"]):
                raise ContractError("Invalid pattern event identity/position/role")
            ids.add(event["id"])
            if event["expression"]["lockExactPitch"] and (event["kind"]!="note" or event["choice"]["exactMidi"] is None):
                raise ContractError("Exact pitch locks require an explicit note")
    instances={}
    uses={}
    total_events=0
    total_cycles=0
    loops=project.get('trackLoops',{})
    for role,cycle in loops.items():
        if not beat(cycle['startBeat'])<beat(cycle['endBeat'])<=end:
            raise ContractError('Track loop must have a positive cycle inside the song')
        if not any(patterns[i['patternId']]['role']==role for i in project['instances'] if i['patternId'] in patterns):
            raise ContractError('An empty track cannot loop')
    for instance in project["instances"]:
        if instance["id"] in instances or instance["patternId"] not in patterns:
            raise ContractError("Duplicate instance or missing pattern")
        pattern=patterns[instance["patternId"]]
        length=instance_length(instance,pattern)
        if length<=0 or beat(instance["beat"])+length>end:
            raise ContractError("Pattern occurrence exceeds song boundary")
        cycles=math.ceil(length/beat(pattern['length']))
        if pattern['role'] in loops:
            loop=loops[pattern['role']];start,stop=beat(loop['startBeat']),beat(loop['endBeat'])
            if not start<=beat(instance['beat'])<beat(instance['beat'])+length<=stop:
                raise ContractError('Track loop source clips must fit inside its cycle')
            cycles*=math.ceil((end-beat(instance['beat']))/(stop-start))
        instances[instance["id"]]=instance
        uses.setdefault(instance["patternId"],[]).append(instance)
        total_cycles+=cycles
        total_events+=cycles*sum(4 if event.get('flam') else 2 for event in pattern['events'])
    if total_events>100000 or total_cycles>100000:
        raise ContractError("Expanded event budget exceeded")
    # Old one-shot overlaps remain accepted. New loop spans and complete track
    # loops must not obscure another saved clip on the same lane.
    for instance in project['instances']:
        pattern=patterns[instance['patternId']]
        if 'playbackLength' in instance or pattern['role'] in loops:
            check_arrangement_space(project,pattern['role'],instance['beat'],instance_length(instance,pattern),instance['id'])
    for occurrences in uses.values():
        if len(occurrences)>1 and not all(occurrence["linked"] for occurrence in occurrences):
            raise ContractError("Shared patterns must be explicitly Linked Repeat")
    wanted={"lead","bass","rhythm","drums", *["drums."+slot for slot in SLOTS]}
    if set(project["mix"]["channels"])!=wanted:
        raise ContractError("Mix must preserve every fixed channel and drum group")
    vocal_ids=set()
    for lane in project["vocals"]:
        if lane["id"] in vocal_ids:
            raise ContractError("Duplicate vocal lane")
        vocal_ids.add(lane["id"])
        takes={take["id"]:take for take in lane["takes"]}
        if len(takes)!=len(lane["takes"]) or (lane["selectedTakeId"] is not None and lane["selectedTakeId"] not in takes):
            raise ContractError("Invalid retained/selected take")
        previous_end=-1
        for region in lane["comp"]:
            if (region["takeId"] not in takes or region["endSeconds"]<=region["startSeconds"]
                    or region["startSeconds"]<previous_end):
                raise ContractError("Comp regions must be ordered, nonoverlapping, and refer to retained takes")
            previous_end=region["endSeconds"]


def load_project(path: Path) -> dict:
    if Path(path).stat().st_size > 16*1024*1024:
        raise ContractError("Project manifest exceeds 16 MiB")
    project=read_json(Path(path).read_bytes())
    validate_project(project)
    return project


def save_project(path: Path, project: dict) -> None:
    validate_project(project)
    atomic_json(path,project)


def duplicate(project: dict, instance_id: str, destination: str, *, linked=False, include_harmony=False) -> dict:
    """Returns an undo-friendly new value. Default copy leaves destination harmony."""
    result=copy.deepcopy(project)
    source=next(item for item in result["instances"] if item["id"]==instance_id)
    pattern=next(item for item in result["patterns"] if item["id"]==source["patternId"])
    if not linked:
        pattern=copy.deepcopy(pattern)
        pattern["id"]="pattern_"+uuid.uuid4().hex
        result["patterns"].append(pattern)
    else:
        for item in result["instances"]:
            if item["patternId"]==pattern["id"]:
                item["linked"]=True
    occurrence={"id":"instance_"+uuid.uuid4().hex,"patternId":pattern["id"],"beat":destination,"linked":linked}
    if 'playbackLength' in source:occurrence['playbackLength']=source['playbackLength']
    result["instances"].append(occurrence)
    if include_harmony:
        # The caller must obtain the SDD's overwrite warning/confirmation in the UI.
        from .music import at
        start=beat(source["beat"])
        target=beat(destination)
        length=instance_length(source,pattern)
        harmony=[item for item in result["harmony"] if not target<=beat(item["beat"])<target+length]
        first=copy.deepcopy(at(project["harmony"],start))
        first["beat"]=str(target)
        harmony.append(first)
        for item in project["harmony"]:
            position=beat(item["beat"])
            if start<position<start+length:
                harmony.append({"beat":str(target+position-start),"chord":copy.deepcopy(item["chord"])})
        if target+length<beat(project["length"]) and not any(beat(item["beat"])==target+length for item in harmony):
            harmony.append({"beat":str(target+length),"chord":copy.deepcopy(at(project["harmony"],target+length)["chord"])})
        result["harmony"]=sorted(harmony,key=lambda item:beat(item["beat"]))
    validate_project(result)
    return result


def make_independent(project: dict, instance_id: str) -> dict:
    result=copy.deepcopy(project)
    instance=next(item for item in result["instances"] if item["id"]==instance_id)
    pattern=copy.deepcopy(next(item for item in result["patterns"] if item["id"]==instance["patternId"]))
    pattern["id"]="pattern_"+uuid.uuid4().hex
    result["patterns"].append(pattern)
    instance.update(patternId=pattern["id"],linked=False)
    validate_project(result)
    return result

