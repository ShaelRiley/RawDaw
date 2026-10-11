"""Offline hybrid instrument preparation; the Governor still never handles PCM.

Native mappings win. Unrecorded targets become explicit reconstructed assets in
the pack's private cache before the native sample player sees them. No network,
external sound bank, or mutable playback RNG is involved.
"""
from __future__ import annotations

import copy
import hashlib
import math
import wave
from array import array

from .contracts import ContractError, RATE, SLOTS
from .music import QUALITIES, REGISTERS

VERSION = 'hybrid-coverage-v1'
TABLE_SIZE = 2048


def chord_notes(root, quality, inversion):
    notes = [48 + root + interval for interval in QUALITIES[quality]]
    return sorted(note + (12 if i < inversion else 0) for i, note in enumerate(notes))


class Coverage:
    def __init__(self, pack):
        self.pack = pack
        self.original_samples = dict(pack.samples)
        self.original_mappings = dict(pack.mappings)
        self.generated = {}
        self.sustained = {}
        self.profiles = {}
        self.instruments = copy.deepcopy(pack.manifest['instruments'])
        addresses = {r['midiAddress'] for r in self.instruments['drums'].values() if r['midiAddress'] is not None}
        for slot in SLOTS:
            row = self.instruments['drums'][slot]
            if row['status'] == 'empty':
                continue  # Intentionally unused extras are not offered as sounds.
            if row['status'] != 'available' or row['pitchClass'] == 'uncertain':
                sample = self._drum(slot)
                address = next(n for n in range(128) if n not in addresses)
                addresses.add(address)
                row.update(status='available', reason='Reconstructed kit sound', sampleId=sample['id'],
                           soundIdentity=row['soundIdentity'] or 'hybrid_' + slot, midiAddress=address,
                           pitchClass='unpitched', pitches=[])
        for role in REGISTERS.keys() | {'rhythm'}:
            if self.instruments[role]['status'] != 'available':
                self.instruments[role].update(status='available', reason='Reconstructed instrument')

    def cost(self, key):
        native = self.original_mappings.get(key)
        return native['lineage']['transformationCost'] if native else 50

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
            notes, chord = [note], None
            # Integral cycles make a sample-accurate, continuously pitched loop.
            frames = round(RATE * 64 / (440 * 2 ** ((note - 69) / 12)))
        elif role == 'rhythm':
            _, root, quality, inversion = key
            if not 0 <= root <= 11 or quality not in QUALITIES or not 0 <= inversion < len(QUALITIES[quality]):
                raise ContractError('Invalid reconstruction target')
            notes = chord_notes(root, quality, inversion)
            chord = dict(root=root, quality=quality, inversion=inversion)
            frames = RATE
        else:
            raise ContractError('Unknown instrument reconstruction role')
        if not native and key in self.original_mappings:
            notes = self.original_mappings[key]['pitches']
        table, source = self._profile(role)
        data = array('d', [0.0]) * frames
        for note in notes:
            frequency = 440 * 2 ** ((note - 69) / 12)
            cycles = round(frames * frequency / RATE)
            # An integral number of cycles avoids loop phase discontinuities.
            step = cycles * TABLE_SIZE / frames
            for i in range(frames):
                phase = (i * step) % TABLE_SIZE
                index = int(phase)
                value = table[index] + (table[(index + 1) % TABLE_SIZE] - table[index]) * (phase - index)
                data[i] += value / len(notes)
        # Two identical periods: first carries the attack, second is pure sustain.
        attack = min(480, frames // 8)
        pcm = array('d', data)
        for i in range(attack):
            x = i / attack
            pcm[i] *= x * x * (3 - 2 * x)
        pcm.extend(data)
        sample = self._write(key, role, notes, chord, pcm, source, dict(startFrame=frames, endFrame=frames * 2, validated=True))
        self.generated[key] = sample
        return sample

    def sustain(self, sample):
        if sample['loop'] or sample['role'] == 'drums':
            return sample
        if sample['id'] in self.sustained:
            return self.sustained[sample['id']]
        role = sample['role']
        chord = sample['chord']
        key = (role, sample['pitches'][0]) if chord is None else (role, chord['root'], chord['quality'], chord['inversion'])
        modeled = self.sample(key, native=False)
        with wave.open(str(self.pack.root / sample['path'])) as audio:
            audio.setpos(sample['onsetFrame'])
            raw = audio.readframes(sample['frames'] - sample['onsetFrame'])
        channels = sample['channels']
        original = array('d', (sum(int.from_bytes(raw[(i * channels + c) * 3:(i * channels + c + 1) * 3], 'little', signed=True)
                            for c in range(channels)) / (channels * 8388608) for i in range(len(raw) // (channels * 3))))
        with wave.open(str(self.pack.root / modeled['path'])) as audio:
            audio.setpos(modeled['loop']['startFrame'])
            raw = audio.readframes(modeled['loop']['endFrame'] - modeled['loop']['startFrame'])
        loop = array('d', (int.from_bytes(raw[i:i + 3], 'little', signed=True) / 8388608 for i in range(0, len(raw), 3)))
        original = original[:1440000 - len(loop)]
        blend = min(1920, len(original) // 4, len(loop) // 4)
        for i in range(blend):
            x = (i + 1) / blend; x = x * x * (3 - 2 * x)
            original[len(original) - blend + i] = original[len(original) - blend + i] * (1 - x) + loop[i] * x
        first = len(original)
        original.extend(loop[blend:]); original.extend(loop[:blend])
        result = self._write(('sustain', sample['id']), role, sample['pitches'], chord, original, sample['id'],
                             dict(startFrame=first, endFrame=len(original), validated=True))
        result['gainDb'] = sample['gainDb']
        self.sustained[sample['id']] = result
        return result

    def _profile(self, role):
        if role in self.profiles:
            return self.profiles[role]
        seeds = [s for s in self.original_samples.values() if s['role'] == role and s['pitches']]
        seeds.sort(key=lambda s: (s['lineage']['transformationCost'], -s['quality']['confidence'], s['id']))
        defaults = {'bass': (1, .22, .08, .03), 'lead': (1, .5, .25, .12), 'rhythm': (1, .4, .22, .1)}
        amplitudes, source = defaults[role], ''
        if seeds:
            seed = seeds[0]
            with wave.open(str(self.pack.root / seed['path']), 'rb') as audio:
                audio.setpos(seed['onsetFrame'])
                raw = audio.readframes(min(8192, seed['frames'] - seed['onsetFrame']))
            channels = seed['channels']
            mono = [sum(int.from_bytes(raw[(i * channels + c) * 3:(i * channels + c + 1) * 3], 'little', signed=True)
                        for c in range(channels)) / (channels * 8388608) for i in range(0, len(raw) // (channels * 3), 4)]
            fundamental = 440 * 2 ** ((min(seed['pitches']) - 69) / 12)
            spectrum = []
            for h in range(1, 9):
                step = 2 * math.pi * fundamental * h * 4 / RATE
                real = sum(v * math.cos(i * step) for i, v in enumerate(mono))
                imag = sum(v * math.sin(i * step) for i, v in enumerate(mono))
                spectrum.append(math.hypot(real, imag))
            if max(spectrum, default=0) > 1e-6:
                scale = max(spectrum)
                amplitudes = [max(.03 / (i + 1), v / scale) for i, v in enumerate(spectrum)]
                amplitudes[0] = max(.5, amplitudes[0])
            source = seed['id']
        table = [sum(a * math.sin(2 * math.pi * (h + 1) * i / TABLE_SIZE) for h, a in enumerate(amplitudes))
                 for i in range(TABLE_SIZE)]
        scale = .22 / max(abs(v) for v in table)
        table = [v * scale for v in table]
        self.profiles[role] = table, source
        return table, source

    def _drum(self, slot):
        # Explicit modeled percussion for gaps; never claim source extraction.
        frames = int(RATE * (.6 if slot in ('hatOpen', 'extra1') else .3))
        pitches = {'kick': 55, 'snare': 180, 'tom1': 110, 'tom2': 165}
        state = int(hashlib.sha256((self.pack.manifest_hash + slot + VERSION).encode()).hexdigest()[:8], 16)
        pcm = array('d')
        phase = 0.0
        for i in range(frames):
            t = i / RATE
            state = (1664525 * state + 1013904223) & 0xffffffff
            noise = state / 2147483648 - 1
            phase += 2 * math.pi * pitches.get(slot, 8000) * (1 + 2 * math.exp(-t * 35)) / RATE
            value = math.sin(phase) if slot in ('kick', 'tom1', 'tom2') else .8 * noise + .2 * math.sin(phase)
            value *= .22 * math.exp(-t * (9 if slot in ('hatOpen', 'extra1') else 24)) * min(1, i / 48)
            value *= min(1, (frames - 1 - i) / 240)
            pcm.append(value)
        return self._write(('drums', slot), 'drums', [], None, pcm, '', None)

    def _write(self, key, role, pitches, chord, pcm, source, loop):
        # Python's wave writer does not add RIFF word padding for an odd mono
        # 24-bit data chunk. A frame outside the sustain loop keeps it canonical.
        if len(pcm) % 2:pcm.append(0.0)
        identity = 'hybrid_' + hashlib.sha256((VERSION + repr(key)).encode()).hexdigest()[:24]
        path = 'prepared/' + identity + '.wav'
        target = self.pack.root / path
        target.parent.mkdir(exist_ok=True)
        raw = bytearray(len(pcm) * 3)
        for i, value in enumerate(pcm):
            raw[i * 3:i * 3 + 3] = round(value * 8388607).to_bytes(3, 'little', signed=True)
        with wave.open(str(target), 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(3); audio.setframerate(RATE); audio.writeframes(raw)
        target.chmod(0o400)
        sample = dict(id=identity, path=path, role=role, articulation=str(key[-1]), sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                      sampleRate=RATE, bitsPerSample=24, channels=1, frames=len(pcm), onsetFrame=0, gainDb=0,
                      pitches=pitches, chord=chord, loop=loop, source=dict(seconds=0, quarterBeat='0', durationSeconds=len(pcm) / RATE),
                      lineage=dict(kind='synthetic', sourceAsset=source, recipe=VERSION + ': source-informed harmonic model' if source else VERSION + ': modeled instrument', transformationCost=50),
                      quality=dict(accepted=True, confidence=1, notes='Reconstructed sound; musical identity checked, source fidelity approximate'))
        if role == 'rhythm':
            self.pack._chord_sample(sample)
        self.pack._wav(target.read_bytes(), path)
        self.pack.samples[identity] = sample
        return sample
