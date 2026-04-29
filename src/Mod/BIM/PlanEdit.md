# BIM Plan Edit

This document describes the current design of `Plan Edit` in the BIM workbench.

Related notes:

- implementation follow-up and branch-local roadmap: [PlanEditTodo.md](PlanEditTodo.md)
- current internal cleanup plan: [bimplan/devtools/PLAN_EDIT_ARCHITECTURE_PLAN.md](bimplan/devtools/PLAN_EDIT_ARCHITECTURE_PLAN.md)
- maintained verification entrypoint: [bimtests/run_plan_edit_headless.py](bimtests/run_plan_edit_headless.py)

`Plan Edit` is a persistent, storey-scoped BIM authoring mode. It uses the
normal 3D document and 3D Inventor view, but constrains interaction to a
plan-oriented editing workflow.

It is not:

- a separate 2D drafting document
- a TechDraw page workflow
- a blocking task dialog that temporarily takes over the UI

The source of truth remains the BIM model:

- walls stay `Wall` objects
- windows and doors stay hosted BIM elements
- spaces stay BIM spaces
- provider-owned semantic objects stay provider-owned BIM objects

The plan view is a representation of the BIM model, not a duplicate drawing.

## Product Contract

Plan Edit should feel like a persistent editor:

- one session at a time
- explicit mode entry and exit
- top orthographic editing in the existing 3D view
- canvas-first interaction
- contextual task-panel controls as a secondary surface
- direct updates to real BIM objects and provider-owned semantics

The primary user loop is:

- choose a storey
- enter Plan Edit
- see plan-oriented visuals and selection behavior
- manipulate walls, openings, spaces, symbols, regions, and provider targets in the view
- exit explicitly when finished

## Public Entry Points

The current public shell is split into three layers:

- [bimcommands/BimPlanEdit.py](bimcommands/BimPlanEdit.py)
  - registers the `BIM_PlanEdit` command
  - re-focuses the active Plan Edit session if one already exists
  - starts a new session otherwise
- [bimcommands/BimPlanSession.py](bimcommands/BimPlanSession.py)
  - compatibility shim
  - re-exports the current session implementation from `bimplan.runtime.session`
- [bimplan/runtime/session.py](bimplan/runtime/session.py)
  - real composition root
  - owns `start_session()`, `get_active_session()`, and `PlanEditSession`

This means the old `bimcommands.BimPlanSession` import path still works, but it
is no longer the architectural home of the feature.

## Session Lifecycle

`PlanEditSession` is the coordinator for the live mode.

On entry it currently:

- validates that an active document and 3D Inventor view exist
- captures viewer state and object-visibility state
- forces plan-friendly preselection and top orthographic view
- collects storeys and resolves the initial active storey
- applies the plan snap profile
- applies storey-scoped visibility
- attaches the GUI selection observer
- attaches document-visual observers
- registers viewport edit callbacks
- refreshes the selected plan target state
- builds and attaches the Plan Edit task-panel widget
- primes caches for overlays, openings, and hover picking
- installs the command gate used by embedded and session-owned tools

On shutdown it restores the captured view and interaction state, detaches
observers, tears down temporary overlays and callbacks, and clears the global
active-session slot.

There is intentionally only one active Plan Edit session.

## Composition Model

`PlanEditSession` is not meant to be a giant behavior bucket. It composes
owned API surfaces, each responsible for one part of the mode.

The current session-owned surfaces instantiated in
[bimplan/runtime/session.py](bimplan/runtime/session.py) are:

- `selection`
- `spaces`
- `openings`
- `wall_relations`
- `wall_create`
- `interaction`
- `input`
- `lifecycle`
- `symbols`
- `windows`
- `viewport`
- `overlays`
- `wall_edit`
- `visibility`
- `providers`
- `storey`
- `snap`
- `performance`
- `document_visuals`
- `status_text`
- `task_panels`

The session should compose and route. Subsystems should own their behavior.

## Module Ownership

### Runtime

The `bimplan/runtime/` package owns session-level coordination:

- `session.py`
  - session creation, active-session tracking, high-level composition
- `lifecycle.py`
  - enter/exit behavior, tool switching, cancel flows, embedded-tool cleanup
- `input.py`
  - viewport event routing and keyboard behavior
- `view.py`
  - viewer capture/restore, callbacks, projection helpers, view policy
- `session_state.py`
  - mutable session state and interaction state wiring
- `tools.py`
  - stable runtime tool identifiers
- `command_gate.py`
  - command ownership boundaries while Plan Edit is active

### Selection

The `bimplan/selection/` package owns plan target resolution and GUI selection
synchronization:

- native GUI selection/preselection sync
- hovered and selected plan-target state
- typed target records and target-kind helpers
- plan-specific picking and activation rules
- edit-node resolution for overlays and handles

Selection is where raw GUI object hits become plan concepts such as wall,
opening, symbol, space, region, or provider target.

### Overlays

The `bimplan/overlays/` package owns tracker-backed plan visuals:

- selected and hovered wall visuals
- wall grips and wall-opening context visuals
- opening overlays and handle pools
- symbol overlays
- space and region overlays
- provider overlay rendering
- shared tracker lifecycle and refresh routing

The overlay layer is render-side only. It should not own business rules for how
objects are edited.

