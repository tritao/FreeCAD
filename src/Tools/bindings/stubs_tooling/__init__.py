"""Support package for the FreeCAD Python binding stub generator.

This package keeps the stub-generation pipeline split by responsibility so the
modules stay navigable without tracing one large script.

Module layout:
- ``model`` holds shared dataclasses, type aliases, defaults, and regexes.
- ``parsing`` holds syntax-oriented helpers for source scanning and AST reads.
- ``type_context_rules`` holds the small manual escape hatch for PyCXX
  contexts that cannot be mapped mechanically yet.
- ``generator`` contains discovery, mapping, merge, and file-emission logic.
- ``cli`` wires the pipeline to the public command-line interface.

A useful reading order is ``model`` -> ``parsing`` ->
``type_context_rules`` -> ``generator`` -> ``cli``.
"""
