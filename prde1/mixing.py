"""Static drum EQ and dynamics settings; no sample edits or Governor decisions."""
from __future__ import annotations

import copy
from .contracts import ContractError, SLOTS

PROCESSING_VERSION = 'drum-mix-v1'
# HP cutoff; bell center, boost/cut, Q; high-shelf center and gain (Hz/dB).
DRUM_PRESETS = {
    'kick': ('Kick punch', 30, 65, 3, .8, 3000, 2),
    'snare': ('Snare crack', 110, 190, 2.5, .9, 4500, 2),
    'hatClosed': ('Closed hat clarity', 450, 6500, -1.5, 1, 9000, 1.5),
    'hatOpen': ('Open hat air', 350, 5000, -1, 1, 10500, 1),
    'tom1': ('Low tom body', 45, 110, 2.5, .8, 3500, 1),
    'tom2': ('High tom attack', 65, 180, 2.5, .8, 4500, 1.5),
    'extra1': ('Extra 1 presence', 100, 2200, 1.5, .9, 8000, 1),
    'extra2': ('Extra 2 air', 180, 3200, -1, .9, 10000, 2),
}
DRUM_COMPRESSOR = dict(on=True, thresholdDb=-26, ratio=3, attackMs=25, releaseMs=100, makeupDb=3)
BASS_SIDECHAIN = dict(on=True, thresholdDb=-30, ratio=4, attackMs=1, releaseMs=140, maxDuckDb=6)


def drum_eq(slot, on=True):
    _, hp, hz, db, q, shelf, air = DRUM_PRESETS[slot]
    return dict(on=on, highpassHz=hp, bellHz=hz, bellDb=db, bellQ=q, shelfHz=shelf, shelfDb=air)


def apply_punch_mix(project):
    """Explicit, undoable starting preset; preserve authored faders and pans."""
    mix = project['mix']
    for slot in SLOTS:
        mix['channels']['drums.'+slot].update(eqPreset='drum-punch', eq=drum_eq(slot))
    mix['drumBusCompressor'] = copy.deepcopy(DRUM_COMPRESSOR)
    mix['bassSidechain'] = copy.deepcopy(BASS_SIDECHAIN)
    mix['compressor'] = dict(on=True,thresholdDb=-18,ratio=2,attackMs=10,releaseMs=150,makeupDb=0)


def processing_settings(project):
    """Old saves stay dry until a creator enables processing or applies a preset."""
    mix = project['mix']; channels = mix['channels']
    present = any('eq' in channels['drums.'+s] or channels['drums.'+s]['eqPreset']=='drum-punch' for s in SLOTS)
    if not present and not any(k in mix for k in ('drumBusCompressor','bassSidechain')):
        return None
    eq = {}
    for slot in SLOTS:
        ch = channels['drums.'+slot]
        eq[slot] = copy.deepcopy(ch.get('eq', drum_eq(slot, ch['eqPreset']=='drum-punch')))
    compressor = copy.deepcopy(mix.get('drumBusCompressor', dict(DRUM_COMPRESSOR, on=False)))
    sidechain = copy.deepcopy(mix.get('bassSidechain', dict(BASS_SIDECHAIN, on=False)))
    group = channels['drums']
    return dict(version=PROCESSING_VERSION, drumEq=eq, drumBusCompressor=compressor, bassSidechain=sidechain,
                drumBusGain=10**(group['gainDb']/20), drumBusPan=group['pan'])


def validate_supported_channel(name, channel):
    if channel['reverbOn'] or channel['delayOn']:
        raise ContractError('This checkpoint cannot render reverb/delay; settings are preserved')
    is_drum = name.startswith('drums.') and name[6:] in SLOTS
    if channel['eqPreset'] not in (('neutral','drum-punch','custom') if is_drum else ('neutral',)):
        raise ContractError('Unsupported EQ preset: '+name+' / '+channel['eqPreset'])
    if 'eq' in channel and not is_drum:
        raise ContractError('Custom EQ is currently supported only on individual drum channels')
    if channel['eqPreset']=='custom' and 'eq' not in channel:
        raise ContractError('Custom drum EQ requires saved filter settings')
    if any(not insert['bypassed'] for insert in channel['inserts']):
        raise ContractError('Active VST effect insert cannot be rendered; explicitly bypass it or use a future host')
