"""Complete General MIDI percussion addresses from the pack's recorded hits.

GM names identify requested articulations. Missing recordings remain explicit
source-derived approximations, never native recordings or synthesized fills.
The immutable eight-channel mixer routes these additional sounds by family.
Reference map: https://data.yamaha.com/files/download/other_assets/8/467418/psra3000_en_dl_a0.pdf
"""
from __future__ import annotations

import copy
import hashlib
import numpy as np

from .contracts import ContractError, RATE, SLOTS, canonical_bytes
from .source_waveform import drum_variant, normalize, pitch_shift, read_pcm

VERSION = 'gm-source-percussion-v1'
NAMES = (
    'Acoustic Bass Drum', 'Bass Drum 1', 'Side Stick', 'Acoustic Snare', 'Hand Clap', 'Electric Snare',
    'Low Floor Tom', 'Closed Hi-Hat', 'High Floor Tom', 'Pedal Hi-Hat', 'Low Tom', 'Open Hi-Hat',
    'Low-Mid Tom', 'High-Mid Tom', 'Crash Cymbal 1', 'High Tom', 'Ride Cymbal 1', 'Chinese Cymbal',
    'Ride Bell', 'Tambourine', 'Splash Cymbal', 'Cowbell', 'Crash Cymbal 2', 'Vibraslap', 'Ride Cymbal 2',
    'High Bongo', 'Low Bongo', 'Mute High Conga', 'Open High Conga', 'Low Conga', 'High Timbale',
    'Low Timbale', 'High Agogo', 'Low Agogo', 'Cabasa', 'Maracas', 'Short Whistle', 'Long Whistle',
    'Short Guiro', 'Long Guiro', 'Claves', 'High Wood Block', 'Low Wood Block', 'Mute Cuica',
    'Open Cuica', 'Mute Triangle', 'Open Triangle',
)
GM = {address: name for address, name in enumerate(NAMES, 35)}
SOUND_SLOTS = frozenset(SLOTS) | {'gm_' + str(address) for address in GM}
_FAMILIES = {
    'kick': {35, 36}, 'snare': {37, 38, 39, 40}, 'hatClosed': {42, 44}, 'hatOpen': {46},
    'tom1': {41, 43, 45, 61, 64, 66, 68, 77}, 'tom2': {47, 48, 50, 60, 62, 63, 65, 76},
    'extra1': {49, 52, 55, 57, 58, 69, 70, 73, 74},
    'extra2': {51, 53, 54, 56, 59, 67, 71, 72, 75, 78, 79, 80, 81},
}
_PREFERENCES = {
    'kick': ('kick', 'tom1', 'tom2', 'snare'), 'snare': ('snare', 'hatClosed', 'extra1', 'kick'),
    'hatClosed': ('hatClosed', 'hatOpen', 'extra1', 'snare'), 'hatOpen': ('hatOpen', 'hatClosed', 'extra1', 'snare'),
    'tom1': ('tom1', 'tom2', 'kick', 'snare'), 'tom2': ('tom2', 'tom1', 'kick', 'snare'),
    'extra1': ('extra1', 'hatOpen', 'hatClosed', 'snare'), 'extra2': ('extra2', 'hatOpen', 'hatClosed', 'snare'),
}


def family(address):
    return next(slot for slot, addresses in _FAMILIES.items() if address in addresses)


def _initialize(pack):
    coverage = pack.coverage
    if hasattr(coverage, 'percussion'):
        return
    coverage.percussion = {}
    coverage.percussion_sources = {}
    original = pack.manifest['instruments']['drums']
    candidates = {slot: coverage.original_samples[row['sampleId']] for slot, row in original.items()
                  if row['status'] == 'available' and row['pitchClass'] == 'unpitched'}
    if not candidates:
        raise ContractError('A complete percussion bank requires at least one recorded unpitched hit')
    for address, name in GM.items():
        mix = family(address)
        exact = next((slot for slot in candidates if original[slot]['midiAddress'] == address), None)
        seed = exact or next((slot for slot in _PREFERENCES[mix] if slot in candidates), next(iter(candidates)))
        source = candidates[seed]
        identity = 'gm_' + str(address) + '_' + hashlib.sha256(canonical_bytes(
            dict(version=VERSION, source=source['id'], sha256=source['sha256']))).hexdigest()[:16]
        row = dict(status='available', reason='Recorded source hit' if exact else 'Source-derived approximate articulation',
                   sampleId=source['id'] if exact else None, displayName=name, soundIdentity=identity,
                   midiAddress=address, pitchClass='unpitched', pitches=[], mixSlot=mix,
                   derived=exact is None, sourceAsset=source['id'] + ':' + source['sha256'])
        coverage.percussion['gm_' + str(address)] = row
        coverage.percussion_sources[address] = (source, seed)


