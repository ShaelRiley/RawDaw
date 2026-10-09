"""Shared, deliberately small JSON Schema vocabulary, plus strict JSON I/O.

The published schemas are ordinary Draft 2020-12 files. This offline validator
implements only their vocabulary, fails on unknown keywords, and rejects NaN,
duplicate keys, ambiguous types and excessive recursion. Semantic checks live
in the pack/project loaders. A general JSON Schema engine is not claimed.
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.0.0-dev.1"
ROOT = Path(__file__).resolve().parent.parent
ROLES = ("lead", "rhythm", "bass", "drums")
SLOTS = ("kick", "snare", "hatClosed", "hatOpen", "tom1", "tom2", "extra1", "extra2")
RATE = 48000


class ContractError(ValueError):
    """Data is invalid or cannot be played faithfully by this checkpoint."""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(data: bytes | str) -> Any:
    try:
        return json.loads(data, object_pairs_hook=_object,
                          parse_constant=lambda v: (_ for _ in ()).throw(ContractError(f"Nonfinite JSON: {v}")))
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ContractError(f"Invalid JSON: {exc}") from exc


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def atomic_json(path: Path, value: Any) -> None:
    """Commit a complete manifest or leave the existing file intact."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".partial", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate(value: Any, name: str) -> None:
    schema = read_json((ROOT / "schemas" / name).read_bytes())
    _validate(value, schema, schema, "$", 0)


def _validate(value: Any, node: dict, root: dict, path: str, depth: int) -> None:
    known = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum",
             "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
             "minimum", "maximum", "minLength", "maxLength", "pattern"}
    if set(node) - known:
        raise ContractError(f"Unsupported schema vocabulary: {set(node) - known}")
    if depth > 64:
        raise ContractError(f"Excessive nesting at {path}")
    if "$ref" in node:
        reference = node["$ref"]
        if not reference.startswith("#/$defs/"):
            raise ContractError("Only local schema definitions are supported")
        return _validate(value, root["$defs"][reference[8:]], root, path, depth + 1)
    kinds = node.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {"object": isinstance(value, dict), "array": isinstance(value, list),
              "string": isinstance(value, str), "integer": type(value) is int,
              "number": type(value) is int or (type(value) is float and math.isfinite(value)),
              "boolean": type(value) is bool, "null": value is None}
    if kinds and not any(checks[kind] for kind in kinds):
        raise ContractError(f"{path}: expected {kinds}")
    if "const" in node and (value != node["const"] or type(value) is not type(node["const"])):
        raise ContractError(f"{path}: incompatible contract value")
    if "enum" in node and value not in node["enum"]:
        raise ContractError(f"{path}: unsupported value {value!r}")
    if isinstance(value, dict):
        missing = set(node.get("required", [])) - value.keys()
        if missing:
            raise ContractError(f"{path}: missing {sorted(missing)}")
        props = node.get("properties", {})
        for key, child in value.items():
            child_schema = props.get(key, node.get("additionalProperties", True))
            if child_schema is False:
                raise ContractError(f"{path}: unknown field {key}")
            if child_schema is not True:
                _validate(child, child_schema, root, path + "." + key, depth + 1)
    if isinstance(value, list):
        if not node.get("minItems", 0) <= len(value) <= node.get("maxItems", 1000000):
            raise ContractError(f"{path}: invalid array length")
        for index, child in enumerate(value):
            if "items" in node:
                _validate(child, node["items"], root, f"{path}[{index}]", depth + 1)
    if isinstance(value, str):
        if not node.get("minLength", 0) <= len(value) <= node.get("maxLength", 10000000):
            raise ContractError(f"{path}: invalid text length")
        if "pattern" in node and re.search(node["pattern"], value) is None:
            raise ContractError(f"{path}: invalid text format")
    if type(value) in (int, float):
        if (type(value) is float and not math.isfinite(value)) or not node.get("minimum", -math.inf) <= value <= node.get("maximum", math.inf):
            raise ContractError(f"{path}: value outside bounds")
