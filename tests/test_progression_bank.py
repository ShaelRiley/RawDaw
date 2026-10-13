"""Distinct curation, exact notation, atomic imports and ordinary harmonic edits."""
import copy
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch

from prde1 import progression_bank as lib
from prde1.contracts import ContractError, canonical_bytes
from prde1.editor import Editor, new_project
from prde1.governor import resolve, rank_progressions
from prde1.music import MODES, chord_identity, roman
from prde1.pack import Pack
from prde1.project import load_project, save_project, validate_project
from tools.build_fixture import make_fixture
from tools.build_progression_bank import build


def authored(name='My loop', **extra):
    return lib.validate_entry(dict(name=name, kind='chords', basis='major-relative',
        sequence='i bVI V i', durations=['1', '2', '1', '2'], **extra))


class ProgressionBank(unittest.TestCase):
    def test_inventory_is_reproducible_distinct_and_has_a_subset_for_every_mode(self):
        entries = lib.catalog()
        self.assertEqual(len(entries), 206)
        self.assertEqual(sum(e['kind'] == 'degrees' for e in entries), 136)
        self.assertEqual(len({lib.musical_signature(e) for e in entries}), len(entries))
        self.assertEqual(len({lib.equivalence_signature(e) for e in entries}), len(entries))
        self.assertEqual(lib.DATA.read_bytes(), canonical_bytes(build()) + b'\n')
        for mode in MODES:
            self.assertGreaterEqual(sum(mode in e['modes'] for e in entries), 20)
            for tonic in range(12):
                for entry in entries:
                    chords = lib.realize(entry, tonic, mode)
                    self.assertEqual(len(chords), len(entry['durations']))
                    if entry['kind'] == 'degrees':
                        self.assertTrue(all(chord_identity(tonic, mode, c)[2] for c in chords))
        self.assertTrue(all(e['credits'][0]['license'] == 'CC0-1.0' for e in entries))

    def test_roman_quality_root_basis_and_inversions_survive_mode_changes(self):
        entry = authored()
        self.assertEqual([chord_identity(9, 'natural_minor', c)[0] for c in lib.realize(entry, 9, 'natural_minor')], [9, 5, 4, 9])
        self.assertEqual([c['quality'] for c in lib.realize(entry, 9, 'natural_minor')], ['minor', 'major', 'major', 'minor'])
        dorian = lib.validate_entry(dict(name='Dorian', kind='chords', basis='mode-relative', sequence='i IV/1', durations=['1']))
        self.assertEqual([lib.chord_name(9, 'dorian', c) for c in lib.realize(dorian, 9, 'dorian')], ['Am', 'D'])
        self.assertEqual(lib.realize(dorian, 9, 'dorian')[1]['inversion'], 1)
        unusual = lib.validate_entry(dict(name='Chromatic', kind='chords', basis='major-relative', sequence='#VI7 bVII I'))
        for mode in MODES:
            roots = [chord_identity(0, mode, c)[0] for c in lib.realize(unusual, 0, mode)]
            self.assertEqual(roots, [10, 10, 0])
        degrees = lib.validate_entry(dict(name='Numbers', kind='degrees', sequence='1 5 1'))
        self.assertEqual([roman(c) for c in lib.realize(degrees, 9, 'natural_minor')], ['i', 'v', 'i'])

    def test_text_and_json_import_deduplicate_and_persist_with_favorites_and_undo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'loops.txt'; source.write_text('Night | i bVI V i | 1 2 1 2\nLoping | 1 4 5 | 3/2 1/2 1\n', encoding='utf-8')
            entries = lib.load_file(source, text_basis='major-relative')
            bank = lib.Bank(root / 'bank.json')
            self.assertEqual(bank.import_entries(entries), (2, 0))
            bank.toggle_favorite(entries[0]['id'])
            reopened = lib.Bank(bank.path)
            self.assertEqual(reopened.entries, bank.entries); self.assertEqual(reopened.favorites, bank.favorites)
            self.assertEqual(reopened.entries[0]['sourceNotation'], 'i bVI V i')
            export = root / 'export.json'; reopened.export(export)
            target = lib.Bank(root / 'target.json'); self.assertEqual(target.import_entries(lib.load_file(export)), (2, 0))
            self.assertEqual(target.entries, reopened.entries)
            renamed = dict(entries[0], name='Different name')
            alias = lib.validate_entry(dict(name='Enharmonic alias', kind='chords', basis='major-relative',
                                           sequence='i #V V i', durations=['1', '2', '1', '2']))
            self.assertEqual(bank.import_entries([renamed, alias, lib.catalog()[0]]), (0, 3))
            bank.remove(entries[0]['id']); self.assertEqual(len(lib.Bank(bank.path).entries), 1)
            bank.undo(); self.assertEqual(lib.Bank(bank.path).entries, entries)
            self.assertIn(entries[0]['id'], lib.Bank(bank.path).favorites)

    def test_invalid_partial_import_and_failed_disk_write_preserve_the_bank(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); bank = lib.Bank(root / 'bank.json'); bank.import_entries([authored()])
            before = bank.path.read_bytes(); original = copy.deepcopy(bank.entries)
            with self.assertRaises(ContractError):
                bank.import_entries([authored('New', durationUnit='beats'), dict(name='Bad', kind='degrees', sequence=[9])])
            self.assertEqual(bank.path.read_bytes(), before); self.assertEqual(bank.entries, original)
            with patch('prde1.progression_bank.atomic_json', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): bank.import_entries([authored('New', durationUnit='beats')])
            self.assertEqual(bank.path.read_bytes(), before); self.assertEqual(bank.entries, original)
            damaged = root / 'damaged.json'; damaged.write_bytes(b'{not a bank}')
            bad = lib.Bank(damaged); self.assertTrue(bad.error)
            with self.assertRaises(ContractError): bad.import_entries([authored()])
            self.assertEqual(damaged.read_bytes(), b'{not a bank}')

    def test_bounded_imports_reject_ambiguous_and_unsupported_data(self):
        invalid = [dict(name='Mixed', kind='chords', basis='major-relative', sequence='I 5 vi'),
                   dict(name='Basis', kind='chords', sequence='I V'),
                   dict(name='Invert', kind='chords', basis='mode-relative', sequence='I/3'),
                   dict(name='Zero', kind='degrees', sequence=[1], durations=['0']),
                   dict(name='Fraction', kind='degrees', sequence=[1], durations=['1/0']),
                   dict(name='Boolean', kind='degrees', sequence=[True]),
                   dict(name='Huge', kind='degrees', sequence=[1]*65),
                   dict(name='Fields', kind='degrees', sequence=[1], mystery=True)]
        for entry in invalid:
            with self.subTest(entry=entry['name']), self.assertRaises(ContractError): lib.validate_entry(entry)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root / 'bad.json'; path.write_text('{"format":"raw-daw-progressions","version":1,"version":2,"entries":[]}')
            with self.assertRaises(ContractError): lib.load_file(path)
            path.write_bytes(b' ' * (lib.MAX_BYTES + 1))
            with self.assertRaises(ContractError): lib.load_file(path)
            text = root / 'bad.txt'; text.write_text('Valid | I V\nInvalid | not-chords\n')
            with self.assertRaisesRegex(ContractError, 'Line 2'): lib.load_file(text)