### Tools

The `bimplan/tools/` package owns concrete editing behaviors:

- wall editing and previews
- wall creation flows
- opening movement and editing
- window placement and size/style editing
- symbol movement and rotation
- wall-join workflows
- space, separator, and region editing flows
- hosted-opening command bridges

Some tools are fully session-owned. Some still bridge into older Draft/BIM
interactive infrastructure where that is not yet fully replaced.

### Providers

The `bimplan/providers/` package is the extension surface for semantic Plan Edit
integrations.

Providers contribute declarative models such as:

- `PlanProviderTargetSpec`
- `PlanOverlaySpec`
- `PlanToolSpec`
- `PlanEditHandleSpec`
- `PlanIssueSpec`
- `PlanSuggestionSpec`
- `PlanContextPanelSpec`
- `PlanInspectorSection`

The registry lives in `providers/contracts.py`, the session-facing behavior in
`providers/runtime.py`, and built-in BIM-owned providers in
`providers/builtin.py`.

The important contract is:

- providers describe targets, overlays, handles, tools, issues, and actions
- the Plan Edit core owns selection, rendering, interaction routing, and action execution

This keeps provider integrations declarative and keeps session ownership inside
the Plan Edit core.

### UI and Read Models

The task-panel UI is split across:

- `ui/controls.py`
  - concrete `PlanEditControlsWidget`
- `ui/control_shell.py`
  - task-panel shell and main button wiring
- `ui/control_editors.py`
  - editor-facing controls for openings, spaces, regions, and similar panels
- `ui/control_integrations.py`
  - provider-facing integration panels
- `task_panel.py`
  - panel attach/detach and refresh helpers
- `task_panel_view_model.py`
  - read-side view models for UI state shaping
- `status_text.py`
  - user-facing status and help text

The task panel is intentionally secondary. It exposes session state and
integration surfaces, but it should not become the primary editing surface.

## Current Interaction Model

The runtime tool identifiers currently live in
[bimplan/runtime/tools.py](bimplan/runtime/tools.py). User-facing and transient
tool states include:

- `Select`
- `Wall`
- `Rect Wall`
- `Window`
- `Region`
- `Separator`
- `Move`
- `Join`
- `Move Wall`
- `Move Opening`
- `Move Symbol`
- `Rotate Symbol`
- `Move Provider`
- `Provider Point`
- `Pick Space Region`
- `Set Space Text`

Two design choices matter here:

- Plan Edit is still a session with a current tool, not a collection of unrelated commands.
- Some tool names represent transient modal states inside the session rather than toolbar buttons.

The task panel switches tools, but the viewport remains the primary interaction
surface.

## Tool Ownership Today

The current architecture is already beyond the original "first iteration", but
it is not at the final target state yet.

Current state:

- wall editing is session-owned
- joins are session-owned
- spaces, regions, separators, symbols, provider handles, and provider point tools are session-owned flows
- hosted window placement is session-owned
- task-panel editing of selected windows is session-owned
- provider integrations are registry-driven and session-owned

Important compatibility edges still remain:

- the plain `Wall` tool still delegates to `bimcommands.BimWall.Arch_Wall()` through a Plan Edit host bridge
- some creation flows still rely on `FreeCAD.activeDraftCommand` and Draft Snapper ownership
- broad defensive exception handling still exists at FreeCAD and Qt boundaries
- some internal surfaces still use forwarding helpers that the cleanup plan intends to reduce

So the direction is clear: keep the session-owned interaction model, and shrink
the remaining embedded-command compatibility shell over time.

## Design Principles

The following principles should remain stable:

- Plan Edit is a BIM authoring mode, not a detached drafting page.
- The BIM model remains the source of truth.
- The existing 3D view remains the editing canvas.
- The task panel is secondary, not primary.
- Selection should resolve to typed plan targets rather than raw GUI hits.
- Providers should contribute declarative data, not own the core interaction loop.
- The session should coordinate; subsystem modules should own behavior.

## Testing As Specification

The most reliable description of current behavior is a combination of this
document and the maintained tests:

- [bimtests/TestBimPlanCore.py](bimtests/TestBimPlanCore.py)
  - core contracts and internal APIs
- [bimtests/TestBimPlanProviderSelectionGui.py](bimtests/TestBimPlanProviderSelectionGui.py)
  - provider-target and preselection behavior
- [bimtests/TestBimPlanEditGui.py](bimtests/TestBimPlanEditGui.py)
  - aggregate GUI workflow coverage
- [bimtests/run_plan_edit_headless.py](bimtests/run_plan_edit_headless.py)
  - maintained headless runner

When this document and the tests disagree, the tests usually reflect the
current shipped behavior more accurately.

## Roadmap Direction

Near-term work should continue in three directions:

- remove internal compatibility indirection where owned APIs already exist
- keep moving creation and editing flows under explicit session ownership
- preserve the provider contract as the main extension mechanism for semantic Plan Edit behavior

For detailed cleanup batches and branch-local follow-up notes, see
[PlanEditTodo.md](PlanEditTodo.md) and
[bimplan/devtools/PLAN_EDIT_ARCHITECTURE_PLAN.md](bimplan/devtools/PLAN_EDIT_ARCHITECTURE_PLAN.md).
