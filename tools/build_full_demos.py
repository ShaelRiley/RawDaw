"""Author three complete demo scores against the existing, immutable CC banks.

These are fixed compositions, not a generic Song Plan generator or source-song
transcriptions. Only metadata is authored here; the Governor selects prepared
assets and the native renderer plays them at their original rate.
"""
from __future__ import annotations

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
from tools.build_parachute_demo import trigger


def chord(degree, quality):
    return dict(degree=degree, quality=quality, inversion=0, alteration=0)


PROFILES = {
    'reach_out': dict(title='Reach Out', bpm=113, tonic=11, mode='natural_minor',
        bars=(4, 8, 4, 12, 8, 4, 12, 8, 8, 4),
        chords={'Bm': chord(1, 'minor'), 'G': chord(6, 'major'), 'A': chord(7, 'major')},
        harmony={
            'intro': ('Bm', 'Bm', 'G', 'A'), 'verse': ('Bm', 'G', 'A', 'Bm'),
            'pre': ('G', 'G', 'A', 'A'), 'chorus': ('G', 'A', 'Bm', 'Bm'),
            'bridge': ('G', 'G', 'Bm', 'A'), 'outro': ('G', 'A', 'A', 'Bm')},
        style='Acoustic pop: syncopated guitar, electric lead hook, half-time bridge.'),
    'where_you_are_now': dict(title='Where You Are Now', bpm=100, tonic=0, mode='natural_minor',
        bars=(4, 8, 4, 8, 8, 4, 8, 8, 8, 4),
        chords={'Cm': chord(1, 'minor'), 'Ab': chord(6, 'major'),
                'Bb': chord(7, 'major'), 'F': chord(4, 'major')},
        harmony={
            'intro': ('Cm', 'Cm', 'Ab', 'Bb'), 'verse': ('Cm', 'Ab', 'Bb', 'Cm'),
            'pre': ('Ab', 'Bb', 'Ab', 'Bb'), 'chorus': ('Cm', 'F', 'Bb', 'Cm'),
            'bridge': ('Ab', 'Ab', 'Bb', 'Cm'), 'outro': ('Bb', 'Ab', 'Bb', 'Cm')},
        style='Synth pop: short vocal calls, a Dorian chorus lift, four-on-the-floor refrain.'),
    'auld_lang_syne_bossa': dict(title='Auld Lang Syne (Bossa)', bpm=130, tonic=5, mode='major',
        bars=(4, 12, 4, 16, 12, 4, 16, 8, 8, 4),
        chords={'F': chord(1, 'major'), 'C7': chord(5, 'dominant7'),
                'Dm': chord(6, 'minor'), 'Bbmaj7': chord(4, 'major7')},
        harmony={
            'intro': ('F', 'F', 'Bbmaj7', 'C7'), 'verse': ('F', 'Dm', 'Bbmaj7', 'C7'),
            'pre': ('Dm', 'Bbmaj7', 'C7', 'C7'), 'chorus': ('F', 'C7', 'Bbmaj7', 'F'),
            'bridge': ('Dm', 'Bbmaj7', 'F', 'C7'), 'outro': ('Bbmaj7', 'C7', 'C7', 'F')},
        style='Bossa: piano anticipations, hand percussion and a melodic call-and-response.'),
}
FORM = (
    ('intro', 'Intro', 'intro'), ('verse_1', 'Verse 1', 'verse'),
    ('pre_1', 'Pre-chorus 1', 'pre'), ('chorus_1', 'Chorus 1', 'chorus'),
    ('verse_2', 'Verse 2', 'verse_2'), ('pre_2', 'Pre-chorus 2', 'pre'),
    ('chorus_2', 'Chorus 2', 'chorus'), ('bridge', 'Bridge', 'bridge'),
    ('final_chorus', 'Final chorus', 'final'), ('outro', 'Outro', 'outro'),
)
SOUNDS = {
    'reach_out': dict(kick='kick', snare='snare', hat='closed_hat', accent='crash'),
    'where_you_are_now': dict(kick='kick', snare='snare', hat='closed_hat',
                             accent='cymbal', bright='bright_backbeat'),
    'auld_lang_syne_bossa': dict(kick='kick', snare='snare', hat='closed_hat',
                               low='hand_perc_low', high='hand_perc_high'),
}


