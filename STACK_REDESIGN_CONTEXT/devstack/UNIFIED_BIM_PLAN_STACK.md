# Unified BIM / Plan Edit perfect-history stack

This dossier contains the publication configuration and every layer's review narrative.

## Stack configuration

```text
# Unified BIM / Plan Edit perfect-history stack.
# Each cut point is a coherent review unit; the Draft interaction layer contains
# its intentionally incremental internal commits.

base upstream/main

github_mode chained

pr_prefix pr/unified-bim-plan-perfect/

body_dir .devstack/pr-bodies/unified-bim-plan-perfect

group generic-foundations Generic FreeCAD foundations
group_body .devstack/group-bodies/unified-bim-plan-perfect/generic-foundations.md
001-ci-output-robustness 4f66ad96980
002-camera-animation 570d870e9c5
003-task-dialog-documents 45fe63ab438
004-coin-sensor-activation a7ba98fe391
005-scene-node-ownership 7371210804b
006-view-provider-back-root b67a832f6b3

group contextual-views Contextual view infrastructure
group_body .devstack/group-bodies/unified-bim-plan-perfect/contextual-views.md
007-view-context 53ac2645310
008-saved-view-definition 554c597e577
009-camera-capture b87e05ece2d
010-contextual-clipping cfdf14b1a9c
011-workbench-context-policy 9a0ffc9fa87
012-viewer-session-appearance 529195150f1
013-dynamic-display-modes c373e674e4f
014-contextual-task-view 3fd74ed9233
015-viewer-representation-instances df493a0e0a8

group interaction-prerequisites Interaction prerequisites
group_body .devstack/group-bodies/unified-bim-plan-perfect/interaction-prerequisites.md
016-draft-interaction-hosts 38663ecff64
017-qrc-dependencies 8ea188421c7

group semantic-bim-foundations Semantic BIM foundations
group_body .devstack/group-bodies/unified-bim-plan-perfect/semantic-bim-foundations.md
018-bim-representation-contract 432630c0ad6
019-plan-footprint-support 8b2a98f57f3
020-footprint-providers 872cad97e5c
021-wall-relations 981c45477f1

group plan-edit-workflows Plan Edit workflows
group_body .devstack/group-bodies/unified-bim-plan-perfect/plan-edit-workflows.md
022-plan-edit-session 14d12cd9394
023-library-semantics d028d7d36fd
024-library-sources 76de4d948ff
025-library-previews 1e3dcd6d740
026-contextual-task-sections 79fa1c3d26c
027-plan-library-integration e626340baf7
028-spaces-regions ac436f1fbc3
029-provider-workflows c5ae7907f35

group semantic-interaction-editing Semantic interaction and contextual editing
group_body .devstack/group-bodies/unified-bim-plan-perfect/semantic-interaction-editing.md
030-semantic-interaction e96e08461fc
031-contextual-editing c481b752de8
032-path-editing cbf461e1571
033-wall-opening-editing 84a12594bbc
034-arbitrary-plane 46df2a0ad02

group consumers-examples Consumers and examples
group_body .devstack/group-bodies/unified-bim-plan-perfect/consumers-examples.md
035-techdraw-consumer 14df7979446
036-examples c88f9296576
```

## 001-ci-output-robustness

---
title: "CI: make GUI test output robust to invalid UTF-8"
---

## Summary

Makes GUI test capture tolerate invalid UTF-8 without losing the surrounding diagnostics.

## Why

Reliable diagnostics are a prerequisite for validating GUI-heavy layers.

## Architectural invariant

Makes GUI test capture tolerate invalid UTF-8 without losing the surrounding diagnostics.

## Changes

