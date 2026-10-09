import copy
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
import wave
import zipfile
from fractions import Fraction
from pathlib import Path
from unittest import mock

from prde1.contracts import ContractError, ROOT, canonical_bytes, read_json, validate
from prde1.governor import context, rank_progressions, resolve, vst_chord_notes
from prde1.music import MODES, at, beat, chord_identity, diatonic, grid_positions, quarter_seconds, roman
from prde1.midi import inspect_midi
from prde1.pack import Pack, safe_path, sha256
from prde1.project import duplicate, load_project, make_independent, save_project, validate_project
from tools.build_fixture import channel, event, make_fixture


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="prde1-tests-")
        cls.root=Path(cls.temp.name)
        cls.base=make_fixture(cls.root/"fixture",extras=2)
        cls.major=load_project(cls.root/"fixture/major.prdeproj")
        cls.minor=load_project(cls.root/"fixture/minor.prdeproj")
        with zipfile.ZipFile(cls.base) as archive:
            cls.files={name:archive.read(name) for name in archive.namelist()}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.project=copy.deepcopy(self.major)
        self.folder=Path(tempfile.mkdtemp(dir=self.root))

    def rewrite(self,edit=None,entries=None,raw_manifest=None):
        files=dict(self.files)
        manifest=read_json(files["manifest.json"])
        if edit:edit(manifest,files)
        files["manifest.json"]=raw_manifest if raw_manifest is not None else canonical_bytes(manifest)
        path=self.folder/"changed.prdepack"
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in files.items():archive.writestr(name,data)
            for entry,data in entries or []:archive.writestr(entry,data)
        return path

    def bind(self,project,pack):
        project["packReference"]={"packId":pack.manifest["packId"],"manifestSha256":pack.manifest_hash}
        return project

    def single(self,role="lead",exact=60,duration="6"):
        self.project["patterns"]=[{"id":"single","role":role,"length":"16","events":[event("held",0,duration,"note" if role!="rhythm" else "chord")],
                                  "provenance":{"sourceClip":"test","license":"MIT","changes":"none"}}]
        self.project["instances"]=[{"id":"single_instance","patternId":"single","beat":"0","linked":False}]
        trigger=self.project["patterns"][0]["events"][0]
        if role!="rhythm":
            trigger["choice"]["exactMidi"]=exact
            trigger["expression"]["lockExactPitch"]=True
        return trigger

    def native(self,pack,plan,name="audio",seek=0):
        path=self.folder/(name+".json"); path.write_bytes(canonical_bytes(plan))
        output=self.folder/(name+".wav")
        result=subprocess.run([str(ROOT/"build/prde1-render"),str(path),str(pack.root),str(output),str(seek)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return output,json.loads(result.stdout)

    # PACK-001..PACK-012: untrusted bytes, honest coverage, actual mappings.
    def test_pack_001_zero_one_two_optional_extras(self):
        for count in (0,1,2):
            def edit(manifest,_):
                for index,slot in enumerate(("extra1","extra2")):
                    if index>=count:
                        manifest["instruments"]["drums"][slot].update(status="empty",reason="Intentionally unused",sampleId=None,displayName="Unassigned",
                                soundIdentity="",midiAddress=None,pitchClass="unpitched",pitches=[])
            with Pack(self.rewrite(edit)) as pack:
                self.assertEqual(sum(pack.manifest["instruments"]["drums"][slot]["status"]=="available" for slot in ("extra1","extra2")),count)

    def test_pack_002_traversal_and_absolute_paths(self):
        for path in ("../escape.json","/escape.json","C:/escape.json","audio\\evil.wav","a//b.json","a/./b.json"):
            with self.subTest(path=path), self.assertRaises(ContractError):safe_path(path)
        with self.assertRaises(ContractError):Pack(self.rewrite(entries=[("../escape.json",b"{}")]))

    def test_pack_003_symlink_rejected(self):
        entry=zipfile.ZipInfo("link.json"); entry.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(ContractError):Pack(self.rewrite(entries=[(entry,b"manifest.json")]))

    def test_pack_004_duplicate_zip_path(self):
        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore",UserWarning)
            path=self.rewrite(entries=[("manifest.json",self.files["manifest.json"])])
        with self.assertRaises(ContractError):Pack(path)

    def test_pack_005_checksum_corruption(self):
        def edit(_,files):
            key=next(key for key in files if key.startswith("audio/lead"))
            data=bytearray(files[key]); data[-1]^=1;files[key]=bytes(data)
        with self.assertRaisesRegex(ContractError,"Checksum"):Pack(self.rewrite(edit))

    def test_pack_006_unknown_version_and_duplicate_json_key(self):
        with self.assertRaises(ContractError):Pack(self.rewrite(lambda m,_:m.update(schemaVersion="999")))
        with self.assertRaises(ContractError):read_json('{"packId":"a","packId":"b"}')
        with self.assertRaises(ContractError):read_json('{"gain":NaN}')

    def test_pack_007_unavailable_required_role_is_honest(self):
        def edit(manifest,_):
            manifest["instruments"]["bass"].update(status="unavailable",sampleId=None,reason="No clean source bass")
            manifest["validation"]["status"]="coverage-limited"
        with Pack(self.rewrite(edit)) as pack:
            self.assertTrue(pack.warnings)
            plan=resolve(self.bind(self.project,pack),pack)
            self.assertFalse(any(item["role"]=="bass" for item in plan["events"]))
            self.assertTrue(any(item["code"]=="missing_role" for item in plan["conflicts"]))
            self.assertFalse(any(item["playable"] for item in rank_progressions(pack,0,"major")))
        def fictitious(manifest,_):manifest["instruments"]["bass"]["sampleId"]="does_not_exist"
        with self.assertRaises(ContractError):Pack(self.rewrite(fictitious))

    def test_pack_008_population_requires_actual_extra_sample(self):
        with self.assertRaises(ContractError):Pack(self.rewrite(lambda m,_:m["instruments"]["drums"]["extra1"].update(sampleId="missing")))

    def test_pack_009_attack_cannot_be_looped(self):
        def edit(manifest,_):
            sample=next(item for item in manifest["samples"] if item["loop"])
            sample["loop"]["startFrame"]=sample["onsetFrame"]
        with self.assertRaisesRegex(ContractError,"sustain"):Pack(self.rewrite(edit))

    def test_pack_010_mapping_cannot_prescribe_retuned_substitute(self):
        def edit(manifest,_):
            mapping=next(item for item in manifest["mappings"] if item["role"]=="bass")
            mapping["note"]+=1
        with self.assertRaisesRegex(ContractError,"identity"):Pack(self.rewrite(edit))

    def test_pack_011_decompression_and_decoded_budgets(self):
        with self.assertRaisesRegex(ContractError,"compression"):Pack(self.rewrite(entries=[("bomb.json",b"0"*1000000)]))
        with mock.patch("prde1.pack.MAX_DECODED",1024),self.assertRaisesRegex(ContractError,"Decoded"):Pack(self.base)

    def test_pack_012_whole_chord_actual_content_checked(self):
        def edit(manifest,_):
            next(item for item in manifest["samples"] if item["role"]=="rhythm")["pitches"]=[60,63,67]
        with self.assertRaisesRegex(ContractError,"pitch set"):Pack(self.rewrite(edit))

    def test_pack_013_midi_is_structural_data_with_stable_drum_addresses(self):
        raw=self.files["clips/source-midi/groove_1.mid"]
        midi=inspect_midi(raw)
        self.assertEqual(midi["ticksPerQuarter"],480)
        self.assertEqual({note["note"] for note in midi["notes"]},{36,38,42,49})
        self.assertEqual(midi["controls"],["source_meter","source_tempo"])
        with self.assertRaises(ContractError):inspect_midi(raw[:-1])
        with self.assertRaises(ContractError):inspect_midi(raw+b"executable?")

    def test_pack_014_unbounded_numbers_fail_with_contract_error(self):
        self.project["harmony"][0]["chord"]["degree"]=10**600
        with self.assertRaises(ContractError):validate_project(self.project)

    # MUSIC/GOVERNOR: labels, local harmony, sample isolation and boundaries.
    def test_music_001_roman_case_minor_example_and_mode_derived_templates(self):
        self.assertEqual([roman(diatonic(9,"natural_minor",degree)) for degree in (4,5,5,4,6,6)],["iv","v","v","iv","VI","VI"])
        self.assertEqual(roman(diatonic(0,"major",7)),"vii°")
        self.assertEqual(roman(diatonic(9,"dorian",4)),"IV")
        v={"degree":5,"alteration":0,"quality":"major","inversion":0}
        self.assertFalse(chord_identity(9,"natural_minor",v)[2])
        self.assertTrue(chord_identity(9,"harmonic_minor",v)[2])

    def test_music_002_all_grids_keep_meter_and_fine_timing(self):
        for segments in (3,4,6,8):
            self.assertEqual(grid_positions(Fraction(0),4,4,segments)[1],Fraction(4,segments))
            self.assertEqual(grid_positions(Fraction(0),3,4,segments)[1],Fraction(3,segments))
            self.assertEqual(grid_positions(Fraction(0),6,8,segments)[1],Fraction(3,segments))
        self.assertEqual(beat("1/7"),Fraction(1,7))

    def test_music_003_tempo_map_uses_quarter_note_units(self):
        tempos=[{"beat":"0","quarterBpm":120},{"beat":"4","quarterBpm":60}]
        self.assertEqual(quarter_seconds(Fraction(8),tempos),6)
        self.assertEqual(quarter_seconds(Fraction(4),tempos),2)

    def test_governor_001_two_harmonies_and_immutable_assets(self):
        original=self.base.read_bytes()
        with Pack(self.base) as pack:
            major=resolve(self.major,pack);minor=resolve(self.minor,pack)
            self.assertEqual(major["conflicts"],[]);self.assertEqual(minor["conflicts"],[])
            self.assertNotEqual(major["events"],minor["events"])
            self.assertTrue(all(sha256((pack.root/item["path"]).read_bytes())==item["sha256"] for item in pack.samples.values()))
            self.assertEqual(sum(item["role"]=="rhythm" for item in major["events"]),4)
        self.assertEqual(original,self.base.read_bytes())

    def test_governor_002_explicit_missing_chord_is_preserved(self):
        self.project["tonalityMap"][0]["mode"]="natural_minor"
        self.project["harmony"][0]["chord"]={"degree":1,"alteration":0,"quality":"minor","inversion":0}
        before=copy.deepcopy(self.project)
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertTrue(any(item["code"]=="missing_chord" for item in plan["conflicts"]))
        self.assertEqual(self.project,before)

    def test_governor_003_incompatible_held_note_fades_without_retrigger(self):
        self.single(exact=64)
        self.project["harmony"]=[{"beat":"0","chord":diatonic(0,"major",1)},{"beat":"1","chord":diatonic(0,"major",4)}]
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertEqual(len(plan["events"]),1)
        voice=plan["events"][0]
        self.assertEqual((voice["endFrame"],voice["endReason"],voice["releaseFrames"]),(24000,"harmonic_boundary",240))

    def test_governor_004_common_held_note_continues_with_validated_sustain(self):
        self.single(exact=60)
        self.project["harmony"]=[{"beat":"0","chord":diatonic(0,"major",1)},{"beat":"1","chord":diatonic(0,"major",4)},
                                  {"beat":"2","chord":diatonic(0,"major",6)},{"beat":"3","chord":diatonic(0,"major",5)}]
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertEqual(len(plan["events"]),1)
        self.assertEqual(plan["events"][0]["endFrame"],72000)

    def test_governor_005_whole_chord_all_pitches_required(self):
        self.single(role="rhythm")
        self.project["harmony"]=[{"beat":"0","chord":diatonic(0,"major",1)},{"beat":"1","chord":diatonic(0,"major",4)}]
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertEqual(len(plan["events"]),1)
        self.assertEqual(plan["events"][0]["endFrame"],24000)
        self.assertEqual(len(vst_chord_notes(0,"major")),3)

    def test_governor_006_exact_lock_conflict_preserved_withheld(self):
        self.single(exact=61)
        before=copy.deepcopy(self.project)
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertEqual(plan["events"],[])
        self.assertEqual(plan["conflicts"][0]["code"],"exact_pitch_conflict")
        self.assertEqual(self.project,before)

    def test_governor_007_pitched_extra_and_semantic_drum_identity(self):
        self.project["patterns"]=[{"id":"hit","role":"drums","length":"16","events":[event("pitched",4,"1/4","drum",sound="tuned_C_stab")],
                                  "provenance":{"sourceClip":"test","license":"MIT","changes":"none"}}]
        self.project["instances"]=[{"id":"hit_instance","patternId":"hit","beat":"0","linked":False}]
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertEqual(plan["events"],[])
        self.assertEqual(plan["conflicts"][0]["code"],"pitched_extra_conflict")
        # Move the same crash identity to Extra 2. MIDI address/sound identity is stable.
        def edit(manifest,_):
            drums=manifest["instruments"]["drums"]
            drums["extra2"]=copy.deepcopy(drums["extra1"])
            drums["extra1"].update(status="empty",reason="Unused",sampleId=None,soundIdentity="",midiAddress=None,pitches=[])
        self.project["patterns"][0]["events"][0]["choice"]["soundIdentity"]="crash"
        with Pack(self.rewrite(edit)) as pack:plan=resolve(self.bind(self.project,pack),pack)
        self.assertEqual(plan["events"][0]["role"],"drums.extra2")

    def test_governor_008_missing_crash_never_becomes_another_extra(self):
        def edit(manifest,_):manifest["instruments"]["drums"]["extra1"].update(status="empty",reason="Unused",sampleId=None,soundIdentity="",midiAddress=None,pitches=[])
        with Pack(self.rewrite(edit)) as pack:plan=resolve(self.bind(self.project,pack),pack)
        self.assertTrue(any(item["code"]=="missing_drum" for item in plan["conflicts"]))
        self.assertFalse(any(item["role"]=="drums.extra2" for item in plan["events"]))

    def test_governor_009_one_shot_stops_at_actual_limit(self):
        self.single(exact=64,duration="16")
        self.project["harmony"]=[{"beat":"0","chord":diatonic(0,"major",1)}]
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertEqual(plan["events"][0]["endReason"],"natural_limit")
        self.assertEqual(plan["events"][0]["endFrame"],round(0.65*48000)-48)

    def test_governor_010_probability_variation_and_audition_are_repeatable(self):
        for pattern in self.project["patterns"]:
            for trigger in pattern["events"]:
                trigger["expression"].update(playPercent=62,changePercent=80,variation="double")
        with Pack(self.base) as pack:
            first=resolve(self.project,pack)
            rank_progressions(pack,0,"major") # audition/ranking cannot consume arrangement randomness
            second=resolve(self.project,pack)
            self.assertEqual(first,second)
            save_project(self.folder/"reopen.prdeproj",self.project)
            self.assertEqual(first,resolve(load_project(self.folder/"reopen.prdeproj"),pack))
            self.project["variation"]["revision"]+=1
            self.assertNotEqual(first["events"],resolve(self.project,pack)["events"])

    def test_governor_011_play_zero_and_disabled_are_silent(self):
        self.single()
        self.project["patterns"][0]["events"][0]["expression"]["playPercent"]=0
        with Pack(self.base) as pack:self.assertEqual(resolve(self.project,pack)["events"],[])
        self.project["patterns"][0]["events"][0].update(enabled=False)
        self.project["patterns"][0]["events"][0]["expression"]["playPercent"]=100
        with Pack(self.base) as pack:self.assertEqual(resolve(self.project,pack)["events"],[])

    def test_governor_012_repeats_use_actual_boundary_context(self):
        trigger=self.single(exact=64,duration="2")
        trigger["expression"].update(lockExactPitch=True,changePercent=100,variation="double")
        self.project["harmony"]=[{"beat":"0","chord":diatonic(0,"major",1)},{"beat":"1","chord":diatonic(0,"major",4)}]
        with Pack(self.base) as pack:plan=resolve(self.project,pack)
        self.assertEqual(len(plan["events"]),1)
        self.assertTrue(any(item["eventId"].endswith(":1") and item["code"]=="exact_pitch_conflict" for item in plan["conflicts"]))

    def test_governor_013_rank_only_actual_prepared_coverage(self):
        with Pack(self.base) as pack:
            ranking=rank_progressions(pack,0,"major")
            self.assertTrue(any(item["playable"] for item in ranking))
            self.assertTrue(all(not item["missing"] for item in ranking if item["playable"]))
            unsupported=rank_progressions(pack,1,"major")
            self.assertFalse(any(item["playable"] for item in unsupported))

    # STATE: independent copies, native session fidelity, explicit capability limits.
    def test_state_001_copy_independence_and_harmony_preservation(self):
        # Free a destination measure, retaining its different Governor harmony.
        self.project["instances"]=[item for item in self.project["instances"] if item["id"]!="bass_instance_1"]
        self.project["patterns"]=[item for item in self.project["patterns"] if item["id"]!="bass_1"]
        result=duplicate(self.project,"bass_instance_0","4")
        self.assertEqual(result["harmony"],self.project["harmony"])
        clone=next(item for item in result["patterns"] if item["id"]==result["instances"][-1]["patternId"])
        clone["events"][0]["expression"]["velocity"]=0.1
        self.assertEqual(result["patterns"][1]["events"][0]["expression"]["velocity"],0.8)
        self.assertEqual(result["variation"],self.project["variation"])

    def test_state_002_linked_repeat_can_be_detached(self):
        self.project["instances"]=[item for item in self.project["instances"] if item["id"]!="bass_instance_1"]
        linked=duplicate(self.project,"bass_instance_0","4",linked=True)
        self.assertEqual(linked["instances"][-1]["patternId"],"bass_0")
        independent=make_independent(linked,linked["instances"][-1]["id"])
        self.assertFalse(independent["instances"][-1]["linked"])
        self.assertNotEqual(independent["instances"][-1]["patternId"],"bass_0")

    def test_state_003_save_reopen_retains_context_and_vocal_seconds(self):
        self.project["vocals"][0]["takes"]=[{"id":"take_1","path":"takes/one.wav","sha256":"0"*64,"startSeconds":2.75,"complete":True}]
        self.project["vocals"][0]["selectedTakeId"]="take_1"
        self.project["tempoMap"][0]["quarterBpm"]=90
        save_project(self.folder/"native.prdeproj",self.project)
        restored=load_project(self.folder/"native.prdeproj")
        self.assertEqual(restored,self.project)
        self.assertEqual(restored["vocals"][0]["takes"][0]["startSeconds"],2.75)
        with Pack(self.base) as pack,self.assertRaisesRegex(ContractError,"Vocal"):resolve(restored,pack)

    def test_state_004_interrupted_manifest_save_preserves_previous(self):
        path=self.folder/"saved.prdeproj";save_project(path,self.project);old=path.read_bytes()
        changed=copy.deepcopy(self.project);changed["title"]="new"
        with mock.patch("prde1.contracts.os.replace",side_effect=OSError("simulated interrupted save")),self.assertRaises(OSError):save_project(path,changed)
        self.assertEqual(path.read_bytes(),old)
        self.assertFalse(list(self.folder.glob("*.partial")))

    def test_state_005_no_silent_effect_drop_or_missing_plugin_export(self):
        self.project["mix"]["master"]["reverbOn"]=True
        with Pack(self.base) as pack,self.assertRaisesRegex(ContractError,"reverb"):resolve(self.project,pack)
        self.project["mix"]["master"]["reverbOn"]=False
        track={"id":"vst_1","pluginId":"missing.test","version":"1","statePath":"state/test.bin","missing":True,"mode":"chord",
               "patterns":[],"percussionMap":{},"channel":channel()}
        self.project["pluginTracks"]=[track]
        with Pack(self.base) as pack:
            with self.assertRaisesRegex(ContractError,"explicit approval"):resolve(self.project,pack)
            self.assertTrue(resolve(self.project,pack,approve_altered=True)["warnings"])
        self.project["pluginTracks"]=[dict(track,id="vst_"+str(index)) for index in range(4)]
        with self.assertRaises(ContractError):validate_project(self.project)

    def test_state_006_default_ambience_off_and_four_vocal_cap(self):
        self.assertFalse(self.project["mix"]["master"]["reverbOn"])
        self.assertFalse(self.project["mix"]["master"]["delayOn"])
        self.assertEqual(len(self.project["vocals"]),1)
        self.assertFalse(self.project["vocals"][0]["correction"]["on"])
        self.project["vocals"]*=5
        with self.assertRaises(ContractError):validate_project(self.project)

    # AUDIO: actual executable sample renders, state reconstruction and preservation.
    def test_audio_001_non_silent_correct_stereo_24bit_and_different_harmonies(self):
        with Pack(self.base) as pack:
            first,report=self.native(pack,resolve(self.major,pack),"major")
            second,_=self.native(pack,resolve(self.minor,pack),"minor")
        self.assertNotEqual(first.read_bytes(),second.read_bytes())
        self.assertGreater(report["peak"],0.05);self.assertLess(report["peak"],0.98)
        with wave.open(str(first),"rb") as stream:
            self.assertEqual((stream.getframerate(),stream.getsampwidth(),stream.getnchannels(),stream.getnframes()),(48000,3,2,384000))

    def test_audio_002_seek_is_exact_slice_with_compressor_and_dither_state(self):
        with Pack(self.base) as pack:
            plan=resolve(self.major,pack)
            full,_=self.native(pack,plan,"full")
            seek,_=self.native(pack,plan,"seek",seek=123457)
            repeat,_=self.native(pack,plan,"repeat")
        self.assertEqual(full.read_bytes(),repeat.read_bytes())
        with wave.open(str(full),"rb") as a,wave.open(str(seek),"rb") as b:
            a.setpos(123457)
            self.assertEqual(a.readframes(a.getnframes()-123457),b.readframes(b.getnframes()))

    def test_audio_003_clipping_abort_preserves_prior_export(self):
        with Pack(self.base) as pack:
            plan=resolve(self.major,pack)
            plan["compressor"]["on"]=False;plan["masterGain"]=4
            for item in plan["events"]:item["gain"]=8
            path=self.folder/"hot.json";path.write_bytes(canonical_bytes(plan))
            output=self.folder/"existing.wav";output.write_bytes(b"previous completed export")
            result=subprocess.run([str(ROOT/"build/prde1-render"),str(path),str(pack.root),str(output)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(output.read_bytes(),b"previous completed export")
        self.assertFalse(list(self.folder.glob("*.partial.*")))

    def test_audio_004_half_open_retrigger_and_hat_choke(self):
        self.project["patterns"]=[{"id":"hats","role":"drums","length":"16","events":[event("open",0,"4","drum",sound="hat_open"),event("closed","1/2","1/4","drum",sound="hat_closed")],
                                  "provenance":{"sourceClip":"test","license":"MIT","changes":"none"}}]
        self.project["instances"]=[{"id":"hats_instance","patternId":"hats","beat":"0","linked":False}]
        with Pack(self.base) as pack:
            plan=resolve(self.project,pack)
            self.assertEqual(plan["events"][0]["endFrame"],plan["events"][1]["startFrame"])
            self.assertEqual(plan["events"][0]["endReason"],"hat_choke")
            self.native(pack,plan,"choke")


if __name__=="__main__":unittest.main()
