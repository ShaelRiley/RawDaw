"""Offline source PCM transformations, without oscillators or synthetic noise.

Source-rate warps change pitch and duration together. Recorded interior regions
supply sustain. Harmonic masks retain polyphonic complex bins before independent
voice warps. Coincident harmonics, bleed and missing fundamentals remain limits.
"""
from __future__ import annotations
import math
import wave
import numpy as np
from .contracts import ContractError, RATE

MAX_NOTE_FRAMES = RATE * 2
MAX_CHORD_FRAMES = RATE * 2 // 5
MAX_SOURCE_FRAMES = RATE


def read_pcm(path, onset=0, limit=MAX_SOURCE_FRAMES):
    with wave.open(str(path), 'rb') as audio:
        channels = audio.getnchannels()
        audio.setpos(onset)
        raw = audio.readframes(min(limit, audio.getnframes() - onset))
    octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
    words = (octets[:, 0].astype(np.int32) | octets[:, 1].astype(np.int32) << 8 |
             octets[:, 2].astype(np.int32) << 16)
    words = (words ^ 0x800000) - 0x800000
    return words.astype(np.float64).reshape(-1, channels) / 8388608


def pcm24(audio):
    if not np.isfinite(audio).all() or np.max(np.abs(audio), initial=0) >= 1:
        raise ContractError('Source transformation produced invalid or clipping PCM')
    words = np.rint(audio * 8388607).astype(np.int32).reshape(-1)
    return np.stack((words & 255, words >> 8 & 255, words >> 16 & 255), axis=1).astype(np.uint8).tobytes()


