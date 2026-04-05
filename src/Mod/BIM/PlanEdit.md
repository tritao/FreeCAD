# BIM Plan Edit

This document defines the intended direction of `Plan Edit` in the BIM workbench and records the first implemented iteration.

`Plan Edit` is not meant to be a separate 2D drafting document. It is a storey-scoped BIM authoring mode that uses the normal 3D document and view, but constrains interaction to top-plan editing.

## Goal

The target workflow is:

- pick a building storey
- enter a dedicated plan-authoring mode
- edit walls, openings, spaces, and related BIM components in top view
- see 2D plan representations while still editing real BIM objects

The source of truth remains the BIM model:

- walls stay `Wall` objects
- windows and doors stay hosted BIM elements
- spaces stay BIM spaces
- the plan view is a representation of BIM, not a separate drawing

This is closer to the Revit floor-plan interaction model than to a generic Draft page or TechDraw workflow.

## First Iteration

The first implemented iteration lives in:

- `src/Mod/BIM/bimcommands/BimPlanEdit.py`
- `src/Mod/BIM/bimcommands/BimPlanSession.py`

The current mode provides:

- command entry via `BIM_PlanEdit`
- activation from the BIM workbench and level/storey context menus
- modeless dock instead of a locked task panel
- top orthographic view while the mode is active
- viewer override mode set to `Footprint`
- theme-aware lighter plan background while the mode is active
- storey selection in the dock
- explicit `Exit Plan Edit`
- direct grips for selected baseless walls:
  - start endpoint
  - end endpoint
  - midpoint
- preview-only wall dragging:
  - the real wall is hidden during drag
  - a temporary preview is shown
  - the wall is updated only on mouse release
- centralized cancellation for active wall editing

The current wall grip rules are:

- endpoint drag is axis-preserving by default
- midpoint drag translates the full wall
- a minimum wall length threshold is enforced
- cancel drops the preview and restores the original wall

## Current Limitations

The first iteration is intentionally narrow. It does not yet provide:

- a native session-owned wall creation tool
- wall joins
- hosted door or window placement
- space detection
- storey-based hide/ghost/lock behavior
- temporary dimensions
- a generalized footprint API for all BIM components

The current `Wall` button still delegates creation to the existing `Arch_Wall` interactive command. That is acceptable for bootstrapping, but it is not the target architecture.

## Core UX Contract

`Plan Edit` should behave like a persistent editor, not like a one-off command dialog.

The mode contract is:

- the active storey defines the editing plane
- the 3D view is forced to top orthographic while the mode is active
- plan representations are shown instead of normal 3D presentation where possible
- direct manipulation happens in the canvas
- the dock is secondary and should only expose session-level controls

The dock should remain small and modeless. It is not the main editing surface.

The primary interactions should happen in the view:

- select wall
- see grips immediately
- drag grips directly
- place new objects directly in plan
- cancel the current subtool with `Esc`
- exit the whole mode explicitly with `Exit Plan Edit`

## Why Plan Edit Needs Session-Owned Tools

The generic Draft and BIM interactive commands are useful infrastructure, but they are not the right lifecycle model for `Plan Edit`.

The current mismatch is:

- `Plan Edit` is a persistent session
- legacy commands such as `Arch_Wall` assume they temporarily own the interaction lifecycle
- Draft toolbar state, `activeDraftCommand`, Snapper state, and task/dialog state are coupled

That mismatch caused much of the first implementation complexity.

The long-term direction is:

- reuse Draft infrastructure
  - Snapper
  - trackers
  - event callback patterns
  - geometry helpers where useful
- stop reusing standalone command lifecycles unchanged inside `Plan Edit`

In practice, `Plan Edit` should own the session, and individual plan tools should be subtools of that session.

## Target Architecture

The intended architecture is:

### `PlanEditSession`

Responsible for:

- entering and leaving plan mode
- capturing and restoring viewer state
- storey scope
- selection policy
- grip and preview overlays
- active subtool routing
- shared cancel and finish behavior

### Modeless `Plan Edit` Dock

Responsible for:

- storey selection
- tool switching
- plan-mode settings
- explicit exit

The dock should not own the editing lifecycle.

### Session-Owned Subtools

Planned subtools:

