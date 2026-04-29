# BIM Plan Edit TODO

This note is the branch-local follow-up list for `Plan Edit`.

Use:

- [PlanEdit.md](PlanEdit.md) for the current design and architecture overview
- [bimplan/devtools/PLAN_EDIT_ARCHITECTURE_PLAN.md](bimplan/devtools/PLAN_EDIT_ARCHITECTURE_PLAN.md)
  for internal API and cleanup work

This file tracks the remaining mode-shell, workflow, and UX work that is still
open after the `bimplan` split already happened.

## Scope

The target remains:

- Sketcher-like mode semantics
- a modeless Plan Edit dock
- the current 3D view as the editing canvas

The target is still not:

- a blocking task dialog that owns the full interaction lifecycle
- a separate plan document
- a dedicated plan-view tab as the default workflow
- a fake object-level `setEdit()` hack just to mimic Sketcher mechanically

## Current Baseline

The old migration phase described in this file is already complete enough that
it should no longer be treated as future work.

Today:

- [bimcommands/BimPlanEdit.py](bimcommands/BimPlanEdit.py) is the public command entrypoint
- [bimcommands/BimPlanSession.py](bimcommands/BimPlanSession.py) is a compatibility shim
- [bimplan/runtime/session.py](bimplan/runtime/session.py) is the real session composition root
- the task-panel shell and controls already live under `bimplan/ui/`
- the viewport status chip already lives in [bimplan/ui/task_panel.py](bimplan/ui/task_panel.py)
- selection, overlays, tools, providers, and view/runtime concerns already have dedicated packages
- dock close already routes through `task_panels.on_panel_closed()` into `session.shutdown()`
- the explicit exit button already calls `session.shutdown()`
- `Esc` already mostly cancels active subtools instead of exiting the full mode

This means the remaining work is no longer "split the monolith". The remaining
work is to harden the mode contract, reduce compatibility edges, and make the
mode more explicit and robust.

## What This File Should Track

Track here:

- mode entry and exit behavior
- tool ownership gaps that are still visible to users
- task-panel and viewport affordance work
- focus, snapper, and embedded-command lifecycle risks
- test gaps in the maintained Plan Edit suites

Do not track here:

- already-completed `bimplan` module extraction
- low-level owned-API cleanup that is already tracked in
  `bimplan/devtools/PLAN_EDIT_ARCHITECTURE_PLAN.md`

## Near-Term Priorities

### 1. Harden mode entry ownership

Goal:

- entering Plan Edit should behave like entering a real mode, not just running another command

Primary files:

- [bimcommands/BimPlanEdit.py](bimcommands/BimPlanEdit.py)
- [bimplan/runtime/session.py](bimplan/runtime/session.py)

Current gap:

- re-triggering `BIM_PlanEdit` already focuses the active session correctly
- starting a new session still does not clearly resolve conflicting GUI ownership first

Concrete tasks:

- detect conflicting task dialogs or edit ownership before starting a session
- decide whether Plan Edit should refuse entry, prompt the user, or cleanly resolve the conflict
- keep the current "focus existing session" behavior intact
- add explicit coverage for conflict handling

Checks:

- triggering `BIM_PlanEdit` twice should only focus the existing panel
- entering Plan Edit with another blocking task dialog open should fail or recover predictably
- entering Plan Edit while another object is in edit should not leave mixed ownership behind

### 2. Keep `shutdown()` as the single canonical mode exit

Goal:

- every real mode exit should converge on one teardown path

Primary files:

- [bimplan/runtime/session.py](bimplan/runtime/session.py)
- [bimplan/runtime/lifecycle.py](bimplan/runtime/lifecycle.py)
- [bimplan/ui/task_panel.py](bimplan/ui/task_panel.py)
- [bimplan/ui/control_shell.py](bimplan/ui/control_shell.py)

Current state:

- panel close already funnels through `on_panel_closed()`
- the dock exit button already calls `session.shutdown()`

Remaining tasks:

- audit document-close and app-teardown paths
- make sure cleanup steps that must run once do not double-run
- keep `close_dialog=False` as an internal teardown control, not a second public exit concept
- add tests for close and teardown edge cases

Checks:

- clicking `Exit Plan Edit` leaves the mode cleanly
- closing the panel leaves the mode cleanly
- document close while Plan Edit is active does not leave stale observers, trackers, or command ownership

### 3. Remove the remaining embedded-command edges

Goal:

- reduce the amount of Plan Edit behavior that still depends on legacy Draft/BIM interactive command ownership

Primary files:

- [bimplan/tools/wall_create.py](bimplan/tools/wall_create.py)
- [bimplan/runtime/lifecycle.py](bimplan/runtime/lifecycle.py)
- [bimplan/tools/hosted_openings.py](bimplan/tools/hosted_openings.py)

Current embedded edges that still matter:

- the plain `Wall` tool still delegates to `bimcommands.BimWall.Arch_Wall()`
- the generic `Move` tool still delegates to `draftguitools.gui_move.Move()`

Related compatibility edges that still exist in session-owned flows:

- several tools still rely on `FreeCAD.activeDraftCommand`
- several point-pick flows still rely on Draft Snapper lifecycle boundaries

Concrete tasks:

