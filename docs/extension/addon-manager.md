# AddonManager Integration

**Status:** Architecture / guide

## Principle

The Extension architecture should integrate with AddonManager instead of creating a second installer, catalog, or trust UI.

AddonManager manages both existing addons and new-style Extension packages.

## Package normalization

AddonManager should work with a common internal model:

```text
package.xml ----------------\
                             -> PackageMetadata
freecad-extension.toml -----/
catalog metadata -----------/
```

Likely normalized concepts include identity, display metadata, version, compatibility, Extension API requirement, required interfaces, execution profile, requested permissions, and available artifacts.

## Compatibility preflight

Before activation, AddonManager/loader should answer:

```text
Is the required Extension API available?
Are required interfaces installed?
Are required major versions available?
Is the execution backend supported?
Are requested permissions grantable?
Does this artifact match the platform/runtime?
```

This is preferable to discovering missing imports after code starts running.

## Execution-profile UX

### Sandboxed

```text
Runs in a restricted extension sandbox.
Requested access:
- modify FreeCAD documents
- use the network
```

### In-process Python

```text
Runs as trusted Python code inside FreeCAD and may access your system with FreeCAD's authority.
```

Do not show a small permission list for in-process code in a way that implies the rest of Python is blocked.

## Install artifacts

For compiled sandboxed extensions, AddonManager should prefer versioned release artifacts when the ecosystem supports them.

Source checkout can remain useful for development and legacy addons.

## State model

New-style extensions benefit from explicit states:

```text
installed
enabled
disabled
incompatible
missing-interface
permission-review-required
failed
```

These states should not depend on WASM.

## Updates

On update:

1. compare package identity/version;
2. re-check API/interface compatibility;
3. compare requested permissions;
4. require review when significant new sandbox capabilities are requested;
5. activate only after successful install/validation.

## Dependencies

Interface dependencies are more precise than language imports.

```toml
[requires]
interfaces = ["org.freecad.bim@1"]
```

AddonManager can resolve this to the installed provider rather than assuming a Python module layout.

## Catalog evolution

The catalog should become capable of describing execution profile, compatible artifacts, Extension API/interface requirements, and package metadata source.

It does not need awareness of opcodes, WAMR configuration, or raw SDK internals.

## Migration strategy

1. parse/display `freecad-extension.toml`;
2. normalize metadata;
3. show execution-profile trust information;
4. preflight API/interface requirements;
5. install sandboxed release artifacts;
6. manage permission deltas;
7. resolve third-party provided-interface dependencies later.
