"""Undoable desktop editing over the existing project and Governor contracts.

This module has no Qt dependency and never reads or transforms audio waveforms.
"""
from __future__ import annotations

import copy
import hashlib
import os
import re
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path

from .contracts import ContractError, SLOTS, VERSION, canonical_bytes, read_json
from .governor import context, resolve
from .music import MODES, NAMES, QUALITIES, REGISTERS, at, beat, chord_identity, chord_suffix, diatonic, quarter_seconds, roman
from .project import check_arrangement_space, duplicate, instance_length, load_project, make_independent, save_project, validate_project
from .sequencer import SequencerEditing


def identity(prefix):
    return prefix + '_' + uuid.uuid4().hex


def channel(gain=-6):
    return dict(gainDb=gain, pan=0, muted=False, eqPreset='neutral', reverbOn=False, delayOn=False, inserts=[])


def new_project(pack, tonic=0, mode='major', bars=4):
    from .music import REGISTRY_VERSION
    source=pack.manifest['source']
    project=dict(formatVersion=VERSION, projectId=identity('project'), title=source['title']+' — new song',
        packReference=dict(packId=pack.manifest['packId'], manifestSha256=pack.manifest_hash),
        musicalRegistryVersion=REGISTRY_VERSION, tempoMap=[dict(beat='0', quarterBpm=120)],
        meterMap=[dict(beat='0', numerator=4, denominator=4, governorSegments=4)],
        tonalityMap=[dict(beat='0', tonic=tonic, mode=mode)],
        harmony=[dict(beat='0', chord=diatonic(tonic, mode, 1))], length=str(bars*4), patterns=[], instances=[],
        variation=dict(seed=uuid.uuid4().hex, revision=0),
        mix=dict(channels={name:channel(-8) for name in ('lead','rhythm','bass','drums', *['drums.'+s for s in SLOTS])},
                 master=channel(0), compressor=dict(on=True, thresholdDb=-12, ratio=2, attackMs=10, releaseMs=150)),
        pluginTracks=[], vocals=[dict(id='vocal_1', visible=True, takes=[], selectedTakeId=None, comp=[],
                                      correction=dict(on=False, target='key-mode'), channel=channel())],
        editorContext=dict(selection='', zoom=1, scrollBeat='0', lastAction='New project'),
        credits=[dict(source=source['title'], license=source['license'], attribution=source['attribution'],
                      changes='New arrangement using prepared source assets')])
    from .mixing import apply_punch_mix
    apply_punch_mix(project)
    return project


def measures(project):
    """Exact bar boundaries, including meter changes and a possible final partial bar."""
    position=Fraction(0); end=beat(project['length']); result=[]
    while position<end:
        meter=at(project['meterMap'], position)
        length=Fraction(4*meter['numerator'], meter['denominator'])
        result.append((position, min(length,end-position), meter))
        position+=length
        if len(result)>4096:raise ContractError('Desktop timeline exceeds 4096 measures')
    return result


def seconds_to_beat(seconds, tempo_map):
    remaining=max(0,seconds); start=Fraction(0); bpm=tempo_map[0]['quarterBpm']
    for entry in tempo_map[1:]:
        boundary=beat(entry['beat']); interval=float(boundary-start)*60/bpm
        if remaining<=interval:break
        remaining-=interval;start=boundary;bpm=entry['quarterBpm']
    return start+Fraction(remaining*bpm/60).limit_denominator(1000000)


def chord_label(project, position, chord=None):
    tone=at(project['tonalityMap'],position)
    chord=chord or at(project['harmony'],position)['chord']
    root,_,_=chord_identity(tone['tonic'],tone['mode'],chord)
    names=('C','D♭','D','E♭','E','F','G♭','G','A♭','A','B♭','B') if tone['tonic'] in (1,3,5,6,8,10) else NAMES
    return roman(chord)+' · '+names[root]+chord_suffix(chord['quality'])


