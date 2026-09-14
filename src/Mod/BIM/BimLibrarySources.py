# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Library root discovery and configuration helpers for BIM local assets."""

from dataclasses import dataclass
import json
import os
import sys

import FreeCAD

CONFIGURED_LIBRARY_ROOTS_KEY = "destinations"
CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY = "destinationsState"
LEGACY_LIBRARY_ROOT_KEY = "destination"
LEGACY_LIBRARY_ADDON_NAME = "parts_library"
LIBRARY_MARKER_FILES = (".freecad-library", "library.json")

LIBRARY_SOURCE_CONFIGURED = "configured"
LIBRARY_SOURCE_MODULE = "module_marker"
LIBRARY_SOURCE_LEGACY = "legacy_fallback"
LIBRARY_SOURCE_PROVIDED = "provided"
LIBRARY_SOURCE_NONE = "none"


@dataclass(frozen=True)
class ConfiguredLibraryRoot:
    """One configured local library root entry."""

    path: str
    enabled: bool = True
    label: str = ""
    metadata_path: str = ""

    def __post_init__(self):

        normalized_path = normalize_library_root(self.path)
        normalized_label, metadata_path = _resolve_library_root_label_info(
            normalized_path,
            self.label,
            self.metadata_path,
        )
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "label", normalized_label)
        object.__setattr__(self, "metadata_path", normalize_library_root(metadata_path))


@dataclass(frozen=True)
class LibraryRoot:
    """One resolved local library root."""

    path: str
    source: str = LIBRARY_SOURCE_PROVIDED
    label: str = ""
    metadata_path: str = ""

    def __post_init__(self):

        normalized_path = normalize_library_root(self.path)
        normalized_label, metadata_path = _resolve_library_root_label_info(
            normalized_path,
            self.label,
            self.metadata_path,
        )
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "source", self.source or LIBRARY_SOURCE_PROVIDED)
        object.__setattr__(self, "label", normalized_label)
        object.__setattr__(self, "metadata_path", normalize_library_root(metadata_path))


def normalize_library_root(path):

    if not path:
        return ""
    return os.path.normpath(path).replace("\\", "/")


def _coerce_library_label(label):

    return " ".join(str(label or "").split()).strip()


def _humanize_library_root_name(name):

    name = _coerce_library_label(name)
    if not name:
        return ""
    if ("_" not in name) and ("-" not in name):
        return name

    words = []
    for chunk in name.replace("-", "_").split("_"):
        chunk = chunk.strip()
        if not chunk:
            continue
        words.append(chunk.title() if chunk.islower() else chunk)
    return " ".join(words) or name


def _read_library_root_metadata(path):

    metadata_path = os.path.join(path, "library.json")
    if not os.path.isfile(metadata_path):
        return "", ""

    normalized_metadata_path = normalize_library_root(metadata_path)
    try:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return "", normalized_metadata_path

    candidates = []
    if isinstance(data, dict):
        candidates.append(data)
        library_data = data.get("library")
        if isinstance(library_data, dict):
            candidates.append(library_data)

    for candidate in candidates:
        for key in ("label", "title", "name"):
            label = _coerce_library_label(candidate.get(key))
            if label:
                return label, normalized_metadata_path

    return "", normalized_metadata_path


def _resolve_library_root_label_info(path, label="", metadata_path=""):

    label = _coerce_library_label(label)
    metadata_path = normalize_library_root(metadata_path)
    if label:
        return label, metadata_path

    if path and os.path.isdir(path):
        metadata_label, metadata_path = _read_library_root_metadata(path)
        if metadata_label:
            return metadata_label, metadata_path

    fallback_name = os.path.basename(path.rstrip("/")) if path else ""
    return _humanize_library_root_name(fallback_name) or path, metadata_path


def get_library_root_label(entry):

    if isinstance(entry, LibraryRoot):
        return entry.label
    if isinstance(entry, ConfiguredLibraryRoot):
        return entry.label

    path = ""
    label = ""
    metadata_path = ""
    if isinstance(entry, dict):
        path = entry.get("path", "")
        label = entry.get("label", "")
        metadata_path = entry.get("metadata_path", "")
    else:
        path = entry
    return _resolve_library_root_label_info(
        normalize_library_root(path),
        label,
        metadata_path,
    )[0]


def coerce_library_roots(entries):

    roots = []
    seen = set()
    for entry in entries or []:
        if isinstance(entry, LibraryRoot):
            root = entry
        elif isinstance(entry, ConfiguredLibraryRoot):
            root = LibraryRoot(
                entry.path,
                LIBRARY_SOURCE_CONFIGURED,
                entry.label,
                entry.metadata_path,
            )
        elif isinstance(entry, dict):
            root = LibraryRoot(
                entry.get("path", ""),
                entry.get("source", LIBRARY_SOURCE_PROVIDED),
                entry.get("label", ""),
                entry.get("metadata_path", ""),
            )
        else:
            root = LibraryRoot(entry, LIBRARY_SOURCE_PROVIDED)

        if not root.path or root.path in seen or not os.path.isdir(root.path):
            continue
        seen.add(root.path)
        roots.append(root)
    return roots


def coerce_configured_library_roots(entries, existing_only=False):

    roots = []
    seen = set()
    for entry in entries or []:
        if isinstance(entry, ConfiguredLibraryRoot):
            root = entry
        elif isinstance(entry, LibraryRoot):
            root = ConfiguredLibraryRoot(
                entry.path,
                True,
                entry.label,
                entry.metadata_path,
            )
        elif isinstance(entry, dict):
            root = ConfiguredLibraryRoot(
                entry.get("path", ""),
                entry.get("enabled", True),
                entry.get("label", ""),
                entry.get("metadata_path", ""),
            )
        else:
            root = ConfiguredLibraryRoot(entry, True)

        if not root.path or root.path in seen:
            continue
        if existing_only and (not os.path.isdir(root.path)):
            continue
        seen.add(root.path)
        roots.append(root)
    return roots


