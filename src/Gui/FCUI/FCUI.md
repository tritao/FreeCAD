# FCUI Proposal

## Executive summary
FreeCAD’s current GUI is largely authored as Qt Widgets `.ui` XML. This proposal introduces **FCUI**, a new declarative UI system that:

- Uses a **Python-like syntax** (familiar to the FreeCAD ecosystem) but is **not executed by CPython**.
- Compiles to a **portable UI module format** executed by a **native runtime**.
- Embeds tightly into FreeCAD via **Qt** (initially with a Qt Widgets compatibility path and/or Qt Canvas renderer).
- Preserves a long-term path to **Web** by keeping rendering and host services abstract (WASM runtime + web renderer later).
- Provides a **mechanical conversion path** from existing `.ui` files.

The design borrows from Slint’s model: **typed properties + reactive bindings + minimal expression subset**, plus a controlled host API for FreeCAD-specific actions and signals.

---

## Goals
### Primary goals
1. **Tight embedding in FreeCAD** (dock widgets, task panels, dialogs) without rewriting FreeCAD’s core.
2. **Mechanical conversion** of many existing Qt Widgets `.ui` files to FCUI definitions (with a clear portability report).
3. A **native runtime** (C++) that evaluates bindings and updates UI incrementally.
4. Renderer abstraction such that **Qt is an implementation detail**.
5. A credible route to **Web execution** for the same UI modules.

### Non-goals (initially)
- Full Python compatibility (no arbitrary Python execution).
- Full fidelity conversion of every Qt widget or stylesheet.
- Replacing FreeCAD’s entire GUI at once.

---

## Key architectural decisions
### 1) Language is a *subset of Python syntax*
- Source looks like Python but is compiled into an FCUI module.
- No general statements in bindings; no arbitrary imports; no reflection/eval.

### 2) Slint-like reactivity
- Properties are constants or bindings.
- Binding expressions form a dependency graph; updates are incremental.

### 3) Two orthogonal backends
- **Renderer backend** (drawing, layout integration, input)
- **Host services backend** (FreeCAD document, selection, commands, transactions)

This is what enables both tight Qt embedding and eventual web.

---

## System overview

### Components
1. **FCUI Language (FCUI-Py)**
   - Python-syntax UI declarations
   - Typed properties, callbacks
   - UI tree construction
   - Binding expressions subset

2. **Compiler toolchain**
   - **Frontend parser (recommended):** use CPython’s official Python parser via `ast.parse` in a **Python-based compiler** (build-time only; the FCUI runtime stays native and does not embed CPython).
   - Validates the FCUI-Py subset + types.
   - Lowers to a stable IR and emits portable module format (`.fcuim`).
   - Produces diagnostics and a portability/conversion report.

3. **Native runtime**
   - Loads `.fcuim`
   - Instantiates component trees
   - Evaluates bindings with a tiny VM
   - Maintains dependency graph
   - Schedules layout/paint
   - Dispatches events to callbacks/commands

4. **Renderer backends**
   - **QtWidgetsRenderer** (compatibility, high conversion coverage)
   - **QtCanvasRenderer** (portable retained-mode renderer; Qt is implementation detail)
   - Future: **WebCanvasRenderer** (Canvas/WebGL/WebGPU)
   - Test: **HeadlessRenderer** (snapshot/layout tests)

5. **Host services backends**
   - **FreeCADHostLocal**: in-process integration (signals + commands)
   - Future: **FreeCADHostRemote**: RPC to a FreeCAD instance (for web UI)

---

## FCUI-Py language sketch

### Component declarations
- Components are declared as classes with typed `prop` and `state`.
- `render()` returns a UI tree.

```python
@component
class Panel:
    title: prop[str] = "Selection"
    count: prop[int]

    def render(self):
        return Column(
            Text(text=self.title),
            Text(text="Count: " + str(self.count)),
            Button(text="Recompute", enabled=self.count > 0, clicked=fc.command("Std_Recompute")),
        )
```

### Binding expression subset (examples)
Allowed:
- Literals, arithmetic, comparisons, boolean ops
- Ternary `a if cond else b`
- Member access on typed objects
- Indexing
- Whitelisted pure functions: `min/max/clamp/len/str/format`

Not allowed:
- Loops, assignments, arbitrary function defs
- `eval/exec`, reflection
- Unbounded dynamic dispatch

### Event model
Prefer **symbolic commands** over lambdas for portability:
- `clicked=fc.command("Std_Recompute")`
- `changed=fc.set_property(obj_id, "Length", value)`

Optional restricted lambdas may be supported as a controlled subset (e.g., “set prop + call command”), but commands are the default.