Touches 1 files across .github.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `.github/scripts/run_gui_tests.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `1/36` of a stacked series. Depends on `main`; review and merge in order.

- Group: `generic-foundations` — Generic FreeCAD foundations (`1/6`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 002-camera-animation

---
title: "Gui: expose camera animation completion"
---

## Summary

Exposes camera-animation completion through the viewer and Python APIs.

## Why

Plan Edit can wait for a completed top-view transition before locking its camera.

## Architectural invariant

Exposes camera-animation completion through the viewer and Python APIs.

## Changes

Touches 9 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `2/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/001-ci-output-robustness`; review and merge in order.

- Group: `generic-foundations` — Generic FreeCAD foundations (`2/6`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/002-camera-animation","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 003-task-dialog-documents

---
title: "Gui: bind task dialogs explicitly to documents"
---

## Summary

Associates task dialogs explicitly with their owning document.

## Why

Viewer-local sessions must not infer document ownership from whichever tab happens to be active.

## Architectural invariant

Associates task dialogs explicitly with their owning document.

## Changes

Touches 164 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `3/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/002-camera-animation`; review and merge in order.

- Group: `generic-foundations` — Generic FreeCAD foundations (`3/6`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 004-coin-sensor-activation

---
title: "Gui: preserve Coin realtime sensor state across activation"
---

## Summary

Preserves Coin realtime-sensor state across window activation changes.

## Why

Transient GUI activation must not corrupt global Coin scheduling state.

## Architectural invariant

Preserves Coin realtime-sensor state across window activation changes.

## Changes

Touches 1 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `4/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/003-task-dialog-documents`; review and merge in order.

- Group: `generic-foundations` — Generic FreeCAD foundations (`4/6`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 005-scene-node-ownership

---
title: "Gui/Draft: remove transient scene nodes through their owner"
---

## Summary

Removes transient scene nodes through their actual owner and makes teardown idempotent.

## Why

Contextual overlays and Draft trackers require safe cleanup during restore and shutdown.

## Architectural invariant

Removes transient scene nodes through their actual owner and makes teardown idempotent.

## Changes

Touches 6 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/Draft/drafttests/test_dimension_gui.py`
- `src/Mod/Draft/drafttests/test_lines_gui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `5/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/004-coin-sensor-activation`; review and merge in order.

- Group: `generic-foundations` — Generic FreeCAD foundations (`5/6`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 006-view-provider-back-root

---
title: "Gui: attach child view providers to their back root"
---

## Summary

Attaches child view providers to the correct back-root scene branch.

## Why

Viewer-context gates depend on correct scene-graph ownership.

## Architectural invariant

Attaches child view providers to the correct back-root scene branch.

## Changes

Touches 1 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `6/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/005-scene-node-ownership`; review and merge in order.

- Group: `generic-foundations` — Generic FreeCAD foundations (`6/6`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 007-view-context

---
title: "Gui: add viewer-local presentation contexts"
---

## Summary

Adds ordered, viewer-local presentation layers with Visible, Hidden, and Inherit resolution.

## Why

Multiple viewers need independent transient state without changing document visibility.

## Architectural invariant

Adds ordered, viewer-local presentation layers with Visible, Hidden, and Inherit resolution.

## Changes

Touches 19 files across src, tests.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `tests/src/Gui/CMakeLists.txt`
- `tests/src/Gui/ViewContext.cpp`
- `tests/src/Gui/ViewProviderDocumentObject.cpp`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `7/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/006-view-provider-back-root`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`1/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/007-view-context","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 008-saved-view-definition

---
title: "App/Gui: persist domain-neutral saved view definitions"
---

## Summary

Adds a domain-neutral persistent view definition with structural object links and reference frames.

## Why

Persistent views should capture generic document state while BIM semantics remain outside App.

## Architectural invariant

Adds a domain-neutral persistent view definition with structural object links and reference frames.

## Changes

