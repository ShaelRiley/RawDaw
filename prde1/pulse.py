"""Repeating note dynamics, independent of the sample and mixer paths."""
from __future__ import annotations

import copy
from fractions import Fraction

from .music import at, beat

PRESETS = {
    'Pop backbeat': [90, 42, 65, 42, 100, 42, 70, 42, 85, 42, 65, 42, 100, 42, 75, 50],
    'Four on the floor': [100, 45, 75, 45] * 4,
    'Offbeat lift': [75, 40, 100, 45] * 4,
    'Half time': [100, 35, 60, 35, 70, 35, 55, 35, 100, 35, 65, 35, 70, 35, 60, 45],
    'Driving eighths': [100, 55, 85, 55] * 4,
    'Sixteenth funk': [100, 50, 65, 80, 90, 45, 75, 55, 95, 55, 65, 80, 90, 50, 75, 65],
    'Tresillo': [100, 45, 50, 90, 45, 50, 95, 55] * 2,
    'Gentle ballad': [85, 35, 50, 35, 65, 35, 55, 35, 75, 35, 50, 35, 65, 35, 55, 40],
    'Waltz': [100, 40, 55, 40, 65, 40, 50, 40, 65, 40, 50, 45],
    'Compound two': [100, 45, 60, 80, 45, 60, 95, 45, 60, 80, 45, 65],
    'Even': [80] * 16,
}


def settings(project):
    return copy.deepcopy(project.get('rhythmicPulse', dict(
        version='pulse-v1', mode='off', preset='Pop backbeat',
        levels=[v / 100 for v in PRESETS['Pop backbeat']], phaseBeat='0')))


def level(project, position):
    config = settings(project)
    meter = at(project['meterMap'], position)
    bar = Fraction(4 * meter['numerator'], meter['denominator'])
    # A scoped audition may begin mid-measure; later meter changes are genuine
    # downbeats and must discard that initial partial-measure offset.
    offset=beat(config.get('phaseBeat', '0')) if beat(meter['beat'])==0 else Fraction(0)
    phase = (position - beat(meter['beat']) + offset) % bar
    index = int(phase / bar * len(config['levels']))
    return config['levels'][index]


def entry_velocity(project, position, authored):
    """Guide sets an editable initial value; On leaves authored data intact."""
    return level(project, position) if settings(project)['mode'] == 'guide' else authored


def playback_velocity(project, position, authored, *, grace=False):
    if settings(project)['mode'] != 'on':
        return authored
    return level(project, position) * (.45 if grace else 1)


def set_pulse(editor, **values):
    def change(project):
        config = settings(project)
        config.update(values)
        project['rhythmicPulse'] = config
    editor.apply('Set rhythmic pulse', change)
