"""Source-only offline sample banks; the native player never transforms PCM."""
from __future__ import annotations
import copy
import hashlib
import io
import os
import tempfile
import time
import wave
from collections import OrderedDict
from pathlib import Path
import numpy as np
from .contracts import ContractError, RATE, ROOT, SLOTS, _validate, canonical_bytes, read_json
from .music import QUALITIES, REGISTERS
from .source_waveform import (MAX_CHORD_FRAMES, MAX_NOTE_FRAMES, drum_variant,
                              normalize, pcm24, pitch_shift, read_pcm,
                              separate_chord, sustain_loop)

VERSION = 'source-waveform-bank-v3'
MAX_PREPARED_BYTES = 256 * 1024 * 1024
MAX_ANALYSIS_BYTES = 16 * 1024 * 1024
MAX_WARP_BYTES = 16 * 1024 * 1024
MAX_SESSION_BYTES = 1024 * 1024 * 1024


def chord_notes(root, quality, inversion):
    notes = [48 + root + interval for interval in QUALITIES[quality]]
    result = notes[inversion:]
    for note in notes[:inversion]:
        while note <= result[-1]:
            note += 12
        result.append(note)
    return result


class Coverage:
    def __init__(self, pack):
        self.pack = pack
        self.original_samples = dict(pack.samples)
        self.original_mappings = dict(pack.mappings)
        self.generated = {}
        self.sustained = {}
        self.voices = {}
        self.source_peaks = {}
        self.warped_voices = OrderedDict()
        self.warped_bytes = 0
        self.analysis_bytes = 0
        self.prepared_bytes = 0
        self.cache_hits = 0
        self.costs = {}
        self.sample_schema = read_json((ROOT / 'schemas/prde1-pack-v1.schema.json').read_bytes())
        location = os.environ.get('RAW_DAW_BANK_CACHE')
        if location is None:
            location = str(Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'raw-daw' / 'sample-banks')
        self.cache = Path(location).expanduser() / pack.manifest_hash / VERSION if location else None
        self.instruments = copy.deepcopy(pack.manifest['instruments'])
        addresses = {r['midiAddress'] for r in self.instruments['drums'].values() if r['midiAddress'] is not None}
        for role in (*REGISTERS, 'rhythm'):
            if not any(s['role'] == role and s['pitches'] for s in self.original_samples.values()):
                raise ContractError(f'Cannot complete {role} bank: supply at least one source recording with declared pitches; synthesized replacements are disabled')
        for slot in SLOTS:
            row = self.instruments['drums'][slot]
            if row['status'] == 'empty':
                continue
            if row['status'] != 'available' or row['pitchClass'] == 'uncertain':
                sample = self._drum(slot)
                standard = {'kick': 36, 'snare': 38, 'hatClosed': 42, 'hatOpen': 46, 'tom1': 45, 'tom2': 48}.get(slot)
                address = standard if standard is not None and standard not in addresses else next(n for n in range(128) if n not in addresses)
                addresses.add(address)
                row.update(status='available', reason='Source-derived kit articulation; original hit was not recorded',
                           sampleId=sample['id'], soundIdentity=row['soundIdentity'] or 'hybrid_' + slot,
                           midiAddress=address, pitchClass='unpitched', pitches=[])
                sample['articulation'] = row['soundIdentity']
                if row['displayName'] == 'Unavailable':
                    row['displayName'] = slot + ' (source-derived)'
        for role in (*REGISTERS, 'rhythm'):
            if self.instruments[role]['status'] != 'available':
                self.instruments[role].update(status='available', reason='Source-derived complete bank')

    def cost(self, key):
        if key in self.costs:
            return self.costs[key]
        native = self.original_mappings.get(key)
        if native:
            return native['lineage']['transformationCost']
        seeds = self._seeds(key[0])
        if key[0] in REGISTERS:
            cost = min(abs(s['pitches'][0] - key[1]) + s['lineage']['transformationCost'] for s in seeds)
        else:
            cost = min(self._chord_cost(s, chord_notes(*key[1:])) for s in seeds)
        self.costs[key] = cost
        return cost

    @staticmethod
    def _chord_cost(source, targets):
        return sum(min(abs(note - source_note) for source_note in source['pitches']) for note in targets) / len(targets) + source['lineage']['transformationCost']

    def _seeds(self, role):
        return [s for s in self.original_samples.values() if s['role'] == role and s['pitches']]

    def sample(self, key, *, native=True):
        if native and key in self.original_mappings:
            return self.original_mappings[key]
        if key in self.generated:
            return self.generated[key]
        role = key[0]
        if role in REGISTERS:
            note = key[1]
            if type(note) is not int or not REGISTERS[role][0] <= note <= REGISTERS[role][1]:
                raise ContractError('Note outside instrument register')
            source = min(self._seeds(role), key=lambda s: (abs(s['pitches'][0] - note), s['lineage']['transformationCost'], -s['quality']['confidence'], s['id']))
            pitches, chord = [note], None
            recipe = f'nearest recorded note {source["pitches"][0]}; band-limited PCM rate warp {note-source["pitches"][0]} semitones; recorded sustain crossfade'
            build = lambda: sustain_loop(pitch_shift(read_pcm(self.pack.root / source['path'], source['onsetFrame']), note - source['pitches'][0]), minimum_note=note, pitch_note=note)
            cost = abs(note - source['pitches'][0]) + source['lineage']['transformationCost']
        elif role == 'rhythm':
            _, root, quality, inversion = key
            if type(root) is not int or not 0 <= root <= 11 or quality not in QUALITIES or type(inversion) is not int or not 0 <= inversion < len(QUALITIES[quality]):
                raise ContractError('Invalid source chord transformation target')
            pitches = chord_notes(root, quality, inversion)
            chord = dict(root=root, quality=quality, inversion=inversion)
            source = min(self._seeds(role), key=lambda s: (self._chord_cost(s, pitches), -s['quality']['confidence'], s['id']))
            recipe = 'recorded polyphonic PCM; stereo complex-bin harmonic masks; nearest recorded voice pitch warps; recombined target voicing; recorded sustain crossfade'
            build = lambda: self._chord(source, pitches)
            cost = self._chord_cost(source, pitches)
        else:
            raise ContractError('Unknown source-bank role')
        result = self._prepare(key, role, pitches, chord, source, recipe, cost, build)
        self.generated[key] = result
        return result

    def _chord(self, source, targets):
        if source['id'] not in self.voices:
            data = read_pcm(self.pack.root / source['path'], source['onsetFrame'], limit=MAX_CHORD_FRAMES)
            self.source_peaks[source['id']] = float(np.max(np.abs(data)))
            voices = separate_chord(data, source['pitches'])
            size = sum(voice.nbytes for voice in voices.values())
            if self.analysis_bytes + size > MAX_ANALYSIS_BYTES:
                self.voices.clear()
                self.analysis_bytes = 0
            self.voices[source['id']] = voices
            self.analysis_bytes += size
        voices = self.voices[source['id']]
        output = np.zeros((MAX_CHORD_FRAMES, source['channels']), dtype=np.float64)
        candidates = [pitch for pitch, voice in voices.items() if np.max(np.abs(voice), initial=0) > 1e-7]
        if not candidates:
            raise ContractError('Rhythm crop cannot supply source-derived voices; record or extract a better chord')
        for note in targets:
            pitch = min(candidates, key=lambda n: (abs(n - note), n))
            voice_key = (source['id'], pitch, note)
            if voice_key in self.warped_voices:
                voice = self.warped_voices.pop(voice_key)
                self.warped_voices[voice_key] = voice
            else:
                voice = pitch_shift(voices[pitch], note - pitch, maximum=MAX_CHORD_FRAMES)
                if len(voice) < len(output):
                    looped, loop = sustain_loop(voice, minimum_note=note, pitch_note=note)
                    repeat = looped[loop['startFrame']:loop['endFrame']]
                    voice = np.concatenate((looped, np.tile(repeat, (1 + MAX_CHORD_FRAMES // len(repeat), 1))))
                voice = voice[:len(output)].copy()
                while self.warped_voices and self.warped_bytes + voice.nbytes > MAX_WARP_BYTES:
                    _, old = self.warped_voices.popitem(last=False)
                    self.warped_bytes -= old.nbytes
                self.warped_voices[voice_key] = voice
                self.warped_bytes += voice.nbytes
            output += voice[:len(output)] / len(targets)
        source_peak = self.source_peaks[source['id']]
        return sustain_loop(normalize(output, peak=min(.42, source_peak)), minimum_note=min(targets))

    def sustain(self, sample):
        if sample['loop'] or sample['role'] == 'drums':
            return sample
        if sample['id'] in self.sustained:
            return self.sustained[sample['id']]
        result = self._prepare(('sustain', sample['id']), sample['role'], sample['pitches'], sample['chord'], sample,
                               'recorded attack retained; recorded interior sustain loop with stereo crossfade',
                               sample['lineage']['transformationCost'],
                               lambda: sustain_loop(read_pcm(self.pack.root / sample['path'], sample['onsetFrame'], limit=MAX_NOTE_FRAMES), minimum_note=min(sample['pitches']), pitch_note=sample['pitches'][0] if len(sample['pitches']) == 1 else None))
        result['gainDb'] = sample['gainDb']
        self.sustained[sample['id']] = result
        return result

    def _drum(self, slot):
        preferences = {'kick': ('tom1', 'tom2', 'snare'), 'snare': ('extra1', 'hatClosed', 'kick'),
                       'hatOpen': ('extra2', 'extra1', 'hatClosed'), 'hatClosed': ('hatOpen', 'extra2', 'extra1'),
                       'tom1': ('tom2', 'kick', 'extra1'), 'tom2': ('tom1', 'kick', 'extra1'),
                       'extra1': ('snare', 'hatOpen', 'kick'), 'extra2': ('extra1', 'hatOpen', 'snare')}
        records = self.pack.manifest['instruments']['drums']
        candidates = [(position, self.original_samples[records[name]['sampleId']]) for position, name in enumerate(preferences[slot])
                      if records[name]['status'] == 'available' and records[name]['pitchClass'] == 'unpitched']
        if not candidates:
            candidates = [(99, s) for s in self.original_samples.values() if s['role'] == 'drums' and not s['pitches']]
        if not candidates:
            raise ContractError(f'Cannot complete {slot}: supply a recorded percussion hit; synthesized replacements are disabled')
        _, source = min(candidates, key=lambda row: (row[0], -row[1]['quality']['confidence'], row[1]['id']))
        return self._prepare(('drums', slot), 'drums', [], None, source,
                             f'recorded {source["articulation"]}; source PCM warp/filter/decay preparation for {slot}; approximate articulation, not an extracted {slot}',
                             12, lambda: (drum_variant(read_pcm(self.pack.root / source['path'], source['onsetFrame']), slot), None))

    def _prepare(self, key, role, pitches, chord, source, recipe, cost, build):
        identity = 'hybrid_' + hashlib.sha256(canonical_bytes(dict(version=VERSION, key=key, source=source['id'], sha256=source['sha256']))).hexdigest()[:24]
        if identity in self.pack.samples:
            return self.pack.samples[identity]
        path = 'prepared/' + identity + '.wav'
        target = self.pack.root / path
        cached = self._cached(identity, key, source, role, pitches, chord)
        if cached is not None:
            sample, raw = cached
            self._account(len(raw))
            self._materialize(target, raw)
            self.pack.samples[identity] = sample
            self.cache_hits += 1
            return sample
        pcm, loop = build()
        if len(pcm) * pcm.shape[1] % 2:
            pcm = np.concatenate((pcm, np.zeros((1, pcm.shape[1]))))
        stream = io.BytesIO()
        with wave.open(stream, 'wb') as audio:
            audio.setnchannels(pcm.shape[1]); audio.setsampwidth(3); audio.setframerate(RATE); audio.writeframes(pcm24(pcm))
        raw = stream.getvalue()
        self._account(len(raw))
        self._materialize(target, raw)
        sample = dict(id=identity, path=path, role=role, articulation=str(key[-1]), sha256=hashlib.sha256(raw).hexdigest(),
                      sampleRate=RATE, bitsPerSample=24, channels=pcm.shape[1], frames=len(pcm), onsetFrame=0, gainDb=source['gainDb'],
                      pitches=pitches, chord=chord, loop=loop, source=copy.deepcopy(source['source']),
                      lineage=dict(kind='pre-rendered', sourceAsset=source['id'] + ':' + source['sha256'],
                                   recipe=VERSION + ': ' + recipe, transformationCost=min(100, cost)),
                      quality=dict(accepted=True, confidence=min(.8, source['quality']['confidence']),
                                   notes='Source-derived waveform transformation. Separation bleed, changed decay/formants and extreme-pitch timbre are approximate; human listening not performed.'))
        if self.pack.manifest['source']['kind'] == 'synthetic_fixture':
            sample['quality']['notes'] = 'Transformed synthetic developer fixture waveform; not source extraction or listening proof.'
        if role == 'rhythm':
            self.pack._chord_sample(sample)
        self.pack._wav(raw, path)
        self._cache(identity, key, source, sample, raw)
        self.pack.samples[identity] = sample
        return sample

    def _account(self, size):
        if self.prepared_bytes + size > MAX_SESSION_BYTES:
            raise ContractError('Prepared session exceeds 1 GiB; reopen the Song Pack to clear unused preparation history')
        self.prepared_bytes += size

    @staticmethod
    def _materialize(target, raw):
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o400)

    def _cached(self, identity, key, source, role, pitches, chord):
        if self.cache is None:
            return None
        try:
            metadata = self.cache / (identity + '.json')
            if metadata.is_symlink() or metadata.stat().st_size > 65536:
                return None
            record = read_json(metadata.read_bytes())
            if record['version'] != VERSION or record['key'] != list(key) or record['sourceSha256'] != source['sha256']:
                return None
            sample = record['sample']
            _validate(sample, self.sample_schema['$defs']['sample'], self.sample_schema, '$cachedSample', 0)
            if (sample['role'] != role or sample['pitches'] != pitches or sample['chord'] != chord
                    or sample['lineage']['kind'] != 'pre-rendered'
                    or sample['lineage']['sourceAsset'] != source['id'] + ':' + source['sha256']
                    or not sample['lineage']['recipe'].startswith(VERSION + ': ')
                    or sample['sampleRate'] != RATE or sample['bitsPerSample'] != 24
                    or sample['onsetFrame'] != 0 or sample['gainDb'] != source['gainDb']):
                return None
            data = self.cache / (identity + '.wav')
            if data.is_symlink() or data.stat().st_size > MAX_NOTE_FRAMES * 6 + 65536:
                return None
            raw = data.read_bytes()
            if sample['id'] != identity or sample['path'] != 'prepared/' + identity + '.wav' or hashlib.sha256(raw).hexdigest() != sample['sha256']:
                return None
            if self.pack._wav(raw, sample['path']) != (sample['channels'], sample['frames']):
                return None
            loop = sample['loop']
            if loop is not None and (role == 'drums' or set(loop) != {'startFrame', 'endFrame', 'validated'}
                    or type(loop['startFrame']) is not int or type(loop['endFrame']) is not int
                    or not 0 < loop['startFrame'] < loop['endFrame'] <= sample['frames']
                    or loop['validated'] is not True):
                return None
            if sample['role'] == 'rhythm':
                self.pack._chord_sample(sample)
            try:
                os.utime(metadata, None)
                os.utime(data, None)
            except OSError:
                pass
            return sample, raw
        except (OSError, ValueError, KeyError, TypeError, ContractError):
            return None

    def _cache(self, identity, key, source, sample, raw):
        if self.cache is None:
            return
        try:
            self.cache.mkdir(parents=True, exist_ok=True)
            files = list(self.cache.glob('hybrid_*.wav'))
            total = sum(p.stat().st_size for p in files)
            for old in sorted(files, key=lambda p: (p.stat().st_mtime_ns, p.name)):
                if total + len(raw) <= MAX_PREPARED_BYTES:
                    break
                total -= old.stat().st_size
                old.unlink(missing_ok=True)
                old.with_suffix('.json').unlink(missing_ok=True)
            for extension, data in (('.wav', raw), ('.json', canonical_bytes(dict(version=VERSION, key=key, sourceSha256=source['sha256'], sample=sample)))):
                descriptor, name = tempfile.mkstemp(prefix=identity + '-', dir=self.cache)
                try:
                    with os.fdopen(descriptor, 'wb') as output:
                        output.write(data); output.flush(); os.fsync(output.fileno())
                    os.replace(name, self.cache / (identity + extension))
                finally:
                    Path(name).unlink(missing_ok=True)
        except OSError:
            pass

    def prepare_bank(self, *, inversions=False):
        started = time.monotonic()
        from .percussion import prepare_bank as prepare_percussion
        percussion = prepare_percussion(self.pack)
        for role, (low, high) in REGISTERS.items():
            for note in range(low, high + 1):
                self.sample((role, note))
        for root in range(12):
            for quality, intervals in QUALITIES.items():
                for inversion in range(len(intervals) if inversions else 1):
                    self.sample(('rhythm', root, quality, inversion))
        return dict(version=VERSION, packId=self.pack.manifest['packId'], manifestSha256=self.pack.manifest_hash,
                    notes={role: high - low + 1 for role, (low, high) in REGISTERS.items()},
                    chords=12 * sum(len(v) if inversions else 1 for v in QUALITIES.values()),
                    inversions=inversions, playableKitSlots=[slot for slot, row in self.instruments['drums'].items() if row['status'] == 'available'],
                    percussionAddresses=[row['midiAddress'] for row in percussion],
                    percussionArticulations=len(percussion),
                    nativeAssets=len(self.original_samples), preparedAssets=len(self.pack.samples) - len(self.original_samples),
                    preparedBytes=self.prepared_bytes, analysisBytes=self.analysis_bytes + self.warped_bytes,
                    preparationSeconds=round(time.monotonic() - started, 3), cacheHits=self.cache_hits,
                    cacheVersion=VERSION, syntheticReplacement=False,
                    maximumNoteWarpSemitones=max(min(abs(note-s['pitches'][0]) for s in self._seeds(role)) for role, (lo, hi) in REGISTERS.items() for note in range(lo, hi+1)),
                    lineage='source PCM warps, masked polyphonic voices and source-derived percussion only',
                    humanListening='not_performed', extremePitchFidelity='approximate; source-dependent')
