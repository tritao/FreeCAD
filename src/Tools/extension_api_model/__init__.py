# pyright: strict

"""Neutral extension API projection built from ``python_api_model``."""

from .model import (
    ExtensionApiModel,
    ExtensionInterface,
    ExtensionOperation,
    ExtensionParameter,
    ExtensionType,
)
from .project import (
    ExtensionProjectionError,
    load_extension_namespace,
    project_api_model,
)

__all__ = [
    "ExtensionApiModel",
    "ExtensionInterface",
    "ExtensionOperation",
    "ExtensionParameter",
    "ExtensionProjectionError",
    "ExtensionType",
    "load_extension_namespace",
    "project_api_model",
]
