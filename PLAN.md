Modernization Plan

Prioritize scope: FreeCAD-owned sources first (e.g. FreeCAD/src/Gui, FreeCAD/src/Mod/*), keep Coin3D (coin/src) and other 3rd-party trees as follow-up/coordination items rather than immediate edits.
Phase 0 – Baseline capture: script a report that lists every legacy call (e.g. glBegin, glMatrixMode, glEnable(GL_LIGHTING)) and the owning module; this becomes our backlog and regression check. Include GLPainter, NavigationStyle, overlay widgets, and custom Inventor nodes as high-impact entries.
Phase 1 – Context + state management: wrap direct state manipulation (glPushAttrib, glDisable(GL_BLEND), etc.) in a small RAII-style helper that uses QOpenGLFunctions / QOpenGLExtraFunctions, forcing all code through a single path. Start with hotspots like FreeCAD/src/Gui/GLPainter.cpp (line 64) and FreeCAD/src/Gui/NaviCube.cpp.
Phase 2 – Projection / matrices: extend Gui::GL::loadProjectionMatrix to cover all current glMatrixMode/glLoadMatrix* usage, migrate callers, then remove raw matrix stack manipulation. This includes camera helpers and overlay widgets that currently push/pop the legacy stack.
Phase 3 – Geometry submission: replace glBegin/glVertex*/glColor* code with VBO/VAO backed helpers. Tackle 2D overlay primitives first (rectangles, lines, text backgrounds) before larger mesh nodes (SoFCMeshObject, etc.), since they are self-contained.
Phase 4 – Shaders & materials: introduce a small shader library (color-only, textured, gizmo) and map legacy fixed-function state (glMaterial, glLightfv, glTexEnvi) to uniform updates. Start with overlays and navigation gizmos, then address Part/Mesh view providers.
Phase 5 – Validation: gate each phase with Core-profile test builds (Qt/OpenGL debug context) and automated render-baseline comparisons for critical scenes to catch regressions early.
Draw Call Abstraction?

Yes—a lightweight draw-call layer is worth adding once the state wrapper (Phase 1) exists. It should encapsulate VAO/VBO binding, shader selection, and uniform setup so higher-level code requests “draw polyline” or “draw tri mesh” instead of issuing GL commands.
Keep it narrow: a Gui::Render::Batch API that exposes a handful of immutable draw descriptors (vertex/index buffers, primitive type, material block) is sufficient. It becomes the seam where we can later plug in different backends (modern OpenGL, Vulkan, Metal) or unit-test rendering logic.
Avoid over-abstracting Coin3D items—bridge from Inventor callbacks into the new layer gradually, starting with FreeCAD-specific nodes (FreeCAD/src/Mod/Part/Gui/SoBrepFaceSet.cpp, SoTextLabel.cpp), then explore upstream contributions for Coin after proof of concept.
Next Steps

Generate the baseline report and circulate it so we agree on ownership per subsystem.
Prototype the state wrapper on GLPainter (FreeCAD/src/Gui/GLPainter.cpp (line 48)) to validate that we can run without legacy stack calls.
Draft the API sketch for the draw-call abstraction and review it with the GUI/rendering team before touching the larger mesh nodes.