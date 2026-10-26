"""Encrypted vault metadata schema and validation rules."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

SCHEMA_VERSION = 1
ROOT_ID = "0" * 32
MAX_ITEMS = 100_000
MAX_NAME_BYTES = 255
MAX_VAULT_NAME_BYTES = 120
_ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")
_WINDOWS_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.IGNORECASE)
_INVALID_NAME_CHARS = frozenset("<>:/\\|?*")
_METADATA_FIELDS = {"schema_version", "vault_name", "root_id", "items"}
_ITEM_FIELDS = {
    "id",
    "parent_id",
    "name",
    "kind",
    "object_id",
    "size_bytes",
    "created_at_ns",
    "modified_at_ns",
    "favorite",
    "trashed",
}


class MetadataValidationError(ValueError):
    """Decrypted metadata violates the versioned schema or resource bounds."""


def validate_segment_name(name: str, *, max_bytes: int = MAX_NAME_BYTES) -> str:
    """Validate a single Windows-compatible filename or folder segment."""

    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise MetadataValidationError("Name must be a non-empty path segment")
    if name[-1] in {" ", "."}:
        raise MetadataValidationError("Names cannot end with a space or period")
    if any(ord(char) < 32 or char in _INVALID_NAME_CHARS for char in name):
        raise MetadataValidationError("Name contains an unsupported character")
    if _WINDOWS_RESERVED.fullmatch(name):
        raise MetadataValidationError("Name is reserved by Windows")
    if len(name.encode("utf-8", errors="strict")) > max_bytes:
        raise MetadataValidationError("Name exceeds the supported length")
    return name


def empty_metadata(vault_name: str) -> dict[str, Any]:
    """Create the initial private metadata snapshot for a new vault."""

    validate_segment_name(vault_name, max_bytes=MAX_VAULT_NAME_BYTES)
    return {
        "schema_version": SCHEMA_VERSION,
        "vault_name": vault_name,
        "root_id": ROOT_ID,
        "items": {},
    }


def validate_metadata(payload: Any) -> dict[str, Any]:
    """Validate metadata structure, bounds, names, object references and tree."""

    if not isinstance(payload, dict) or set(payload) != _METADATA_FIELDS:
        raise MetadataValidationError("Metadata fields do not match schema v1")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise MetadataValidationError("Unsupported metadata schema")
    validate_segment_name(payload["vault_name"], max_bytes=MAX_VAULT_NAME_BYTES)
    if payload["root_id"] != ROOT_ID:
        raise MetadataValidationError("Invalid root identifier")
    items = payload["items"]
    if not isinstance(items, dict) or len(items) > MAX_ITEMS:
        raise MetadataValidationError("Item collection exceeds supported bounds")

    normalized: dict[str, dict[str, Any]] = {}
    sibling_names: set[tuple[str, str]] = set()
    object_ids: set[str] = set()
    for item_id, item in items.items():
        if not isinstance(item_id, str) or not _ID_PATTERN.fullmatch(item_id) or item_id == ROOT_ID:
            raise MetadataValidationError("Invalid item identifier")
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
            raise MetadataValidationError("Item fields do not match schema v1")
        if item["id"] != item_id:
            raise MetadataValidationError("Item identifier does not match its map key")
        parent_id = item["parent_id"]
        if not isinstance(parent_id, str) or (
            parent_id != ROOT_ID and not _ID_PATTERN.fullmatch(parent_id)
        ):
            raise MetadataValidationError("Invalid parent identifier")
        name = validate_segment_name(item["name"])
        if item["kind"] not in {"file", "folder"}:
            raise MetadataValidationError("Invalid item type")
        if type(item["favorite"]) is not bool or type(item["trashed"]) is not bool:
            raise MetadataValidationError("Invalid item flags")
        for timestamp in (item["created_at_ns"], item["modified_at_ns"]):
            if type(timestamp) is not int or timestamp < 0:
                raise MetadataValidationError("Invalid item timestamp")

        if item["kind"] == "folder":
            if item["object_id"] is not None or item["size_bytes"] is not None:
                raise MetadataValidationError("Folders cannot reference file objects")
        else:
            object_id = item["object_id"]
            if not isinstance(object_id, str) or not _ID_PATTERN.fullmatch(object_id):
                raise MetadataValidationError("Invalid file object identifier")
            if object_id in object_ids:
                raise MetadataValidationError("File object is referenced more than once")
            object_ids.add(object_id)
            if type(item["size_bytes"]) is not int or item["size_bytes"] < 0:
                raise MetadataValidationError("Invalid file size")

        collision_key = (parent_id, unicodedata.normalize("NFC", name).casefold())
        if collision_key in sibling_names:
            raise MetadataValidationError("Duplicate sibling name")
        sibling_names.add(collision_key)
        normalized[item_id] = item

    for _item_id, item in normalized.items():
        parent_id = item["parent_id"]
        if parent_id == ROOT_ID:
            continue
        parent = normalized.get(parent_id)
        if parent is None or parent["kind"] != "folder":
            raise MetadataValidationError("Item parent is missing or not a folder")
        if parent["trashed"] != item["trashed"]:
            raise MetadataValidationError("Trash state must be consistent through a folder tree")

    for item_id in normalized:
        visited: set[str] = set()
        current_id = item_id
        while current_id != ROOT_ID:
            if current_id in visited:
                raise MetadataValidationError("Folder tree contains a cycle")
            visited.add(current_id)
            if len(visited) > 256:
                raise MetadataValidationError("Folder nesting exceeds supported depth")
            current_id = normalized[current_id]["parent_id"]

    return payload