Touches 10 files across src, tests.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `tests/src/Gui/ViewProviderDocumentObject.cpp`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `8/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/007-view-context`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`2/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 009-camera-capture

---
title: "App/Gui: add versioned camera capture and apply"
---

## Summary

Adds validated codec/version/payload camera capture and apply.

## Why

Opaque viewer serialization needs an explicit stable contract before it can be persisted.

## Architectural invariant

Adds validated codec/version/payload camera capture and apply.

## Changes

Touches 9 files across src, tests.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `tests/src/Gui/CMakeLists.txt`
- `tests/src/Gui/CoinCameraCodec.cpp`
- `tests/src/Gui/ViewProviderDocumentObject.cpp`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `9/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/008-saved-view-definition`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`3/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/009-camera-capture","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 010-contextual-clipping

---
title: "App/Gui: add persistent contextual clipping"
---

## Summary

Persists renderer-neutral clipping planes and realizes them per viewer.

## Why

Saved clipping belongs to the document while activation remains viewer-local.

## Architectural invariant

Persists renderer-neutral clipping planes and realizes them per viewer.

## Changes

Touches 13 files across src, tests.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `tests/src/Gui/ViewContext.cpp`
- `tests/src/Gui/ViewProviderDocumentObject.cpp`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `10/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/009-camera-capture`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`4/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 011-workbench-context-policy

---
title: "Gui: make workbench context policy explicit"
---

## Summary

Makes Global, Document, and View workbench policies explicit while preserving the historic Document default.

## Why

Plan sessions need predictable workbench ownership without an incidental product-default change.

## Architectural invariant

Makes Global, Document, and View workbench policies explicit while preserving the historic Document default.

## Changes

Touches 7 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `11/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/010-contextual-clipping`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`5/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 012-viewer-session-appearance

---
title: "Gui: expose per-view session appearance controls"
---

## Summary

Adds reversible per-view background and NaviCube overrides.

## Why

Plan Edit must not mutate global appearance preferences.

## Architectural invariant

Adds reversible per-view background and NaviCube overrides.

## Changes

Touches 7 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `12/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/011-workbench-context-policy`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`6/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 013-dynamic-display-modes

---
title: "Gui: support dynamic display mode refresh and overrides"
---

## Summary

Refreshes dynamic display modes and reapplies late viewer overrides safely.

## Why

Footprints and library assets can appear after restore or provider changes.

## Architectural invariant

Refreshes dynamic display modes and reapplies late viewer overrides safely.

## Changes

Touches 8 files across src, tests.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `tests/src/Gui/ViewProviderDocumentObject.cpp`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `13/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/012-viewer-session-appearance`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`7/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 014-contextual-task-view

---
title: "Gui: add contextual TaskView action panels"
---

## Summary

Adds generic contextual TaskView action panels and empty-state handling.

## Why

Selection-driven BIM actions need a reusable GUI host rather than BIM-specific TaskView plumbing.

## Architectural invariant

Adds generic contextual TaskView action panels and empty-state handling.

## Changes

