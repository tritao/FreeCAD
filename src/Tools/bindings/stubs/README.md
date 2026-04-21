# Python Stub Overlays

This directory contains manually curated `.pyi` overlays for Python APIs that
are registered outside the generated class-wrapper `.pyi` binding path.

Use the helper to regenerate discovery output and run the smoke checks:

```sh
src/Tools/bindings/stubs/check-stubs.sh
```

The helper runs the stub generator:

```sh
python3 src/Tools/bindings/generate_stubs.py --root . --out-dir src/Tools/bindings/stubs/generated
```

The implementation now lives under `src/Tools/bindings/stubs_tooling/`:
`model.py` for shared types and regexes, `parsing.py` for low-level source
parsing, `generator.py` for stub construction, and `cli.py` for argument
handling. `type_context_rules.py` holds the remaining manual PyCXX context
classifications that are not derivable yet.

That command writes:

- `stubs/`: import-shaped public stubs with overlays from this directory
  applied, plus mapped PyCXX type method tables where the runtime type can be
  tied to a public or private stub name. This tree is suitable for a
  type-checker search path and is the generated output committed in-tree.
- `debug/registration-stubs/`: flat permissive skeletons from C++
  registration tables for local generator inspection. These debug outputs are
  not committed.
- `debug/class-stubs/`: public class stubs derived from binding `.pyi` specs,
  with generator-only decorators stripped. This is also a flat debug view and
  is not committed.

Keep hand-written public module overlays under `inputs/overlays/`. Keep
generated PyCXX type signature inputs under `inputs/pycxx-overrides/`, using
public import names such as `inputs/pycxx-overrides/FreeCADGui/_View3DInventor.pyi`
for class methods and package-shaped module paths such as
`inputs/pycxx-overrides/modules/FreeCAD/Console.pyi` for module functions. Do
not edit generated output directly; use it as input for curated overlays or
source signature overrides.

Use package-shaped overlay paths that mirror the public import tree, such as
`inputs/overlays/Part/__init__.pyi` or `inputs/overlays/Part/Geom2d.pyi`.
Third-party packages such as Pivy should stay out of this tree until their
stubs are ready to be maintained or generated at the package source.

Public module overlays merge top-level symbols into generated modules instead of
replacing the whole file. Keep overlays focused on aliases, helper types, and
manual APIs that the generator still cannot model.

The helper also runs the smoke checks from this directory:

```sh
python3 src/Tools/bindings/generate_stubs.py check --root . --out-dir src/Tools/bindings/stubs/generated
```

## Recommended Direction

Prefer generated stubs for classes that already have binding `.pyi` specs.
Those files are close to the C++ wrapper source of truth and can be improved
without creating a second hand-written API surface.

When the same binding class is exported through multiple public module paths,
the merged public stubs keep one canonical class body and make the other
symbols re-export aliases. `FreeCAD.Base` is canonical for classes sourced from
`src/Base/`, which preserves type identity for APIs that use paths such as
`FreeCAD.Vector`, `FreeCAD.Base.Vector`, or `Part.Precision`.

Use `inputs/pycxx-overrides/` for PyCXX type method tables that the inventory
tool can map to a public class. These fragments are source inputs to the
generator, not the published stub tree. Use `@typing_only` on methods inside a
binding `.pyi` class when extra typing-only methods belong to that class and
should stay next to the binding source. Use class-body `if TYPE_CHECKING:`
blocks for typing-only attributes that should stay next to the binding source.
Use curated overlays for APIs that
still need hand-written public module stubs, including manual `PyMethodDef`,
Boost.Python, or pybind code that is not represented in the binding `.pyi`
generator model. Keep these files focused on public Python signatures. Avoid
moving raw generated skeletons into the tree without reviewing the signatures
against the implementation.

When a manual API is large or actively changing, prefer adding generator input
for it instead of growing a large overlay. When it is small, stable, or hard to
model in the generator, a maintained overlay is the lower-risk option.

### Typing-only Members

Prefer source-side typing additions when they naturally belong to an existing
binding class.

- Use `@typing_only` for methods.
- Use class-body `if TYPE_CHECKING:` blocks for attributes.

This split matches the current binding parser behavior:

- the legacy method parser still walks class-body `if` blocks, so
  `if TYPE_CHECKING:` is not enough to hide methods from binding generation
- the legacy attribute parser only consumes top-level class attributes, so
  attributes inside `if TYPE_CHECKING:` stay stub-only

The public stub generator flattens class-body `if TYPE_CHECKING:` attribute
blocks into ordinary class members in the emitted stubs, so the published stub
surface stays clean.

## Maintenance Notes

Use `generate_stubs.py` in scripts and documentation. Do not introduce another
entrypoint name for the same pipeline.

When a PyCXX type context still needs a manual rule, add it in
`stubs_tooling/type_context_rules.py`. Use an internal reason for helper types
that should not surface publicly, and use public targets only when the current
discovery path cannot map the context automatically.
