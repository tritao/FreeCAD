# Unified BIM stack redesign context

This directory is a snapshot of local, state-bound devstack metadata supplied for architectural analysis. It is not live project configuration and must not be merged into FreeCAD source history.

The code and commit history are inherited from `unified-bim-plan-stack`. Treat `devstack/stack.conf` as the authoritative snapshot of the current 70-layer configuration. Treat `UNIFIED_BIM_PLAN_STACK.md` and older narratives as historical material: the dossier still describes an obsolete 36-layer generation in places.

The configured stack ends at commit `80042b99736`; the integration branch continues to committed tip `97ced34fea0`, leaving 50 commits outside the configured layers. Layer 64 spans 201 commits. Seven drawing-sheet layers (064 through 070) have no individual PR-body files in the state snapshot.

The source worktree also had 19 uncommitted files when this snapshot was created. Those files are not present in this branch.

This branch is analysis-only. Do not publish its devstack layers or use it as a merge candidate.
