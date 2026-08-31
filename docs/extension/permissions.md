# Extension Permissions and Trust

**Status:** Normative

## Principle

Permissions protect meaningful authority boundaries. They do not mirror the API method tree.

A permission system is valuable for sandboxed extensions because memory isolation alone does not restrict what privileged host calls an extension may perform.

## Initial permission vocabulary

Recommended initial set:

```text
document.read
document.modify
filesystem.read
filesystem.write
network
process
ui
```

This list should stay small until a concrete security/use-case boundary requires another capability.

## What does not need a permission

Pure value computation should normally not require a capability simply because it is exposed through the Extension API.

Examples include vector/matrix operations and local computation. Queries over an already legitimately held value/resource also should not automatically require a new permission unless they expose protected information.

## Permission assignment

An Extension operation may declare the permission required to invoke it. The semantic model owns this relationship. Runtime-specific host tables should derive from the model where practical.

## Sandbox enforcement

For a sandboxed profile:

1. package metadata declares requested permissions;
2. AddonManager/loader determines the granted set;
3. the host validates each privileged operation;
4. the sandbox has no alternate unrestricted path to the protected capability.

## In-process Python

Granular host permissions do **not** make unrestricted in-process Python safe.

An in-process addon can potentially access Python filesystem, network, process, and other FreeCAD APIs directly.

The UI must distinguish:

```text
Sandboxed extension
  constrained to granted capabilities

In-process addon
  trusted code running with FreeCAD process authority
```

A package may still declare semantic capabilities for documentation/dependency purposes, but FreeCAD must not present them as complete isolation.

## User-facing wording

Users should see meaningful descriptions rather than raw strings.

```text
document.modify -> modify open FreeCAD documents
filesystem.write -> write files
```

An update that adds a significant capability should require renewed review for sandboxed extensions.

## Filesystem direction

Filesystem permissions should eventually pair with scoped APIs such as user-selected files, extension-private storage, project-relative storage, and explicit path grants.

The v1 capability vocabulary can remain coarse while APIs evolve toward scoped resources.

## Network and process

`network` and `process` are high-authority capabilities. A sandboxed runtime should not expose them merely because the source language normally has those facilities.

## UI permission

`ui` represents privileged FreeCAD UI services, not direct Qt object access. The exact user-consent policy may evolve.

## No per-method explosion

Avoid capabilities such as:

```text
document.object.label.read
document.object.label.write
geometry.shape.volume.read
document.transaction.open
```

The permission model should remain comprehensible to authors and users.
