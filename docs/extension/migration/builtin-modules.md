# Built-in Module Adoption

**Status:** Guide

## Goal

Built-in modules should be able to adopt the Extension architecture incrementally without an all-or-nothing rewrite.

## Step 1 — identify stable domain concepts

Choose a small public surface external developers actually need. Do not start by exporting every implementation function.

## Step 2 — design a stable interface

For example:

```text
org.freecad.bim@1
```

Define operations, value/resource types, threading behavior, events, and compatibility expectations.

## Step 3 — adapt existing implementation

Keep current Python/C++ code and write the provider adapter around it. No sandbox conversion is required.

## Step 4 — dogfood core interfaces

Where reasonable, use the Extension API for ordinary document/UI operations inside the module. This tests public ergonomics but should not become an artificial performance requirement for internal paths.

## Step 5 — expose provider to SDKs

Once normalized, generate Python typing/facade, C++/Rust SDK access, documentation, and sandbox host dispatch.

## Step 6 — migrate external consumers

External addons can depend on the stable interface rather than module-internal imports.

## What not to do

Do not rewrite a mature module entirely to fit the public API, force privileged internal code into a sandbox, expose Qt/Coin objects merely because the module currently uses them, or version the public interface every time an internal class changes.

The provider adapter exists precisely to decouple those layers.
