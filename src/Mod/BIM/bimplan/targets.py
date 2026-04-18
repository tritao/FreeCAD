# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target records exposed by BIM Plan Edit integrations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanTarget:
    kind: str
    document_name: str = ""
    object_name: str = ""
    label: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    semantic_label: str = ""
    is_selected: bool = False
    is_primary: bool = False
