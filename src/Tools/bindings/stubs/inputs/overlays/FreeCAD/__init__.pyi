# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from . import Console as Console
from . import Units as Units
from typing import TYPE_CHECKING, Literal, Sequence, TypeAlias, overload

if TYPE_CHECKING:
    from Part import Feature as _PartFeature

_FileTypeModules: TypeAlias = dict[str, str | list[str] | None]
_LogLevelName: TypeAlias = Literal["Default", "Error", "Warning", "Message", "Log", "Trace"]

GuiUp: int
ActiveDocument: Document | None
@overload
def getImportType() -> _FileTypeModules: ...
@overload
def getImportType(extension: str, /) -> list[str]: ...
@overload
def getExportType() -> _FileTypeModules: ...
@overload
def getExportType(extension: str, /) -> list[str]: ...
