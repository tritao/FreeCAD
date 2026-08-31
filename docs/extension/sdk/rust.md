# Rust Extension SDK Guide

**Status:** Guide

## Package

Recommended package:

```text
freecad-extension-sdk
```

The exact imported crate alias can be finalized before release; normal public naming should avoid `wasm`.

## Target experience

```rust
fn run(fc: &freecad::Context) -> Result<(), freecad::Error> {
    let doc = fc.documents().active()?;
    let shape = fc.part().make_box(10.0, 20.0, 30.0)?;

    let mut tx = doc.transaction("Create box")?;
    let object = doc.add_object(shape, "Box")?;
    object.set_label("Bracket")?;
    tx.commit()?;
    Ok(())
}
```

## Errors

Use `Result<T, Error>`. Semantic host failures and runtime/transport failures may have distinct variants under one SDK error type.

## Resources

Use typed resource wrappers. Do not expose public `u64` handles.

Owned cleanup can use `Drop` where best-effort release is safe, with explicit `close()` where meaningful release failure must be observable.

## `no_std`

The current backend can support lightweight `#![no_std]` guests. Keep a minimal core layer usable there, with optional convenience features behind crate features if required.

## Generated code

A published/installed crate is preferable to asking applications to `include!` generated files manually.

## Raw access

If needed, advanced transport APIs can live under `freecad::raw` and should not be the default documentation path.
