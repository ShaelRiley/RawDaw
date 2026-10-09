"""Fetch only the three saved, licensed source sets; pin every downloaded byte.

Original recordings/stems are inputs and are not bundled with the prepared
packs. This command downloads public artist files without account credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent


def verified(raw, expected):
    if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        raise ValueError("Authorized source changed: size/hash mismatch")


def download(url, page, expected):
    if not url.startswith("https://ccmixter.org/content/"):
        raise ValueError("Unexpected source host")
    request = urllib.request.Request(url, headers={"Referer": page, "User-Agent": "Mozilla/5.0 PRDE1-source-preparation/0.2"})
    with urllib.request.urlopen(request, timeout=30) as stream:
        raw = stream.read(expected["bytes"] + 1)
    verified(raw, expected)
    return raw


def fetch(recipe, destination):
    grouped = {}
    for asset in recipe["inputs"].values():
        relative = PurePosixPath(asset["path"])
        if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
            raise ValueError("Unsafe saved source path")
        path = destination / str(relative)
        if path.is_file():
            verified(path.read_bytes(), asset)
            continue
        grouped.setdefault(asset["downloadUrl"], []).append(asset)
    for url, assets in grouped.items():
        expected = recipe.get("archives", {}).get(url, assets[0])
        raw = download(url, assets[0]["sourcePage"], expected)
        if url in recipe.get("archives", {}):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if len(archive.infolist()) > 64:
                    raise ValueError("Source archive entry budget exceeded")
                for asset in assets:
                    matches = [entry for entry in archive.infolist()
                               if not entry.is_dir() and PurePosixPath(entry.filename).name == Path(asset["path"]).name
                               and not entry.filename.startswith("__MACOSX/")]
                    if len(matches) != 1 or matches[0].file_size != asset["bytes"]:
                        raise ValueError("Missing/ambiguous source archive member")
                    content = archive.read(matches[0])
                    verified(content, asset)
                    write(destination / asset["path"], content)
        else:
            if len(assets) != 1:
                raise ValueError("Unexpected direct-download assignment")
            write(destination / assets[0]["path"], raw)
    print(recipe["packId"], "all source hashes verified", flush=True)


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_bytes(raw)
    temporary.replace(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    args = parser.parse_args()
    for recipe in json.loads((ROOT / "recipes" / "cc-songs.json").read_text()):
        fetch(recipe, args.sources)