### Lists and repeaters
Instead of loops, use a declarative repeater:

```python
Repeat(model=fc.selection.items, key=lambda o: o.id,
       template=lambda o: Row(Text(o.label), Button("Select", clicked=fc.select(o.id))))
```

Compiler treats `Repeat` specially for keyed child reconciliation.

---

## Portable module format (`.fcuim`)

### Contents
- Component schemas (props/state/callback signatures)
- UI template tree
- Per-property bindings encoded as bytecode for a small expression VM
- String/number const pools
- Optional debug/source map data

### Binding VM
A minimal instruction set (~40–80 ops) sufficient for:
- load prop/state
- load external signal
- arithmetic/compare/boolean
- string concat/format
- conditional select
- call builtin-pure by ID

This VM is small enough to port to WASM later.

---

## Runtime design

### Reactive dependency graph
- Each bound property stores a binding closure.
- Evaluating a binding records the signals it reads.
- When a dependency changes, the binding re-evaluates.

### Incremental updates
- Changed values update node props.
- If layout-affecting props change → re-layout affected subtree.
- Paint uses dirty regions when supported.

### Scheduling
- Batched updates on the GUI thread.
- Desktop: schedule via Qt event loop.
- Web: schedule via requestAnimationFrame/event loop.

---

## Renderer backends

### A) QtWidgetsRenderer (compatibility mode)
Purpose: **maximize mechanical `.ui` conversion** and integrate immediately.

- Builds real `QWidget` and `QLayout` objects.
- Maps FCUI nodes to QWidget classes.
- Events connect to FCUI callbacks/commands.

Pros:
- High fidelity to existing `.ui` behavior.
- Fast adoption inside current FreeCAD docking/task panels.

Cons:
- Not web portable.

### B) QtCanvasRenderer (portable mode)
Purpose: **renderer abstraction and portability**.

- Retained-mode scenegraph managed by FCUI runtime.
- Paint via QPainter (and later optional GPU path).
- Text shaping and image decoding via Qt services.
- Optional hidden native widgets for IME/accessibility text input.

Pros:
- Renderer is an implementation detail.
- Same UI template can target web renderer later.

Cons:
- Needs more initial work for rich widgets (trees, tables, etc.).

### C) Future WebCanvasRenderer
- Same retained scenegraph and layout model.
- Backend draws to Canvas/WebGL/WebGPU.
- Accessibility may be enhanced via a parallel semantics tree.

### D) Headless/Test renderer
- Executes bindings/layout without UI.
- Enables snapshot tests, regression tests, and conversion validation.

---

## Host Services API (FreeCAD integration)

### Design principle
Expose FreeCAD capabilities as **typed, reactive sources** + **commands**:

- Reactive sources (“signals”): selection count, active doc name, object properties.
- Commands: recompute, set property, run FreeCAD command, begin/end transaction.

### Example capability surface
- `fc.selection.count` (signal[int])
- `fc.selection.items` (signal[list[ObjectRef]])
- `fc.doc.active` (signal[DocRef])
- `fc.prop(obj, "Length")` (signal[float])
- `fc.command("Std_Recompute")` (Command)
- `fc.set_property(obj_id, prop_name, value)` (Command)
- `fc.transaction("Edit")` (scoped command/group)

### Backends
- **FreeCADHostLocal**: implemented in-process.
  - Transitional implementation can call FreeCAD Python APIs behind a stable boundary.
  - Target implementation should wrap needed APIs in C++ for robustness/perf.

- **FreeCADHostRemote** (future): RPC protocol.
  - Signals stream to UI.
  - Commands go back.
  - Enables running the same `.fcuim` in a browser.

---

## Qt `.ui` conversion strategy

### Why it matters
FreeCAD’s existing dialogs/panels are mostly Qt Designer `.ui` (Qt Widgets). Mechanical conversion reduces migration cost.

### Conversion pipeline
1. Parse `.ui` XML into **Designer IR** (loss-minimizing).
2. Convert Designer IR → FCUI template tree.
3. Emit **portability report**:
   - portable mapping coverage
   - remaining `NativeWidget` nodes
   - unsupported properties or stylesheets

### Designer IR schema (conceptual)
- Widget tree with `kind`, `objectName`, properties
- Layout nodes with margins/spacing/stretch/alignment
- Connections: (sender, signal, receiver, slot)
- Promoted/custom widgets metadata

### Mapping rules (examples)
Layouts:
- VBox/HBox/Grid/Form/Stacked → Column/Row/Grid/Form/Tabs/Stack

