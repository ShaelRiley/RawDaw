"""Shared inventory for preparation, integration checks, and distribution.

Only recipe/project metadata is read here; playback has no preparation dependencies.
"""
import json
import re
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
    if any(not isinstance(identity,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',identity) for identity in ids):
        raise ValueError('Unsafe pack identity in source catalog')
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate pack in source catalog")
    for recipe in result:demonstration_suffixes(recipe)
    return result


def demonstration_suffixes(recipe):
    """Each entry advertises only the arrangements actually supplied with it."""
    result=recipe.get('demonstrationSuffixes',['a','b','full'])
    if (not isinstance(result,list) or not result or len(result)>3
            or any(suffix not in ('a','b','full') for suffix in result)
            or len(result)!=len(set(result))):
        raise ValueError('Invalid source demonstration inventory')
    return result


def projects():
    return [ROOT / "packs" / (recipe["packId"] + "_" + suffix + ".prdeproj")
            for recipe in recipes() for suffix in demonstration_suffixes(recipe)]


def pack_for_project(project):
    """Full song names need not have the short auditions' _a/_b suffix."""
    from prde1.project import load_project
    project = Path(project)
    return project.parent / (load_project(project)['packReference']['packId'] + '.prdepack')