def parse_progression(text, tonic, mode):
    """Numbers are explicitly mode-derived; Roman case/quality is authored."""
    numerals=('I','II','III','IV','V','VI','VII'); result=[]
    for token in re.split(r'[\s,–—-]+',text.strip()):
        if not token:continue
        if token in tuple(str(n) for n in range(1,8)):
            result.append(diatonic(tonic,mode,int(token)));continue
        match=re.fullmatch(r'([♭♯b#]?)([IViv]+)(.*?)(?:/([1-6])(?:st|nd|rd|th)?)?',token)
        if not match or match[2].upper() not in numerals or not (match[2].islower() or match[2].isupper()):raise ContractError('Use degrees 1–7 or Roman chords, e.g. i IIImaj7 VI iv')
        prefix,base,suffix,inversion=match.groups()
        suffix=suffix.replace('♭','b').replace('♯','#')
        authored={'':('major','minor'),'6':('major6','minor6'),'7':('dominant7','minor7'),
                  '9':('dominant9','minor9'),'11':('dominant11','minor11'),'13':('dominant13','minor13'),
                  'add9':('add9','minorAdd9'),'6/9':('major6Add9','minor6Add9')}
        aliases={'maj7':'major7','maj9':'major9','maj13':'major13','maj7#11':'major7Sharp11',
                 'm':'minor','m6':'minor6','m7':'minor7','m9':'minor9','m11':'minor11','m13':'minor13',
                 'madd9':'minorAdd9','m6/9':'minor6Add9','m(maj7)':'minorMajor7','m(maj9)':'minorMajor9',
                 '(maj7)':'minorMajor7','(maj9)':'minorMajor9','°7':'diminished7','dim7':'diminished7',
                 'ø7':'halfDiminished7','m7b5':'halfDiminished7','°':'diminished','dim':'diminished',
                 '+':'augmented','aug':'augmented','+7':'dominant7Sharp5','7#5':'dominant7Sharp5',
                 '7b5':'dominant7b5','7b9':'dominant7b9','7#9':'dominant7Sharp9',
                 '7sus4':'dominant7sus4','9sus4':'dominant9sus4','sus2':'sus2','sus4':'sus4','5':'power'}
        if suffix in authored:quality=authored[suffix][base.islower()]
        else:quality=aliases.get(suffix)
        if quality is None:raise ContractError('Unsupported chord quality; use a registered triad, sixth, seventh, ninth, eleventh or thirteenth')
        if int(inversion or 0)>=len(QUALITIES[quality]):raise ContractError('Impossible inversion for this chord quality')
        result.append(dict(degree=numerals.index(base.upper())+1, alteration={'':0,'♭':-1,'b':-1,'♯':1,'#':1}[prefix],
                           quality=quality,inversion=int(inversion or 0)))
    if not result:raise ContractError('Enter at least one chord')
    return result


def new_event(role, position, duration, sound='', tone=0, register=None):
    return dict(id=identity('event'), beat=str(position), duration=str(duration), enabled=True,
        kind={'lead':'note','bass':'note','rhythm':'chord','drums':'drum'}[role],
        choice=dict(tone=tone,registerMidi=register if register is not None else (40 if role=='bass' else 64),exactMidi=None,soundIdentity=sound),
        expression=dict(velocity=.8,attackMs=0,playPercent=100,changePercent=0,variation='none',locked=False,lockExactPitch=False))


def atomic_copy(source, destination):
    """Cancellation never reaches this commit step; existing exports survive failures."""
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+destination.name+'-',suffix='.partial',dir=destination.parent)
    try:
        with os.fdopen(fd,'wb') as out,Path(source).open('rb') as inp:
            while block:=inp.read(1024*1024):out.write(block)
            out.flush();os.fsync(out.fileno())
        os.replace(name,destination)
    finally:
        if os.path.exists(name):os.unlink(name)


