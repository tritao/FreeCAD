# Portable UI and View APIs

**Status:** Architecture / future design guidance

## Principle

Portable/sandboxed Extension APIs should expose FreeCAD UI concepts, not implementation object graphs.

Do not make these portable API types:

```text
QWidget
QObject
QAction
SoNode
SoSeparator
PySide object
Pivy object
```

Trusted in-process Python may continue using those APIs.

## Candidate semantic services

```text
commands
actions
menus/toolbars
task panels
selection
camera
overlays
scene primitives/resources
gizmos
notifications
```

## Declarative bias

Prefer declarative or host-owned UI construction where feasible. FreeCAD remains responsible for Qt ownership, GUI thread affinity, Coin/scene lifetime, theme, and accessibility.

## Built-in modules

Built-in providers may internally translate Extension UI calls into Qt/Coin objects. This allows `org.freecad.ui@1` to remain stable even if implementation technology changes.

## Escape hatch

Advanced in-process APIs may expose implementation-specific objects separately. Code using those escape hatches should not expect portability to a sandboxed profile.
