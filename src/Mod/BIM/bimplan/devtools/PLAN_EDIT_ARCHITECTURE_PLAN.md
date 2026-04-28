# Plan Edit Target Architecture

This document describes the desired long-term shape for BIM Plan Edit and a pragmatic migration path from the current codebase.

The goal is not to make the code more abstract. The goal is to make ownership clear, keep interaction paths fast, and make FreeCAD-specific lifecycle behavior easier to reason about.

## Design Goals

- `PlanEditSession` is a composition root, not a feature owner.
- Domain behavior lives in real services with real methods.
- State is typed and grouped by ownership.
- Picking, selection, overlays, tools, providers, UI, and document visual invalidation have distinct responsibilities.
- FreeCAD, Qt, Coin, and Draft tracker behavior stays near adapter/edge code.
- Refresh work is explicit and cheap on hot interaction paths.
- Refactors must remove complexity, reduce API surface, improve measured behavior, or make a bug class harder to reintroduce.

## Non-Goals

- Do not build a generic event bus or dependency injection framework.
- Do not add `__getattr__` proxy surfaces.
- Do not replace forwarding lists with reflection or auto-exported module APIs.
- Do not split files just to split files.
- Do not preserve broad internal compatibility shims once owned call sites have moved.
- Do not hide FreeCAD-specific timing issues behind generic abstractions.

## Target Shape

`PlanEditSession` should mostly wire services together:

```python
session.state
session.document
session.viewport
session.selection
session.picking
session.overlays
session.tools
session.providers
session.ui
session.lifecycle
```

The session may coordinate lifecycle and shared references, but it should not become a flat API with hundreds of feature methods.

## State Model

State should live in one typed tree:

```python
@dataclass
class PlanEditState:
    lifecycle: LifecycleState
    selection: SelectionState
    hover: HoverState
    overlays: OverlayState
    tools: ToolState
    providers: ProviderState
    ui: UIState
    caches: PlanEditCaches
```

Rules:

- No new raw `session._foo` state.
- Services mutate their owned state directly.
- Cross-domain state changes go through the owning service.
- Compatibility state aliases are temporary migration scaffolding and should shrink over time.

## Services

Services should be regular classes, not facades backed by method lists.

Good:

```python
class WallOverlayService:
    def sync_selected(self): ...
    def sync_hovered(self): ...
    def clear_grips(self): ...
```

Avoid:

```python
_WALL_OVERLAY_FORWARDERS = (...)
```

Module-level helper functions are fine when they are pure helpers or FreeCAD adapters. They should not be the long-term public ownership surface for a domain service.

## Selection

Selection owns semantic editor selection and GUI selection synchronization.

Target service shape:

```python
session.selection.state
session.selection.refresh
session.selection.sync
session.selection.activation
```

Responsibilities:

- normalize and store primary/secondary selected targets
- apply semantic selection changes
- synchronize to and from `FreeCADGui.Selection`
- schedule deferred GUI selection replay when needed
- refresh selected-target visuals by delegating to overlay/tool owners

Selection should not own geometric picking policy.

## Picking

Picking should be its own subsystem, separate from selection.

Target public API:

```python
session.picking.pick(mouse_pos, mode="click")
session.picking.hover(mouse_pos)
session.picking.pick_edit_node(mouse_pos)
```

Internal shape:

```text
picking/
  coordinator.py
  context.py
  handles.py
  providers.py
  openings.py
  symbols.py
  walls.py
  regions.py
  spaces.py
```

`PickingCoordinator` owns priority order. Individual pickers own target-specific hit testing.

Suggested click priority:

1. selected edit handles
2. provider overlay targets when provider overlay mode is focused
3. openings and symbols
4. walls
5. regions
6. spaces

The priority rules should be explicit and tested. Picking performance should remain measurable with the existing Plan Edit perf trace.

## Tools

Plan Edit is tool-driven. Tools should be first-class state machines.

Target tool contract:

```python
class PlanTool:
    def enter(self): ...
    def leave(self): ...
    def on_mouse_move(self, event): ...
    def on_mouse_press(self, event): ...
    def on_key(self, event): ...
    def cancel(self): ...
```

Expected tools:

- `SelectTool`
- `WallCreateTool`
- `WallEditTool`
- `OpeningTool`
- `SymbolTool`
- `SpaceTool`
- `RegionTool`
- `JoinTool`
- `ProviderPointTool`

`runtime/input.py` should become a dispatcher into the active tool, not a growing policy module.

## Overlays

Grouped overlay services are the right direction and should stay.

