# FCUI Qt Native Viewer (sample)

Standalone CMake + Qt Widgets app that loads FCUI module JSON (`.fcuim.json`) and renders it.

## Architecture
- `FCUIQtRuntime` (library target): module loader + binding VM + widget builder
- `FCUIQtHost` (interface): provides reactive host values and executes commands
- `fcui_qt_viewer` (app): uses `MockHost` to drive `fc.selection.count` and prints commands

## Build

From the FreeCAD repo root:

```bash
cmake -S src/Gui/FCUIQtSample -B /tmp/fcui-qt-build
cmake --build /tmp/fcui-qt-build -j
```

## Run

```bash
/tmp/fcui-qt-build/fcui_qt_viewer /tmp/fcui-qt-build/fcui_shell/main.fcuim.json
```

The window includes small controls to live-update `title` and `count` props and re-evaluate bindings.

It also includes a mock host signal (`fc.selection.count`) you can tick to see host-driven reactivity without FreeCAD.
