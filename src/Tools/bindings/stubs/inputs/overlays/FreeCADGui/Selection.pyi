# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from enum import IntEnum
from typing import Protocol

from FreeCAD import DocumentObject
from FreeCADGui import SelectionObject

_Point3 = tuple[float, float, float]

class ResolveMode(IntEnum):
    NoResolve = 0
    OldStyleElement = 1
    NewStyleElement = 2
    FollowLink = 3

class SelectionStyle(IntEnum):
    NormalSelection = 0
    GreedySelection = 1

class _SelectionGate(Protocol):
    def allow(self, doc: object, obj: DocumentObject, sub: str, /) -> bool: ...

class Filter:
    def __init__(self, filter: str, /) -> None: ...
    def match(self) -> bool: ...
    def test(self, obj: DocumentObject, sub_name: str = "", /) -> bool: ...
    def result(self) -> list[tuple[SelectionObject, ...]]: ...
    def setFilter(self, filter: str, /) -> None: ...
    def getFilter(self) -> str: ...
