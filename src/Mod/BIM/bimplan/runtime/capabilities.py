# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared helpers for optional runtime capabilities at dynamic boundaries."""


def get_attr(obj, attr_name, default=None):
    if obj is None:
        return default
    try:
        return getattr(obj, attr_name, default)
    except Exception:
        return default


def get_callable(obj, attr_name):
    method = get_attr(obj, attr_name)
    return method if callable(method) else None


def call_if_supported(obj, attr_name, *args, **kwargs):
    method = get_callable(obj, attr_name)
    if method is None:
        return None
    return method(*args, **kwargs)


def set_attr_if_present(obj, attr_name, value):
    if get_attr(obj, attr_name, None) is None:
        return False
    try:
        setattr(obj, attr_name, value)
        return True
    except Exception:
        return False