Touches 3 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `14/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/013-dynamic-display-modes`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`8/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 015-viewer-representation-instances

---
title: "Gui: add viewer-local representation instances"
---

## Summary

Adds transient viewer-owned representation branches behind ViewContext gates.

## Why

Derived geometry must be local to a viewer and must retain semantic source identity.

## Architectural invariant

Adds transient viewer-owned representation branches behind ViewContext gates.

## Changes

Touches 4 files across src, tests.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `tests/src/Gui/ViewProviderDocumentObject.cpp`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `15/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/014-contextual-task-view`; review and merge in order.

- Group: `contextual-views` — Contextual view infrastructure (`9/9`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 016-draft-interaction-hosts

---
title: "Draft: let legacy tools use interaction hosts"
---

## Summary

Builds a reusable Draft interaction host with cancellation, temporary snap profiles, working planes, point customization, hints, and legacy-tool adoption.

## Why

Plan Edit should consume Draft interaction mechanics without surrendering session ownership.

## Architectural invariant

Builds a reusable Draft interaction host with cancellation, temporary snap profiles, working planes, point customization, hints, and legacy-tool adoption.

## Changes

Touches 10 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/Draft/TestDraftGui.py`
- `src/Mod/Draft/drafttests/test_gui_snapper.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `16/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/015-viewer-representation-instances`; review and merge in order.

- Group: `interaction-prerequisites` — Interaction prerequisites (`1/2`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 017-qrc-dependencies

---
title: "Build: track Qt resource dependencies"
---

## Summary

Tracks Qt resource inputs in the build graph.

## Why

Generated resources used by the following BIM layers must rebuild when their sources change.

## Architectural invariant

Tracks Qt resource inputs in the build graph.

## Changes

Touches 2 files across cMake, src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- Verified by the focused downstream contract tests and per-cut-point build gate.

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `17/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/016-draft-interaction-hosts`; review and merge in order.

- Group: `interaction-prerequisites` — Interaction prerequisites (`2/2`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 018-bim-representation-contract

---
title: "BIM: establish canonical semantic representation contract"
---

## Summary

Defines the single canonical renderer-neutral BIM representation, mapping, and provider-dispatch contract.

## Why

BIM semantics must precede every Plan, Section, viewer, and TechDraw consumer.

## Architectural invariant

Defines the single canonical renderer-neutral BIM representation, mapping, and provider-dispatch contract.

## Changes

Touches 4 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArch.py`
- `src/Mod/BIM/bimtests/TestArchRepresentation.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `18/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/017-qrc-dependencies`; review and merge in order.

- Group: `semantic-bim-foundations` — Semantic BIM foundations (`1/4`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 019-plan-footprint-support

---
title: "BIM: add generic plan footprint support"
---

## Summary

Adds generic plan cut contexts, footprint caching, and the Footprint display mode.

## Why

Object providers need one shared plan-representation foundation.

## Architectural invariant

Adds generic plan cut contexts, footprint caching, and the Footprint display mode.

## Changes

Touches 8 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestArchBuildingPart.py`
- `src/Mod/BIM/bimtests/TestArchComponent.py`
- `src/Mod/BIM/bimtests/TestArchPlanGeometry.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `19/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/018-bim-representation-contract`; review and merge in order.

- Group: `semantic-bim-foundations` — Semantic BIM foundations (`2/4`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 020-footprint-providers

---
title: "BIM: add footprint representation providers"
---

## Summary

Implements contextual footprint providers for BIM object families.

## Why

Object-specific representation policy belongs to semantic providers, not a central type dispatcher.

## Architectural invariant

Implements contextual footprint providers for BIM object families.

## Changes

Touches 10 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestArchEquipment.py`
- `src/Mod/BIM/bimtests/TestArchFootprintGui.py`
- `src/Mod/BIM/bimtests/TestArchStructure.py`
- `src/Mod/BIM/bimtests/TestArchStructureGui.py`
- `src/Mod/BIM/bimtests/TestArchWall.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `20/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/019-plan-footprint-support`; review and merge in order.

- Group: `semantic-bim-foundations` — Semantic BIM foundations (`3/4`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/020-footprint-providers","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 021-wall-relations

---
title: "BIM: establish wall relation semantics"
---

## Summary

Adds wall endpoints, joints, junctions, solvers, commands, tests, and the BIMWallJoins fixture.

## Why

Contextual wall editing requires stable semantic relation ownership first.

## Architectural invariant

Adds wall endpoints, joints, junctions, solvers, commands, tests, and the BIMWallJoins fixture.

## Changes

Touches 38 files across data, src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArch.py`
- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestArchWall.py`
- `src/Mod/BIM/bimtests/TestArchWallGeometry.py`
- `src/Mod/BIM/bimtests/TestArchWallGui.py`
- `src/Mod/BIM/bimtests/TestArchWallJoinMatrix.py`
- `src/Mod/BIM/bimtests/TestArchWallJoint.py`
- `src/Mod/BIM/bimtests/TestArchWallJunction.py`
- `src/Mod/BIM/bimtests/TestArchWallJunctionMatrix.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `21/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/020-footprint-providers`; review and merge in order.