Widgets:
- QLabel → Text
- QPushButton → Button
- QLineEdit → TextInput
- QCheckBox → Toggle
- QComboBox → Dropdown
- QSpinBox/QDoubleSpinBox → NumberInput
- QGroupBox → Group
- QTabWidget → Tabs
- QScrollArea → Scroll

### Escape hatch for fidelity
- `NativeWidget("QTreeView")` etc. for complex views and promoted widgets.
- Supported in QtWidgetsRenderer, flagged as non-portable.

### Signals/slots conversion
- Common signals map to FCUI events (clicked/toggled/textChanged).
- Auto-connect slots become `CallbackRef("onX")` stubs unless mapped to known commands.

---

## Implementation plan (phased)

### Phase 0 — Foundations
Deliverables:
- FCUI-Py subset specification (allowed AST nodes for bindings/events)
- **Reference compiler frontend in Python** using CPython `ast.parse` (canonical syntax + locations + error messages)
- Module format v0 (schema + versioning)
- Minimal CLI: `fcui compile` and `fcui ui2fcui` (converter)

### Phase 1 — Runtime MVP + Qt embedding
Deliverables:
- Native runtime: binding VM, dependency graph, scheduler
- FreeCAD mount points: dock widget/task panel integration hooks
- FreeCADHostLocal v0: selection + basic commands
- Minimal widget set (Text, Button, Row/Column, basic inputs)

Success criteria:
- A simple FCUI panel runs inside FreeCAD and reacts to selection.

### Phase 2 — QtWidgetsRenderer compatibility path
Deliverables:
- QtWidgetsRenderer backend
- `.ui` → Designer IR → FCUI conversion tool
- Portability report generation

Success criteria:
- Convert and run a representative set of existing `.ui` panels with minimal manual edits.

### Phase 3 — Portable renderer (QtCanvasRenderer) + parity push
Deliverables:
- QtCanvasRenderer retained-mode scenegraph
- Layout engine covering common `.ui` constraints
- Focus, keyboard navigation, text input strategy
- Expand primitives: Tabs, Scroll, Group, Form, basic Table/Tree (initial)

Success criteria:
- Increasing fraction of converted UIs run on portable renderer without NativeWidget fallback.

### Phase 4 — Tooling and dev experience
Deliverables:
- Source maps + runtime error mapping
- Headless renderer + snapshot tests
- Inspector/devtools (component tree, bindings, dependency tracing)
- Hot reload (module swap, preserve state where possible)

Success criteria:
- Fast iteration and reliable regression testing for migrated UIs.

### Phase 5 — Web path (architecture locked-in earlier)
Deliverables:
- Runtime compiled to WASM
- WebCanvasRenderer MVP
- FreeCADHostRemote protocol + reference server

Success criteria:
- Same `.fcuim` runs in browser driving a FreeCAD instance via RPC.

---

## Risks and mitigations

1. **Widget coverage gap** (trees/tables/advanced editors)
   - Mitigation: QtWidgetsRenderer + NativeWidget escape hatch; prioritize a portable Table/Tree model early.

2. **Style/UX divergence** between QtWidgets and portable renderers
   - Mitigation: theme tokens; progressive migration; portability report.

3. **FreeCAD API surface is Python-centric**
   - Mitigation: capability-based host API; start with Python gateway behind stable interface; incrementally move hot paths to C++ wrappers.

4. **Text input/IME/accessibility** in canvas
   - Mitigation: hybrid approach with hidden native Qt input widgets; semantics tree for accessibility.

5. **Mechanical conversion expectations too high**
   - Mitigation: measure conversion coverage; provide reports; define a supported `.ui` subset; allow gradual replacement.

---

## Governance and adoption
- Keep FCUI optional initially: ship as an add-on layer.
- Migrate a few high-value panels first (task panels, property editors, wizards).
- Maintain a compatibility renderer so conversion doesn’t stall.
- Track progress with metrics:
  - % of `.ui` panels converted
  - % running without NativeWidget
  - performance (layout/paint time)
  - bug regression rate via snapshots

---

## Appendix: Practical “first set” of portable primitives
- Layout: Row, Column, Grid, Form, Stack, Spacer, Scroll
- Content: Text, Icon, Separator
- Input: Button, Toggle, TextInput, NumberInput, Dropdown
- Containers: Group, Tabs
- Lists: Repeat, List
- Integration: Command, NativeWidget (qt-only), Portal (advanced)

---

## Appendix: Conversion report output (example)
- Converted widgets: 42/50
- NativeWidget required: QTreeView, CustomSketchEditor
- Unsupported properties: sizePolicy on 3 nodes; stylesheet on 7 nodes
- Unmapped connections: onOkClicked, onCancelClicked (stubs generated)