def resample(audio, ratio, maximum=MAX_NOTE_FRAMES):
    """Band-limited PCM rate warp retaining stereo phase relations."""
    if not np.isfinite(ratio) or not 1 / 2048 <= ratio <= 2048:
        raise ContractError('Pitch transformation exceeds the source-warp profile')
    # Crop input before resampling; squeezing a long output to fit would detune it.
    audio = audio[:max(8, min(len(audio), math.floor(maximum * ratio)))]
    count = max(8, min(maximum, round(len(audio) / ratio)))
    if count == len(audio):
        return audio.copy()
    spectrum = np.fft.rfft(audio, axis=0)
    result = np.zeros((count // 2 + 1, audio.shape[1]), dtype=np.complex128)
    shared = min(count, len(audio))
    bins = shared // 2 + 1
    result[:bins] = spectrum[:bins]
    if shared % 2 == 0:
        if count < len(audio):
            result[shared // 2] *= 2
        elif count > len(audio):
            result[shared // 2] *= .5
    return np.fft.irfft(result, n=count, axis=0) * (count / len(audio))


def pitch_shift(audio, semitones, maximum=MAX_NOTE_FRAMES):
    return resample(audio, 2 ** (semitones / 12), maximum)


def normalize(audio, peak=None):
    audio = np.asarray(audio, dtype=np.float64).copy()
    audio -= np.mean(audio, axis=0, keepdims=True)
    actual = np.max(np.abs(audio), initial=0)
    if actual < 1e-10:
        raise ContractError('Source crop has no usable waveform energy; supply a new source crop')
    audio *= min(.72 / actual, 1 if peak is None else peak / actual)
    return audio


def sustain_loop(audio, *, minimum_note=None, pitch_note=None, preserve_attack=True):
    """Crossfade a bounded recorded interior into a repeating sustain."""
    audio = normalize(audio)
    minimum = max(512, round(RATE * .12))
    if minimum_note is not None:
        minimum = max(minimum, math.ceil(2 * RATE / (440 * 2 ** ((minimum_note - 69) / 12))))
    if len(audio) < minimum * 2:
        base = audio
        if pitch_note is not None:
            period = RATE / (440 * 2 ** ((pitch_note - 69) / 12))
            cycles = max(1, math.floor(len(base) / period))
            base = base[:min(len(base), max(2, round(cycles * period)))]
        audio = np.tile(base, (math.ceil(minimum * 2 / len(base)), 1))[:minimum * 2]
        blend = min(96, len(base) // 8)
        for boundary in range(len(base), len(audio), len(base)):
            if boundary + blend >= len(audio):
                break
            weights = np.linspace(0, 1, blend + 1)[1:, None]
            audio[boundary:boundary + blend] = audio[boundary - blend:boundary] * (1 - weights) + audio[boundary:boundary + blend] * weights
    frames = len(audio)
    start = max(1, min(frames // 3, frames - minimum - 1))
    end = min(max(start + minimum, frames - max(1, frames // 40)), frames)
    if pitch_note is not None:
        period = RATE / (440 * 2 ** ((pitch_note - 69) / 12))
        cycles = max(1, math.floor((end - start) / period))
        end = min(frames, start + round(cycles * period))
    blend = min(round(RATE * .025), (end - start) // 4, start)
    if blend < 1:
        raise ContractError('Source crop is too short to prepare a sustain loop')
    weights = np.linspace(0, 1, blend + 1)[1:, None]
    weights = weights * weights * (3 - 2 * weights)
    audio[end - blend:end] = audio[end - blend:end] * (1 - weights) + audio[start - blend:start] * weights
    audio[end - 1] = audio[start - 1]
    if preserve_attack:
        attack = min(96, start)
        audio[:attack] *= np.linspace(0, 1, attack)[:, None]
    return audio[:end], dict(startFrame=start, endFrame=end, validated=True)


def separate_chord(audio, pitches):
    """Complex-bin harmonic masks, stereo retained; no new spectral partials."""
    pitches = sorted(set(pitches))
    size, hop = 8192, 2048
    window = np.sqrt(np.hanning(size))
    padding = size // 2
    padded = np.pad(audio, ((padding, size), (0, 0)))
    frequencies = np.fft.rfftfreq(size, 1 / RATE)
    masks = []
    for note in pitches:
        fundamental = 440 * 2 ** ((note - 69) / 12)
        harmonics = np.maximum(1, np.rint(frequencies / fundamental))
        expected = harmonics * fundamental
        distance = np.abs(frequencies - expected)
        bandwidth = np.maximum(RATE / size * 1.8, expected * .014)
        mask = np.exp(-.5 * (distance / bandwidth) ** 2) / np.sqrt(harmonics)
        mask[(frequencies < fundamental * .94) | (distance > bandwidth * 3)] = 0
        masks.append(mask)
    masks = np.asarray(masks)
    masks /= np.maximum(1, np.sum(masks, axis=0))[None, :]
    voices = [np.zeros_like(padded) for _ in pitches]
    normalization = np.zeros(len(padded))
    for start in range(0, len(padded) - size + 1, hop):
        spectrum = np.fft.rfft(padded[start:start + size] * window[:, None], axis=0)
        normalization[start:start + size] += window * window
        for index, mask in enumerate(masks):
            voices[index][start:start + size] += np.fft.irfft(spectrum * mask[:, None], n=size, axis=0) * window[:, None]
    denominator = np.maximum(normalization, 1e-12)[:, None]
    return {note: (voice / denominator)[padding:padding + len(audio)] for note, voice in zip(pitches, voices)}


def drum_variant(audio, slot):
    """Warp/filter recorded kit material into an explicitly derived articulation."""
    if slot in ('tom1', 'tom2'):
        audio = pitch_shift(audio, 7 if slot == 'tom1' else 12, maximum=RATE)
        spectrum = np.fft.rfft(audio, axis=0)
        frequency = np.fft.rfftfreq(len(audio), 1 / RATE)
        spectrum *= (1 / (1 + (frequency / 1800) ** 4))[:, None]
        audio = np.fft.irfft(spectrum, n=len(audio), axis=0)
    elif slot in ('hatClosed', 'hatOpen'):
        spectrum = np.fft.rfft(audio, axis=0)
        frequency = np.fft.rfftfreq(len(audio), 1 / RATE)
        spectrum *= (1 - 1 / (1 + (frequency / 1800) ** 4))[:, None]
        audio = np.fft.irfft(spectrum, n=len(audio), axis=0)
        if slot == 'hatOpen' and len(audio) < RATE // 3:
            audio = resample(audio, .5, maximum=RATE)
        if slot == 'hatClosed':
            audio = audio[:RATE // 8]
    elif slot == 'kick':
        audio = pitch_shift(audio, -12, maximum=RATE)
    audio = normalize(audio, peak=.35)
    fade = min(480, len(audio) // 4)
    audio[:min(48, len(audio))] *= np.linspace(0, 1, min(48, len(audio)))[:, None]
    audio[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return audio