def phrase(pack_id, family, role):
    events = []
    chorus = family in ('chorus', 'final')
    bridge = family.startswith('bridge')
    sparse = family in ('intro', 'outro') or bridge
    lift = family.endswith('_lift')
    for bar in range(4):
        energy = 1 - .18 * bar if family == 'outro' else 1
        def note(offset, tone=0, duration='1/2', velocity=.72, register=None, **expression):
            trigger(events, 4 * bar + Fraction(offset), duration,
                    'chord' if role == 'rhythm' else 'note', tone=tone,
                    register=register or (36 if role == 'bass' else 65),
                    velocity=velocity * energy, **expression)
        def hit(offset, slot, velocity=.65):
            trigger(events, 4 * bar + Fraction(offset), '1/4', 'drum',
                    sound=pack_id + '_source_' + SOUNDS[pack_id][slot], velocity=velocity * energy)

        if family == 'outro' and bar == 3:
            # An authored tonic cadence, including a final short pickup; no
            # silence padding or unsupported sustain of a one-shot sample.
            if role == 'drums':
                hit('0', 'kick', .6)
                if pack_id == 'auld_lang_syne_bossa': hit('2', 'low', .4)
            else:
                for offset in (('0', '2', '3') if role != 'lead' else ('2', '3')):
                    note(offset, tone=0, duration='1/2', velocity=.7)
            continue

        if role == 'rhythm':
            if pack_id == 'reach_out':
                offsets = ('0', '1/2', '3/2', '2', '5/2', '7/2') if chorus else (
                    ('0', '2') if sparse else ('0', '1/2', '2', '5/2', '7/2') if lift else ('0', '1/2', '2', '5/2'))
                gate = '3/8' if chorus else '3/4'
            elif pack_id == 'where_you_are_now':
                offsets = ('0', '1', '2', '3') if chorus else (
                    ('0', '2') if sparse else ('0', '3/2', '5/2') if lift else ('0', '2', '7/2'))
                gate = '7/8' if chorus or sparse else '3/4'
            else:
                offsets = ('0', '1/2', '3/2', '5/2', '7/2') if chorus else (
                    ('0', '5/2') if sparse else ('0', '3/2', '5/2', '7/2'))
                # The prepared C7 is only .2 seconds. Its articulation is
                # intentionally a short stab, rather than invented sustain.
                gate = '3/8'
            for n, offset in enumerate(offsets):
                note(offset, duration=gate, velocity=(.78 if chorus else .61) - .1 * (n % 2))
        elif role == 'bass':
            if family == 'intro' and bar < 2: continue
            if pack_id == 'reach_out':
                offsets = ('0', '3/2', '2', '7/2') if chorus or lift else ('0', '2', '7/2') if family == 'verse_2' else ('0', '2')
                tones = (0, 2, 0, 1)
            elif pack_id == 'where_you_are_now':
                offsets = ('0', '1/2', '3/2', '2', '5/2', '7/2') if chorus else ('0', '2', '7/2') if lift or family == 'verse_2' else ('0', '2')
                tones = (0, 0, 2, 0, 0, 1)
            else:
                offsets = ('0', '3/2', '2', '7/2') if chorus or lift else ('0', '2')
                tones = (0, 2, 0, 2)
            for n, offset in enumerate(offsets):
                note(offset, tone=tones[n], duration='3/4' if n % 2 == 0 else '3/8',
                     velocity=.82 if n % 2 == 0 else .64,
                     play=96 if family == 'verse_2' and n > 1 else 100)
        elif role == 'lead':
            gate = '1/4' if pack_id == 'where_you_are_now' else '1/2'
            if chorus:
                if pack_id == 'reach_out':
                    hooks = (
                        (('0', 2), ('3/4', 1), ('3/2', 0), ('5/2', 1), ('3', 2)),
                        (('0', 0), ('1', 1), ('3/2', 2), ('5/2', 1), ('7/2', 0)),
                        (('0', 2), ('1', 1), ('2', 0), ('3', 1)),
                        (('0', 1), ('3/4', 2), ('2', 1), ('3', 0)),
                    )
                elif pack_id == 'where_you_are_now':
                    hooks = (
                        (('0', 0), ('3/4', 1), ('5/4', 1), ('2', 2), ('11/4', 0), ('7/2', 1)),
                        (('0', 2), ('3/4', 1), ('5/4', 0), ('2', 2), ('11/4', 1), ('7/2', 2)),
                        (('0', 0), ('3/4', 2), ('3/2', 1), ('2', 0), ('3', 2)),
                        (('0', 1), ('1', 0), ('7/4', 1), ('5/2', 2), ('7/2', 0)),
                    )
                else:
                    hooks = (
                        (('0', 2), ('1', 1), ('3/2', 2), ('5/2', 1)),
                        (('1/2', 2), ('3/2', 1), ('2', 3), ('3', 2)),
                        (('0', 1), ('1', 2), ('3/2', 3), ('5/2', 1), ('7/2', 3)),
                        (('0', 2), ('3/2', 1), ('5/2', 2), ('3', 1)),
                    )
                for n, (offset, tone) in enumerate(hooks[bar]):
                    note(offset, tone=tone, duration=gate, velocity=.85 if n == 0 else .74, locked=True)
            elif family == 'intro':
                if bar == 3:
                    note('2', tone=2, duration=gate, velocity=.57)
                    note('3', tone=0, duration=gate, velocity=.62)
            elif bridge:
                for offset, tone in (('0', (1, 2, 1, 0)[bar]), ('5/2', 0)) if lift else (('1', (1, 2, 1, 0)[bar]),):
                    note(offset, tone=tone, duration=gate, velocity=.58, register=59)
            elif family == 'outro':
                note('1', tone=1 if bar == 0 else 2, duration=gate, velocity=.61)
            elif family.startswith('pre'):
                for offset, tone in (('0', 0), ('3/2', 1), ('5/2', 2), ('7/2', 1)):
                    note(offset, tone=tone, duration=gate, velocity=.71 if lift else .65)
            else:
                offsets = ('1/2', '2') if pack_id != 'auld_lang_syne_bossa' else ('0', '3/2', '3')
                for n, offset in enumerate(offsets):
                    note(offset, tone=((0, 1, 2, 0)[bar] + n) % 3, duration=gate, velocity=.62 - .05 * (n % 2))
                if family == 'verse_2' or bar == 3:
                    note('7/2', tone=0, duration=gate, velocity=.59,
                         play=96, change=12 if family == 'verse_2' else 0, variation='nearby_note')
        else:
            if family == 'intro':
                if bar >= 2: hit('0', 'kick', .65)
                if bar == 3:
                    for offset in ('0', '1', '2', '3'): hit(offset, 'hat', .32)
                    hit('3', 'snare', .5)
                continue
            if pack_id == 'reach_out':
                for offset in (('0', '3/4', '2', '7/2') if chorus else ('0',) if bridge else ('0', '2')):
                    hit(offset, 'kick', .82 if chorus else .68)
                for offset in (('3',) if bridge else ('1', '3')): hit(offset, 'snare', .83 if chorus else .67)
                divisions = 8 if chorus or lift or family == 'verse_2' else 4
                for n in range(divisions): hit(Fraction(4*n, divisions), 'hat', .47 if n % 2 == 0 else .3)
                if chorus and bar == 0: hit('0', 'accent', .45)
            elif pack_id == 'where_you_are_now':
                for offset in (('0', '1', '2', '3') if chorus else ('0',) if bridge else ('0', '3/2', '2')):
                    hit(offset, 'kick', .85 if chorus else .69)
                for offset in (('3',) if bridge else ('1', '3')):
                    hit(offset, 'snare', .76 if chorus else .64)
                    if chorus: hit(offset, 'bright', .44)
                divisions = 8 if chorus or lift or family == 'verse_2' else 4
                for n in range(divisions): hit(Fraction(4*n, divisions), 'hat', .4 if n % 2 == 0 else .5)
                if chorus and bar == 0: hit('0', 'accent', .32)
            else:
                for offset in ('0', '2'): hit(offset, 'kick', .58 if sparse else .69)
                for offset in ('1', '3'): hit(offset, 'snare', .36 if sparse else .47)
                for offset in ('0', '3/2', '2'): hit(offset, 'low', .51 if sparse else .66)
                for n, offset in enumerate(('1/2', '1', '5/2', '3', '7/2') if chorus else ('1', '5/2', '3')):
                    hit(offset, 'high', .5 if n % 2 == 0 else .39)
                for offset in ('0', '1', '2', '3'): hit(offset, 'hat', .28 if sparse else .37)
            if bar == 3 and (lift or family == 'final'):
                for n, offset in enumerate(('13/4', '7/2', '15/4')):
                    hit(offset, 'high' if pack_id == 'auld_lang_syne_bossa' else 'snare', .38 + .1*n)
    return events


