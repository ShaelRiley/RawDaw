"""Common extended harmonies retain identity through notation and bank imports."""
import copy
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from prde1.contracts import ContractError
from prde1.editor import new_event, new_project, parse_progression
from prde1.music import MODES, QUALITIES, chord_identity, roman
from prde1.progression_bank import chord_name, realize, validate_entry
from prde1.project import load_project, save_project
from prde1.sequencer import settings


class ExtendedHarmony(unittest.TestCase):
    def test_extended_chords_mean_their_actual_tones_and_case(self):
        parsed = parse_progression('I6 i6 Iadd9 iadd9 I6/9 i6/9 V9 ii9 V11 ii11 V13 Imaj13 ii13 V7b9 V7#9 Imaj7#11', 0, 'major')
        self.assertEqual([c['quality'] for c in parsed], [
            'major6', 'minor6', 'add9', 'minorAdd9', 'major6Add9', 'minor6Add9',
            'dominant9', 'minor9', 'dominant11', 'minor11', 'dominant13', 'major13',
            'minor13', 'dominant7b9', 'dominant7Sharp9', 'major7Sharp11'])
        self.assertEqual(set(chord_identity(0, 'major', parsed[0])[1]), {0, 4, 7, 9})
        self.assertEqual(set(chord_identity(0, 'major', parsed[4])[1]), {0, 2, 4, 7, 9})
        self.assertEqual(set(chord_identity(0, 'major', parsed[13])[1]), {7, 8, 11, 2, 5})
        self.assertEqual(chord_name(0, 'major', parsed[-1]), 'Cmaj7#11')

    def test_every_registered_quality_and_true_inversion_roundtrips_roman_notation(self):
        for quality, intervals in QUALITIES.items():
            for inversion in range(len(intervals)):
                with self.subTest(quality=quality, inversion=inversion):
                    authored = dict(degree=5, alteration=-1, quality=quality, inversion=inversion)
                    self.assertEqual(parse_progression(roman(authored), 0, 'major'), [authored])
        for text in ('I/3', 'V9/5', 'Imaj13/7', 'Iunknown', 'V7#11', 'Iv9'):
            with self.subTest(text=text), self.assertRaises(ContractError):
                parse_progression(text, 0, 'major')

    def test_imported_extended_progression_retains_authored_roots_in_every_mode(self):
        entry = validate_entry(dict(name='Extended turnaround', kind='chords', basis='major-relative',
                                    sequence='ii9 V7♭9 Imaj13/6th', durations=['1']))
        self.assertEqual([c['quality'] for c in entry['sequence']], ['minor9', 'dominant7b9', 'major13'])
        for mode in MODES:
            realized = realize(entry, 0, mode)
            self.assertEqual([chord_identity(0, mode, c)[0] for c in realized], [2, 7, 0])
            self.assertEqual(realized[-1]['inversion'], 6)
            self.assertEqual([chord_name(0, mode, c) for c in realized], ['Dm9', 'G7b9', 'Cmaj13'])

    def test_full_midi_grid_includes_both_extremes_and_note_zero_is_not_defaulted(self):
        for role in ('bass', 'lead'):
            rows = settings(dict(role=role, length='4'), None)['rows']
            self.assertEqual({row['note'] for row in rows}, set(range(128)))
            event = new_event(role, Fraction(0), Fraction(1), register=0)
            self.assertEqual(event['choice']['registerMidi'], 0)

    def test_legacy_pitch_grid_expands_without_mutating_saved_expression(self):
        pattern = dict(role='bass', length='4')
        config = settings(pattern, None)
        config.pop('bankProfile')
        config['rows'] = [row for row in config['rows'] if 28 <= row['note'] <= 60]
        row = next(row for row in config['rows'] if row['note'] == 48)
        row.update(velocityScale=.35, solo=True, offsetPercent=17)
        pattern['sequencer'] = config
        original = copy.deepcopy(pattern)
        expanded = settings(pattern, None)
        self.assertEqual({row['note'] for row in expanded['rows']}, set(range(128)))
        self.assertEqual(next(r for r in expanded['rows'] if r['note'] == 48), row)
        self.assertEqual(pattern, original)

    def test_current_pitch_grid_keeps_intentionally_hidden_or_reordered_rows(self):
        pattern = dict(role='lead', length='4')
        config = settings(pattern, None)
        config['rows'] = [config['rows'][3],config['rows'][1]]
        pattern['sequencer'] = config
        self.assertEqual(settings(pattern,None),config)

    def test_saved_project_preserves_every_quality_including_its_highest_inversion(self):
        metadata = SimpleNamespace(manifest={'source': dict(title='Registry persistence test', license='CC0-1.0',
                            attribution='Test metadata'), 'packId': 'metadata_only'}, manifest_hash='0'*64)
        project = new_project(metadata)
        project['length'] = str(len(QUALITIES))
        project['harmony'] = [dict(beat=str(i), chord=dict(degree=1, alteration=0, quality=quality,
                             inversion=len(intervals)-1)) for i, (quality, intervals) in enumerate(QUALITIES.items())]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'extended.prdeproj'
            save_project(path, project)
            self.assertEqual(load_project(path), project)


if __name__ == '__main__':
    unittest.main()
