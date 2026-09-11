# BIM Upstream Series Plan

This note records the recommended upstream split for the current `next` branch.
It reflects the cleaned history as of 2026-04-15 after the branch was restacked
to reduce reviewer load in the library and Plan Edit work.

The intended shape is four stacked PRs:

1. GUI/task watcher prerequisites
2. BIM Library semantic core and managed roots
3. BIM Library preview generation and browser polish
4. Plan Edit integration and footprint follow-up fixes

This file is a branch-local planning aid. It should not be treated as part of
the upstream feature series unless we explicitly decide to upstream it.

## Series 1

Suggested PR title:

`Gui/BIM: add contextual task watcher foundations`

Recommended range:

`f24c3754fa^..958f912601`

Recommended tip:

`958f912601`

Commits:

- `f24c3754fa` `Gui: refresh late display overrides for linked library assets`
- `37f6cda021` `Gui: add contextual task watcher panels`
- `958f912601` `BIM: define contextual task watcher sections`

Why this should stand alone:

- It is mostly generic GUI and workbench task-view plumbing.
- Later BIM Library and Plan Edit work reuse these hooks but do not define them.
- Splitting the old mixed watcher commit here removes the last broad GUI/BIM coupling at the start of the stack.

Suggested cover text:

This series adds the generic task-view and contextual watcher groundwork needed
by the later BIM Library and Plan Edit changes.

The main additions are:

- late display refresh hooks for linked library assets
- contextual task watcher panels and empty-state handling in the task view
- BIM workbench watcher section wiring on top of that generic GUI support

I would like this reviewed first because it is a small prerequisite and does not
require the semantic library model to be understood yet.

## Series 2

Suggested PR title:

`BIM: add semantic library assets and managed local roots`

Recommended range:

`4d20f5d905^..bfbd4f8664`

Recommended base:

`958f912601`

Recommended tip:

`bfbd4f8664`

Commits:

- `4d20f5d905` `BIM: add equipment plan symbol footprint support`
- `772b12d631` `BIM: add semantic asset handling to Library Browser`
- `002a1c27b8` `BIM: improve library browser loading and layout`
- `baed217f95` `BIM: improve library insert targeting and placement previews`
- `226fb188d8` `BIM: add plan contract helpers for equipment assets`
- `4572f0ba85` `BIM: normalize library equipment definitions`
- `ce362fc699` `BIM: add local library source resolver`
- `760e96f253` `BIM: support multiple managed local libraries`
- `bfbd4f8664` `BIM: add semantic asset providers for Library Browser`

Why this should be a separate core series:

- It establishes the semantic asset model used by the library browser.
- It teaches equipment objects and library definitions about authored plan symbols, anchors, and managed roots.
- It keeps the browser’s semantic and insertion behavior together without yet introducing preview-generation follow-ups.

Suggested cover text:

This series turns the BIM Library Browser into a semantic asset browser with
managed local roots and equipment-aware library definitions.

The main changes are:

- plan-symbol footprint support for equipment objects
- semantic asset loading in the BIM Library browser
- improved definition normalization and insertion targeting
- managed local library root discovery and multi-root support
- provider-based semantic asset routing for future asset kinds

This stack intentionally stops at the semantic/core browser boundary. It teaches
the library what assets are and how they should be inserted, but it does not yet
cover the preview-generation and UI polish follow-up work.

Reviewer note:

The original broad semantic library commit was split here into:

- equipment plan-symbol footprint support
- pure Library Browser semantic handling

That split removes the early cross-over between equipment display support and
the browser-side semantic loader.

## Series 3

Suggested PR title:

`BIM: add library previews and polish the browser UX`

Recommended range:

`34bbb7d522^..ea0cae3884`

Recommended base:

`bfbd4f8664`

Recommended tip:

`ea0cae3884`

Commits:

- `34bbb7d522` `BIM: add generated library preview fallbacks`
- `c81e74c63c` `BIM: add auto library preview mode`
- `57d297ceb2` `BIM: polish local library browser UX`
- `4d666c09b9` `BIM: simplify local library header provenance`
- `ea0cae3884` `BIM: stabilize headless GUI test runs`

Why this should be its own series:

- It is still library-focused, but it is no longer about asset semantics or root management.
- It is mostly preview generation, UX cleanup, and deterministic GUI coverage.
- Reviewers can evaluate browser behavior and test hardening separately from the semantic asset core.

Suggested cover text:

This series builds on the semantic library core by adding generated 2D/3D
preview fallbacks, automatic preview-mode selection, and the browser polish
needed to make multi-root local libraries usable day to day.

The user-visible changes are:

- generated previews for assets without authored thumbnails
- automatic 2D previews in Plan Edit and 3D previews otherwise
- cleaner browser layout and less noisy header provenance
- headless-stable GUI coverage for the new browser behavior

## Series 4

Suggested PR title:

`BIM Plan Edit: integrate semantic library assets and refresh footprint updates`

Recommended range:

`e66cf8ef2d^..1b7368c67d`

Recommended base:

`ea0cae3884`

Recommended tip:

`1b7368c67d`

Commits:

- `e66cf8ef2d` `BIM Plan Edit: use semantic library equipment symbols`
- `5b3b980c8a` `BIM Plan Edit: refresh semantic library footprint updates`
- `53bcd7a17a` `BIM Plan Edit: preserve input hint placeholders`
- `ccb618b74b` `BIM: harden area projection handling`
- `a4c027a17b` `Gui/BIM: refresh dynamic footprint display modes`
- `1b7368c67d` `BIM: fix footprint and Plan Edit GUI regressions`

Why this should be the final stacked PR:

- It depends on the semantic library model and browser preview behavior introduced earlier.
- It is the first series that moves the live Plan Edit session onto semantic library assets.
- It also contains the footprint refresh and regression fixes that were uncovered only once those semantic assets were exercised in the session.

Suggested cover text:

This series connects the semantic BIM Library asset model to the live Plan Edit
session. Library equipment definitions become usable semantic plan objects, and
the session refreshes their footprint and display state correctly during plan
editing.

The follow-up fixes here are not independent cleanup. They were required once
semantic library assets were driven through the live Plan Edit and footprint
paths, especially around dynamic display refresh and GUI regressions.

Reviewer note:

`a4c027a17b` stays in this series even though it touches `src/Gui/`, because it
is part of the footprint-refresh behavior exercised by the Plan Edit changes,
not a standalone BIM Library prerequisite.

## Suggested Branches

If you want explicit branch tips for stacked PRs:

```bash
git branch pr1-gui-taskwatchers 958f912601
git branch pr2-bim-library-core bfbd4f8664
git branch pr3-bim-library-preview ea0cae3884
git branch pr4-bim-plan-edit-library 1b7368c67d
```

If upstream wants even smaller fallback chunks, the most natural extra split
points are:

- after `4d20f5d905` to review equipment footprint support before the browser-side semantic loader
- after `760e96f253` to review managed local roots before the provider refactor
- after `c81e74c63c` to review preview generation separately from the later UX polish
