"""Shared inventory for preparation, integration checks, and distribution.

Only recipe metadata is read here; playback has no preparation dependencies.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def recipes():
    result = []
    for name in json.loads((ROOT / "recipes/catalog.json").read_text()):
        path = Path(name)
        if path.is_absolute() or len(path.parts) != 1 or path.suffix != ".json":
            raise ValueError("Unsafe recipe catalog path")
        result.extend(json.loads((ROOT / "recipes" / path).read_text()))
    ids = [recipe["packId"] for recipe in result]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate pack in source catalog")
    return result


def projects():
    return [ROOT / "packs" / (recipe["packId"] + "_" + suffix + ".prdeproj")
            for recipe in recipes() for suffix in ("a", "b")]
