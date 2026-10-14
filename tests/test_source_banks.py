"""Actual source waveform reuse, stereo identity, cache repair and bank bounds."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from prde1.contracts import ContractError, RATE, ROOT, canonical_bytes
from prde1.coverage import Coverage, VERSION, chord_notes
from prde1.music import QUALITIES
from prde1.pack import Pack
from prde1.editor import Editor, new_project
from prde1.project import load_project, save_project
from fractions import Fraction
from prde1.source_waveform import (normalize, pitch_shift, read_pcm,
                                  separate_chord, sustain_loop)
from tools.build_fixture import make_fixture


class SourceWaveforms(unittest.TestCase):
    def test_rate_warp_uses_recorded_phase_and_channels_without_new_oscillators(self):
        # Aperiodic source fingerprint and opposite stereo phases survive the
        # actual octave warp. This cannot pass an unrelated instrument model.
        rng = np.random.default_rng(12)
        source = rng.normal(0, .03, 8192)
        stereo = np.stack((source, -source), axis=1)
        self.assertTrue(np.array_equal(pitch_shift(stereo, 0), stereo))
        shifted = pitch_shift(stereo, 12)
        self.assertEqual(len(shifted), 4096)
        self.assertLess(np.max(np.abs(shifted[:, 0] + shifted[:, 1])), 1e-12)
        original = np.fft.rfft(stereo, axis=0)
        transformed = np.fft.rfft(shifted, axis=0)
        self.assertTrue(np.allclose(transformed[:-1], original[:len(transformed)-1] / 2, atol=1e-12))

    def test_polyphonic_demixing_retains_source_channel_images_and_real_pitch_energy(self):
        positions = np.arange(RATE // 2) / RATE
        a = np.sin(2 * np.pi * 440 * positions) * .15
        b = np.cos(2 * np.pi * 523.2511306 * positions) * .12
        stereo = np.stack((a, b), axis=1)
        separated = separate_chord(stereo, [69, 72])
        self.assertGreater(np.sqrt(np.mean(separated[69][:, 0] ** 2)), .08)
        self.assertLess(np.sqrt(np.mean(separated[69][:, 1] ** 2)), .02)
        self.assertGreater(np.sqrt(np.mean(separated[72][:, 1] ** 2)), .06)
        self.assertLess(np.sqrt(np.mean(separated[72][:, 0] ** 2)), .02)
        with self.assertRaisesRegex(ContractError, 'source crop|Source crop'):
            normalize(np.zeros((10000, 2)))

    def test_recorded_sustain_loop_preserves_stereo_seam_and_extended_chord_bass(self):
        t = np.arange(RATE // 2) / RATE
        stereo = np.stack((np.sin(2 * np.pi * 220 * t), np.cos(2 * np.pi * 220 * t)), axis=1) * .1
        held, loop = sustain_loop(stereo, minimum_note=57)
        self.assertTrue(np.array_equal(held[loop['endFrame']-1], held[loop['startFrame']-1]))
        for quality, intervals in QUALITIES.items():
            for inversion in range(len(intervals)):
                notes = chord_notes(1, quality, inversion)
                self.assertEqual(min(notes) % 12, (1 + intervals[inversion]) % 12)
                self.assertEqual({n % 12 for n in notes}, {(1 + n) % 12 for n in intervals})

    def test_extreme_mono_loop_length_preserves_target_pitch_instead_of_detuning_seam(self):
        # Exact developer sine isolates loop tuning from source-crop estimates.
        source_note = 64
        source_frequency = 440 * 2 ** ((source_note - 69) / 12)
        source = (.2 * np.sin(2 * np.pi * source_frequency * np.arange(RATE) / RATE))[:, None]
        for note in (0, 12, 48, 84, 127):
            audio, loop = sustain_loop(pitch_shift(source, note-source_note), minimum_note=note, pitch_note=note)
            frequency = 440 * 2 ** ((note - 69) / 12)
            length = loop['endFrame'] - loop['startFrame']
            cycles = round(length * frequency / RATE)
            self.assertLessEqual(abs(length - cycles * RATE / frequency), .500001)
            self.assertTrue(np.array_equal(audio[loop['endFrame']-1], audio[loop['startFrame']-1]))


class SourceBankPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.path = make_fixture(cls.root / 'fixture', extras=1)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_nearest_seed_hash_and_cache_reuse_survive_corrupt_metadata(self):
        with patch.dict(os.environ, {'RAW_DAW_BANK_CACHE': str(self.root / 'cache')}):
            with Pack(self.path) as pack:
                prepared = pack.sample_for(('lead', 125))
                self.assertEqual(prepared['lineage']['kind'], 'pre-rendered')
                source = pack.coverage.original_mappings[('lead', 71)]
                self.assertEqual(prepared['lineage']['sourceAsset'], source['id'] + ':' + source['sha256'])
                cache = pack.coverage.cache
                expected = copy.deepcopy(prepared)
                raw = (pack.root / prepared['path']).read_bytes()
            with Pack(self.path) as reopened:
                self.assertEqual(reopened.sample_for(('lead', 125)), expected)
                self.assertEqual(reopened.coverage.cache_hits, 1)
            metadata = cache / (prepared['id'] + '.json')
            record = json.loads(metadata.read_text())
            record['sample']['pitches'] = [1]
            record['sample']['loop'] = dict(startFrame=999999, endFrame=-1, validated=False)
            metadata.write_bytes(canonical_bytes(record))
            with Pack(self.path) as repaired:
                result = repaired.sample_for(('lead', 125))
                self.assertEqual(result, expected)
                self.assertEqual((repaired.root / result['path']).read_bytes(), raw)
                self.assertEqual(repaired.coverage.cache_hits, 0)

    def test_silent_source_and_missing_role_never_acquire_a_synth_replacement(self):
        with Pack(self.path) as pack:
            missing = copy.copy(pack)
            missing.samples = {k: v for k, v in pack.samples.items() if v['role'] != 'lead'}
            with self.assertRaisesRegex(ContractError, 'source recording.*synthesized replacements are disabled'):
                Coverage(missing)

    def test_legacy_reconstructed_kit_identity_reopens_using_source_waveforms(self):
        # Earlier saved projects named missing hats hybrid_hatOpen. Changing
        # preparation must keep that authored identity playable after upgrade.
        path = ROOT / 'packs/parachute.prdepack'
        with Pack(path) as pack:
            editor = Editor(new_project(pack), pack)
            clip = editor.add_pattern('drums', Fraction(0), Fraction(4))
            editor.toggle_step(clip, Fraction(0), Fraction(1, 4), 'hybrid_hatOpen')
            target = self.root / 'legacy-kit.prdeproj'
            save_project(target, editor.project)
            expected = editor.plan()
            self.assertFalse(expected['conflicts'])
            self.assertEqual(expected['events'][0]['role'], 'drums.hatOpen')
            sample = pack.samples[expected['assets'][0]['id']]
            self.assertEqual(sample['lineage']['kind'], 'pre-rendered')
        with Pack(path) as reopened:
            self.assertEqual(Editor(load_project(target), reopened).plan(), expected)

    def test_complete_root_bank_uses_source_assets_and_stays_compact(self):
        with patch.dict(os.environ, {'RAW_DAW_BANK_CACHE': ''}):
            with Pack(self.path) as pack:
                report = pack.coverage.prepare_bank()
                self.assertEqual(report['notes'], dict(bass=128, lead=128))
                self.assertEqual(report['chords'], len(QUALITIES) * 12)
                self.assertFalse(report['syntheticReplacement'])
                self.assertLess(report['preparedBytes'], 100 * 1024 * 1024)
                self.assertLess(report['analysisBytes'], 32 * 1024 * 1024)
                self.assertEqual(pack.instruments['drums']['extra2']['status'], 'empty')
                for target in (('lead', 0), ('lead', 127), ('bass', 0), ('bass', 127), ('rhythm', 11, 'dominant13', 0)):
                    sound = pack.sample_for(target)
                    self.assertEqual(sound['lineage']['kind'], 'pre-rendered')
                    self.assertGreater(np.max(np.abs(read_pcm(pack.root / sound['path']))), 1e-6)
                self.assertTrue(all(s['lineage']['kind'] == 'pre-rendered' and 'fixture waveform' in s['quality']['notes']
                                    for s in pack.samples.values() if s['id'].startswith('hybrid_')))


if __name__ == '__main__':
    unittest.main()