- Group: `semantic-bim-foundations` — Semantic BIM foundations (`4/4`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/021-wall-relations","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 022-plan-edit-session

---
title: "BIM: add the Plan Edit session workflow"
---

## Summary

Introduces the reversible Plan Edit session, storey selection, camera transition, command gate, appearance, visibility, and task panel lifecycle.

## Why

The workflow should consume the generic foundations in their final form from its first commit.

## Architectural invariant

Introduces the reversible Plan Edit session, storey selection, camera transition, command gate, appearance, visibility, and task panel lifecycle.

## Changes

Touches 12 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestBimPlanEditSessionGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `22/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/021-wall-relations`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`1/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 023-library-semantics

---
title: "BIM: add semantic library asset model"
---

## Summary

Defines semantic library assets independently from browser and Plan Edit UI.

## Why

Asset identity and classification must remain reusable outside one presentation.

## Architectural invariant

Defines semantic library assets independently from browser and Plan Edit UI.

## Changes

Touches 6 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArch.py`
- `src/Mod/BIM/bimtests/TestArchEquipment.py`
- `src/Mod/BIM/bimtests/TestBimAssetSemantics.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `23/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/022-plan-edit-session`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`2/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/023-library-semantics","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 024-library-sources

---
title: "BIM: add managed local library sources"
---

## Summary

Adds ordered, enabled managed local library roots.

## Why

Asset discovery needs a persistent source model before browser presentation.

## Architectural invariant

Adds ordered, enabled managed local library roots.

## Changes

Touches 4 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArch.py`
- `src/Mod/BIM/bimtests/TestBimLibrarySources.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `24/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/023-library-semantics`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`3/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/024-library-sources","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 025-library-previews

---
title: "BIM: add generated library previews and browser UX"
---

## Summary

Adds cached generated 2D/3D previews and multi-root browser behavior.

## Why

Users need scalable visual discovery without embedding Plan Edit semantics in the browser.

## Architectural invariant

Adds cached generated 2D/3D previews and multi-root browser behavior.

## Changes

Touches 5 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestBimLibraryBrowserGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `25/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/024-library-sources`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`4/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/025-library-previews","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 026-contextual-task-sections

---
title: "BIM: define contextual task watcher sections"
---

## Summary

Lets TaskView watchers contribute selection-dependent sections.

## Why

Plan and library actions should compose through generic contextual UI.

## Architectural invariant

Lets TaskView watchers contribute selection-dependent sections.

## Changes

Touches 4 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestBimTaskWatcherGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `26/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/025-library-previews`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`5/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 027-plan-library-integration

---
title: "BIM Plan Edit: select semantic library preview by context"
---

## Summary

Selects semantic library preview modes from the active Plan Edit context.

## Why

The Plan consumer should configure, not redefine, the asset and preview systems.

## Architectural invariant

Selects semantic library preview modes from the active Plan Edit context.

## Changes

Touches 4 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestBimPlanEditLibraryGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `27/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/026-contextual-task-sections`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`6/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 028-spaces-regions

---
title: "BIM: add spaces and regions to Plan Edit"
---

## Summary

Adds Space Separators, Plan Regions, and their contextual Plan Edit behavior.

## Why

Spaces and regions are first-class BIM semantics over the same plan context.

## Architectural invariant

Adds Space Separators, Plan Regions, and their contextual Plan Edit behavior.

## Changes

Touches 12 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/TestArchGui.py`
- `src/Mod/BIM/bimtests/TestArchFootprintGui.py`
- `src/Mod/BIM/bimtests/TestArchSpace.py`
- `src/Mod/BIM/bimtests/TestArchSpaceGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `28/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/027-plan-library-integration`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`7/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/028-spaces-regions","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 029-provider-workflows

---
title: "BIM: establish provider-owned Plan Edit workflows"
---

## Summary

Establishes provider-owned actions, points, picking, overlays, rendering, and orchestration.

## Why

Object-specific behavior belongs with providers while the session coordinates capabilities.

## Architectural invariant

Establishes provider-owned actions, points, picking, overlays, rendering, and orchestration.

## Changes

Touches 92 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestBimPlanEditSessionGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `29/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/028-spaces-regions`; review and merge in order.

- Group: `plan-edit-workflows` — Plan Edit workflows (`8/8`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/029-provider-workflows","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 030-semantic-interaction

---
title: "BIM: add semantic representation interaction"
---

## Summary

Extends the canonical representation with semantic snap, pick, handle, and operation types.

## Why

Interaction must resolve to BIM identity rather than transient Coin geometry.

## Architectural invariant

Extends the canonical representation with semantic snap, pick, handle, and operation types.

## Changes

Touches 10 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestArchRepresentation.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `30/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/029-provider-workflows`; review and merge in order.

- Group: `semantic-interaction-editing` — Semantic interaction and contextual editing (`1/5`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 031-contextual-editing

---
title: "BIM: add the contextual editing framework"
---

## Summary

Adds begin, preview, validate, commit, cancel, transaction, and refresh semantics.

## Why

All contextual tools need one robust editing lifecycle.

## Architectural invariant

Adds begin, preview, validate, commit, cancel, transaction, and refresh semantics.

## Changes

Touches 12 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestArchRepresentation.py`
- `src/Mod/BIM/bimtests/TestBimPlanEditSessionGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `31/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/030-semantic-interaction`; review and merge in order.

- Group: `semantic-interaction-editing` — Semantic interaction and contextual editing (`2/5`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/031-contextual-editing","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 032-path-editing

---
title: "BIM: add contextual path editing"
---

## Summary

Adds native, Draft, and Sketcher path ownership and typed path edits.

## Why

Path manipulation must edit the semantic owner and preserve constraints and joins.

## Architectural invariant

Adds native, Draft, and Sketcher path ownership and typed path edits.

## Changes

Touches 6 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestArchRepresentation.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `32/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/031-contextual-editing`; review and merge in order.

- Group: `semantic-interaction-editing` — Semantic interaction and contextual editing (`3/5`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/032-path-editing","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 033-wall-opening-editing

---
title: "BIM: add contextual wall and opening editing"
---

## Summary

Adds relation-aware wall and hosted-opening edits with guarded previews and rollback.

## Why

The main architectural objects should be editable through the active context without converted copies.

## Architectural invariant

Adds relation-aware wall and hosted-opening edits with guarded previews and rollback.

## Changes

Touches 7 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestArchFootprintGui.py`
- `src/Mod/BIM/bimtests/TestArchRepresentation.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `33/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/032-path-editing`; review and merge in order.

- Group: `semantic-interaction-editing` — Semantic interaction and contextual editing (`4/5`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 034-arbitrary-plane

---
title: "BIM: add arbitrary-plane representation contexts"
---

## Summary

Generalizes representation projection, slicing, snapping, and handles to arbitrary reference frames.

## Why

Plan, Section, and Elevation must be contexts over one representation mechanism.

## Architectural invariant

Generalizes representation projection, slicing, snapping, and handles to arbitrary reference frames.

## Changes

Touches 5 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestArchRepresentation.py`
- `src/Mod/BIM/bimtests/TestArchSectionPlane.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `34/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/033-wall-opening-editing`; review and merge in order.

- Group: `semantic-interaction-editing` — Semantic interaction and contextual editing (`5/5`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 035-techdraw-consumer

---
title: "TechDraw: consume semantic BIM representations"
---

## Summary

Routes supported SectionPlane output through semantic BIM representations with explicit all-or-nothing legacy fallback.

## Why

Interactive views and documentation should consume the same provider geometry.

## Architectural invariant

Routes supported SectionPlane output through semantic BIM representations with explicit all-or-nothing legacy fallback.

## Changes

Touches 4 files across src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestArchSectionPlane.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `35/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/034-arbitrary-plane`; review and merge in order.

- Group: `consumers-examples` — Consumers and examples (`1/2`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->

## 036-examples

---
title: "BIM: add Plan Edit examples and end-to-end fixtures"
---

## Summary

Adds generated Basic and Path Ownership documents plus executable end-to-end GUI tests.

## Why

The final layer should demonstrate only stable APIs and validate installed fixtures.

## Architectural invariant

Adds generated Basic and Path Ownership documents plus executable end-to-end GUI tests.

## Changes

Touches 7 files across data, src.

## Compatibility

No temporary same-stack compatibility contract is introduced.

## Tests

- `src/Mod/BIM/bimtests/TestBimPlanEditExamplesGui.py`

## Intentionally deferred

Capabilities owned by later stack layers remain deferred to those layers.

<!-- AUTOGEN:BEGIN -->
### Patch Set

> [!IMPORTANT]
> Part `36/36` of a stacked series. Depends on `pr/unified-bim-plan-perfect/035-techdraw-consumer`; review and merge in order.

- Group: `consumers-examples` — Consumers and examples (`2/2`)

<!-- DEVSTACK:REVIEWSTACK {"version":2,"current_branch":"pr/unified-bim-plan-perfect/036-examples","stack":[{"branch":"pr/unified-bim-plan-perfect/036-examples","commits":["c88f9296576bd201b5c642668aa1e18629867f1f"]},{"branch":"pr/unified-bim-plan-perfect/035-techdraw-consumer","commits":["14df797944670b98a6696861a73cd451b2e92ce3"]},{"branch":"pr/unified-bim-plan-perfect/034-arbitrary-plane","commits":["46df2a0ad0221f10cfb73ed6724642170135f5d5"]},{"branch":"pr/unified-bim-plan-perfect/033-wall-opening-editing","commits":["84a12594bbc896e343862b426a5504bf438d0763"]},{"branch":"pr/unified-bim-plan-perfect/032-path-editing","commits":["cbf461e1571b593ba4e98e6ea25605b8ac19800d"]},{"branch":"pr/unified-bim-plan-perfect/031-contextual-editing","commits":["c481b752de817b33b8540329d3eb92d4514d026c"]},{"branch":"pr/unified-bim-plan-perfect/030-semantic-interaction","commits":["e96e08461fcf931e5e472cd4ed8d28a39dda6043"]},{"branch":"pr/unified-bim-plan-perfect/029-provider-workflows","commits":["c5ae7907f358fa60f9d8f977de2b0b162256ee99"]},{"branch":"pr/unified-bim-plan-perfect/028-spaces-regions","commits":["ac436f1fbc3f6fe2b9eb4b601904d0ca992658ab"]},{"branch":"pr/unified-bim-plan-perfect/027-plan-library-integration","commits":["e626340baf721f6fcf3d10c81ad9e64a0fcd8a8b"]},{"branch":"pr/unified-bim-plan-perfect/026-contextual-task-sections","commits":["79fa1c3d26ce72e7306ffb5cc5b4bcf44ea44d46"]},{"branch":"pr/unified-bim-plan-perfect/025-library-previews","commits":["1e3dcd6d74090f8004f960caa4a07599d05af574"]},{"branch":"pr/unified-bim-plan-perfect/024-library-sources","commits":["76de4d948ff9377b278a73056c386468bdb4d1ac"]},{"branch":"pr/unified-bim-plan-perfect/023-library-semantics","commits":["d028d7d36fd5e6884c84f2012636a2b90840c5fd"]},{"branch":"pr/unified-bim-plan-perfect/022-plan-edit-session","commits":["14d12cd939462afd006c95154e4deeb74764e82a"]},{"branch":"pr/unified-bim-plan-perfect/021-wall-relations","commits":["981c45477f1826d5f451b4b0bc92b31281d8b8cd"]},{"branch":"pr/unified-bim-plan-perfect/020-footprint-providers","commits":["872cad97e5cf3998cf392aeb386b8003a871a50c"]},{"branch":"pr/unified-bim-plan-perfect/019-plan-footprint-support","commits":["8b2a98f57f3afd29d826aeca9d2113640b93d008"]},{"branch":"pr/unified-bim-plan-perfect/018-bim-representation-contract","commits":["432630c0ad6a07bdfa2dd044ab484e7b8d837c4d"]},{"branch":"pr/unified-bim-plan-perfect/017-qrc-dependencies","commits":["8ea188421c7fe896a9556fd804f5cc7855478c68"]},{"branch":"pr/unified-bim-plan-perfect/016-draft-interaction-hosts","commits":["c9f97cf4d2abd1cf1545250998c8028dee531447","3e462dcd13d8ebf86dc95dea413e1f75a9c68f5f","7991845f3440feca195ed25c52187b4b6f3ba2f5","cd083b6601031ec6acafa6f473ffb8b0faa19bad","d402f58243db28c75b6f415f8b4e4a578d47fb74","20b64a1310ddb0ea705a83a3a923299909c377c6","1cd6fdfdd59c59b48b34e90f49a52916a40eaf1b","38663ecff649b6ed63232ec2edcd4478667854ea"]},{"branch":"pr/unified-bim-plan-perfect/015-viewer-representation-instances","commits":["df493a0e0a82d3ecab1528b42c81c4ded3dbeb00"]},{"branch":"pr/unified-bim-plan-perfect/014-contextual-task-view","commits":["3fd74ed92337209fec55c6a39c2d5b863abaccde"]},{"branch":"pr/unified-bim-plan-perfect/013-dynamic-display-modes","commits":["c373e674e4f9c148f0ba3ba2f6b1b1d48fde7ebf"]},{"branch":"pr/unified-bim-plan-perfect/012-viewer-session-appearance","commits":["529195150f1df4e05a5e32ef0cdb39fe8d49f041"]},{"branch":"pr/unified-bim-plan-perfect/011-workbench-context-policy","commits":["9a0ffc9fa87a16b051c25f3a67cb2dc3d6a066d6"]},{"branch":"pr/unified-bim-plan-perfect/010-contextual-clipping","commits":["cfdf14b1a9cbabefd5b16d9669e6735bb9ca0950"]},{"branch":"pr/unified-bim-plan-perfect/009-camera-capture","commits":["b87e05ece2d9cdc3977def6692f7d3fd403be1b0"]},{"branch":"pr/unified-bim-plan-perfect/008-saved-view-definition","commits":["554c597e577414804a72da1cb7c7de2d997f0d87"]},{"branch":"pr/unified-bim-plan-perfect/007-view-context","commits":["53ac2645310f7b3f9d759a031562e6f80afb94dc"]},{"branch":"pr/unified-bim-plan-perfect/006-view-provider-back-root","commits":["b67a832f6b3ba4ebb79c1e5f4ae2aac219c313ea"]},{"branch":"pr/unified-bim-plan-perfect/005-scene-node-ownership","commits":["7371210804b36df12557ab74c27a17066eb4c319"]},{"branch":"pr/unified-bim-plan-perfect/004-coin-sensor-activation","commits":["a7ba98fe391ccd947997132cdc5c4cb950ec0ef5"]},{"branch":"pr/unified-bim-plan-perfect/003-task-dialog-documents","commits":["45fe63ab4382cd82fd918b47b3abcc419ef5949b"]},{"branch":"pr/unified-bim-plan-perfect/002-camera-animation","commits":["570d870e9c517d7a5d4140f7d9feefe35db040bb"]},{"branch":"pr/unified-bim-plan-perfect/001-ci-output-robustness","commits":["4f66ad96980065709cbd47079bc954ee31adc268"]}]} -->

<!-- AUTOGEN:END -->