def _get_parts_library_params():

    return FreeCAD.ParamGet("User parameter:Plugins/parts_library")


def _parse_configured_library_roots(raw_value):

    if not raw_value:
        return []

    values = None
    try:
        parsed = json.loads(raw_value)
    except Exception:
        parsed = None

    if isinstance(parsed, str):
        values = [parsed]
    elif isinstance(parsed, (list, tuple)):
        values = list(parsed)

    if values is None:
        values = []
        for line in str(raw_value).replace("\r", "\n").split("\n"):
            for part in line.split(os.pathsep):
                part = part.strip()
                if part:
                    values.append(part)

    return [root.path for root in coerce_library_roots(values)]


def _parse_configured_library_root_entries(raw_value):

    if not raw_value:
        return []

    values = None
    try:
        parsed = json.loads(raw_value)
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        values = [parsed]
    elif isinstance(parsed, (list, tuple)):
        values = list(parsed)
    elif isinstance(parsed, str):
        values = [parsed]

    return coerce_configured_library_roots(values)


def set_configured_library_root_entries(entries):

    normalized_roots = coerce_configured_library_roots(entries)
    params = _get_parts_library_params()
    params.SetString(
        CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY,
        json.dumps(
            [
                {
                    "path": root.path,
                    "enabled": bool(root.enabled),
                }
                for root in normalized_roots
            ]
        ),
    )

    enabled_paths = [root.path for root in normalized_roots if root.enabled]
    params.SetString(CONFIGURED_LIBRARY_ROOTS_KEY, json.dumps(enabled_paths))
    params.SetString(LEGACY_LIBRARY_ROOT_KEY, enabled_paths[0] if enabled_paths else "")
    return normalized_roots


def get_configured_library_root_entries():

    params = _get_parts_library_params()
    raw_entries = params.GetString(CONFIGURED_LIBRARY_ROOT_ENTRIES_KEY, "")
    entries = _parse_configured_library_root_entries(raw_entries)
    if not entries:
        entries = [
            ConfiguredLibraryRoot(root.path, True, root.label, root.metadata_path)
            for root in coerce_library_roots(
                _parse_configured_library_roots(params.GetString(CONFIGURED_LIBRARY_ROOTS_KEY, ""))
            )
        ]
    if not entries:
        entries = [
            ConfiguredLibraryRoot(root.path, True, root.label, root.metadata_path)
            for root in coerce_library_roots([params.GetString(LEGACY_LIBRARY_ROOT_KEY, "")])
        ]

    enabled_paths = [root.path for root in entries if root.enabled]
    primary = normalize_library_root(params.GetString(LEGACY_LIBRARY_ROOT_KEY, ""))
    raw_roots = params.GetString(CONFIGURED_LIBRARY_ROOTS_KEY, "")
    if entries and (
        (not raw_entries)
        or (not raw_roots)
        or (primary != (enabled_paths[0] if enabled_paths else ""))
    ):
        set_configured_library_root_entries(entries)

    return entries


def set_configured_library_roots(roots):

    configured_roots = [
        ConfiguredLibraryRoot(root.path, True, root.label, root.metadata_path)
        for root in coerce_library_roots(roots)
    ]
    set_configured_library_root_entries(configured_roots)
    return [root.path for root in configured_roots]


def get_configured_library_roots():

    return [
        root.path
        for root in coerce_configured_library_roots(
            get_configured_library_root_entries(),
            existing_only=True,
        )
        if root.enabled
    ]


def _iter_module_search_roots():

    seen = set()
    additional_paths = FreeCAD.ConfigGet("AdditionalModulePaths") or ""
    for raw_path in additional_paths.split(";"):
        path = normalize_library_root(raw_path.strip())
        if not path or path in seen or not os.path.isdir(path):
            continue
        seen.add(path)
        yield path

    for raw_path in sys.path:
        path = normalize_library_root(raw_path)
        if not path or path in seen or not os.path.isdir(path):
            continue
        seen.add(path)
        yield path


def _find_marked_library_roots(module_root):

    roots = []
    seen = set()
    for candidate in (module_root, os.path.join(module_root, "Library")):
        if not os.path.isdir(candidate):
            continue
        for marker in LIBRARY_MARKER_FILES:
            if os.path.isfile(os.path.join(candidate, marker)):
                normalized = normalize_library_root(candidate)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    roots.append(normalized)
                break
    return roots


def resolve_library_roots():

    roots = []
    seen = set()

    def append_root(path, source):
        root = LibraryRoot(path, source)
        if not root.path or root.path in seen or not os.path.isdir(root.path):
            return
        seen.add(root.path)
        roots.append(root)

    for entry in get_configured_library_root_entries():
        if entry.enabled and os.path.isdir(entry.path):
            append_root(entry.path, LIBRARY_SOURCE_CONFIGURED)

    for module_root in _iter_module_search_roots():
        for discovered in _find_marked_library_roots(module_root):
            append_root(discovered, LIBRARY_SOURCE_MODULE)

    addondir = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", LEGACY_LIBRARY_ADDON_NAME)
    if os.path.isdir(addondir):
        append_root(addondir, LIBRARY_SOURCE_LEGACY)

    return roots


def resolve_library_root_paths():

    return [root.path for root in resolve_library_roots()]


def resolve_library_root_info():

    roots = resolve_library_roots()
    if roots:
        return roots[0].path, roots[0].source
    return "", LIBRARY_SOURCE_NONE


def resolve_library_root():

    return resolve_library_root_info()[0]