```python
session.overlays.manager
session.overlays.geometry
session.overlays.walls
session.overlays.openings
session.overlays.symbols
session.overlays.spaces
session.overlays.providers
```

Top-level `session.overlays` should only coordinate cross-overlay concerns:

- queue visual refresh
- queue view-scale refresh
- consume dirty visual flags
- flush tracker teardown safely

It should not provide a flat compatibility surface for every overlay method.

## Document Visuals

`document_visuals` should be a coordinator.

Target API:

```python
document_visuals.on_object_changed(obj, prop)
document_visuals.on_object_deleted(obj)
document_visuals.invalidate(obj=None)
document_visuals.flush()
```

It should route changes to owners:

- `session.openings.on_document_changed(obj, prop)`
- `session.spaces.on_document_changed(obj, prop)`
- `session.overlays.symbols.on_document_changed(obj, prop)`
- `session.selection.refresh.on_document_changed(obj, prop)`
- `session.providers.invalidate_for_object(obj)`

It should not directly own wall, opening, symbol, space, provider, or selection refresh policy.

## UI Refresh

Task panel and controls refresh should use explicit reasons:

```python
ui.refresh(reason="full")
ui.refresh(reason="selection")
ui.refresh(reason="tool")
ui.refresh(reason="provider_overlay_mode")
ui.refresh(reason="document")
```

Rules:

- ordinary wall selection must not rebuild provider snapshots
- hover movement must not rebuild task-panel UI
- provider panels refresh only when visible state, provider context, or provider selection actually changes
- UI view models should read from owned services and avoid compatibility fallbacks

## Providers

Providers should be isolated from hot interaction paths.

Target grouping:

```python
session.providers.runtime
session.providers.picking
session.providers.editing
session.providers.panel_model
```

Rules:

- provider target and overlay calls are cached by stable Plan Edit context
- provider snapshot rebuilds are not triggered by ordinary non-provider selection
- provider calls at hover time should use cached overlays/targets whenever possible
- external provider failures are contained at provider boundaries

## FreeCAD Integration

FreeCAD-specific behavior should remain explicit and close to the edge:

- `FreeCADSelectionAdapter`
- `FreeCADDocumentObserver`
- `CoinOverlayTrackerManager`
- `QtTaskPanelController`
- `DraftSnapAdapter`

These do not need to become formal interfaces unless tests or lifecycle issues justify it. The important part is that FreeCAD/Qt/Coin timing concerns do not leak across every service.

## Proposed Package Shape

```text
bimplan/
  session.py
  state.py
  lifecycle.py

  selection/
    service.py
    state.py
    refresh.py
    gui_sync.py
    activation.py

  picking/
    coordinator.py
    context.py
    handles.py
    providers.py
    openings.py
    symbols.py
    walls.py
    regions.py
    spaces.py

  overlays/
    service.py
    manager.py
    geometry.py
    walls.py
    openings.py
    symbols.py
    spaces.py
    providers.py

  tools/
    base.py
    select.py
    wall_create.py
    wall_edit.py
    opening.py
    symbol.py
    space.py
    region.py
    join.py
    provider_point.py

  providers/
    runtime.py
    picking.py
    editing.py
    panel_model.py

  ui/
    task_panel.py
    controls.py
    status.py
```

This is a target shape, not a required one-shot move.

## Migration Plan

### Phase 0: Stabilize Current Work

- Keep the current grouped `session.selection` and `session.overlays` direction.
- Do not start new broad wrapper refactors.
- Keep unrelated Arch Space and Plan Edit behavior changes separate from architecture commits.
- Restore or commit dirty work before starting structural changes that need clean validation.

Validation:

- `python -m py_compile` on touched modules
- focused Plan Edit GUI suites for touched workflows
- no mixed commits with unrelated room-boundary or model-core work

### Phase 1: Freeze Architecture Rules

- No new raw `session._foo` state.
- No new flat `session.selection.*` or `session.overlays.*` methods for owned code.
- No new generated forwarder lists.
- New tests patch owner services, not historical flat methods.
- Module-level entrypoints are allowed only as compatibility shims or pure helpers.

Validation:

- add review checklist entries or comments in the architecture plan
- reject new call sites that bypass grouped services
- run `python src/Mod/BIM/bimplan/devtools/cruft_report.py` and check:
  - `Flat session.selection Calls`
  - `Flat session.overlays Calls`
  - `Forwarder Surfaces`
  - `session._* Reads Outside Owners`
- run `python src/Mod/BIM/bimplan/devtools/cruft_report.py --check-grouped-api`
  before committing selection/overlay work