def records(pack):
    """Available metadata requires no PCM preparation; preserve all old kit rows."""
    _initialize(pack)
    return {**pack.instruments['drums'], **pack.coverage.percussion}


all_records = records


def record(pack, slot):
    if slot in SLOTS:
        return pack.instruments['drums'][slot]
    _initialize(pack)
    try:
        return pack.coverage.percussion[slot]
    except KeyError as exc:
        raise ContractError('Unknown percussion articulation') from exc


def address_slot(pack, address):
    if address in GM:
        return 'gm_' + str(address)
    return next((slot for slot, row in pack.instruments['drums'].items()
                 if row['status'] == 'available' and row['midiAddress'] == address), None)


def semantic_slot(pack, name):
    """Library aliases are explicit musical requests, not replacements of extras."""
    if name in SOUND_SLOTS:
        return name
    aliases = {'crash': 49, 'ride': 51, 'clap': 39, 'cowbell': 56, 'tambourine': 54,
               'shaker': 70, 'sideStick': 37}
    if name in aliases:
        return 'gm_' + str(aliases[name])
    return next((slot for slot, row in records(pack).items()
                 if row['soundIdentity'].casefold() == name.casefold() or row['displayName'].casefold() == name.casefold()), None)


def sample(pack, slot):
    row = record(pack, slot)
    if row['status'] != 'available':
        raise ContractError('This optional source kit slot is unassigned')
    if row['sampleId'] is not None:
        return pack.samples[row['sampleId']]
    address = row['midiAddress']
    source, seed_slot = pack.coverage.percussion_sources[address]
    target = row['mixSlot']
    # Every operation transforms a recording. No oscillators, random excitation,
    # MIDI synthesizer, generated noise, or unrelated external bank is involved.
    def build():
        audio = read_pcm(pack.root / source['path'], source['onsetFrame'], limit=RATE)
        processing_family = target if target in ('kick', 'snare', 'hatClosed', 'hatOpen', 'tom1', 'tom2') else 'hatOpen'
        audio = drum_variant(audio, processing_family)
        shifts = {35: -3, 37: 7, 39: 2, 40: 3, 41: -5, 43: -2, 44: 2, 45: 0, 47: -2,
                  48: 2, 50: 5, 60: 7, 61: 2, 62: 5, 63: 3, 64: -2, 65: 9, 66: 4,
                  67: 12, 68: 7, 75: 9, 76: 12, 77: 7, 78: 4, 79: 2, 80: 12, 81: 12}
        audio = pitch_shift(audio, shifts.get(address, (address % 5)-2), maximum=RATE)
        frequency = np.fft.rfftfreq(len(audio), 1 / RATE)
        if address in (37, 54, 56, 67, 68, 71, 72, 75, 76, 77, 80, 81):
            centers = {56: 850, 67: 1700, 68: 1250, 71: 2800, 72: 2400, 80: 5800, 81: 5800}
            center = centers.get(address, 1900)
            mask = np.exp(-.5*((frequency-center)/(center*.3))**2)
            spectrum = np.fft.rfft(audio, axis=0)
            audio = np.fft.irfft(spectrum*mask[:, None], n=len(audio), axis=0)
        seconds = {37: .075, 39: .17, 44: .08, 54: .19, 55: .24, 58: .31, 62: .13, 69: .13,
                   70: .11, 71: .18, 72: .65, 73: .15, 74: .5, 75: .055, 76: .1, 77: .12, 78: .15, 80: .15, 81: .6}.get(address, .5)
        length = min(len(audio), max(48, round(seconds*RATE)))
        audio = audio[:length].copy()
        audio *= np.exp(-np.linspace(0, 5 if address in (37, 62, 75, 78, 80) else 3, len(audio)))[:, None]
        audio = normalize(audio, peak=.3)
        fade = min(480, len(audio)//4)
        audio[-fade:] *= np.linspace(1, 0, fade)[:, None]
        audio[:min(48,len(audio))] *= np.linspace(0,1,min(48,len(audio)))[:,None]
        return audio, None
    result = pack.coverage._prepare((VERSION, address), 'drums', [], None, source,
        f'recorded {seed_slot} PCM; pitch warp/filter/decay for GM {address} {GM[address]}; approximate articulation, not an extracted recording',
        20, build)
    row['sampleId'] = result['id']
    return result


def prepare_bank(pack):
    for address in GM:
        sample(pack, 'gm_' + str(address))
    return [copy.deepcopy(record(pack, 'gm_' + str(address))) for address in GM]
