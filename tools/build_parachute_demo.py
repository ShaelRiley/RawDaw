"""Author a complete, editable song using only the existing Parachute bank.

This fixed demo score is not a general Song Plan generator or a source-song
transcription. Chords, phrasing and MIDI dynamics are authored metadata; the
Governor and native renderer retain sole responsibility for sample selection.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prde1.contracts import atomic_json
from prde1.governor import resolve
from prde1.pack import Pack
from prde1.project import load_project, save_project, validate_project

BPM = 165
CHORDS = {
    'i': dict(degree=1, quality='minor', inversion=0, alteration=0),
    'IIImaj7': dict(degree=3, quality='major7', inversion=0, alteration=0),
    'iv': dict(degree=4, quality='minor', inversion=0, alteration=0),
    'VI': dict(degree=6, quality='major', inversion=0, alteration=0),
    'V': dict(degree=5, quality='major', inversion=0, alteration=0),
}
FORM = (
    ('intro', 'Intro', 4, 'intro', ('i', 'i', 'VI', 'iv')),
    ('verse_1', 'Verse 1', 16, 'verse', ('i', 'IIImaj7', 'VI', 'iv')),
    ('pre_1', 'Pre-chorus 1', 8, 'pre', ('iv', 'iv', 'VI', 'VI', 'iv', 'VI', 'V', 'V')),
    ('chorus_1', 'Chorus 1', 16, 'chorus', ('i', 'VI', 'IIImaj7', 'iv')),
    ('verse_2', 'Verse 2', 16, 'verse_2', ('i', 'IIImaj7', 'VI', 'iv')),
    ('pre_2', 'Pre-chorus 2', 8, 'pre', ('iv', 'iv', 'VI', 'VI', 'iv', 'VI', 'V', 'V')),
    ('chorus_2', 'Chorus 2', 16, 'chorus', ('i', 'VI', 'IIImaj7', 'iv')),
    ('bridge', 'Bridge', 8, 'bridge', ('VI', 'VI', 'iv', 'iv', 'i', 'iv', 'VI', 'V')),
    ('final_chorus', 'Final chorus', 16, 'final', ('i', 'VI', 'IIImaj7', 'iv')),
    ('outro', 'Outro', 4, 'outro', ('VI', 'iv', 'V', 'i')),
)


def trigger(events, position, duration, kind, *, tone=0, register=65, velocity=.75,
            sound='', play=100, change=0, variation='none', locked=False):
    events.append(dict(id=f'event_{len(events)}', beat=str(Fraction(position)),
        duration=str(Fraction(duration)), enabled=True, kind=kind,
        choice=dict(exactMidi=None, registerMidi=register, soundIdentity=sound, tone=tone),
        expression=dict(velocity=round(velocity, 4), attackMs=0, playPercent=play,
                        changePercent=change, variation=variation, locked=locked, lockExactPitch=False)))


def phrase(family, role):
    events = []
    for bar in range(4):
        start = 4 * bar
        energy = (1 - .18 * bar) if family == 'outro' else 1
        def note(offset, tone=0, duration='1/2', velocity=.75, register=None, **expression):
            trigger(events, Fraction(start) + Fraction(offset), duration,
                    'chord' if role == 'rhythm' else 'note', tone=tone,
                    register=register or (36 if role == 'bass' else 69),
                    velocity=velocity * energy, **expression)
        def hit(offset, slot, velocity=.7, **expression):
            trigger(events, Fraction(start) + Fraction(offset), '1/4', 'drum',
                    sound='parachute_' + slot, velocity=velocity * energy, **expression)
        chorus = family in ('chorus', 'final')
        sparse = family in ('intro', 'bridge', 'outro')
        lift = family in ('pre_lift', 'bridge_lift')
        if role == 'rhythm':
            offsets = ('0', '1/2', '1', '3/2', '2', '5/2', '3', '7/2') if chorus else (
                ('0', '2') if sparse else ('0', '1/2', '2', '5/2', '7/2') if lift else ('0', '1/2', '2', '5/2'))
            if family == 'outro' and bar == 3:
                note('2', duration='7/4', velocity=.7)
            else:
                for n, offset in enumerate(offsets):
                    note(offset, duration='3/8' if chorus else '3/4', velocity=(.84 if chorus else .66) - .12 * (n % 2))
        elif role == 'bass':
            if family == 'intro' and bar < 2:
                continue
            offsets = ('0', '1', '2', '3', '7/2') if chorus or lift else ('0', '2', '7/2') if family == 'verse_2' else ('0', '2')
            if family == 'outro' and bar == 3:
                note('2', duration='2', velocity=.78, register=34)
            else:
                for n, offset in enumerate(offsets):
                    # Root remains covered even for F major: its prepared bass
                    # has no A/C. The lower root is a deliberate register choice.
                    note(offset, duration='3/4', velocity=.85 if n == 0 else .7,
                         play=94 if family == 'verse_2' and n == 2 else 100,
                         change=14 if family == 'verse_2' and n > 0 else 0, variation='gate')
        elif role == 'lead':
            if family == 'intro':
                if bar == 3:
                    note('2', tone=2, velocity=.65); note('3', tone=0, velocity=.6)
            elif chorus:
                hooks = (
                    (('0', 2), ('3/4', 1), ('3/2', 0), ('2', 1), ('3', 2)),
                    (('0', 1), ('1', 2), ('3/2', 1), ('5/2', 0), ('3', 1)),
                    (('0', 1), ('3/4', 2), ('3/2', 3), ('5/2', 1)),
                    (('0', 2), ('1', 1), ('2', 0), ('3', 2)),
                )
                for n, (offset, tone) in enumerate(hooks[bar]):
                    note(offset, tone=tone, duration='1/2', velocity=.88 if n == 0 else .76,
                         register=69, locked=True)
            elif family in ('bridge', 'bridge_lift'):
                tone = (1 if bar < 2 else 2) if family == 'bridge' else (2, 2, 1, 0)[bar]
                note('0', tone=tone, duration='3/2', velocity=.64, register=70)
                if family == 'bridge_lift':
                    note('5/2', tone=tone, velocity=.66, register=70)
            elif family == 'outro':
                if bar == 3:
                    note('2', tone=0, duration='3/2', velocity=.7, register=70)
                elif bar < 2:
                    note('1', tone=1 if bar == 0 else 2, velocity=.68, register=70)
            elif family in ('pre', 'pre_lift'):
                for offset, tone in (('0', 0), ('1', 1), ('2', 0), ('3', 2)):
                    note(offset, tone=tone, velocity=.7 if family == 'pre' else .8)
            else:
                note('1/2', tone=(0, 1, 1, 2)[bar], velocity=.64)
                note('2', tone=(1, 0, 2, 0)[bar], velocity=.61)
                if family == 'verse_2' or bar == 3:
                    note('3', tone=0, velocity=.6, play=95, change=12, variation='nearby_note')
        else:
            if family == 'intro':
                if bar >= 2:
                    hit('0', 'kick', .68)
                if bar == 3:
                    for offset in ('0', '1', '2', '3'):
                        hit(offset, 'hatClosed', .35)
                    hit('3', 'snare', .54)
            elif family == 'outro' and bar == 3:
                hit('2', 'kick', .74)
            else:
                kicks = ('0', '3/4', '2', '5/2', '7/2') if chorus else ('0', '2', '7/2') if not sparse else ('0',)
                for offset in kicks:
                    hit(offset, 'kick', .84 if chorus else .72)
                for offset in (('3',) if family.startswith('bridge') else ('1', '3')):
                    hit(offset, 'snare', .86 if chorus else .7)
                divisions = 8 if chorus or lift or family == 'verse_2' else 4
                for n in range(divisions):
                    hit(Fraction(4 * n, divisions), 'hatClosed', .54 if n % 2 == 0 else .36,
                        play=94 if family == 'verse_2' and n % 2 else 100)
                if bar == 3 and family != 'outro':
                    for n, offset in enumerate(('13/4', '7/2', '15/4') if lift or family == 'final' else ('15/4',)):
                        hit(offset, 'snare', .4 + n * .12)
    return events


def compose():
    project = copy.deepcopy(load_project(ROOT / 'packs/parachute_a.prdeproj'))
    project.update(projectId='parachute_full', title='Parachute — full-length demo', length='448',
                   patterns=[], instances=[], harmony=[], tonalityMap=[],
                   tempoMap=[dict(beat='0', quarterBpm=BPM)],
                   variation=dict(seed='parachute-full-demo-v1', revision=0),
                   editorContext=dict(selection='intro_rhythm_0', scrollBeat='0', zoom=.35,
                                      lastAction='Full-length Parachute demo authored'))
    project['credits'].append(dict(source='PRDE1 full-length demo score', license='MIT (arrangement metadata only)',
        attribution='Authored for Shael Riley; source audio retains its separate Suno paid-account declaration.',
        changes='New 112-bar form, recurring hook, section voicings, phrasing and MIDI dynamics; no source audio altered.'))
    patterns = {}
    sections = []
    cursor = 0
    for section_id, label, bars, family, chords in FORM:
        start = cursor
        for bar in range(bars):
            chord = chords[bar % len(chords)]
            position = str(4 * (start + bar))
            project['harmony'].append(dict(beat=position, chord=copy.deepcopy(CHORDS[chord])))
            mode = 'harmonic_minor' if chord == 'V' else 'natural_minor'
            if not project['tonalityMap'] or project['tonalityMap'][-1]['mode'] != mode:
                project['tonalityMap'].append(dict(beat=position, tonic=10, mode=mode))
        for phrase_index in range(bars // 4):
            style = family
            if family in ('pre', 'bridge') and phrase_index == 1:
                style += '_lift'
            for role in ('rhythm', 'bass', 'lead', 'drums'):
                # The exact same lead hook returns in all three choruses. Other
                # sections and the final chorus's rhythm retain their contrast.
                key = ('chorus' if style == 'final' and role == 'lead' else style) + '_' + role
                if key not in patterns:
                    patterns[key] = dict(id=key, role=role, length='16', events=phrase(key.rsplit('_' + role, 1)[0], role),
                        provenance=dict(sourceClip='PRDE1 authored full-length Parachute demo',
                                        license='MIT (performance metadata; source samples retain their rights)',
                                        changes='New four-bar phrase; recurring uses are explicitly linked. No sample processing.'))
                if not patterns[key]['events']:
                    continue
                project['instances'].append(dict(id=f'{section_id}_{role}_{phrase_index}', patternId=key,
                                                 beat=str(4 * (start + 4 * phrase_index)), linked=False))
        cursor += bars
        sections.append(dict(id=section_id, name=label, startBar=start + 1, bars=bars,
                             startBeat=str(4 * start), endBeat=str(4 * cursor),
                             startSeconds=round(start * 240 / BPM, 6), endSeconds=round(cursor * 240 / BPM, 6),
                             chords=list(chords)))
    uses = Counter(instance['patternId'] for instance in project['instances'])
    for instance in project['instances']:
        instance['linked'] = uses[instance['patternId']] > 1
    project['patterns'] = [pattern for key, pattern in patterns.items() if key in uses]
    assert cursor == 112
    validate_project(project)
    return project, dict(project='parachute_full.prdeproj', quarterBpm=BPM, meter='4/4', bars=cursor,
                         durationSeconds=round(cursor * 240 / BPM, 6), sections=sections,
                         note='Companion score description, not native section-lock or generic Song Plan state.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'packs/parachute_full.prdeproj')
    args = parser.parse_args()
    project, score = compose()
    with Pack(ROOT / 'packs/parachute.prdepack') as pack:
        plan = resolve(project, pack)
        if plan['conflicts']:
            raise ValueError('Full demo has unresolved authored material: ' + json.dumps(plan['conflicts'][:5]))
    save_project(args.output, project)
    atomic_json(args.output.with_suffix('.arrangement.json'), score)
    print(f'{args.output}: {score["bars"]} bars, {score["durationSeconds"]:.3f} seconds, {len(plan["events"])} covered events')


if __name__ == '__main__':
    main()