- implement or plan a native straight-wall creation flow owned fully by the session
- decide whether the generic `Move` tool should remain embedded or gain a plan-owned replacement
- keep the embedded host bridge narrow and explicit wherever removal is not practical yet
- keep cancel behavior and focus restoration consistent for all remaining embedded tools

Checks:

- switching away from an embedded tool should not leave Draft or Snapper state behind
- `Esc` should cleanly cancel any embedded tool without exiting the full mode
- moving between embedded and session-owned tools should not corrupt selection or overlay state

### 4. Tighten mode affordances without making the dock primary

Goal:

- users should be able to tell immediately that the document is in Plan Edit and which tool is active

Primary files:

- [bimplan/ui/controls.py](bimplan/ui/controls.py)
- [bimplan/ui/control_shell.py](bimplan/ui/control_shell.py)
- [bimplan/ui/task_panel.py](bimplan/ui/task_panel.py)
- [bimplan/ui/status_text.py](bimplan/ui/status_text.py)

Current state:

- the dock already has a mode header and explicit exit
- the viewport status chip already exists

Remaining tasks:

- make sure the dock header, current-tool state, and viewport chip tell one coherent story
- keep `Exit Plan Edit` visually distinct
- review whether the mode still needs a dedicated narrow toolbar for discoverability
- avoid turning the task panel into the primary editing surface

Checks:

- users should immediately recognize the active mode
- users should be able to identify the active subtool without reading implementation-specific hints
- task-panel state and viewport chip state should stay in sync during tool changes

### 5. Keep the dock secondary and focus-safe

Goal:

- the view owns interaction; the dock controls the session

Primary files:

- [bimplan/ui/control_shell.py](bimplan/ui/control_shell.py)
- [bimplan/runtime/lifecycle.py](bimplan/runtime/lifecycle.py)

Current state:

- the dock is already modeless
- Plan Edit already suppresses some Draft toolbar focus interactions during point picks

Remaining tasks:

- audit point-focus suppression and restore behavior
- make sure Snapper flows always return focus ownership to the correct place
- reject any new Plan Edit feature that requires a blocking task dialog unless there is no better alternative

Checks:

- starting a point-pick flow should keep the interaction centered on the viewport
- accepting or canceling a point-pick flow should restore focus and toolbar state predictably

## Medium-Term Product Follow-Up

These are valid next steps, but they should follow the mode-shell hardening work
above rather than compete with it.

### Native straight wall tool

The most important product gap is still the lack of a fully session-owned
straight wall tool to replace the embedded `Arch_Wall` flow.

Desired outcome:

- wall creation and wall editing follow one consistent session-owned lifecycle
- wall previews, cancel behavior, and selection behavior match the rest of Plan Edit

### Tool discoverability

If the mode still feels hidden after the dock and viewport affordance pass,
consider a narrow Plan Edit toolbar that reflects the real session tools.

If added, keep it intentionally small:

- `Select`
- `Wall`
- `Rect Wall`
- `Move`
- `Join`
- `Window`
- `Space`
- `Region`
- `Separator`
- `Exit`

This should reinforce mode boundaries, not turn Plan Edit into a generic Draft
toolbar.

### Optional GUI edit-state integration

This remains optional.

Question:

- can Plan Edit participate in generic GUI edit-state signaling without pretending to be a normal object edit dialog?

Relevant APIs to investigate later:

- document `setEdit()/resetEdit()` flow
- user edit mode state in `Gui::Application`
- `signalInEdit` / `signalResetEdit`
- `setUserEditMode()`

Acceptable outcomes:

- reuse only user-edit-mode state and generic mode indicators
- add a generic session-edit abstraction later
- decide not to integrate if object-edit assumptions are too strong

Not acceptable:

- forcing Plan Edit into a fake object edit just to get Sketcher-like visuals

## Immediate Implementation Order

Do these first:

1. entry conflict handling in `BIM_PlanEdit.Activated()`
2. teardown audit around `session.shutdown()`
3. embedded `Wall` and `Move` ownership review
4. dock/header/status-chip affordance pass
5. focus and Snapper lifecycle audit

Do these next:

1. decide whether to add a dedicated Plan Edit toolbar
2. continue replacing embedded tool paths with session-owned flows
3. investigate optional GUI edit-state integration only after the mode shell feels stable

## Test Checklist

Add or extend coverage for:

- entering Plan Edit with no active conflicts
- entering Plan Edit while another task dialog is open
- entering Plan Edit while another edit owner is active
- re-triggering `BIM_PlanEdit` while the session is already active
- closing the dock exits the mode cleanly
- `Exit Plan Edit` exits the mode cleanly
- `Esc` cancels subtools but does not silently leave Plan Edit
- switching between session-owned and embedded tools keeps selection and overlays coherent
- mode state is fully cleaned up on document close
- mode state is fully cleaned up on teardown paths triggered outside the normal exit button

## Non-Goals For This Pass

Do not mix this roadmap with:

- new experimental plan-edit subtools that change the product surface area
- large internal API cleanup batches already tracked elsewhere
- a separate plan view, tab, or document
- a Draft-style all-purpose command panel

The purpose of this pass is to make Plan Edit behave like a robust, explicit
mode with clear ownership boundaries.
