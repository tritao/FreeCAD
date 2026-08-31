# SPDX-License-Identifier: LGPL-2.1-or-later

"""Naming policy for generated Wasm operation entry points."""

from __future__ import annotations

import re


def _camel_case(value: str) -> str:
    parts = [part for part in re.split(r"[_-]+", value) if part]
    if not parts:
        raise ValueError("operation name cannot be empty")
    return parts[0][:1].lower() + parts[0][1:] + "".join(
        part[:1].upper() + part[1:] for part in parts[1:]
    )


def _upper_first(value: str) -> str:
    return value[:1].upper() + value[1:]


def operation_name(
    stable_id: str,
    *,
    source: str | None = None,
    property_access: str | None = None,
) -> str:
    """Return the language-neutral generated operation name."""

    if source is not None:
        source_parts = source.split(".")
        if len(source_parts) < 2:
            raise ValueError(f"operation source '{source}' has no owner")
        owner = _camel_case(source_parts[-2])
        member = source_parts[-1]
        if member == "__init__":
            member_name = "New"
        elif property_access == "read" and owner == "documentObject":
            member_name = "Get" + _upper_first(member)
        elif property_access == "write" and owner == "documentObject":
            member_name = "Set" + _upper_first(member)
        else:
            member_name = _upper_first(member)
        return owner + member_name

    scope, local_id = stable_id.split("/", 1)
    scope = scope.rsplit("@", 1)[0].rsplit(".", 1)[-1]
    if scope == "host" and local_id == "handle_release":
        return "release"
    if scope == "host":
        return _camel_case(local_id)
    return _camel_case(scope) + _upper_first(_camel_case(local_id))


def guest_method_name(
    stable_id: str,
    *,
    source: str | None = None,
    property_access: str | None = None,
) -> str:
    """Return the generated guest method name under the shared policy."""

    return operation_name(
        stable_id,
        source=source,
        property_access=property_access,
    )