- `Select`
- `Wall`
- `Move`
- `Join`
- `Door`
- `Window`
- `Space`

These tools should use a shared interaction contract:

- enter
- mouse press
- mouse move
- key press
- accept
- cancel

### BIM Object Adaptation

The mode should update BIM objects directly:

- baseless walls via endpoint logic
- later, base-driven walls via base geometry updates
- later, hosted openings and spaces

The interaction layer should be new. The BIM semantics should be reused.

## Toolbar Scope

The recommended first real toolbar for `Plan Edit` is:

- `Select`
- `Wall`
- `Move`
- `Join`
- `Door`
- `Window`
- `Space`
- `Exit`

This toolbar is intentionally narrow. `Plan Edit` should not become a general Draft sandbox in top view.

Generic Draft creation tools such as arcs, circles, splines, arrays, or generic drafting helpers should stay out of the default plan-edit workflow unless a specific BIM-authoring need justifies them.

## Wall Editing Rules

For the next iterations, wall behavior should be explicit.

### Selection

- selecting one baseless wall shows direct grips
- empty-canvas click clears selection
- clicking a grip starts editing immediately

### Endpoint Drag

- default behavior preserves the wall axis
- dragging changes wall length, not wall angle
- invalid too-short walls are rejected
- a future modifier may allow free-angle endpoint editing if needed

### Midpoint Drag

- midpoint drag is pure translation
- wall vector and length are preserved

### Preview

- the real wall should not be recomputed on every mouse move
- a lightweight plan preview should be shown during drag
- the real BIM object should be updated once on commit

### Cancel

All cancel routes should converge on one semantic operation:

- restore original wall state if necessary
- clear preview and temporary callbacks
- keep selection stable
- return to `Select`

That includes:

- `Esc`
- clicking `Select`
- `Exit Plan Edit`
- closing the dock

## Why a Native Plan Wall Tool Is Needed

The current wall editing path is already session-owned. Wall creation is not.

The current creation path still delegates to `Arch_Wall`, which means:

- different lifecycle rules for create vs edit
- handoff complexity between `Plan Edit` and Draft/BIM command state
- extra cleanup logic for cursor, Snapper, and command state

The next major implementation step should therefore be a native `Plan Wall Tool`.

That tool should:

- be owned by `PlanEditSession`
- create baseless walls directly in plan
- use the same preview and cancel rules as grip editing
- avoid taking over the UI with separate task panels

This does not require reimplementing wall semantics from scratch. It requires a new interaction layer that reuses wall creation logic underneath.

## Recommended Roadmap

### Phase 1

Completed in the first iteration:

- persistent plan mode entry
- modeless dock
- storey selection
- plan-view state
- direct wall grips
- preview-only drag editing

### Phase 2

Next:

- native `Plan Wall Tool`
- remove reliance on delegated `Arch_Wall` interaction inside plan mode
- keep wall creation and wall editing under one session-owned model

### Phase 3

After wall creation is session-owned:

- storey-scoped visibility and locking
- ghost or hide above/below levels
- better plan-mode selection filtering

### Phase 4

Then:

- wall joins
- hosted door and window placement
- direct opening repositioning on host walls

### Phase 5

Later:

- room and space detection
- temporary dimensions
- generalized component footprints
- columns, grids, stairs, fixtures

## Concrete Principles To Preserve

The following decisions should remain stable unless there is a strong reason to change them:

- `Plan Edit` is a BIM authoring mode, not a Draft page
- the source of truth is the BIM model
- the 3D view remains the editing canvas
- the dock is secondary, not primary
- direct manipulation should dominate over panel-driven editing
- the session should own interaction state
- standalone command lifecycles should not be embedded unchanged inside `Plan Edit`

## File Ownership

Current files:

- `src/Mod/BIM/bimcommands/BimPlanEdit.py`
  - command entry
- `src/Mod/BIM/bimcommands/BimPlanSession.py`
  - session, dock, grips, drag preview, selection observer

Likely next files once the feature grows:

- `src/Mod/BIM/bimcommands/BimPlanWallTool.py`
- `src/Mod/BIM/bimcommands/BimPlanJoinTool.py`
- `src/Mod/BIM/bimcommands/BimPlanFootprints.py`

For now, the implementation remains intentionally compact while the interaction model is still being validated.
