"""
FreeCAD FCUI main shell module (FCUI-Py).

This file is parsed (not executed) by `src/Gui/FCUI/tools/fcui_compile.py` and
compiled into the bootstrap `.fcuim.json` module format.
"""


@component
class AppShell:
    title: prop[str] = "FCUI Shell"

    def render(self):
        return Column(
            Text(text=self.title),
            Separator(),
            NativeWidget(kind="View3D", class_name="View3DInventorViewer", id="MainView"),
        )
