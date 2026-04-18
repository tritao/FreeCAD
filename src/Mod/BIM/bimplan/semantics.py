# SPDX-License-Identifier: LGPL-2.1-or-later

"""Neutral semantic records exposed by BIM Plan Edit integrations."""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class PlanSemanticRecord:
    target_kind: str
    document_name: str = ""
    object_name: str = ""
    label: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    semantic_label: str = ""
    space_key: str = ""
    space_label: str = ""
    source_space_name: str = ""
    usage_category: str = ""
    object_role: str = ""
    semantic_preset: str = ""
    host_ref: str = ""
    mount_height_mm: Optional[float] = None
    requirement_tags: Tuple[str, ...] = ()
