"""Pure musical metadata; deliberately has no audio or sample-file API."""
from __future__ import annotations

from fractions import Fraction

from .contracts import ContractError

REGISTRY_VERSION = "core-v1-dev.1"
MODES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "natural_minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "melodic_minor_ascending": (0, 2, 3, 5, 7, 9, 11),
}
QUALITIES = {
    "major": (0, 4, 7), "minor": (0, 3, 7), "diminished": (0, 3, 6), "augmented": (0, 4, 8),
    "power": (0, 7), "sus2": (0, 2, 7), "sus4": (0, 5, 7),
    "major7": (0, 4, 7, 11), "minor7": (0, 3, 7, 10), "dominant7": (0, 4, 7, 10),
    "halfDiminished7": (0, 3, 6, 10), "diminished7": (0, 3, 6, 9), "minorMajor7": (0, 3, 7, 11),
}
REGISTERS = {"bass": (28, 60), "lead": (48, 84)}
NAMES = ("C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B")


def beat(value: str) -> Fraction:
    result = Fraction(value)
    if result < 0 or result > 65536 or result.denominator > 1000000:
        raise ContractError("Musical position exceeds profile bounds")
    return result


def grid_positions(start: Fraction, numerator: int, denominator: int, segments: int) -> list[Fraction]:
    if segments not in (3, 4, 6, 8) or denominator not in (2,4,8,16) or not 1 <= numerator <= 16:
        raise ContractError("Unsupported meter/grid")
    length = Fraction(4 * numerator, denominator)
    return [start + index * length / segments for index in range(segments)]


def at(events: list[dict], position: Fraction) -> dict:
    current = events[0]
    for event in events[1:]:
        if beat(event["beat"]) > position:
            break
        current = event
    return current


def chord_identity(tonic: int, mode: str, chord: dict) -> tuple[int, tuple[int,...], bool]:
    if mode not in MODES or chord["quality"] not in QUALITIES:
        raise ContractError("Unknown musical registry entry")
    scale = {(tonic + interval) % 12 for interval in MODES[mode]}
    root = (tonic + MODES[mode][chord["degree"] - 1] + chord["alteration"]) % 12
    pitches = tuple((root + interval) % 12 for interval in QUALITIES[chord["quality"]])
    return root, pitches, set(pitches).issubset(scale)


def diatonic(tonic: int, mode: str, degree: int) -> dict:
    intervals = MODES[mode]
    index = degree - 1
    distances = tuple((intervals[(index + step) % 7] - intervals[index]) % 12 for step in (0,2,4))
    for quality, content in QUALITIES.items():
        if content == distances:
            return {"degree": degree, "alteration": 0, "quality": quality, "inversion": 0}
    raise ContractError("No registered diatonic triad")


def roman(chord: dict) -> str:
    base = ("I", "II", "III", "IV", "V", "VI", "VII")[chord["degree"] - 1]
    quality = chord["quality"]
    if quality in ("minor", "diminished", "minor7", "halfDiminished7", "diminished7", "minorMajor7"):
        base = base.lower()
    suffix = {"diminished": "°", "augmented": "+", "power": "5", "sus2": "sus2", "sus4": "sus4",
              "major7": "maj7", "minor7": "7", "dominant7": "7", "halfDiminished7": "ø7",
              "diminished7": "°7", "minorMajor7": "(maj7)"}.get(quality, "")
    prefix = {0: "", -1: "♭", 1: "♯"}[chord["alteration"]]
    inversion = ("", "/1st", "/2nd", "/3rd")[chord["inversion"]]
    return prefix + base + suffix + inversion


def quarter_seconds(position: Fraction, tempo_map: list[dict]) -> float:
    total = 0.0
    start = Fraction(0)
    bpm = tempo_map[0]["quarterBpm"]
    for entry in tempo_map[1:]:
        boundary = beat(entry["beat"])
        if boundary >= position:
            break
        total += float(boundary - start) * 60 / bpm
        start, bpm = boundary, entry["quarterBpm"]
    return total + float(position - start) * 60 / bpm
