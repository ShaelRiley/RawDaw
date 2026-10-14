"""Offline one-bar performance library, with explicit harmony and kit adaptation."""
from __future__ import annotations

import copy
import hashlib
import gzip
import zipfile
from functools import lru_cache
from fractions import Fraction
from pathlib import Path

from .contracts import ROOT, ContractError, read_json
from .music import beat
from .percussion import records as drum_records, semantic_slot

DATA = ROOT / 'prde1/data/clips'


@lru_cache(maxsize=1)
def catalog():
    path=DATA/'index.json.gz'
    if path.stat().st_size>4*1024*1024:raise ContractError('Clip library exceeds its size budget')
    with gzip.open(path,'rb') as stream:raw=stream.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:raise ContractError('Expanded clip library exceeds its size budget')
    data=read_json(raw)
    if data['format']!='raw-daw-clips-v1' or not 1<=len(data['clips'])<=4096:raise ContractError('Invalid clip library')
    if len({c['id'] for c in data['clips']})!=len(data['clips']):raise ContractError('Duplicate library identities')
    return data


def find(clip_id):
    return next(c for c in catalog()['clips'] if c['id']==clip_id)


def midi_bytes(clip):
    with zipfile.ZipFile(DATA/'midi-clips.zip') as archive:
        entry=archive.getinfo(clip['id']+'.mid')
        if entry.file_size>4*1024*1024:raise ContractError('Clip MIDI exceeds its budget')
        raw=archive.read(entry)
    if hashlib.sha256(raw).hexdigest()!=clip['midiSha256']:raise ContractError('Library MIDI integrity check failed')
    return raw


def bar_at(project,position):
    from .editor import measures
    return next((bar for bar in measures(project) if bar[0]<=position<bar[0]+bar[1]),None)


def compatible(project,clip,position):
    bar=bar_at(project,position)
    if bar is None:raise ContractError('Choose a measure inside the song')
    start,length,meter=bar
    if position!=start:raise ContractError('Place one-bar clips at a measure downbeat')
    if clip['meter']!=[meter['numerator'],meter['denominator']]:
        raise ContractError(f"Choose a {meter['numerator']}/{meter['denominator']} clip; this clip is {clip['meter'][0]}/{clip['meter'][1]}. Timing is preserved.")
    if length!=beat(clip['pattern']['length']):raise ContractError('Extend the final partial measure before placing this clip')


def native_pattern(editor,clip,position):
    from .sequencer import settings
    from .pulse import entry_velocity
    pattern=copy.deepcopy(clip['pattern']);report=[];events=[];seen={}
    instruments=drum_records(editor.pack)
    for event in pattern['events']:
        if pattern['role']=='drums':
            sound=event['choice']['soundIdentity'];slot=semantic_slot(editor.pack,sound)
            if slot is None or instruments[slot]['status']!='available':
                report.append(sound+' omitted: this bank has no matching sound');continue
            event['choice']['soundIdentity']=instruments[slot]['soundIdentity']
            if instruments[slot].get('derived'):
                report.append(instruments[slot]['displayName']+' uses a source-derived approximate articulation')
            key=(event['beat'],event['choice']['soundIdentity'])
            if key in seen:
                old=seen[key];old['expression']['velocity']=max(old['expression']['velocity'],event['expression']['velocity'])
                report.append('Simultaneous '+sound+' articulations merged into one hit');continue
            seen[key]=event
        event['expression']['velocity']=entry_velocity(editor.project,position+beat(event['beat']),event['expression']['velocity'])
        event['expression']['lockExactPitch']=False
        events.append(event)
    if not events:raise ContractError('This clip has no sounds represented by the loaded bank')
    pattern['events']=events;pattern['sequencer']=settings(pattern,editor.pack)
    pattern['provenance']['changes']+=' | Library '+catalog()['version']+'; clip '+clip['id']+'; source SHA-256 '+clip['sourceSha256']
    if report:pattern['provenance']['changes']+=' | '+'; '.join(sorted(set(report)))
    return pattern,sorted(set(report))


def place(editor,clip,position):
    """One undoable insertion, including the source credit and conversion report."""
    from .editor import identity
    compatible(editor.project,clip,position)
    pattern,report=native_pattern(editor,clip,position)
    try:editor.check_instance_space(pattern['role'],position,beat(pattern['length']))
    except ContractError as error:
        if 'overlap' in str(error):raise ContractError('This track already has a pattern here. Choose an empty measure.') from error
        raise
    pattern['id']=identity('pattern');instance=dict(id=identity('instance'),patternId=pattern['id'],beat=str(position),linked=False)
    credit=dict(source=clip['origin']+' / '+clip['id'],license=clip['license']+' — '+(
        'https://creativecommons.org/licenses/by/4.0/' if clip['license']=='CC-BY-4.0' else 'https://creativecommons.org/publicdomain/zero/1.0/'),
        attribution=clip['attribution']+' '+clip['sourceUrl'],changes=pattern['provenance']['changes'])
    def change(project):
        project['patterns'].append(pattern);project['instances'].append(instance)
        if not any(c['source']==credit['source'] for c in project['credits']):project['credits'].append(credit)
    editor.apply('Place '+clip['name'],change)
    return instance['id'],report


def audition(editor,clip,position):
    """Use the actual destination harmony/pulse without altering authored state."""
    from .editor import Editor
    from .sequencer import audition_project
    compatible(editor.project,clip,position)
    project=copy.deepcopy(editor.project);project['patterns']=[];project['instances']=[];project.pop('trackLoops',None)
    candidate=Editor(project,editor.pack);instance,_=place(candidate,clip,position)
    return audition_project(candidate,instance)[0]
