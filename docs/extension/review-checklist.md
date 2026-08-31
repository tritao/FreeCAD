# Architecture Review Checklist

**Status:** Guide

Use this checklist when reviewing the architecture or implementation changes.

## Public model

- Does the proposal describe a FreeCAD semantic concept rather than a runtime transport detail?
- Is the concept representable in `ExtensionApiModel` without WAMR/WASM knowledge?
- Are stable IDs independent of generated language naming?
- Are values and resources distinguished deliberately?

## Compatibility

- Is a breaking semantic change reflected in interface major versioning?
- Are FreeCAD version, interface version, SDK version, and backend ABI version kept separate?
- Does existing `import FreeCAD` code remain supported?

## SDKs

- Can the operation be expressed naturally in C++, Rust, and Python?
- Does the public facade avoid integer handles/opcodes/dispatch buffers?
- Are ownership and errors language-native?

## Execution

- Is the execution class (`serialized`, `ui`, or `concurrent`) clear?
- Are lifecycle and resource invalidation rules defined?
- Could the change introduce nested callback reentrancy?

## Events

- Is the event owned by an interface?
- Is it lossless or coalescible?
- Is its payload portable across runtimes?
- Does transaction timing expose coherent state?

## Security

- Does a new permission protect a meaningful trust boundary?
- Is it enforceable for the intended execution profile?
- Is the UI careful not to imply sandboxing for in-process Python?

## Packaging/Addons

- Is developer-authored metadata semantic rather than generated runtime data?
- Is information duplicated between `package.xml`, TOML, and language build files?
- Can AddonManager preflight compatibility without executing extension code?

## Providers

- Can consumers resolve the interface without linking/importing provider internals?
- Are provider types portable?
- Does provider unload invalidate resources and subscriptions safely?

## Complexity check

Before adding an abstraction, ask:

> Does this remove real duplication or prevent a real bug in the current-scale API?

If the benefit appears only at a hypothetical very large API, defer it.
