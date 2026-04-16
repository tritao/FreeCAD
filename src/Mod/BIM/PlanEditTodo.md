# BIM Plan Edit TODO

This note turns the current `PlanEdit.md` direction into an implementation
checklist.

The target is:

- Sketcher-like edit-mode semantics
- a modeless Plan Edit dock
- the current 3D view as the editing canvas

The target is not:

- a blocking task dialog that owns the full interaction lifecycle
- a separate plan document
- a new tab or viewer as the default Plan Edit path
- a fake object-level `setEdit()` hack just to mimic Sketcher mechanically

## Core Decision

Plan Edit should copy Sketcher's mode contract, not Sketcher's exact task-dialog
mechanism.

That means:

- entering Plan Edit should feel like entering a dedicated edit mode
- only one Plan Edit session may be active at a time
- conflicting dialogs or edit states should be resolved before entry
- there must be one explicit mode exit path
- closing the dock must leave the mode
- `Esc` should cancel the active subtool, not necessarily exit the whole mode

The session, not the panel, should own the lifecycle.

## Current Shell

Current entry/ownership points:

- [BimPlanEdit.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/bimcommands/BimPlanEdit.py)
  - `BIM_PlanEdit.Activated()`
- [BimPlanSession.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/bimcommands/BimPlanSession.py)
  - `start_session()`
  - `PlanEditSession.enter()`
  - `PlanEditSession.shutdown()`
  - `PlanEditSession.on_panel_closed()`
  - `PlanEditDockWidget`

This is already close to the desired architecture. The missing part is a
clearer "edit mode shell" around the session entry and exit rules.

## Phase 1: Entry and Exit Shell

Goal:

- make Plan Edit feel like a real edit mode before changing tool internals

### 1. Harden entry ownership in `BIM_PlanEdit.Activated()`

File:

- [BimPlanEdit.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/bimcommands/BimPlanEdit.py)

Changes:

- keep the current "if session exists, focus the dock" behavior
- before starting a new session, detect conflicting GUI ownership
- mirror Sketcher-style conflict handling:
  - active task dialog already open
  - another document object already in edit

Concrete tasks:

- add a helper to query whether another edit/dialog owner is active
- add a helper to prompt the user to close the conflicting UI state
- only call `BimPlanSession.start_session()` after conflicts are resolved

Checks:

- triggering `BIM_PlanEdit` twice should only focus the existing dock
- entering Plan Edit with another blocking task dialog open should prompt cleanly
- entering Plan Edit while another object is in edit should either refuse or reset that edit cleanly

### 2. Make `shutdown()` the single canonical exit path

File:

- [BimPlanSession.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/bimcommands/BimPlanSession.py)

Relevant methods:

- `shutdown()`
- `on_panel_closed()`
- `detach_task_panel()`

Changes:

- keep every exit route converging on `shutdown()`
- avoid duplicating teardown semantics in button handlers or dock events
- keep `close_dialog=False` only as an internal teardown control, not as a separate public exit concept

Concrete tasks:

- audit all callers of `shutdown()`
- ensure dock close, command re-trigger, document close, and app teardown all funnel through the same session exit logic
- document which cleanup steps must only happen once

Checks:

- clicking `Exit Plan Edit` leaves the mode
- closing the dock leaves the mode
- document close while Plan Edit is active does not leave stale callbacks or overlays

## Phase 2: Make the Mode Visually Explicit

Goal:

- make Plan Edit feel like entering Sketch edit mode without using a blocking task panel

### 3. Strengthen mode affordances in the dock and viewport

File:

- [BimPlanSession.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/bimcommands/BimPlanSession.py)

Relevant areas:

- `PlanEditDockWidget`
- `_refresh_task_panel_status()`
- viewport status chip helpers

Changes:

- keep the dock small and modeless
- make the mode header clearer
- keep one obvious exit control
- make the current tool and storey state more legible

Concrete tasks:

- tighten the dock header copy so it reads as a mode, not a generic widget
- keep `Exit Plan Edit` visually distinct
- make the viewport status chip authoritative for current mode/tool state
- ensure tool switches update dock state and viewport state together

Checks:

- users should be able to tell immediately that the document is in Plan Edit mode
- users should be able to tell which subtool is active without reading implementation-specific text

