"""Bounded SMF structural reader. Import/adaptation UI is a later checkpoint.

MIDI is data. Track control messages are reported, not executed or allowed to
change project tempo, program, pitch, or pack selection.
"""
from __future__ import annotations

import struct
from .contracts import ContractError


def inspect_midi(raw:bytes):
    if len(raw)<14 or len(raw)>4*1024*1024 or raw[:8]!=b"MThd\x00\x00\x00\x06":
        raise ContractError("Invalid/budget-exceeding Standard MIDI File")
    format_,tracks,division=struct.unpack_from(">HHH",raw,8)
    if format_ not in (0,1) or not 1<=tracks<=32 or (format_==0 and tracks!=1) or not 1<=division<=32767:
        raise ContractError("Only PPQ SMF types 0 and 1 supported by this contract")
    cursor=14
    notes=[]
    controls=set()
    for _ in range(tracks):
        if cursor+8>len(raw) or raw[cursor:cursor+4]!=b"MTrk":
            raise ContractError("Missing MIDI track chunk")
        size=struct.unpack_from(">I",raw,cursor+4)[0]
        cursor+=8
        end=cursor+size
        if end>len(raw):raise ContractError("Truncated MIDI track")
        tick=0; running=None; held={}; finished=False; events=0
        def variable():
            nonlocal cursor
            value=0
            for _ in range(4):
                if cursor>=end:raise ContractError("Truncated MIDI variable length")
                byte=raw[cursor];cursor+=1;value=(value<<7)|(byte&127)
                if byte<128:return value
            raise ContractError("Overlong MIDI variable length")
        while cursor<end:
            if finished:raise ContractError("Data after MIDI end-of-track")
            tick+=variable();events+=1
            if events>100000 or tick>division*65536 or cursor>=end:raise ContractError("MIDI event/time budget exceeded")
            status=raw[cursor]
            if status>=128:
                cursor+=1
                running=status if status<240 else None
            elif running is not None:
                status=running
            else:raise ContractError("MIDI running status has no preceding channel message")
            if status in (240,247,255):
                if status==255:
                    if cursor>=end:raise ContractError("Missing MIDI meta type")
                    kind=raw[cursor];cursor+=1
                else:kind=None
                length=variable()
                if cursor+length>end:raise ContractError("Truncated MIDI system/meta payload")
                if kind==47:
                    if length:raise ContractError("Invalid MIDI end-of-track length")
                    finished=True
                elif kind==81:controls.add("source_tempo")
                elif kind==88:controls.add("source_meter")
                elif status in (240,247):controls.add("ignored_sysex")
                cursor+=length
            elif 128<=status<=239:
                kind=status&240; channel=status&15; length=1 if kind in (192,208) else 2
                if cursor+length>end or any(byte>=128 for byte in raw[cursor:cursor+length]):
                    raise ContractError("Invalid MIDI channel payload")
                first=raw[cursor];second=raw[cursor+1] if length==2 else None;cursor+=length
                key=(channel,first)
                if kind==144 and second:
                    if key in held:raise ContractError("Overlapping same-address MIDI notes require explicit voice interpretation")
                    held[key]=(tick,second)
                elif kind==128 or (kind==144 and not second):
                    if key not in held:raise ContractError("Unmatched MIDI note-off")
                    start,velocity=held.pop(key)
                    if tick<=start:raise ContractError("Nonpositive MIDI note duration")
                    notes.append({"tick":start,"durationTicks":tick-start,"channel":channel,"note":first,"velocity":velocity})
                elif kind==176:controls.add("ignored_controller")
                elif kind==192:controls.add("ignored_program_change")
                elif kind==224:controls.add("ignored_pitch_bend")
                else:controls.add("ignored_pressure")
            else:raise ContractError("Unsupported MIDI system event")
        if not finished or held:raise ContractError("Missing end-of-track or dangling MIDI notes")
    if cursor!=len(raw):raise ContractError("Extra MIDI chunks/trailing data")
    return {"format":format_,"tracks":tracks,"ticksPerQuarter":division,"notes":sorted(notes,key=lambda n:(n["tick"],n["channel"],n["note"])),"controls":sorted(controls)}
