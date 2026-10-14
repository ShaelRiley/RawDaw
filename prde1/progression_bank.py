"""Offline, reusable harmony templates. No audio processing or runtime network.

Degrees explicitly follow the destination mode; authored Roman qualities never
do. Major-relative roots are converted by pitch class into the project registry.
Loading writes ordinary, self-contained harmony and uses the existing undo path.
"""
from __future__ import annotations

import copy
import hashlib
import re
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

from .contracts import ContractError, atomic_json, canonical_bytes, read_json
from .music import MODES, NAMES, QUALITIES, REGISTERS, at, beat, chord_identity, chord_suffix, diatonic, quarter_seconds, roman

FORMAT = 'raw-daw-progressions'
VERSION = 1
MAX_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_CHORDS = 64
DATA = Path(__file__).resolve().parent / 'data/progressions.json'
ENTRY_FIELDS = {'id', 'name', 'style', 'section', 'modes', 'kind', 'basis', 'sequence',
                'durations', 'durationUnit', 'description', 'sourceNotation', 'credits', 'priority'}


def _text(value, label, limit=240, *, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ContractError(f'{label} must be text of at most {limit} characters')
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise ContractError(f'{label} contains control characters')
    return value.strip()


def _duration(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ContractError('Durations must be positive integers or rational strings, e.g. "1/2"')
    try:
        result = beat(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ContractError('Invalid progression duration') from exc
    if not 0 < result <= 128 or result.denominator > 192:
        raise ContractError('Each duration must be > 0, at most 128, with denominator at most 192')
    return str(result)


def musical_signature(entry):
    """No tonic, name, genre or transposed copies inflate the distinct inventory."""
    return canonical_bytes({k: entry[k] for k in ('kind', 'basis', 'sequence', 'durations', 'durationUnit')})


def equivalence_signature(entry):
    """Enharmonic spellings are equal only when they agree in every mode."""
    sequence = entry['sequence']
    if entry['kind'] == 'chords':
        sequence = [dict(roots=[(MODES['major' if entry['basis'] == 'major-relative' else mode][c['degree']-1]
                                 + c['alteration']) % 12 for mode in MODES],
                         quality=c['quality'], inversion=c['inversion']) for c in sequence]
    return canonical_bytes(dict(kind=entry['kind'], sequence=sequence,
                                durations=entry['durations'], durationUnit=entry['durationUnit']))


def validate_entry(value):
    if not isinstance(value, dict) or set(value) - ENTRY_FIELDS:
        raise ContractError('Progression must be an object with documented fields only')
    entry = copy.deepcopy(value)
    entry['name'] = _text(entry.get('name'), 'Progression name', 100)
    for key, default, limit in [('style', 'Custom', 80), ('section', 'Loop', 80),
                                ('description', '', 1000), ('sourceNotation', '', 2000)]:
        entry[key] = _text(entry.get(key, default), key, limit, empty=key in ('description', 'sourceNotation'))
    kind = entry.get('kind')
    if kind not in ('degrees', 'chords'):
        raise ContractError('kind must be "degrees" (mode-derived) or "chords" (exact qualities)')
    basis = entry.get('basis', 'mode-relative' if kind == 'degrees' else None)
    if basis not in ('mode-relative', 'major-relative') or (kind == 'degrees' and basis != 'mode-relative'):
        raise ContractError('Declare basis "mode-relative" or "major-relative"; degrees are mode-relative')
    entry['basis'] = basis
    sequence = entry.get('sequence')
    if isinstance(sequence, str):
        entry['sourceNotation'] = entry['sourceNotation'] or sequence
        if kind == 'degrees':
            tokens = re.split(r'[\s,–—-]+', sequence.strip())
            if not tokens or not all(token in tuple(str(i) for i in range(1, 8)) for token in tokens):
                raise ContractError('Degree templates use numbers 1–7 only')
            sequence = [int(token) for token in tokens]
        else:
            if re.search(r'(^|[\s,–—-])[1-7]($|[\s,–—-])', sequence):
                raise ContractError('Use Roman chords only for exact-quality entries; numbers belong in degree templates')
            from .editor import parse_progression
            sequence = parse_progression(sequence, 0, 'major')
    if not isinstance(sequence, list) or not 1 <= len(sequence) <= MAX_CHORDS:
        raise ContractError(f'Each progression needs 1–{MAX_CHORDS} chords')
    if kind == 'degrees':
        if any(type(n) is not int or not 1 <= n <= 7 for n in sequence):
            raise ContractError('Degree templates use integers 1–7 only')
    else:
        for chord in sequence:
            if not isinstance(chord, dict) or set(chord) != {'degree', 'alteration', 'quality', 'inversion'}:
                raise ContractError('Each exact chord needs degree, alteration, quality and inversion')
            if (type(chord['degree']) is not int or not 1 <= chord['degree'] <= 7
                    or type(chord['alteration']) is not int or chord['alteration'] not in (-1, 0, 1)
                    or not isinstance(chord['quality'], str) or chord['quality'] not in QUALITIES
                    or type(chord['inversion']) is not int
                    or not 0 <= chord['inversion'] < len(QUALITIES[chord['quality']])):
                raise ContractError('Unknown chord quality, invalid degree/accidental or impossible inversion')
    entry['sequence'] = sequence
    durations = entry.get('durations', ['1'])
    if not isinstance(durations, list) or len(durations) not in (1, len(sequence)):
        raise ContractError('Provide one duration or one duration per chord')
    lengths = [_duration(v) for v in durations]
    if len(lengths) == 1:
        lengths *= len(sequence)
    if sum(Fraction(v) for v in lengths) > 512:
        raise ContractError('A progression cycle may span at most 512 duration units')
    entry['durations'] = lengths
    entry['durationUnit'] = entry.get('durationUnit', 'bars')
    if entry['durationUnit'] not in ('bars', 'beats'):
        raise ContractError('durationUnit must be "bars" or quarter-note "beats"')
    modes = entry.get('modes', list(MODES))
    if not isinstance(modes, list) or not modes or any(not isinstance(m, str) or m not in MODES for m in modes):
        raise ContractError('modes must be a nonempty list of supported mode names')
    entry['modes'] = list(dict.fromkeys(modes))
    priority = entry.get('priority', 3)
    if type(priority) is not int or not 1 <= priority <= 5:
        raise ContractError('priority must be an integer 1–5')
    entry['priority'] = priority
    credits = entry.get('credits', [dict(source=entry['name'], license='User-supplied; rights unspecified',
                                      attribution='Imported or authored by the user', changes='Reusable harmony')])
    if not isinstance(credits, list) or not 1 <= len(credits) <= 4096:
        raise ContractError('Provide 1–4096 credit records within the bank file limit')
    for record in credits:
        if not isinstance(record, dict) or set(record) != {'source', 'license', 'attribution', 'changes'}:
            raise ContractError('Each credit needs source, license, attribution and changes')
        for key in record:
            record[key] = _text(record[key], 'Credit ' + key, 2000)
    entry['credits'] = credits
    entry['id'] = 'progression_' + hashlib.sha256(musical_signature(entry)).hexdigest()[:24]
    return entry


def validate_bank(value):
    if (not isinstance(value, dict) or set(value) - {'format', 'version', 'entries', 'favorites'}
            or value.get('format') != FORMAT or type(value.get('version')) is not int
            or value['version'] != VERSION):
        raise ContractError(f'Expected {FORMAT} bank version {VERSION}')
    entries = value.get('entries')
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ContractError(f'A bank may contain at most {MAX_ENTRIES} progressions')
    result = []
    for i, entry in enumerate(entries):
        try:
            result.append(validate_entry(entry))
        except (ValueError, TypeError, KeyError) as exc:
            raise ContractError(f'Progression {i+1}: {exc}') from exc
    favorites = value.get('favorites', [])
    if not isinstance(favorites, list) or len(favorites) > MAX_ENTRIES + 1024:
        raise ContractError('Invalid favorites list')
    for identity in favorites:
        if not isinstance(identity, str) or not re.fullmatch(r'progression_[a-f0-9]{24}', identity):
            raise ContractError('Invalid favorite progression identity')
    return result, set(favorites)


def load_file(path, *, text_basis='mode-relative', text_unit='bars'):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ContractError('Progression import exceeds 2 MiB')
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ContractError('Progression import exceeds 2 MiB')
    if path.suffix.lower() == '.json':
        return validate_bank(read_json(data))[0]
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ContractError('Text progressions must use UTF-8') from exc
    result = []
    for line_number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(('# ', '//')):
            continue
        fields = [s.strip() for s in line.split('|')]
        if len(fields) > 3:
            raise ContractError(f'Line {line_number}: use Name | chords | durations')
        name, notation = fields[:2] if len(fields) >= 2 else (f'Imported {line_number}', fields[0])
        tokens = re.split(r'[\s,–—-]+', notation)
        kind = 'degrees' if all(t in tuple(str(i) for i in range(1, 8)) for t in tokens) else 'chords'
        try:
            result.append(validate_entry(dict(name=name, style='Imported', kind=kind,
                basis='mode-relative' if kind == 'degrees' else text_basis,
                sequence=notation, sourceNotation=notation, durationUnit=text_unit,
                durations=fields[2].replace(',', ' ').split() if len(fields) == 3 else ['1'],
                credits=[dict(source=path.name, license='User-supplied; rights unspecified',
                              attribution=name, changes='Imported progression; original notation retained')])) )
        except (ValueError, TypeError, KeyError) as exc:
            raise ContractError(f'Line {line_number}: {exc}') from exc
        if len(result) > MAX_ENTRIES:
            raise ContractError(f'A bank may contain at most {MAX_ENTRIES} progressions')
    if not result:
        raise ContractError('The file contains no progressions')
    return result


@lru_cache(maxsize=1)
def catalog():
    entries, _ = validate_bank(read_json(DATA.read_bytes()))
    if len({e['id'] for e in entries}) != len(entries):
        raise ContractError('Built-in progression bank contains duplicate musical identities')
    return tuple(entries)


def relative_root(offset, mode, preferred=None):
    """Represent every actual root with the registry's ±1 accidentals."""
    scale = MODES[mode]
    candidates = []
    for i, interval in enumerate(scale):
        delta = (offset - interval + 6) % 12 - 6
        if delta in (-1, 0, 1):
            candidates.append((i+1 != preferred, abs(delta), i+1, delta))
    if not candidates:
        raise ContractError('Root cannot be represented in the selected mode')
    _, _, degree, alteration = min(candidates)
    return degree, alteration


def realize(entry, tonic, mode):
    if entry['kind'] == 'degrees':
        return [diatonic(tonic, mode, degree) for degree in entry['sequence']]
    result = copy.deepcopy(entry['sequence'])
    if entry['basis'] == 'major-relative':
        for chord in result:
            offset = (MODES['major'][chord['degree']-1] + chord['alteration']) % 12
            chord['degree'], chord['alteration'] = relative_root(offset, mode, chord['degree'])
    return result


def chord_name(tonic, mode, chord):
    root, _, _ = chord_identity(tonic, mode, chord)
    return NAMES[root] + chord_suffix(chord['quality'])


def ranked(pack, tonic, mode, entries=None):
    """Explainable modal recommendations and preparation costs; no PCM creation."""
    entries = catalog() if entries is None else entries
    chord_costs = {}
    note_costs = {(role, pitch): min(pack.coverage.cost((role, n)) for n in range(low, high+1)
                                   if n % 12 == pitch)
                  for role, (low, high) in REGISTERS.items() for pitch in range(12)}
    result = []
    for entry in entries:
        chords = realize(entry, tonic, mode)
        weighted = []
        for chord, duration in zip(chords, entry['durations']):
            root, pitches, _ = chord_identity(tonic, mode, chord)
            key = (root, chord['quality'], chord['inversion'])
            if key not in chord_costs:
                chord_costs[key] = pack.coverage.cost(('rhythm', *key))
            costs = [chord_costs[key], *[note_costs[(role, pitch)] for role in REGISTERS for pitch in pitches]]
            weighted.extend((cost, Fraction(duration)) for cost in costs)
        worst = max((cost for cost, _ in weighted), default=0)
        average = float(sum(cost * duration for cost, duration in weighted) / sum(d for _, d in weighted))
        suitable = mode in entry['modes']
        targets = {(chord_identity(tonic, mode, c)[0], c['quality'], c['inversion']) for c in chords}
        native = sum(('rhythm', *key) in pack.coverage.original_mappings and chord_costs[key] == 0 for key in targets)
        reconstructed = sum(('rhythm', *key) not in pack.coverage.original_mappings for key in targets)
        prepared = len(targets) - native - reconstructed
        fidelity = f'{native} native chord voicings, {prepared} stored variants, {reconstructed} reconstructed; lead/bass native targets preferred'
        result.append(dict(id=entry['id'], entry=entry, degrees=[c['degree'] for c in chords], chords=chords,
                           display=[roman(c) for c in chords], chordNames=[chord_name(tonic, mode, c) for c in chords],
                           playable=True, missing=[], recommended=suitable, worstPreparationCost=worst,
                           nativeChordCount=native, preparedChordCount=prepared, reconstructedChordCount=reconstructed,
                           averagePreparationCost=average, explanation=fidelity + ' · ' + entry['description']))
    return sorted(result, key=lambda r: (not r['recommended'], r['worstPreparationCost'],
                                        r['entry']['priority'], r['averagePreparationCost'], r['id']))


def advance_bars(project, position, amount):
    remaining = Fraction(amount)
    changes = project['meterMap']
    while remaining:
        meter = at(changes, position)
        length = Fraction(4 * meter['numerator'], meter['denominator'])
        following = next((beat(m['beat']) for m in changes if beat(m['beat']) > position), None)
        if following is None or position + remaining * length <= following:
            return position + remaining * length
        remaining -= (following - position) / length
        position = following
    return position


def harmony_cycle(project, entry, start=Fraction(0), *, repeat=True):
    end = beat(project['length'])
    if not 0 <= start < end:
        raise ContractError('Load position must be inside the song')
    entries = []
    position = Fraction(start)
    index = 0
    while position < end:
        number = index % len(entry['sequence'])
        duration = Fraction(entry['durations'][number])
        stop = advance_bars(project, position, duration) if entry['durationUnit'] == 'bars' else position + duration
        stop = min(stop, end)
        boundaries = [position, *[beat(t['beat']) for t in project['tonalityMap'] if position < beat(t['beat']) < stop]]
        for boundary in boundaries:
            tone = at(project['tonalityMap'], boundary)
            chord = realize(entry, tone['tonic'], tone['mode'])[number]
            entries.append(dict(beat=str(boundary), chord=chord))
        position = stop
        index += 1
        if index > 16384:
            raise ContractError('Progression produces too many chord changes')
        if not repeat and index == len(entry['sequence']):
            break
    return entries, position


def cycle_end(project, entry, start=Fraction(0)):
    position = Fraction(start)
    for duration in entry['durations']:
        position = advance_bars(project, position, Fraction(duration)) if entry['durationUnit'] == 'bars' else position + Fraction(duration)
    return position


def load_into(editor, entry, *, start=Fraction(0), repeat=True, grow_empty=False):
    entry = validate_entry(entry)
    start = Fraction(start)
    def change(project):
        if (grow_empty and repeat and start == 0 and not project['instances']
                and not any(v['takes'] or v['comp'] for v in project['vocals'])
                and not any(t['patterns'] for t in project['pluginTracks'])):
            target = cycle_end(project, entry)
            if target > beat(project['length']):
                if quarter_seconds(target, project['tempoMap']) > 1800:
                    raise ContractError('This cycle exceeds the 30-minute playback profile. Shorten its durations or increase tempo.')
                project['length'] = str(target)
        entries, end = harmony_cycle(project, entry, start, repeat=repeat)
        old = project['harmony']
        retained = [v for v in old if not start <= beat(v['beat']) < end]
        if end < beat(project['length']) and not any(beat(v['beat']) == end for v in retained):
            retained.append(dict(beat=str(end), chord=copy.deepcopy(at(old, end)['chord'])))
        project['harmony'] = sorted(retained + entries, key=lambda v: beat(v['beat']))
        for credit in entry['credits']:
            if credit not in project['credits']:
                project['credits'].append(copy.deepcopy(credit))
    editor.apply('Load progression: ' + entry['name'], change)


def audition_project(editor, entry, position=Fraction(0)):
    """One native whole-chord attack per harmonic change; arrangement stays intact."""
    from .editor import new_event
    entry = validate_entry(entry)
    project = copy.deepcopy(editor.project)
    project.pop('trackLoops', None)
    project.pop('loopPlayback', None)
    for key in ('tempoMap', 'meterMap', 'tonalityMap'):
        first = copy.deepcopy(at(project[key], position)); first['beat'] = '0'; project[key] = [first]
    bar = Fraction(4 * project['meterMap'][0]['numerator'], project['meterMap'][0]['denominator'])
    length = sum(Fraction(v) for v in entry['durations']) * (bar if entry['durationUnit'] == 'bars' else 1)
    project['length'] = str(length)
    project['harmony'], _ = harmony_cycle(project, entry, repeat=False)
    if 'rhythmicPulse' in project:
        original_meter = at(editor.project['meterMap'], position)
        offset = beat(project['rhythmicPulse'].get('phaseBeat', '0')) if beat(original_meter['beat']) == 0 else 0
        project['rhythmicPulse']['phaseBeat'] = str((position - beat(original_meter['beat']) + offset) % bar)
    changes = [beat(v['beat']) for v in project['harmony']] + [length]
    events = [new_event('rhythm', p, (stop-p)*Fraction(9, 10)) for p, stop in zip(changes, changes[1:])]
    project['patterns'] = [dict(id='progression_preview', role='rhythm', length=str(length), events=events,
        provenance=dict(sourceClip=entry['name'], license=entry['credits'][0]['license'], changes='Independent chord progression audition'))]
    project['instances'] = [dict(id='progression_preview_instance', patternId='progression_preview', beat='0', linked=False)]
    project['pluginTracks'] = []
    for lane in project['vocals']:
        lane.update(takes=[], comp=[], selectedTakeId=None, correction=dict(on=False, target='key-mode'))
    # A muted rhythm lane must not turn a harmony audition into silent audio.
    project['mix']['channels']['rhythm']['muted'] = False
    project['mix']['master']['muted'] = False
    return project


def capture(project, start, end, name):
    start, end = Fraction(start), Fraction(end)
    if not 0 <= start < end <= beat(project['length']):
        raise ContractError('Choose a nonempty region inside the song')
    first_tone = at(project['tonalityMap'], start)
    boundaries = sorted({start, *[beat(v['beat']) for k in ('harmony', 'tonalityMap') for v in project[k]
                                  if start < beat(v['beat']) < end], end})
    sequence = []
    for position in boundaries[:-1]:
        tone = at(project['tonalityMap'], position)
        chord = copy.deepcopy(at(project['harmony'], position)['chord'])
        root, _, _ = chord_identity(tone['tonic'], tone['mode'], chord)
        chord['degree'], chord['alteration'] = relative_root((root - first_tone['tonic']) % 12, 'major')
        sequence.append(chord)
    return validate_entry(dict(name=name, kind='chords', basis='major-relative', sequence=sequence,
        durations=[str(right-left) for left, right in zip(boundaries, boundaries[1:])], durationUnit='beats',
        description='Saved from the chord lane; exact qualities and quarter-note durations retained.',
        sourceNotation=' '.join(roman(c) for c in sequence), credits=copy.deepcopy(project['credits'])))


class Bank:
    """Atomic personal collection, deduplicated across built-ins and imports."""
    def __init__(self, path):
        self.path = Path(path) if path else None
        self.entries = []
        self.favorites = set()
        self.history = []
        self.revision = 0
        self.error = ''
        if self.path and self.path.exists():
            try:
                if self.path.stat().st_size > MAX_BYTES:
                    raise ContractError('Stored bank exceeds 2 MiB')
                self.entries, self.favorites = validate_bank(read_json(self.path.read_bytes()))
                identities = {equivalence_signature(e): e['id'] for e in catalog()}
                unique = []
                for entry in self.entries:
                    signature = equivalence_signature(entry)
                    if signature not in identities:
                        unique.append(entry); identities[signature] = entry['id']
                    elif entry['id'] in self.favorites:
                        self.favorites.discard(entry['id']); self.favorites.add(identities[signature])
                self.entries = unique
            except (ValueError, OSError) as exc:
                self.error = 'Stored progression bank could not be read: ' + str(exc)

    def all(self):
        return (*catalog(), *self.entries)

    def _save(self, entries, favorites):
        if self.error:
            raise ContractError(self.error + '. The original file is preserved; repair or move it before saving bank changes.')
        payload = dict(format=FORMAT, version=VERSION, entries=entries, favorites=sorted(favorites))
        if len(canonical_bytes(payload)) > MAX_BYTES:
            raise ContractError('Stored bank would exceed 2 MiB')
        if self.path:
            atomic_json(self.path, payload)

    def _commit(self, entries):
        identities = {e['id'] for e in (*catalog(), *entries)}
        favorites = self.favorites & identities
        self._save(entries, favorites)
        self.history.append((copy.deepcopy(self.entries), self.favorites.copy())); self.history = self.history[-20:]
        self.entries = entries; self.favorites = favorites
        self.revision += 1

    def import_entries(self, values):
        if not isinstance(values, (list, tuple)) or not values or len(values) > MAX_ENTRIES:
            raise ContractError('Choose a nonempty progression bank within the entry limit')
        incoming = [validate_entry(v) for v in values]
        known = {equivalence_signature(e) for e in self.all()}
        candidate = copy.deepcopy(self.entries)
        added = 0
        for entry in incoming:
            signature = equivalence_signature(entry)
            if signature in known:
                continue
            candidate.append(entry); known.add(signature); added += 1
        if len(candidate) > MAX_ENTRIES:
            raise ContractError('Personal bank has reached its 2048-progression limit')
        if added:
            self._commit(candidate)
        return added, len(incoming) - added

    def remove(self, identity):
        candidate = [e for e in self.entries if e['id'] != identity]
        if candidate == self.entries:
            raise ContractError('Only entries in My bank can be removed')
        self._commit(candidate)

    def undo(self):
        if self.history:
            entries, favorites = self.history[-1]
            self._save(entries, favorites)
            self.entries, self.favorites = self.history.pop(); self.revision += 1

    def toggle_favorite(self, identity):
        favorites = self.favorites ^ {identity}
        if identity not in {e['id'] for e in self.all()}:
            raise ContractError('Unknown progression')
        self._save(self.entries, favorites)
        self.favorites = favorites; self.revision += 1

    def export(self, path):
        atomic_json(Path(path), dict(format=FORMAT, version=VERSION, entries=self.entries))