def compose(pack_id):
    profile = PROFILES[pack_id]
    project = copy.deepcopy(load_project(ROOT / 'packs' / (pack_id + '_a.prdeproj')))
    project.update(projectId=pack_id + '_full', title=profile['title'] + ' — full-length demo',
        length=str(4 * sum(profile['bars'])), patterns=[], instances=[], harmony=[], tonalityMap=[],
        tempoMap=[dict(beat='0', quarterBpm=profile['bpm'])],
        variation=dict(seed=pack_id + '-full-demo-v1', revision=0),
        editorContext=dict(selection='intro_rhythm_0', scrollBeat='0', zoom=.4,
                           lastAction='Full-length demo authored'))
    project['credits'].append(dict(source='PRDE1 full-length demo score',
        license='MIT (arrangement metadata only)',
        attribution='Authored for Shael Riley; source audio retains the credited CC BY 3.0 license.',
        changes='New complete form, recurring hook, section phrasing and MIDI dynamics; no source audio altered.'))
    patterns, sections, cursor = {}, [], 0
    for (section_id, label, family), bars in zip(FORM, profile['bars']):
        harmonic_family = {'verse_2': 'verse', 'final': 'chorus'}.get(family, family)
        chords = profile['harmony'][harmonic_family]
        start = cursor
        for bar in range(bars):
            name = chords[bar % 4]
            tonic, mode = profile['tonic'], profile['mode']
            shape = profile['chords'][name]
            if pack_id == 'where_you_are_now' and harmonic_family == 'chorus':
                mode = 'dorian'  # F major's A is legal; Ab returns in the verses.
            elif pack_id == 'auld_lang_syne_bossa' and family == 'bridge':
                tonic, mode = 2, 'natural_minor'
                shape = dict(Dm=chord(1, 'minor'), Bbmaj7=chord(6, 'major7'),
                             F=chord(3, 'major'), C7=chord(7, 'dominant7'))[name]
            position = str(4 * (start + bar))
            project['harmony'].append(dict(beat=position, chord=copy.deepcopy(shape)))
            if not project['tonalityMap'] or (project['tonalityMap'][-1]['tonic'], project['tonalityMap'][-1]['mode']) != (tonic, mode):
                project['tonalityMap'].append(dict(beat=position, tonic=tonic, mode=mode))
        for phrase_index in range(bars // 4):
            style = family + '_lift' if family in ('pre', 'bridge') and (phrase_index == 1 or section_id == 'pre_2') else family
            for role in ('rhythm', 'bass', 'lead', 'drums'):
                # Keep the chorus hook's identity through the final reprise;
                # accompany it with a fuller rhythm and percussion ending.
                pattern_family = 'chorus' if style == 'final' and role == 'lead' else style
                key = pattern_family + '_' + role
                if key not in patterns:
                    patterns[key] = dict(id=key, role=role, length='16', events=phrase(pack_id, pattern_family, role),
                        provenance=dict(sourceClip='PRDE1 authored full-length ' + profile['title'] + ' demo',
                            license='MIT (performance metadata; source samples retain their rights)',
                            changes='New four-bar phrase, explicitly linked recurrences; no sample processing.'))
                if patterns[key]['events']:
                    project['instances'].append(dict(id=f'{section_id}_{role}_{phrase_index}', patternId=key,
                        beat=str(4 * (start + 4 * phrase_index)), linked=False))
        cursor += bars
        sections.append(dict(id=section_id, name=label, startBar=start + 1, bars=bars,
            startBeat=str(4 * start), endBeat=str(4 * cursor), chords=list(chords),
            startSeconds=round(start * 240 / profile['bpm'], 6), endSeconds=round(cursor * 240 / profile['bpm'], 6)))
    uses = Counter(instance['patternId'] for instance in project['instances'])
    for instance in project['instances']: instance['linked'] = uses[instance['patternId']] > 1
    project['patterns'] = [pattern for key, pattern in patterns.items() if key in uses]
    validate_project(project)
    return project, dict(project=pack_id + '_full.prdeproj', quarterBpm=profile['bpm'], meter='4/4', bars=cursor,
        durationSeconds=round(cursor * 240 / profile['bpm'], 6), style=profile['style'], sections=sections,
        note='Fixed authored score description, not native section-lock or generic Song Plan state. Not a source-song transcription.')


def main():
    for pack_id in PROFILES:
        project, score = compose(pack_id)
        with Pack(ROOT / 'packs' / (pack_id + '.prdepack')) as pack:
            plan = resolve(project, pack)
            if plan['conflicts']:
                raise ValueError(pack_id + ': uncovered authored material: ' + json.dumps(plan['conflicts'][:5]))
        target = ROOT / 'packs' / (pack_id + '_full.prdeproj')
        save_project(target, project)
        atomic_json(target.with_suffix('.arrangement.json'), score)
        print(f'{target.name}: {score["bars"]} bars, {score["durationSeconds"]:.3f} seconds, {len(plan["events"])} covered events')


if __name__ == '__main__':
    main()