class ProgressionPlayback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.root = Path(cls.temp.name)
        cls.path = make_fixture(cls.root / 'fixture', extras=2)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_an_empty_song_can_grow_for_a_full_cycle_but_placed_music_keeps_its_length(self):
        with Pack(self.path) as pack:
            project = new_project(pack); editor = Editor(project, pack); entry = authored()
            lib.load_into(editor, entry, grow_empty=True)
            self.assertEqual(editor.project['length'], '24')
            self.assertEqual(len(editor.project['harmony']), 4)
            editor.undo(); self.assertEqual(editor.project, project)
            editor.add_pattern('bass', F(0), F(4))
            lib.load_into(editor, entry, grow_empty=True)
            self.assertEqual(editor.project['length'], '16')

    def test_meter_aware_fill_recomputes_mode_derived_chords_at_tonality_changes_and_undoes(self):
        with Pack(self.path) as pack:
            project = new_project(pack, bars=8); project['length'] = '30'
            project['meterMap'] += [dict(beat='8', numerator=3, denominator=4, governorSegments=3),
                                   dict(beat='14', numerator=6, denominator=8, governorSegments=6),
                                   dict(beat='20', numerator=7, denominator=8, governorSegments=4)]
            project['tonalityMap'] += [dict(beat='10', tonic=9, mode='natural_minor'), dict(beat='17', tonic=2, mode='dorian')]
            editor = Editor(project, pack); original = copy.deepcopy(editor.project)
            entry = lib.validate_entry(dict(name='Changing measures', kind='degrees', sequence=[1, 4], durations=['2', '1']))
            lib.load_into(editor, entry)
            self.assertEqual([v['beat'] for v in editor.project['harmony']], ['0', '8', '10', '11', '17', '20', '27'])
            self.assertEqual(editor.project['harmony'][2]['chord']['quality'], 'minor')
            self.assertEqual(editor.project['harmony'][4]['chord']['quality'], 'major')
            for key in ('tempoMap', 'meterMap', 'tonalityMap', 'patterns', 'instances', 'mix', 'vocals', 'variation'):
                self.assertEqual(editor.project[key], original[key])
            editor.undo(); self.assertEqual(editor.project, original)

    def test_single_cycle_restores_surrounding_harmony_and_saved_project_outlives_bank_entry(self):
        with Pack(self.path) as pack:
            project = new_project(pack, bars=8); project['harmony'].append(dict(beat='24', chord=dict(degree=4, alteration=0, quality='minor', inversion=0)))
            editor = Editor(project, pack); entry = authored()
            lib.load_into(editor, entry, start=F(4), repeat=False)
            self.assertEqual(editor.project['harmony'][0], project['harmony'][0])
            self.assertEqual(next(v for v in editor.project['harmony'] if v['beat']=='28')['chord']['quality'], 'minor')
            bank = lib.Bank(self.root / 'personal.json'); bank.import_entries([entry]); bank.remove(entry['id'])
            path = self.root / 'saved.prdeproj'; save_project(path, editor.project)
            self.assertEqual(load_project(path), editor.project)
            self.assertEqual(editor.project['harmony'][1]['chord']['quality'], 'minor')

    def test_all_bank_candidates_rank_without_pcm_creation_and_auditions_use_real_assets(self):
        with Pack(self.path) as pack:
            editor = Editor(new_project(pack), pack); original = canonical_bytes(editor.project)
            before = len(pack.samples); rows = rank_progressions(pack, 0, 'major')
            self.assertEqual(len(rows), 206); self.assertEqual(len(pack.samples), before)
            self.assertTrue(all(r['playable'] and not r['missing'] for r in rows))
            for name in ('Open road', 'Velvet circle', 'First-inversion stroll'):
                entry = next(e for e in lib.catalog() if e['name'] == name)
                preview = lib.audition_project(editor, entry, F(1)); validate_project(preview)
                plan = resolve(preview, pack); self.assertEqual(plan['conflicts'], [])
                self.assertEqual(len(plan['events']), len(entry['sequence']))
                self.assertTrue(all(event['role'] == 'rhythm' for event in plan['events']))
            self.assertEqual(canonical_bytes(editor.project), original)

    def test_capture_retains_actual_chords_timing_and_provenance(self):
        with Pack(self.path) as pack:
            project = new_project(pack, 9, 'natural_minor', bars=8)
            project['harmony'] += [dict(beat='3', chord=dict(degree=6, alteration=0, quality='major', inversion=1)),
                                   dict(beat='7', chord=dict(degree=5, alteration=0, quality='major', inversion=0))]
            captured = lib.capture(project, F(1), F(11), 'Saved minor')
            self.assertEqual(captured['durations'], ['2', '4', '4'])
            self.assertEqual([lib.chord_name(9, 'natural_minor', c) for c in lib.realize(captured, 9, 'natural_minor')], ['Am', 'F', 'E'])
            self.assertEqual(captured['credits'], project['credits'])
            self.assertEqual(lib.realize(captured, 9, 'dorian')[1]['inversion'], 1)


if __name__ == '__main__': unittest.main()
