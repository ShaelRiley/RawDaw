"""Reproducible offline curation from verified CC sources and original CC0 scores.

Source parsing is preparation-only: same-address drum retriggers end the preceding
hit explicitly. The runtime continues to use the strict, bounded SMF reader.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import gzip
import io
import json
import struct
import sys
import zipfile
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prde1.contracts import canonical_bytes
from prde1.editor import new_event
from prde1.midi import encode_notes, inspect_midi
from prde1.music import QUALITIES

ROOT = Path(__file__).resolve().parents[1]
GMD_HASH = '651cbc524ffb891be1a3e46d89dc82a1cecb09a57c748c7b45b844c4841dcc1e'
GMD_URL = 'https://magenta.tensorflow.org/datasets/groove'
PIANO_URL = 'https://opengameart.org/content/piano-3-bass-with-drums'
PIANO_HASH = 'afab30422131a5af25680fb66579b3f1b46350cd4b5c0c773ec5082040189aa5'
DRUM_MAP = {36:'kick',35:'kick',38:'snare',40:'snare',37:'snare',
    48:'tom2',50:'tom2',45:'tom1',47:'tom1',43:'tom1',58:'tom1',
    46:'hatOpen',26:'hatOpen',42:'hatClosed',22:'hatClosed',44:'hatClosed',
    49:'crash',55:'crash',57:'crash',52:'crash',51:'ride',59:'ride',53:'ride'}
GM = {'kick':36,'snare':38,'hatClosed':42,'hatOpen':46,'tom1':45,'tom2':48,'crash':49,'ride':51}

# Different phrase structures, not transposed copies of one phrase.
PULSES = [
 ('Whole-bar anchor','1000000000000000','Ballad'), ('Half-bar anchors','1000000010000000','Ballad'),
 ('Quarter drive','1000100010001000','Pop rock'), ('Eighth drive','1010101010101010','Pop rock'),
 ('Sixteenth motor','1111111111111111','Dance'), ('Offbeat lift','0010001000100010','Dance'),
 ('Backbeat answer','0000100000001000','Pop'), ('Tresillo','1000001000001000','Latin'),
 ('Anticipation','1000000100000001','Pop'), ('Push and rest','1001000010010000','Funk'),
 ('Rock gallop','1011101110111011','Rock'), ('Half-time answer','1000000010100000','Hip hop'),
 ('Dotted accents','1001001001001001','Latin'), ('Upbeat conversation','0010010000100100','Funk'),
 ('Pickup and hold','1000000000001010','Ballad'), ('Chorus lift','1010100010101010','Pop rock'),
 ('Sparse verse','1000000000100000','Pop'), ('Stutter answer','1100000011000000','Dance'),
 ('Skip-step hook','1000101000101000','Pop'), ('Late answer','1000000000010010','Soul'),
 ('Downbeat cascade','1110100011101000','Rock'), ('Two-beat pocket','1000010010000100','Funk'),
 ('Offbeat doubles','0011001100110011','Dance'), ('Driving turnaround','1010101010101111','Rock'),
 ('Three plus five','1001000010010010','Latin'), ('Broken eighths','1010001010100010','Pop'),
 ('Syncopated refrain','1001010010010100','Soul'), ('Open chorus','1000100000101000','Pop rock'),
 ('End-bar answer','1000000010000110','Hip hop'), ('Short call','1010000000100000','Pop'),
 ('Long call short answer','1000101000001010','Ballad'), ('Alternating pushes','1000010010100100','Funk'),
]


def source_notes(raw):
    """Read source MIDI with a documented retrigger interpretation for percussion."""
    try:
        d = inspect_midi(raw)
        return d['ticksPerQuarter'], d['notes']
    except ValueError:
        pass
    if len(raw)>4*1024*1024 or raw[:8]!=b'MThd\0\0\0\6':raise ValueError('Bad source MIDI')
    fmt,tracks,ppq=struct.unpack_from('>HHH',raw,8)
    if fmt not in (0,1) or not 1<=tracks<=32 or not 1<=ppq<=32767:raise ValueError('Unsupported source MIDI')
    cursor=14;notes=[]
    for _ in range(tracks):
        if raw[cursor:cursor+4]!=b'MTrk':raise ValueError('Missing source track')
        size=struct.unpack_from('>I',raw,cursor+4)[0];cursor+=8;end=cursor+size
        if end>len(raw):raise ValueError('Truncated source track')
        held={};tick=0;running=None
        def vlq():
            nonlocal cursor
            value=0
            for _ in range(4):
                if cursor>=end:raise ValueError('Truncated source event')
                b=raw[cursor];cursor+=1;value=(value<<7)|(b&127)
                if b<128:return value
            raise ValueError('Overlong source delta')
        def finish(key):
            if key in held:
                first,velocity=held.pop(key)
                if tick>first:notes.append(dict(tick=first,durationTicks=tick-first,channel=key[0],note=key[1],velocity=velocity))
        while cursor<end:
            tick+=vlq();status=raw[cursor]
            if status>=128:cursor+=1;running=status if status<240 else None
            elif running is not None:status=running
            else:raise ValueError('Missing running status')
            if status in (240,247,255):
                kind=raw[cursor] if status==255 else None
                if status==255:cursor+=1
                length=vlq();cursor+=length
                if cursor>end:raise ValueError('Truncated system payload')
            else:
                kind=status&240;channel=status&15;length=1 if kind in (192,208) else 2
                data=raw[cursor:cursor+length];cursor+=length
                if len(data)!=length or any(b>=128 for b in data):raise ValueError('Invalid source message')
                if kind not in (128,144):continue
                key=(channel,data[0]);finish(key)
                if kind==144 and data[1]:held[key]=(tick,data[1])
        for key in list(held):finish(key)
    if cursor!=len(raw):raise ValueError('Trailing source data')
    return ppq,sorted(notes,key=lambda n:(n['tick'],n['note']))


def score(role,positions,tones=(0,), *, meter=(4,4),short=True):
    length=F(4*meter[0],meter[1]);events=[];step=length/len(positions)
    hits=[i for i,b in enumerate(positions) if b=='1']
    for i,col in enumerate(hits):
        tone=tones[i%len(tones)];duration=step*F(3,4) if short else (hits[i+1]*step if i+1<len(hits) else length)-col*step
        event=new_event(role,col*step,duration,tone=tone,register=(36 if role=='bass' else 60)+(0,4,7)[tone%3]+12*(tone//3))
        event['id']='e_'+str(i);event['expression']['velocity']=.9 if col%4==0 else .7
        events.append(event)
    return events


def build(groove,piano,output):
    output.mkdir(parents=True,exist_ok=True);sources=output/'sources';sources.mkdir(exist_ok=True)
    archive=groove.read_bytes()
    if hashlib.sha256(archive).hexdigest()!=GMD_HASH:raise ValueError('GMD archive SHA-256 differs from official release')
    (sources/'groove-v1.0.0-midionly.zip').write_bytes(archive)
    piano_raw=piano.read_bytes()
    if hashlib.sha256(piano_raw).hexdigest()!=PIANO_HASH:raise ValueError('CC0 piano source differs from the verified collection source')
    (sources/'ypiano3basswithdrum.mid').write_bytes(piano_raw)
    clips=[];seen=set();midi_files={};report=collections.Counter()
    def admit(role,name,style,events,meter,origin,bar,source_file,source_hash,*,source_tempo=120,source_chord=None,section='Verse / chorus',changes=''):
        # Ignore velocity and absolute transposition when identifying a phrase.
        shape=[(e['beat'],e['duration'],e['choice']['tone'],e['choice']['soundIdentity'],e['choice']['registerMidi']) for e in events]
        if role in ('bass','lead') and shape:
            base=min(x[-1] for x in shape);shape=[(*x[:-1],x[-1]-base) for x in shape]
        key=hashlib.sha256(canonical_bytes([role,meter,shape])).hexdigest()
        if key in seen or not events:return False
        seen.add(key);cid=role+'_'+key[:20];length=F(4*meter[0],meter[1])
        for i,e in enumerate(events):e['id']='e_'+str(i)
        is_original=origin=='Raw Daw original';license='CC-BY-4.0' if origin=='Groove MIDI Dataset' else 'CC0-1.0'
        url=GMD_URL if license=='CC-BY-4.0' else PIANO_URL if not is_original else 'https://github.com/ShaelRiley/RawDaw'
        attribution='Groove MIDI Dataset, Google LLC; Gillick, Roberts, Engel, Eck and Bamman (2019).' if license=='CC-BY-4.0' else 'Tozan — Piano 3 Bass With Drums (2022).' if not is_original else 'Raw Daw original pattern collection.'
        changes=changes or 'One-bar original performance; released under CC0. Canonical C-major MIDI follows destination harmony on placement.'
        provenance=dict(sourceClip=f'{origin}: {source_file}, measure {bar}',license=license,changes=changes)
        pattern=dict(id='clip_'+key[:20],role=role,length=str(length),events=events,provenance=provenance)
        notes=[]
        for e in events:
            pitches=[GM[e['choice']['soundIdentity']]] if role=='drums' else [60,64,67] if role=='rhythm' else [e['choice']['registerMidi']]
            for pitch in pitches:notes.append(dict(beat=F(e['beat']),duration=F(e['duration']),note=pitch,channel=9 if role=='drums' else 0,velocity=e['expression']['velocity']))
        raw=encode_notes(notes,meter=meter,length=length);midi_files[cid+'.mid']=raw
        clips.append(dict(id=cid,name=name,role=role,style=style,section=section,meter=list(meter),hits=len(events),origin=origin,
            sourceUrl=url,license=license,attribution=attribution,sourceFile=source_file,sourceBar=bar,sourceSha256=source_hash,
            sourceTempo=source_tempo,inferredSourceChord=source_chord,midiSha256=hashlib.sha256(raw).hexdigest(),pattern=pattern))
        return True
    for role in ('bass','lead','rhythm'):
        contours=[(0,0,2,0),(0,1,2,1),(0,2,3,2)] if role=='bass' else [(0,1,2,1),(2,1,0,1),(0,2,3,1)]
        if role=='rhythm':contours=[(0,)]
        for name,rhythm,style in PULSES:
            for ci,tones in enumerate(contours):
                for short in ((True,False) if role=='rhythm' else (True,)):
                    events=score(role,rhythm,tones,short=short)
                    admit(role,name+(' · short' if short else ' · held')+(' · '+('root pocket','chord walk','octave turn')[ci] if role=='bass' else ' · '+('rising','falling','arch')[ci] if role=='lead' else ''),style,events,(4,4),'Raw Daw original',1,'original',hashlib.sha256(canonical_bytes(events)).hexdigest())
        for meter,label in [((3,4),'Waltz'),((6,8),'Compound')]:
            for index,rhythm in enumerate(['100010001000','101010101010','100000100000','001000001000','100101100101','100010100010','111010111010','100000000110']):
                for ci,tones in enumerate(contours):
                    admit(role,label+' '+str(index+1)+' · '+str(ci+1),label,score(role,rhythm,tones,meter=meter),meter,'Raw Daw original',1,'original',hashlib.sha256((label+rhythm+str(tones)).encode()).hexdigest())
    # Round-robin styles and performances; at most two selected bars per recording.
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        rows=list(csv.DictReader(z.read(next(n for n in z.namelist() if n.endswith('info.csv'))).decode().splitlines()))
        groups=collections.defaultdict(list)
        for row in rows:
            if row['time_signature']=='4-4':groups[row['style'].split('/')[0]].append(row)
        selected=collections.Counter();count=0
        for round_ in range(30):
            for style,items in sorted(groups.items()):
                if round_>=len(items) or count>=320:continue
                row=items[round_];fn=next(n for n in z.namelist() if n.endswith('/'+row['midi_filename']));raw=z.read(fn)
                try:ppq,notes=source_notes(raw)
                except (ValueError,IndexError,struct.error):report['source_parse_rejected']+=1;continue
                last=max((n['tick']+n['durationTicks'] for n in notes),default=0)
                for bar in range(1,min(last//(4*ppq),33)):
                    first=bar*4*ppq;part=[n for n in notes if first<=n['tick']<first+4*ppq and n['note'] in DRUM_MAP]
                    if not 5<=len(part)<=48 or not any(DRUM_MAP[n['note']]=='kick' for n in part):continue
                    events=[]
                    for n in part:
                        pos=F(n['tick']-first,ppq);duration=min(F(1,8),4-pos)
                        e=new_event('drums',pos,duration,DRUM_MAP[n['note']]);e['expression']['velocity']=n['velocity']/127;events.append(e)
                    if admit('drums',row['style'].replace('/',' · ').title()+' · '+row['beat_type']+' '+str(count+1),style.title(),events,(4,4),'Groove MIDI Dataset',bar+1,row['midi_filename'],hashlib.sha256(raw).hexdigest(),source_tempo=int(row['bpm']),section='Fill / transition' if row['beat_type']=='fill' else 'Verse / chorus',changes='Selected one complete 4/4 measure; raw timing/velocities retained, TD-11 sounds normalized to semantic kit roles, bounded one-shot gates, same-address source retriggers ended explicitly. Destination extras are mapped only to matching sounds.'):
                        count+=1;selected[row['id']]+=1
                    if selected[row['id']]>=2:break
    # Explicit source voices, rather than an invented automatic separator.
    ppq,notes=source_notes(piano_raw)
    for role,channel in [('bass',2),('lead',3),('rhythm',0)]:
        voice=[n for n in notes if n['channel']==channel];last=max(n['tick']+n['durationTicks'] for n in voice)
        for bar in range(last//(4*ppq)):
            first=bar*4*ppq;part=[n for n in voice if first<=n['tick']<first+4*ppq]
            if not 2<=len(part)<=24:continue
            attacks=collections.defaultdict(list)
            for n in part:attacks[n['tick']].append(n)
            # Coarse harmonic inference is curation metadata; destination is authoritative.
            pcs=collections.Counter(n['note']%12 for n in part)
            root,quality=max(((r,q) for r in range(12) for q in ('major','minor','diminished')),key=lambda rq:sum(pcs[(rq[0]+p)%12] for p in QUALITIES[rq[1]]))
            source_pitches=[(root+i)%12 for i in QUALITIES[quality]];events=[]
            for tick,chord_notes in sorted(attacks.items()):
                n=min(chord_notes,key=lambda n:n['note']) if role=='bass' else max(chord_notes,key=lambda n:n['note'])
                tone=min(range(3),key=lambda t:min((n['note']-source_pitches[t])%12,(source_pitches[t]-n['note'])%12))
                pos=F(tick-first,ppq);duration=min(F(max(v['durationTicks'] for v in chord_notes) if role=='rhythm' else n['durationTicks'],ppq),4-pos)
                register=max(28 if role=='bass' else 48,min(60 if role=='bass' else 84,n['note']))
                e=new_event(role,pos,duration,tone=tone,register=register);e['expression']['velocity']=n['velocity']/127;events.append(e)
            admit(role,'Tozan · '+role.title()+' phrase '+str(bar+1),'Piano pop',events,(4,4),'Piano 3 Bass With Drums',bar+1,'ypiano3basswithdrum.mid',hashlib.sha256(piano_raw).hexdigest(),source_tempo=None,source_chord=dict(root=root,quality=quality),changes=f'Explicit source channel {channel+1}; one-bar slice; simultaneous chord attacks collapsed for Chords or highest/lowest attack voice selected for melodic role; nearest inferred chord-tone relationship retained; register bounded; held gates clipped at loop boundary; destination chord governs playback. Source has no tempo event; canonical MIDI uses 120 qBPM.')
    # Compound/waltz kit grooves are authored explicitly for their own meters.
    for meter,label in [((3,4),'Waltz'),((6,8),'Compound')]:
        for variant in range(8):
            length=F(4*meter[0],meter[1]);events=[]
            for slot,hits in [('kick',[0,6] if variant%2 else [0]),('snare',[4,8] if meter==(3,4) else [6]),('hatClosed',list(range(0,12,1 if variant>=4 else 2)))]:
                for hit in hits:
                    pos=length*F(hit,12);e=new_event('drums',pos,F(1,8),slot);e['expression']['velocity']=.9 if slot!='hatClosed' else .65;events.append(e)
            if variant%4>=2:
                e=new_event('drums',length*F(11,12),F(1,8),'tom1');events.append(e)
            for i,e in enumerate(events):e['id']='e_'+str(i)
            admit('drums',label+' pocket '+str(variant+1),label,events,meter,'Raw Daw original',1,'original',hashlib.sha256(canonical_bytes(events)).hexdigest())
    clips.sort(key=lambda c:(c['role'],c['style'],c['name']))
    catalog=dict(format='raw-daw-clips-v1',version='2026.10.13',clips=clips,curation=dict(counts=dict(collections.Counter(c['role'] for c in clips)),origins=dict(collections.Counter(c['origin'] for c in clips)),rejections=dict(report)))
    (output/'index.json.gz').write_bytes(gzip.compress(canonical_bytes(catalog)+b'\n',mtime=0))
    with zipfile.ZipFile(output/'midi-clips.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(midi_files.items()):
            entry=zipfile.ZipInfo(name,(2026,10,13,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,raw)
    print(json.dumps(catalog['curation'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--groove',type=Path,required=True);p.add_argument('--piano',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'prde1/data/clips');a=p.parse_args();build(a.groove,a.piano,a.output)
