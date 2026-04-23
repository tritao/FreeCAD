# SPDX-License-Identifier: LGPL-2.1-or-later

"""Compatibility shim for the Plan Edit session implementation."""

from bimplan.runtime import session as _session

for _name in dir(_session):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_session, _name)

__all__ = [name for name in globals() if not name.startswith("__")]
