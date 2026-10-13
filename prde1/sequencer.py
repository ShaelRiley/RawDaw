"""Persistent step-sequencer controls and musical edits, independent of Qt/PCM."""
from __future__ import annotations
import copy
import math
from fractions import Fraction
from pathlib import Path

from .contracts import ContractError, SLOTS, atomic_json, read_json
from .music import REGISTERS, NAMES, at, beat, chord_identity


def note_name(note):
    return NAMES[note % 12] + str(note // 12 - 1)


def row_id(role, address):
    return 'd_' + address if role == 'drums' else 'n_' + str(address) if role in REGISTERS else 'chord'


def row_defaults(role, address, label=''):
    return dict(id=row_id(role, address), note=address if role in REGISTERS else None,
                sound=address if role == 'drums' else '', label=label, muted=False, solo=False,
                velocityScale=1, velocityOffset=0, gatePercent=100, swingPercent=50, offsetPercent=0, flamPercent=12)


def settings(pattern, pack):
    if 'sequencer' in pattern:
        return copy.deepcopy(pattern['sequencer'])
    role = pattern['role']
    rows = [row_defaults(role, n) for n in range(REGISTERS[role][1], REGISTERS[role][0] - 1, -1)] if role in REGISTERS else (
        [row_defaults(role, slot) for slot in SLOTS] if role == 'drums' else [row_defaults(role, 'chord')])
    return dict(version='step-v1', stepBeat=str(max(Fraction(1,4),beat(pattern['length'])/1024)), defaultVelocity=.8, pitchMode='follow', entryMode='poly' if role == 'drums' else 'mono', rows=rows)


def pitch(project, pack, instance, event):
    role = next(p['role'] for p in project['patterns'] if p['id'] == instance['patternId'])
    choice = event['choice']
    if event['expression']['lockExactPitch']:
        return choice['exactMidi']
    position = beat(instance['beat']) + beat(event['beat'])
    tonality = at(project['tonalityMap'], position)
    _, pitches, _ = chord_identity(tonality['tonic'], tonality['mode'], at(project['harmony'], position)['chord'])
    target = pitches[choice['tone'] % len(pitches)]
    low, high = REGISTERS[role]
    return min((n for n in range(low, high + 1) if n % 12 == target),
               key=lambda n: (abs(n - choice['registerMidi']), pack.coverage.cost((role, n)), n))


def event_row(project, pack, instance, pattern, event):
    if pattern['role'] == 'drums':
        slot = next((slot for slot, row in pack.instruments['drums'].items() if row['soundIdentity'] == event['choice']['soundIdentity']), None)
        return row_id('drums', slot) if slot else 'unknown'
    if pattern['role'] in REGISTERS:
        return row_id(pattern['role'], pitch(project, pack, instance, event))
    return 'chord'


def controls_for(project, pack, instance, pattern, event):
    config = settings(pattern, pack)
    identity = event_row(project, pack, instance, pattern, event)
    row = next((r for r in config['rows'] if r['id'] == identity), None)
    if row is None:
        if pattern['role'] in REGISTERS:row=row_defaults(pattern['role'],pitch(project,pack,instance,event))
        elif pattern['role']=='drums':row=row_defaults('drums',identity[2:] if identity.startswith('d_') else 'kick')
        else:row=row_defaults('rhythm','chord')
    return row, config


def effective_events(project, pack, instance, pattern, authored):
    """Static row controls expand to ordinary triggers before harmonic validation."""
    if 'sequencer' not in pattern and not authored.get('flam') and not authored.get('offsetBeat'):
        return [authored]
    row, config = controls_for(project, pack, instance, pattern, authored)
    if row is None or row['muted'] or (any(r['solo'] for r in config['rows']) and not row['solo']):
        return []
    event = copy.deepcopy(authored)
    step = beat(config['stepBeat']); position = beat(authored['beat'])
    if int(position / step) % 2:
        position += step * Fraction(str((row['swingPercent'] - 50) / 50))
    position += step * Fraction(str(row['offsetPercent'] / 100)) + Fraction(authored.get('offsetBeat', '0'))
    position = (position % beat(pattern['length'])).limit_denominator(1000000)
    if position>=beat(pattern['length']):position=Fraction(0)
    event['beat'] = str(position)
    event['duration'] = str(max(Fraction(1,1000000),(beat(event['duration']) * Fraction(str(row['gatePercent'] / 100))).limit_denominator(1000000)))
    event['expression']['velocity'] = max(0, min(1, event['expression']['velocity'] * row['velocityScale'] + row['velocityOffset']))
    if not event.get('flam'):
        return [event]
    grace = copy.deepcopy(event); grace['_subtrigger'] = 'flam'
    grace['_chanceId'] = authored['id']
    offset = (step * Fraction(str(row['flamPercent'] / 100))).limit_denominator(1000000)
    grace['beat'] = str(max(Fraction(0), position - abs(offset)).limit_denominator(1000000))
    if offset >= 0 and position == 0:
        event['beat'] = str(abs(offset))
    elif offset < 0:
        grace['beat'] = str(((position + abs(offset)) % beat(pattern['length'])).limit_denominator(1000000))
    grace['duration'] = str(min(beat(event['duration']), max(Fraction(1, 48000), abs(offset))))
    grace['expression']['velocity'] *= .45
    return [grace, event]


def validate_pattern(pattern):
    config = pattern.get('sequencer')
    if config:
        if not 0 < beat(config['stepBeat']) <= 4 or math.ceil(beat(pattern['length']) / beat(config['stepBeat'])) > 1024:
            raise ContractError('Step grid must contain 1–1024 columns')
        identities = set()
        for row in config['rows']:
            role = pattern['role']
            if row['id'] in identities:
                raise ContractError('Duplicate step row')
            identities.add(row['id'])
            if role in REGISTERS:
                if type(row['note']) is not int or not REGISTERS[role][0] <= row['note'] <= REGISTERS[role][1] or row['sound'] or row['id'] != row_id(role, row['note']):
                    raise ContractError('Pitch row outside role register')
            elif role == 'drums':
                if row['note'] is not None or row['sound'] not in SLOTS or row['id'] != row_id(role, row['sound']):
                    raise ContractError('Invalid kit row identity')
            elif row['id'] != 'chord' or row['note'] is not None or row['sound']:
                raise ContractError('Rhythm uses a whole-chord row')
    for event in pattern['events']:
        if abs(Fraction(event.get('offsetBeat', '0'))) > 4:
            raise ContractError('Step timing offset exceeds four beats')


def audition_project(editor, instance_id, row=None, column=0):
    """Isolate a pattern or pitch without changing saved variation or authorship."""
    from .editor import new_event
    project=copy.deepcopy(editor.project);instance=copy.deepcopy(editor.instance(instance_id));pattern=copy.deepcopy(editor.pattern(instance_id))
    start=beat(instance['beat']);length=beat(pattern['length'])
    if row is not None:
        start+=column*beat(settings(pattern,editor.pack)['stepBeat']);length=Fraction(1,2)
        event=new_event(pattern['role'],Fraction(0),length)
        if pattern['role']=='drums':
            record=editor.pack.instruments['drums'][row['sound']]
            if record['status']!='available':raise ContractError('This optional kit sound is unassigned')
            event['choice']['soundIdentity']=record['soundIdentity']
            root=record['pitches'][0]%12 if record['pitches'] else None
        elif pattern['role'] in REGISTERS:
            event['choice'].update(exactMidi=row['note'],registerMidi=row['note']);event['expression']['lockExactPitch']=True;root=row['note']%12
        else:root=None
        pattern['events']=[event];pattern.pop('sequencer',None);pattern['length']=str(length)
    for name in ('harmony','tonalityMap','tempoMap','meterMap'):
        first=copy.deepcopy(at(project[name],start));first['beat']='0'
        project[name]=[first]+[dict(copy.deepcopy(e),beat=str(beat(e['beat'])-start)) for e in project[name] if start<beat(e['beat'])<start+length]
    if row is not None and root is not None:
        project['tonalityMap']=[dict(beat='0',tonic=root,mode='major')]
        project['harmony']=[dict(beat='0',chord=dict(degree=1,alteration=0,quality='power',inversion=0))]
    instance['beat']='0';instance['linked']=False;project['patterns']=[pattern];project['instances']=[instance];project['length']=str(length)
    project['pluginTracks']=[]
    for lane in project['vocals']:lane.update(takes=[],comp=[],selectedTakeId=None);lane['correction']['on']=False
    return project,start


def placement_preview_plan(editor, instance_id, identity, position, event_id=None):
    """Resolve a short note audition without committing an edit or variation.

    Entry auditions the authored sound rather than its play/variation lottery.
    Row/channel mutes, volume, gate, timing and harmonic eligibility still apply.
    """
    from .editor import Editor
    from .governor import resolve
    from .contracts import RATE, validate
    project,_=audition_project(editor,instance_id)
    candidate=Editor(project,editor.pack)
    if event_id is None:
        candidate.paint_steps(instance_id,[(identity,position)],exact=settings(candidate.pattern(instance_id),editor.pack)['pitchMode']=='exact')
        event=next(e for e in candidate.step_matches(instance_id,identity,position) if e['enabled'])
    else:event=next(e for e in candidate.pattern(instance_id)['events'] if e['id']==event_id)
    event=copy.deepcopy(event)
    event['expression'].update(playPercent=100,changePercent=0,variation='none',locked=True)
    event['flam']=False  # Entry previews the primary sound, not a pattern fill.
    candidate.pattern(instance_id)['events']=[event]
    plan=resolve(candidate.project,editor.pack)
    if not plan['events'] or not any(e['gain']>0 for e in plan['events']):return None
    origin=min(e['startFrame'] for e in plan['events'])
    for e in plan['events']:
        e['startFrame']-=origin;e['endFrame']=min(e['endFrame']-origin,2*RATE)
        e['releaseFrames']=min(e['releaseFrames'],e['endFrame']-e['startFrame'])
    plan['events']=[e for e in plan['events'] if e['endFrame']>e['startFrame']]
    plan['endFrame']=max(e['endFrame'] for e in plan['events'])
    validate(plan,'prde1-events-v1.schema.json')
    return plan


class SequencerEditing:
    def _step_edit(self, instance_id, label, callback):
        pid = self.instance(instance_id)['patternId']
        def change(project):
            target = next(p for p in project['patterns'] if p['id'] == pid)
            previous_length=beat(target['length'])
            callback(target, project)
            if beat(target['length'])>previous_length:
                for occurrence in (i for i in project['instances'] if i['patternId']==pid):
                    start=beat(occurrence['beat']);stop=start+beat(target['length'])
                    for other in project['instances']:
                        if other['id']==occurrence['id']:continue
                        part=next(p for p in project['patterns'] if p['id']==other['patternId'])
                        if part['role']==target['role'] and max(start,beat(other['beat']))<min(stop,beat(other['beat'])+beat(part['length'])):
                            raise ContractError('A longer pattern would overlap another pattern on this track')
        self.apply(label, change)

    def set_sequencer(self, instance_id, **values):
        def edit(pattern, _):
            config = settings(pattern, self.pack); config.update(values); pattern['sequencer'] = config
        self._step_edit(instance_id, 'Set step grid', edit)

    def set_row(self, instance_id, identity, **values):
        def edit(pattern, _):
            config = settings(pattern, self.pack)
            next(row for row in config['rows'] if row['id'] == identity).update(values)
            pattern['sequencer'] = config
        self._step_edit(instance_id, 'Adjust step row', edit)

    def step_matches(self, instance_id, identity, position):
        instance = self.instance(instance_id); pattern = self.pattern(instance_id)
        return [e for e in pattern['events'] if beat(e['beat']) == position and event_row(self.project, self.pack, instance, pattern, e) == identity]

    def paint_steps(self, instance_id, cells, *, enabled=True, exact=False):
        from .editor import new_event
        instance = self.instance(instance_id)
        def edit(pattern, project):
            config = settings(pattern, self.pack); pattern['sequencer'] = config
            step = beat(config['stepBeat'])
            for identity, position in cells:
                if not 0 <= position < beat(pattern['length']): continue
                row = next(r for r in config['rows'] if r['id'] == identity)
                matches = [e for e in pattern['events'] if beat(e['beat']) == position and event_row(project, self.pack, instance, pattern, e) == identity]
                if not enabled:
                    for e in matches:e['enabled'] = False
                    continue
                role = pattern['role']; sound = ''; tone = 0
                if role == 'drums':
                    record = self.pack.instruments['drums'][row['sound']]
                    if record['status'] != 'available':raise ContractError('This optional kit row is unassigned')
                    sound = record['soundIdentity']
                elif role in REGISTERS:
                    absolute = beat(instance['beat']) + position
                    tonality = at(project['tonalityMap'], absolute)
                    _, pitches, _ = chord_identity(tonality['tonic'], tonality['mode'], at(project['harmony'], absolute)['chord'])
                    if row['note'] % 12 not in pitches:raise ContractError('Choose a pitch belonging to the governing chord in this column')
                    tone = pitches.index(row['note'] % 12)
                if config['entryMode'] == 'mono':
                    for e in pattern['events']:
                        if beat(e['beat']) == position and e not in matches:e['enabled'] = False
                if matches:
                    for e in matches:e['enabled'] = True
                else:
                    e = new_event(role, position, min(step, beat(pattern['length']) - position), sound, tone, row['note'])
                    e['expression']['velocity'] = config['defaultVelocity']
                    if role in REGISTERS:e['choice']['exactMidi'] = row['note']; e['expression']['lockExactPitch'] = exact
                    pattern['events'].append(e)
        self._step_edit(instance_id, 'Draw steps' if enabled else 'Erase steps', edit)

    def edit_step_values(self, instance_id, ids, **values):
        def edit(pattern, _):
            for e in pattern['events']:
                if e['id'] not in ids:continue
                for name, value in values.items():
                    if name in ('flam', 'offsetBeat', 'duration', 'enabled'):e[name] = value
                    else:e['expression'][name] = value
        self._step_edit(instance_id, 'Edit step expression', edit)

    def transpose_column(self, instance_id, position, direction):
        instance=self.instance(instance_id)
        def edit(pattern, project):
            if pattern['role'] not in REGISTERS:raise ContractError('Pitch shifting a column applies to bass and lead')
            tone=at(project['tonalityMap'],beat(instance['beat'])+position)
            _,pitches,_=chord_identity(tone['tonic'],tone['mode'],at(project['harmony'],beat(instance['beat'])+position)['chord'])
            low,high=REGISTERS[pattern['role']]
            for e in pattern['events']:
                if e['enabled'] and beat(e['beat'])==position:
                    note=pitch(project,self.pack,instance,e)
                    choices=[n for n in range(low,high+1) if n%12 in pitches and (n-note)*direction>0]
                    if not choices:raise ContractError('No higher/lower permitted pitch in this register')
                    note=min(choices,key=lambda n:abs(n-note));e['choice'].update(tone=pitches.index(note%12),registerMidi=note,exactMidi=note)
        self._step_edit(instance_id,'Move pitch column',edit)

    def row_action(self, instance_id, identity, action, *, step=None, every=2, start=0, payload=None):
        if not 1<=every<=16:raise ContractError('Fill interval must be 1–16 steps')
        from .editor import identity as new_id
        instance = self.instance(instance_id)
        if action == 'fill':
            config = settings(self.pattern(instance_id), self.pack); size = beat(config['stepBeat'])
            cells = [(identity, i * size) for i in range(start, math.ceil(beat(self.pattern(instance_id)['length']) / size), every)]
            self.paint_steps(instance_id, cells);return
        def edit(pattern, project):
            config = settings(pattern, self.pack); size = beat(config['stepBeat'])
            events = [e for e in pattern['events'] if event_row(project, self.pack, instance, pattern, e) == identity]
            if action in ('clear', 'cut'):
                pattern['events'] = [e for e in pattern['events'] if e not in events]
            elif action == 'shift':
                for e in events:e['beat'] = str((beat(e['beat']) + step * size) % beat(pattern['length']))
            elif action == 'reverse':
                for e in events:e['beat'] = str(max(Fraction(0), beat(pattern['length']) - size - beat(e['beat'])))
            elif action == 'paste':
                row = next(r for r in config['rows'] if r['id'] == identity)
                pattern['events'] = [e for e in pattern['events'] if e not in events]
                for source in payload:
                    e = copy.deepcopy(source); e['id'] = new_id('event')
                    if beat(e['beat']) >= beat(pattern['length']):continue
                    if pattern['role'] == 'drums':e['choice']['soundIdentity'] = self.pack.instruments['drums'][row['sound']]['soundIdentity']
                    elif pattern['role'] in REGISTERS:
                        tone = at(project['tonalityMap'], beat(instance['beat']) + beat(e['beat']))
                        _, pitches, _ = chord_identity(tone['tonic'], tone['mode'], at(project['harmony'], beat(instance['beat']) + beat(e['beat']))['chord'])
                        if row['note'] % 12 not in pitches:raise ContractError('Paste target pitch conflicts with a governing chord')
                        e['choice'].update(tone=pitches.index(row['note'] % 12), exactMidi=row['note'], registerMidi=row['note'])
                    pattern['events'].append(e)
            elif action == 'delete':
                pattern['events'] = [e for e in pattern['events'] if e not in events]
                config['rows'] = [r for r in config['rows'] if r['id'] != identity]; pattern['sequencer'] = config
            elif action in ('up', 'down'):
                index = next(i for i, r in enumerate(config['rows']) if r['id'] == identity)
                target = max(0, min(len(config['rows']) - 1, index + (-1 if action == 'up' else 1)))
                config['rows'][index], config['rows'][target] = config['rows'][target], config['rows'][index]; pattern['sequencer'] = config
        self._step_edit(instance_id, action.title() + ' row', edit)

    def tie_steps(self, instance_id, identity, first, last, *, split=False):
        from .editor import new_event
        instance = self.instance(instance_id)
        def edit(pattern, project):
            size = beat(settings(pattern, self.pack)['stepBeat']); stop = min(beat(pattern['length']), last + size)
            matches = sorted([e for e in pattern['events'] if e['enabled'] and first <= beat(e['beat']) < stop and event_row(project, self.pack, instance, pattern, e) == identity], key=lambda e:beat(e['beat']))
            if not matches:return
            if split:
                source = copy.deepcopy(matches[0]); pattern['events'] = [e for e in pattern['events'] if e not in matches]
                position = beat(source['beat']); stop = min(beat(pattern['length']), position + beat(source['duration']))
                while position < stop:
                    e = copy.deepcopy(source);e['id'] = new_event(pattern['role'], position, size)['id'];e['beat'] = str(position);e['duration'] = str(min(size, stop - position))
                    pattern['events'].append(e);position += size
            else:
                source = matches[0]; source['duration'] = str(stop - beat(source['beat']))
                pattern['events'] = [e for e in pattern['events'] if e not in matches[1:]]
        self._step_edit(instance_id, 'Split tied steps' if split else 'Tie steps', edit)

    def pattern_action(self, instance_id, action, *, value=None):
        def edit(pattern, _):
            if action == 'clear':pattern['events'] = []
            elif action == 'quantize':
                size = beat(settings(pattern, self.pack)['stepBeat'])
                for e in pattern['events']:e['beat'] = str(min(beat(pattern['length']) - size, round(beat(e['beat']) / size) * size))
            elif action == 'length':
                if any(beat(e['beat']) >= value or beat(e['beat']) + beat(e['duration']) > value for e in pattern['events']):
                    raise ContractError('Steps extend beyond that length; erase or shorten them first')
                pattern['length'] = str(value)
            elif action == 'fit':
                ratio = value / beat(pattern['length'])
                for e in pattern['events']:e['beat'] = str((beat(e['beat']) * ratio).limit_denominator(1000000));e['duration'] = str(max(Fraction(1,1000000),(beat(e['duration']) * ratio).limit_denominator(1000000)))
                if 'sequencer' in pattern:pattern['sequencer']['stepBeat'] = str((beat(pattern['sequencer']['stepBeat']) * ratio).limit_denominator(1000000))
                pattern['length'] = str(value)
        self._step_edit(instance_id, action.title() + ' pattern', edit)

    def save_pattern(self, instance_id, path):
        atomic_json(path, dict(formatVersion='step-pattern-v1', pattern=self.pattern(instance_id),
                               sourcePack=self.project['packReference'], credits=self.project['credits']))

    def load_pattern(self, instance_id, path):
        if path.stat().st_size > 8 * 1024 * 1024:raise ContractError('Pattern file exceeds eight MiB')
        data = read_json(path.read_bytes())
        if not isinstance(data,dict) or data.get('formatVersion') != 'step-pattern-v1' or set(data) != {'formatVersion', 'pattern', 'sourcePack', 'credits'} or not isinstance(data['pattern'],dict):raise ContractError('Unknown pattern format')
        if data['pattern']['role'] != self.pattern(instance_id)['role']:raise ContractError('Load this pattern on a matching instrument track')
        if data['sourcePack'] != self.project['packReference'] and data['pattern']['role'] == 'drums':raise ContractError('This kit pattern uses a different Song Pack; sound identities require explicit remapping')
        def edit(pattern, project):
            identity = pattern['id'];pattern.clear();pattern.update(copy.deepcopy(data['pattern']));pattern['id'] = identity
            for credit in data['credits']:
                if credit not in project['credits']:project['credits'].append(credit)
        self._step_edit(instance_id, 'Load step pattern', edit)

    def import_midi(self,instance_id,path,mapping=None):
        from .midi import inspect_midi
        from .editor import new_event
        if path.stat().st_size>4*1024*1024:raise ContractError('MIDI file exceeds four MiB')
        data=inspect_midi(path.read_bytes());notes=data['notes']
        if not notes:raise ContractError('This MIDI file has no note events')
        instance=self.instance(instance_id);role=self.pattern(instance_id)['role'];mapping=mapping or {}
        addresses={row['midiAddress']:slot for slot,row in self.pack.instruments['drums'].items() if row['status']=='available'}
        standard={35:'kick',36:'kick',38:'snare',40:'snare',42:'hatClosed',44:'hatClosed',46:'hatOpen',41:'tom1',43:'tom1',45:'tom1',47:'tom2',48:'tom2',50:'tom2'}
        def edit(pattern,project):
            imported=[];seen=set()
            for note in notes:
                position=Fraction(note['tick'],data['ticksPerQuarter']);duration=Fraction(note['durationTicks'],data['ticksPerQuarter'])
                if role=='rhythm' and position in seen:
                    matching=next(e for e in imported if beat(e['beat'])==position);matching['duration']=str(max(beat(matching['duration']),duration));continue
                seen.add(position);sound=''
                if role=='drums':
                    slot=mapping.get(note['note'],addresses.get(note['note'],standard.get(note['note'])))
                    if slot not in SLOTS or self.pack.instruments['drums'][slot]['status']!='available':raise ContractError(f"Map MIDI note {note['note']} to a populated kit row before importing")
                    sound=self.pack.instruments['drums'][slot]['soundIdentity']
                elif role in REGISTERS and not REGISTERS[role][0]<=note['note']<=REGISTERS[role][1]:
                    raise ContractError('Imported MIDI includes notes outside this instrument register')
                e=new_event(role,position,duration,sound,register=note['note']);e['expression']['velocity']=note['velocity']/127
                if role in REGISTERS:e['choice']['exactMidi']=note['note'];e['expression']['lockExactPitch']=True
                imported.append(e)
            length=max(beat(pattern['length']),max(beat(e['beat'])+beat(e['duration']) for e in imported))
            pattern['length']=str(length);pattern['events']=imported;pattern['sequencer']=settings(pattern,self.pack)
            ordered=sorted(imported,key=lambda e:beat(e['beat']))
            overlap=any(beat(a['beat'])+beat(a['duration'])>beat(b['beat']) for a,b in zip(ordered,ordered[1:]))
            if role in REGISTERS and overlap:pattern['sequencer']['entryMode']='poly'
            pattern['provenance']=dict(sourceClip=path.name,license='user-supplied MIDI',changes='Note timing retained; rhythm chord attacks use the active Governor; no tempo/controller changes imported')
        self._step_edit(instance_id,'Import MIDI notes',edit)
        return data['controls']

    def export_midi(self,instance_id,path):
        from .midi import encode_notes
        from .editor import seconds_to_beat
        from .governor import resolve
        import os,tempfile
        project,_=audition_project(self,instance_id);plan=resolve(project,self.pack)
        if plan['conflicts']:raise ContractError('Resolve the pattern pitch/sound conflicts before MIDI export')
        notes=[]
        for voice in plan['events']:
            start=seconds_to_beat(voice['startFrame']/48000,project['tempoMap']);stop=seconds_to_beat(voice['endFrame']/48000,project['tempoMap'])
            if voice['role'].startswith('drums.'):
                slot=voice['role'].split('.')[1];pitches=[self.pack.instruments['drums'][slot]['midiAddress']];channel=9
            else:pitches=voice['notePitches'];channel=0
            # MIDI velocity is authored expression, before channel/sample gain.
            address=voice['id'].split(':')[1]
            source=next(e for e in project['patterns'][0]['events'] if e['id']==address)
            controls,_=controls_for(project,self.pack,project['instances'][0],project['patterns'][0],source)
            velocity=max(0,min(1,source['expression']['velocity']*(controls['velocityScale'] if controls else 1)+(controls['velocityOffset'] if controls else 0)))
            if ':flam:' in voice['id']:velocity*=.45
            for note in pitches:notes.append(dict(beat=start,duration=stop-start,note=note,channel=channel,velocity=velocity))
        raw=encode_notes(notes,project['tempoMap'][0]['quarterBpm'],tempo_map=project['tempoMap']);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(dir=path.parent,suffix='.partial')
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(name,path)
        finally:
            if os.path.exists(name):os.unlink(name)