### 4. Add a dedicated Plan Edit toolbar

Goal:

- get Sketcher-like mode clarity without giving the task panel primary ownership

Files:

- likely [InitGui.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/InitGui.py)
- likely [BimPlanSession.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/bimcommands/BimPlanSession.py)

Changes:

- show a narrow Plan Edit toolbar while the session is active
- hide or de-emphasize unrelated actions while the session is active if practical

Suggested first toolbar:

- `Select`
- `Wall`
- `Rect Wall`
- `Move`
- `Join`
- `Exit`

Checks:

- the toolbar should reinforce mode boundaries
- the dock should remain secondary

## Phase 3: Clarify Input Semantics

Goal:

- make the mode contract predictable

### 5. Separate subtool cancel from mode exit

File:

- [BimPlanSession.py](/media/joao/DEV/FreeCAD-Distro/FreeCAD/src/Mod/BIM/bimcommands/BimPlanSession.py)

Relevant areas:

- key handlers
- `_cancel_embedded_tool()`
- `_cancel_rect_wall_tool()`
- `_cancel_wall_edit()`
- `_cancel_pending_edit()`
- `_cancel_symbol_handle_point_pick()`

Desired rules:

- `Esc` cancels the active subtool or modal edit
- `Esc` returns to `Select` when appropriate
- `Esc` does not exit the full mode unless there is an explicit separate decision to do so later
- `Exit Plan Edit` and dock close exit the full mode

Concrete tasks:

- document current `Esc` behavior in tests
- normalize cancel behavior across wall edit, opening move, symbol move, and embedded Draft-style tools
- avoid hidden mode exits from cancel paths

Checks:

- every subtool should have one predictable cancel rule
- exiting the whole mode should remain explicit

### 6. Keep the dock from stealing the interaction lifecycle

Goal:

- the dock controls the session, but does not become the editing surface

Changes:

- keep keyboard focus and point-pick behavior centered on the view
- only use the dock for storey/tool/session controls
- avoid embedding standalone task widgets into the dock

Concrete tasks:

- audit focus suppression and restore logic in `PlanEditDockWidget`
- keep point-pick and tracker workflows view-owned
- reject any new Plan Edit feature that requires a blocking task dialog unless there is no better alternative

## Phase 4: Optional Deeper Integration with GUI Edit State

Goal:

- improve consistency with Sketcher if the generic GUI hooks are good enough

This is optional and should happen only after the mode shell is stable.

### 7. Investigate using generic edit-state signals without forcing a task dialog

Relevant GUI APIs:

- document `setEdit()/resetEdit()` flow
- user edit mode state in `Gui::Application`
- `signalInEdit` / `signalResetEdit`
- `setUserEditMode()`

Question to answer:

- can Plan Edit participate in generic GUI edit-state signaling without pretending to be a normal object edit dialog?

Acceptable outcomes:

- reuse only user-edit-mode state and mode indicators
- add a generic session-edit abstraction later
- decide not to integrate if object-edit assumptions are too strong

Not acceptable:

- forcing Plan Edit into a fake object edit just to get Sketcher-like visuals

## Immediate Implementation Order

Do these first:

1. entry conflict handling in `BIM_PlanEdit.Activated()`
2. teardown audit around `PlanEditSession.shutdown()`
3. explicit mode affordance pass on the dock and viewport status chip
4. dedicated Plan Edit toolbar
5. cancel/exit behavior normalization

Do these later:

1. generic GUI edit-state integration
2. any optional multi-view or alternate-view experiments

## Test Checklist

Add or extend GUI coverage for:

- entering Plan Edit with no active conflicts
- entering Plan Edit while another task dialog is open
- re-triggering `BIM_PlanEdit` while the session is already active
- closing the dock exits the mode cleanly
- `Exit Plan Edit` exits the mode cleanly
- `Esc` cancels subtools but does not silently leave Plan Edit
- mode state survives normal tool switching
- mode state is fully cleaned up on document close

## Non-Goals for This Pass

Do not mix this shell work with:

- new plan-edit subtools
- new preview systems
- a separate plan view or tab
- a Draft-style all-purpose command panel

The purpose of this pass is to make Plan Edit behave like a robust mode first.
