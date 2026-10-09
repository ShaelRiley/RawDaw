"""Untrusted archives become read-only, validated prepared sample banks."""
from __future__ import annotations

import hashlib
import io
import stat
import struct
import tempfile
import unicodedata
import wave
import zipfile
from pathlib import Path, PurePosixPath

from .contracts import ContractError, RATE, ROLES, SLOTS, read_json, validate
from .music import QUALITIES, REGISTERS
from .midi import inspect_midi

MAX_ARCHIVE = 256 * 1024 * 1024
MAX_UNPACKED = 512 * 1024 * 1024
MAX_DECODED = 256 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_RATIO = 200
MAX_JSON = 8 * 1024 * 1024
MAX_AUDIO = 1440000 * 2 * 3 + 65536


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or len(value) > 255 or value != unicodedata.normalize("NFC", value)
            or path.is_absolute() or "\\" in value or ":" in value or "\x00" in value
            or any(part in (".", "..", "") for part in value.split("/"))
            or any(ord(char) < 32 for char in value) or str(path) != value):
        raise ContractError(f"Unsafe archive path: {value!r}")
    return value


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Pack:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._temporary = None
        self.root = None
        self.manifest = {}
        self.samples = {}
        self.mappings = {}
        self.warnings = []
        if self.path.stat().st_size > MAX_ARCHIVE:
            raise ContractError("Archive exceeds 256 MiB")
        try:
            with zipfile.ZipFile(self.path) as archive:
                self._load(archive)
        except (zipfile.BadZipFile, RuntimeError, EOFError, wave.Error, OSError) as exc:
            self.close()
            raise ContractError(f"Invalid pack: {exc}") from exc
        except Exception:
            self.close()
            raise

    def _load(self, archive):
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES or sum(entry.file_size for entry in entries) > MAX_UNPACKED:
            raise ContractError("Archive entry/decompression budget exceeded")
        names = set()
        for entry in entries:
            path = safe_path(entry.filename)
            mode = entry.external_attr >> 16
            if (entry.is_dir() or (mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG))
                    or entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
                    or entry.filename != entry.orig_filename):
                raise ContractError("Unsafe archive entry type")
            if path in names:
                raise ContractError(f"Duplicate archive path: {path}")
            names.add(path)
            if entry.file_size > max(1,entry.compress_size) * MAX_RATIO:
                raise ContractError("Excessive compression ratio")
            cap = MAX_AUDIO if path.endswith(".wav") else MAX_JSON
            if entry.file_size > cap or PurePosixPath(path).suffix not in (".json", ".wav", ".mid"):
                raise ContractError("Unsupported entry or size")
        if "manifest.json" not in names:
            raise ContractError("Missing root manifest.json")
        raw_manifest = archive.read("manifest.json")
        self.manifest = read_json(raw_manifest)
        validate(self.manifest, "prde1-pack-v1.schema.json")
        self.manifest_hash = sha256(raw_manifest)
        files = self.manifest["files"]
        if set(files) != names - {"manifest.json"}:
            raise ContractError("File registry must cover every archive entry exactly")
        for path, digest in files.items():
            safe_path(path)
            if sha256(archive.read(path)) != digest:
                raise ContractError(f"Checksum mismatch: {path}")
        required = [*self.manifest["maps"].values(), self.manifest["clips"]["index"],
                    self.manifest["channelPresets"], self.manifest["provenance"],
                    self.manifest["qa"], self.manifest["preview"]]
        for path in required:
            if path not in files:
                raise ContractError(f"Missing companion file: {path}")
        for path in files:
            if path.endswith(".json"):
                read_json(archive.read(path))
            elif path.endswith(".mid"):
                inspect_midi(archive.read(path))
            elif path.endswith(".wav"):
                self._wav(archive.read(path), path)
        decoded = 0
        for sample in self.manifest["samples"]:
            identity = sample["id"]
            if identity in self.samples:
                raise ContractError(f"Duplicate sample ID: {identity}")
            path = sample["path"]
            if path not in files or sample["sha256"] != files[path] or not path.startswith("audio/" + sample["role"] + "/"):
                raise ContractError(f"Bad sample registry path/hash: {identity}")
            channels, frames = self._wav(archive.read(path), path)
            if channels != sample["channels"] or frames != sample["frames"]:
                raise ContractError(f"Incorrect sample dimensions: {identity}")
            decoded += frames * channels * 4
            if decoded > MAX_DECODED:
                raise ContractError("Decoded sample budget exceeds 256 MiB")
            if not 0 <= sample["onsetFrame"] < frames:
                raise ContractError("Onset marker out of bounds")
            loop = sample["loop"]
            if loop and (sample["role"] == "drums" or not sample["onsetFrame"] < loop["startFrame"] < loop["endFrame"] <= frames):
                raise ContractError("Unsafe sustain loop; attacks/drum hits cannot loop")
            pitches = sample["pitches"]
            if sample["role"] in ("lead", "bass"):
                low, high = REGISTERS[sample["role"]]
                if len(pitches) != 1 or not low <= pitches[0] <= high or sample["chord"] is not None:
                    raise ContractError("Invalid single-note identity/register")
            if sample["role"] == "rhythm":
                self._chord_sample(sample)
            self.samples[identity] = sample
        for mapping in self.manifest["mappings"]:
            identity = mapping["sampleId"]
            sample = self.samples.get(identity)
            if not sample or sample["role"] != mapping["role"]:
                raise ContractError("Mapping references nonexistent/wrong-role sample")
            if mapping["role"] == "rhythm":
                if mapping["note"] is not None or sample["chord"] != {"root":mapping["root"],"quality":mapping["quality"],"inversion":mapping["inversion"]}:
                    raise ContractError("Whole-chord mapping differs from prepared identity")
                key = ("rhythm",mapping["root"],mapping["quality"],mapping["inversion"])
            else:
                if mapping["root"] is not None or mapping["quality"] is not None or sample["pitches"] != [mapping["note"]] or mapping["inversion"] != 0:
                    raise ContractError("Note mapping differs from prepared identity")
                key = (mapping["role"], mapping["note"])
            if key in self.mappings:
                raise ContractError("Ambiguous primary mapping")
            self.mappings[key] = sample
        instruments = self.manifest["instruments"]
        for role in ("lead","rhythm","bass"):
            self._status(instruments[role], role, required=True)
            if instruments[role]["status"] == "available" and not any(key[0]==role for key in self.mappings):
                raise ContractError("Available instrument lacks musical mappings")
        identities = set()
        addresses = set()
        for slot in SLOTS:
            record = instruments["drums"][slot]
            self._status(record, "drums", required=slot not in ("extra1","extra2"))
            if record["status"] == "available":
                if not record["soundIdentity"] or record["midiAddress"] is None:
                    raise ContractError("Populated drum requires sound identity and MIDI address")
                if record["soundIdentity"] in identities or record["midiAddress"] in addresses:
                    raise ContractError("Ambiguous drum identity/address")
                identities.add(record["soundIdentity"])
                addresses.add(record["midiAddress"])
                sample = self.samples[record["sampleId"]]
                if record["pitches"] != sample["pitches"] or (record["pitchClass"]=="pitched" and not record["pitches"]):
                    raise ContractError("Drum pitch metadata mismatch")
                if record["soundIdentity"]!=sample["articulation"]:
                    raise ContractError("Drum semantic identity differs from sample articulation")
                if record["pitchClass"] == "uncertain":
                    self.warnings.append(f"{slot}: uncertain pitch classification; withheld until reviewed")
        if self.warnings and self.manifest["validation"]["status"] == "complete":
            raise ContractError("Complete pack declares unavailable/uncertain required coverage")
        self.clips = read_json(archive.read(self.manifest["clips"]["index"]))
        if not isinstance(self.clips, list):
            raise ContractError("Clip index must be an array")
        for clip in self.clips:
            for key in ("normalizedPath", "midiPath"):
                if clip.get(key) not in files:
                    raise ContractError("Clip index references missing data")
            if not clip.get("license") or not clip.get("origin"):
                raise ContractError("Clip provenance/license missing")
        self._temporary = tempfile.TemporaryDirectory(prefix="prde1-pack-")
        self.root = Path(self._temporary.name)
        for name in names:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            target.chmod(0o400)

    @staticmethod
    def _wav(raw, path):
        if raw[:4]!=b"RIFF" or raw[8:12]!=b"WAVE" or len(raw)<44 or struct.unpack_from("<I",raw,4)[0]!=len(raw)-8:
            raise ContractError(f"Invalid RIFF boundaries: {path}")
        cursor=12
        chunks={}
        while cursor+8<=len(raw):
            kind=raw[cursor:cursor+4]
            size=struct.unpack_from("<I",raw,cursor+4)[0]
            if cursor+8+size>len(raw):
                raise ContractError(f"Truncated WAV chunk: {path}")
            if kind in (b"fmt ",b"data"):
                if kind in chunks:
                    raise ContractError(f"Duplicate WAV chunk: {path}")
                chunks[kind]=raw[cursor+8:cursor+8+size]
            cursor+=8+size+(size&1)
        if cursor!=len(raw) or b"fmt " not in chunks or b"data" not in chunks or len(chunks[b"fmt "])<16:
            raise ContractError(f"Malformed WAV: {path}")
        fmt=struct.unpack_from("<HHIIHH",chunks[b"fmt "])
        if fmt[0]!=1 or fmt[1] not in (1,2) or fmt[2]!=RATE or fmt[3]!=RATE*fmt[1]*3 or fmt[4]!=fmt[1]*3 or fmt[5]!=24:
            raise ContractError(f"Only ordinary RIFF PCM 24-bit supported by core: {path}")
        with wave.open(io.BytesIO(raw), "rb") as audio:
            if (audio.getframerate()!=RATE or audio.getsampwidth()!=3 or audio.getnchannels() not in (1,2)
                    or audio.getcomptype()!="NONE" or not 1<=audio.getnframes()<=1440000):
                raise ContractError(f"Expected 48 kHz mono/stereo 24-bit PCM: {path}")
            channels, frames = audio.getnchannels(), audio.getnframes()
            if len(audio.readframes(frames+1)) != frames*channels*3:
                raise ContractError(f"Truncated PCM data: {path}")
            return channels, frames

    @staticmethod
    def _chord_sample(sample):
        identity = sample["chord"]
        if (not isinstance(identity,dict) or set(identity)!={"root","quality","inversion"}
                or type(identity["root"]) is not int or not 0<=identity["root"]<=11
                or identity["quality"] not in QUALITIES or type(identity["inversion"]) is not int):
            raise ContractError("Invalid chord sample identity")
        intervals=QUALITIES[identity["quality"]]
        inversion=identity["inversion"]
        actual=sample["pitches"]
        expected={(identity["root"]+interval)%12 for interval in intervals}
        if (not 0<=inversion<len(intervals) or not actual or {note%12 for note in actual}!=expected
                or min(actual)%12 != (identity["root"]+intervals[inversion])%12):
            raise ContractError("Prepared chord pitch set/inversion mismatch")

    def _status(self, record, role, required):
        status=record["status"]
        if status=="available":
            sample=self.samples.get(record["sampleId"])
            if not sample or sample["role"]!=role:
                raise ContractError("Available role/slot references missing sample")
        else:
            if record["sampleId"] is not None or not record["reason"] or (required and status=="empty"):
                raise ContractError("Missing required material must be explicitly unavailable with a reason")
            if required:
                self.warnings.append(f"{role}: {record['reason']}")

    def close(self):
        if self._temporary:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
