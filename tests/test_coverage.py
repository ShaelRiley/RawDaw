"""Musical coverage, actual PCM, stable preparation and hybrid playback."""
import copy
import hashlib
import json
import math
import subprocess
import tempfile
import unittest
import wave
from fractions import Fraction
from pathlib import Path

from prde1.contracts import ROOT, RATE, canonical_bytes
from prde1.editor import Editor
from prde1.governor import rank_progressions, resolve
from prde1.music import MODES, QUALITIES, REGISTERS
from prde1.pack import Pack
from prde1.project import load_project, save_project
from tools.build_fixture import make_fixture, event


class CompleteCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.path = make_fixture(cls.root / 'fixture', extras=2)
        cls.project = load_project(cls.root / 'fixture/major.prdeproj')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_modes_keys_progressions_rank_playable_without_materializing_catalog(self):
        with Pack(self.path) as pack:
            before = len(pack.samples)
            for tonic in range(12):
                for mode in MODES:
                    for row in rank_progressions(pack, tonic, mode):
                        self.assertTrue(row['playable'])
                        self.assertEqual(row['missing'], [])
            self.assertEqual(len(pack.samples), before)

    def test_every_registered_note_is_real_nonzero_pcm_and_native_samples_win(self):
        with Pack(self.path) as pack:
            for key, native in pack.mappings.items():
                self.assertIs(pack.sample_for(key), native)
            for role, (low, high) in REGISTERS.items():
                for note in range(low, high + 1):
                    sample = pack.sample_for((role, note))
                    self.assertEqual(sample['pitches'], [note])
                    with wave.open(str(pack.root / sample['path'])) as audio:
                        self.assertTrue(any(audio.readframes(audio.getnframes())))

    def test_borrowed_chord_and_fourth_tone_on_a_triad_play_and_reopen_identically(self):
        project = copy.deepcopy(self.project)
        project['harmony'] = [dict(beat='0', chord=dict(degree=1, alteration=0, quality='minor7', inversion=3))]
        project['patterns'][2]['events'][0]['choice']['tone'] = 6
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with Pack(self.path) as pack:
            plan = resolve(project, pack)
            self.assertEqual(plan['conflicts'], [])
            for voice in plan['events']:
                if voice['role'] in ('bass', 'lead', 'rhythm'):
                    self.assertTrue({n % 12 for n in voice['notePitches']}.issubset({0, 3, 7, 10}))
            rhythm = next(v for v in plan['events'] if v['role'] == 'rhythm')
            self.assertEqual(min(rhythm['notePitches']) % 12, 10)
            self.assertEqual(rhythm['endFrame'], RATE * 2)
            editor = Editor(project, pack)
            self.assertTrue(editor.covered_notes('lead', Fraction(0)))
            saved = self.root / 'hybrid.prdeproj'; save_project(saved, project)
            pcm_hashes = {s['id']: s['sha256'] for s in pack.samples.values() if s['id'].startswith('hybrid_')}
        with Pack(self.path) as reopened:
            self.assertEqual(resolve(load_project(saved), reopened), plan)
            self.assertEqual({s['id']: s['sha256'] for s in reopened.samples.values() if s['id'].startswith('hybrid_')}, pcm_hashes)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), digest)

    def test_generated_chord_has_every_expected_fundamental_in_actual_pcm(self):
        with Pack(self.path) as pack:
            for quality in QUALITIES:
                sample = pack.sample_for(('rhythm', 1, quality, len(QUALITIES[quality]) - 1))
                with wave.open(str(pack.root / sample['path'])) as audio:
                    audio.setpos(sample['loop']['startFrame'])
                    raw = audio.readframes(RATE)
                values = [int.from_bytes(raw[i:i + 3], 'little', signed=True) / 8388608 for i in range(0, len(raw), 12)]
                for note in sample['pitches']:
                    frequency = round(440 * 2 ** ((note - 69) / 12))
                    step = math.tau * frequency / (RATE / 4)
                    magnitude = math.hypot(sum(v * math.cos(i * step) for i, v in enumerate(values)),
                                           sum(v * math.sin(i * step) for i, v in enumerate(values))) * 2 / len(values)
                    self.assertGreater(magnitude, .003, (quality, note, magnitude))

    def test_odd_length_native_attack_can_sustain_with_a_seamless_valid_riff_loop(self):
        with Pack(self.path) as pack:
            native = pack.mappings[('lead', 64)]
            odd = dict(native, id=native['id'] + '_odd', onsetFrame=native['onsetFrame'] + 1)
            sample = pack.coverage.sustain(odd)
            raw = (pack.root / sample['path']).read_bytes()
            self.assertEqual(pack._wav(raw, sample['path']), (1, sample['frames']))
            with wave.open(str(pack.root / sample['path'])) as audio:
                pcm = audio.readframes(audio.getnframes())
            a = (sample['loop']['startFrame'] - 1) * 3
            b = (sample['loop']['endFrame'] - 1) * 3
            self.assertEqual(pcm[a:a + 3], pcm[b:b + 3])

    def test_native_export_of_all_qualities_inversions_and_roots_has_no_silent_events(self):
        project = copy.deepcopy(self.project)
        with Pack(self.path) as pack:
            for quality, intervals in QUALITIES.items():
                chords = [dict(degree=1, alteration=0, quality=quality, inversion=i) for root in range(12) for i in range(len(intervals))]
                count = len(chords); project['length'] = str(count)
                project['tonalityMap'] = [dict(beat=str(index), tonic=index // len(intervals), mode='major') for index in range(count)]
                project['harmony'] = [dict(beat=str(index), chord=chord) for index, chord in enumerate(chords)]
                project['patterns'] = [dict(id='coverage', role='rhythm', length=str(count),
                    events=[event('chord_' + str(index), index, '1', 'chord') for index in range(count)],
                    provenance=dict(sourceClip='coverage test', license='MIT', changes='none'))]
                project['instances'] = [dict(id='coverage_instance', patternId='coverage', beat='0', linked=False)]
                plan = resolve(project, pack)
                self.assertEqual(plan['conflicts'], [])
                self.assertEqual(len(plan['events']), count)
                plan_path = self.root / 'coverage.json'; plan_path.write_bytes(canonical_bytes(plan))
                output = self.root / 'coverage.wav'
                result = subprocess.run([str(ROOT / 'build/prde1-render'), str(plan_path), str(pack.root), str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['eventCount'], count)
                with wave.open(str(output)) as audio:
                    for index in range(count):
                        audio.setpos(index * RATE // 2 + 2400)
                        raw = audio.readframes(2048)
                        peak = max(abs(int.from_bytes(raw[i:i + 3], 'little', signed=True)) for i in range(0, len(raw), 3))
                        self.assertGreater(peak, 1000, (quality, index))