- run `python src/Mod/BIM/bimplan/devtools/cruft_report.py --max-forwarder-surfaces 0`
  while the current forwarder baseline is being retired
- run `python src/Mod/BIM/bimplan/devtools/cruft_report.py --check-no-private-session-reads`
  before committing architecture cleanup work

### Phase 2: Extract Picking As Its Own Subsystem

This is the highest-value next structural move because picking is both complex and performance-sensitive.

Current progress:

- `PlanSelectionPickingService` has been removed; picking is owned by `session.picking`.
- Selection no longer carries a second copy of click/edit-node/provider/space/region picking logic.
- Provider-overlay edit-node decoding, document-object resolution, and visible-target object-info helpers now live in `selection/provider_overlay_picking.py`.
- Target-specific picking logic is split into owner modules:
  - `selection/overlay_picking.py` for symbol/opening overlay hit testing.
  - `selection/area_picking.py` for space/region area picking.
  - `selection/edit_node_picking.py` for handle and edit-node picking.
  - `selection/provider_overlay_picking.py` for provider overlay picking.
- `session.picking` now exists as the owned Plan Edit picking service.
- Production interaction code now calls `session.picking`.
- Click target resolution and priority ordering now live in `bimplan/picking/coordinator.py`.
- `selection/picking.py` has been removed.
- The owned picking service now uses `session.picking.pick(...)`, `session.picking.hover(...)`, and `session.picking.pick_edit_node(...)` consistently.

Steps:

1. Introduce the owned `session.picking` service. Done.
2. Move selected-handle picking into an owned picker module. Done in `selection/edit_node_picking.py`.
3. Move provider overlay picking into an owned picker module. Done in `selection/provider_overlay_picking.py`.
4. Move opening and symbol picking into owned picker modules. Done in `selection/overlay_picking.py`.
5. Move region/space fallback picking into owned picker modules. Done in `selection/area_picking.py`.
6. Remove the old `selection/picking.py` shim and `session.selection.picking` adapter. Done.
7. Make `session.picking.pick(...)` the owned Plan Edit call path. Done.
8. Remove shim functions once internal call sites and low-level tests are migrated. Done.

Validation:

- `TestBimPlanCore` picking tests
- `TestBimPlanProviderSelectionGui`
- `TestBimPlanEditGuiOpenings`
- `TestBimPlanEditGuiSymbols`
- `TestBimPlanEditGuiSpaces`
- targeted wall click/hover test
- compare perf trace before/after for `get_plan_target_at_position`, hover picking, and provider overlay picking

### Phase 3: Reduce Document Visuals To A Coordinator

Current progress:

- Opening footprint refresh and host recompute helpers now live on `session.openings`.
- Opening and symbol visual dependency checks now live on their owner services.
- `document_visuals.py` routes opening, symbol, space/region, and secondary-selection document changes to owner services.
- Selected/hovered wall document-change handling now lives in `selection.refresh`.
- `document_visuals.py` still owns document observer attach/detach, deferral, flush ordering, and shared invalidation.

Steps:

1. List every branch in `document_visuals.py` by target kind. Done.
2. Move opening-specific refresh to the opening owner. Done.
3. Move symbol-specific refresh to symbol overlays. Done.
4. Move space/region-specific refresh to the space/region owner. Done.
5. Move secondary selection refresh to selection refresh service. Done.
6. Keep document observer attach/detach, deferral, and flush ordering in `document_visuals`. Done.

Validation:

- document visual invalidation tests
- opening GUI tests
- spaces GUI tests
- provider selection GUI tests
- targeted stale-overlay regressions

### Phase 4: Make Tools First-Class State Machines

Current progress:

- A minimal `PlanToolHandler` contract exists beside the current tool-id enum.
- `SelectTool` owns Select left-click, hover behavior, and edit-node activation.
- `JoinTool` owns Join mouse, hover, and key behavior.
- `WallEditTool` owns active wall edit Tab/Enter/Escape keyboard behavior.
- `OpeningMoveTool` owns opening move anchor/cancel keyboard behavior.
- `SymbolEditTool` owns symbol move/rotate cancel keyboard behavior.
- `RegionTool` owns region drawing finalize/cancel keyboard behavior.
- `SpaceTextTool` owns space text placement cancel keyboard behavior.
- `SpaceSeparatorTool` owns separator placement cancel keyboard behavior.
- `RectWallTool` owns rectangular wall placement cancel keyboard behavior.
- `WindowTool` owns hosted-window placement cancel keyboard behavior.
- `ProviderPointTool` owns provider point placement cancel keyboard behavior.
- `ProviderMoveTool` owns provider handle-move cancel keyboard behavior.
- `PickSpaceRegionTool` owns region-candidate mouse and Escape-key behavior.
- `runtime/input.py` owns raw Coin event normalization and table-based tool dispatch.