class Editor(SequencerEditing):
    def __init__(self, project, pack, path=None):
        validate_project(project)
        if project['packReference']!={'packId':pack.manifest['packId'],'manifestSha256':pack.manifest_hash}:
            raise ContractError('Project needs its exact Song Pack version; choose the matching .prdepack')
        self.project=copy.deepcopy(project);self.pack=pack;self.path=Path(path) if path else None
        self.undo_stack=[];self.redo_stack=[];self.serial=0
        self.saved=canonical_bytes(self.project) if path else None

    @property
    def dirty(self):
        if self.saved is None:return True
        saved=read_json(self.saved);saved.pop('editorContext')
        current=copy.deepcopy(self.project);current.pop('editorContext')
        return canonical_bytes(saved)!=canonical_bytes(current)

    @property
    def fingerprint(self):
        value=copy.deepcopy(self.project);value.pop('editorContext')
        return hashlib.sha256(canonical_bytes(value)).hexdigest()

    def apply(self, label, mutate):
        candidate=copy.deepcopy(self.project)
        returned=mutate(candidate)
        if returned is not None:candidate=returned
        validate_project(candidate)
        if candidate==self.project:return
        candidate['editorContext']['lastAction']=label
        self.undo_stack.append((label,self.project));self.undo_stack=self.undo_stack[-80:]
        while sum(len(canonical_bytes(p)) for _,p in self.undo_stack)>32*1024*1024:self.undo_stack.pop(0)
        self.project=candidate;self.redo_stack.clear();self.serial+=1

    def undo(self):
        if self.undo_stack:
            label,previous=self.undo_stack.pop();self.redo_stack.append((label,self.project));self.project=previous;self.serial+=1

    def redo(self):
        if self.redo_stack:
            label,next_project=self.redo_stack.pop();self.undo_stack.append((label,self.project));self.project=next_project;self.serial+=1

    def save(self,path=None):
        target=Path(path) if path else self.path
        if target is None:raise ContractError('Choose a project file')
        save_project(target,self.project);self.path=target;self.saved=canonical_bytes(self.project)

    def instance(self,instance_id):return next(i for i in self.project['instances'] if i['id']==instance_id)

    def pattern(self,instance_id):
        instance=self.instance(instance_id)
        return next(p for p in self.project['patterns'] if p['id']==instance['patternId'])

    def instance_length(self,instance_id):
        return instance_length(self.instance(instance_id),self.pattern(instance_id))

    def check_instance_space(self,role,start,length,exclude=''):
        check_arrangement_space(self.project,role,start,length,exclude)

    def move_instance(self,instance_id,position):
        """Move a musical block; stable IDs retain variation and source edits."""
        role=self.pattern(instance_id)['role'];length=self.instance_length(instance_id)
        self.check_instance_space(role,position,length,instance_id)
        def change(p):next(i for i in p['instances'] if i['id']==instance_id)['beat']=str(position)
        self.apply('Move clip',change)

    def resize_instance(self,instance_id,length):
        """Extend a clip by repeating its source; allow a partial final cycle."""
        length=beat(str(length));instance=self.instance(instance_id);pattern=self.pattern(instance_id)
        self.check_instance_space(pattern['role'],instance['beat'],length,instance_id)
        def change(p):
            target=next(i for i in p['instances'] if i['id']==instance_id)
            if length==beat(pattern['length']):target.pop('playbackLength',None)
            else:target['playbackLength']=str(length)
        self.apply('Resize looping clip',change)

    def set_track_loop(self,role,on,start=None,end=None):
        if role not in ('lead','bass','rhythm','drums'):raise ContractError('Unknown instrument track')
        def change(p):
            loops=p.setdefault('trackLoops',{})
            if not on:
                loops.pop(role,None)
                if not loops:p.pop('trackLoops',None)
                return
            patterns={part['id']:part for part in p['patterns']}
            clips=[i for i in p['instances'] if patterns[i['patternId']]['role']==role]
            if not clips:raise ContractError('Place a clip before looping this track')
            first=beat(str(start)) if start is not None else min(beat(i['beat']) for i in clips)
            last=beat(str(end)) if end is not None else max(beat(i['beat'])+instance_length(i,patterns[i['patternId']]) for i in clips)
            loops[role]=dict(startBeat=str(first),endBeat=str(last))
        self.apply('Loop '+role+' track' if on else 'Stop '+role+' track loop',change)

    def set_playback_loop(self,on):
        def change(p):p['loopPlayback']=bool(on)
        self.apply('Loop song playback' if on else 'Stop song playback loop',change)

    def set_map(self,name,position,values,label):
        if not 0<=position<beat(self.project['length']):raise ContractError('Position must be inside the song')
        def change(p):
            entry=dict(beat=str(position),**values)
            p[name]=sorted([i for i in p[name] if beat(i['beat'])!=position]+[entry],key=lambda i:beat(i['beat']))
        self.apply(label,change)

    def set_chord(self,position,chord):self.set_map('harmony',position,dict(chord=chord),'Edit chord')

    def fill_progression(self,chords,durations):
        if len(chords)!=len(durations) or any(d<=0 for d in durations):raise ContractError('Give one positive duration per chord')
        def change(p):
            entries=[];position=Fraction(0);n=0
            while position<beat(p['length']):
                entries.append(dict(beat=str(position),chord=copy.deepcopy(chords[n%len(chords)])))
                position+=durations[n%len(durations)];n+=1
                if n>16384:raise ContractError('Too many chord changes')
            p['harmony']=entries
        self.apply('Fill custom progression',change)

    def add_pattern(self,role,position,length,source=None):
        pattern=copy.deepcopy(source) if source else dict(role=role,length=str(length),events=[],
            provenance=dict(sourceClip='Raw Daw desktop authored pattern',license='MIT',changes='New performance'))
        pattern['id']=identity('pattern')
        self.check_instance_space(role,position,beat(pattern['length']))
        if source:
            from .pulse import entry_velocity
            for event in pattern['events']:
                event['expression']['velocity']=entry_velocity(self.project,position+beat(event['beat']),event['expression']['velocity'])
        instance=dict(id=identity('instance'),patternId=pattern['id'],beat=str(position),linked=False)
        def change(p):p['patterns'].append(pattern);p['instances'].append(instance)
        self.apply('Place '+role+' pattern',change)
        return instance['id']

    def copy(self,instance_id,position,linked=False,include_harmony=False):
        self.check_instance_space(self.pattern(instance_id)['role'],position,self.instance_length(instance_id))
        before={i['id'] for i in self.project['instances']}
        self.apply('Linked repeat' if linked else 'Duplicate pattern',
                   lambda p:duplicate(p,instance_id,str(position),linked=linked,include_harmony=include_harmony))
        return next(i['id'] for i in self.project['instances'] if i['id'] not in before)

    def detach(self,instance_id):self.apply('Make independent',lambda p:make_independent(p,instance_id))

    def remove_instance(self,instance_id):
        def change(p):
            p['instances']=[i for i in p['instances'] if i['id']!=instance_id]
            used={i['patternId'] for i in p['instances']};p['patterns']=[v for v in p['patterns'] if v['id'] in used]
            roles={v['role'] for v in p['patterns']}
            if 'trackLoops' in p:
                p['trackLoops']={role:cycle for role,cycle in p['trackLoops'].items() if role in roles}
                if not p['trackLoops']:p.pop('trackLoops')
        self.apply('Remove pattern',change)

    def edit_event(self,instance_id,event_id,updated):
        pattern_id=self.instance(instance_id)['patternId']
        def change(p):
            pattern=next(v for v in p['patterns'] if v['id']==pattern_id)
            pattern['events']=[copy.deepcopy(updated) if e['id']==event_id else e for e in pattern['events']]
        self.apply('Edit step',change)

    def toggle_step(self,instance_id,position,duration,sound=''):
        pattern=self.pattern(instance_id);pid=pattern['id'];role=pattern['role']
        matches=[e for e in pattern['events'] if beat(e['beat'])==position and (role!='drums' or e['choice']['soundIdentity']==sound)]
        if matches:
            def change(p):
                target=next(v for v in p['patterns'] if v['id']==pid)
                enabled=not any(e['enabled'] for e in matches)
                for e in target['events']:
                    if e['id'] in {v['id'] for v in matches}:e['enabled']=enabled
        else:
            from .percussion import records as drum_records
            if role=='drums' and not any(v['status']=='available' and v['soundIdentity']==sound for v in drum_records(self.pack).values()):
                raise ContractError('This drum slot has no prepared sound')
            tone=0
            if role in REGISTERS:
                absolute=beat(self.instance(instance_id)['beat'])+position
                _,_,pitches,legal=context(self.project,absolute)
                if legal:
                    available=[n for n,pc in enumerate(pitches) if any(k[0]==role and k[1]%12==pc for k in self.pack.mappings)]
                    if available:tone=available[0]
            event=new_event(role,position,duration,sound,tone)
            from .pulse import entry_velocity
            event['expression']['velocity']=entry_velocity(self.project,beat(self.instance(instance_id)['beat'])+position,event['expression']['velocity'])
            def change(p):next(v for v in p['patterns'] if v['id']==pid)['events'].append(event)
        self.apply('Toggle step',change)

    def delete_event(self,instance_id,event_id):
        pid=self.instance(instance_id)['patternId']
        def change(p):
            pattern=next(v for v in p['patterns'] if v['id']==pid)
            pattern['events']=[e for e in pattern['events'] if e['id']!=event_id]
        self.apply('Delete step',change)

    def set_mix(self,name,**values):
        def change(p):(p['mix']['master'] if name=='master' else p['mix']['channels'][name]).update(values)
        self.apply('Adjust '+name+' mix',change)

    def resize(self,bars):
        if not 1<=bars<=512:raise ContractError('Choose 1–512 bars')
        def change(p):
            position=Fraction(0)
            for _ in range(bars):
                meter=at(p['meterMap'],position);position+=Fraction(4*meter['numerator'],meter['denominator'])
            # Existing music/media is never truncated by a song-length control.
            patterns={v['id']:v for v in p['patterns']}
            if any(beat(i['beat'])+instance_length(i,patterns[i['patternId']])>position for i in p['instances']):
                raise ContractError('Patterns extend past that ending. Move or remove them first')
            if any(beat(v['beat'])>=position for key in ('harmony','tempoMap','meterMap','tonalityMap') for v in p[key]):
                raise ContractError('Map changes extend past that ending. Remove those changes first')
            p['length']=str(position)
        self.apply('Change song length',change)

    def regenerate(self):
        def change(p):p['variation']['revision']+=1
        self.apply('Regenerate variation',change)

    def plan(self):return resolve(self.project,self.pack)

    def covered_notes(self,role,position):
        _,_,pitches,legal=context(self.project,position)
        low,high=REGISTERS[role]
        return [note for note in range(low,high+1) if note%12 in pitches]

    def source_patterns(self):
        rows=read_json((self.pack.root/self.pack.manifest['clips']['index']).read_bytes())
        result=[]
        for row in rows:
            pattern=read_json((self.pack.root/row['normalizedPath']).read_bytes())
            result.append((row,pattern))
        return result