Steps:

1. Define a minimal `PlanTool` base contract. Done.
2. Convert select behavior first. Done.
3. Convert wall create/edit next. Done.
4. Convert opening/symbol/space/region workflows. Done.
5. Leave provider point tool last because it crosses provider runtime and UI. Done.
6. Shrink `runtime/input.py` to event dispatch. Done.

Validation:

- workflow-specific GUI suites
- undo/redo regressions for wall, opening, symbol, and space workflows
- manual smoke test in a real FreeCAD session

### Phase 5: Finish Typed State Migration

Current progress:

- Private selected-target compatibility aliases are removed for primary, pending, and secondary selection state.
- Tests that asserted pending selection now use `selection_state.pending_selected_plan_target`.
- Private lifecycle compatibility aliases are removed; lifecycle code uses `lifecycle_state`.
- Private task-panel compatibility aliases are removed; task-panel code uses `task_panel_state`.
- Private provider point compatibility aliases are removed; provider tests use `provider_point_state`.
- Private input-event compatibility aliases are removed; input tests use `input_event_state`.
- Private selection-sync compatibility aliases are removed; selection sync uses `selection_sync_state`.
- Private hover-pick compatibility aliases are removed; hover picking uses `hover_pick_state`.
- Private wall-grip runtime compatibility aliases are removed; wall grip sync uses `wall_grip_state`.
- Private plan-region tool compatibility aliases are removed; region creation uses `plan_region_tool_state`.
- Private performance trace compatibility aliases are removed; tracing uses `performance_state`.
- Private viewport compatibility aliases are removed; view setup and status chips use `viewport_state`.
- Private document-visual compatibility aliases are removed; visual update deferral uses `document_visual_state`.
- Unused private interaction compatibility aliases are removed; embedded host/name and space editing use `interaction_state`.
- Unused private region-pick edit-space compatibility alias is removed; region picking uses `space_region_pick_state`.
- Unused private provider render-state compatibility aliases are removed; provider overlays use `provider_transient_state`.
- Unused private opening-transient compatibility aliases are removed; opening overlays/editing use `opening_transient_state`.

Steps:

1. Audit remaining state-backed compatibility properties.
2. Remove aliases by ownership group.
3. Update tests to use typed state builders.
4. Keep temporary compatibility only for real external entrypoints.

Validation:

- `rg "session\\._"` review in `bimplan`
- `devtools/cruft_report.py`
- full Plan Edit headless runner where stable

### Phase 6: Provider Boundary Cleanup

Steps:

1. Keep provider runtime caching scoped by stable context.
2. Move provider picking logic out of selection/picking.
3. Move provider edit actions under provider editing service.
4. Document which provider hooks are public API.
5. Remove session-method fallback hooks that are only test leftovers.

Validation:

- provider GUI suite
- provider action context tests
- perf trace for provider-heavy files

## Refactoring Gate

Do not proceed with a refactor unless it satisfies at least one:

- deletes a compatibility layer
- shrinks a large module
- reduces public API surface
- removes duplicated logic
- improves measured performance
- makes a known bug class harder to reintroduce

If a change only moves functions to new names, do not do it.

## Testing Strategy

Use focused suites by ownership:

- selection and picking: `TestBimPlanCore`, provider selection GUI, targeted wall/opening/symbol/space tests
- overlays: workflow-specific GUI suites plus scenegraph regressions
- providers: provider GUI suite and provider context tests
- document visuals: stale visual and save/reload regressions
- tools: workflow GUI suites and undo/redo tests

Use perf traces for hot paths:

- hover movement
- wall selection
- opening/symbol picking
- provider overlay picking
- task-panel refresh

## Stop Conditions

The architecture is in good shape when:

- `PlanEditSession` mostly wires services.
- no internal owned code relies on flat compatibility APIs.
- picking is a separate subsystem with explicit priority rules.
- `document_visuals` coordinates invalidation and delegates target-specific behavior.
- state is typed and raw aliases are shrinking.
- task-panel refresh reasons are explicit.
- provider work is cached and out of ordinary hover/selection paths.
- the main Plan Edit workflow suites stay green.
- perf traces show no obvious provider or task-panel rebuilds on ordinary wall selection.
