# Viewer-local view context

`Gui::ViewContext` carries transient, viewer-owned presentation state without changing document
properties or shared view-provider fields. A context contains ordered layers; the most recently
added override for an object wins. Removing a layer restores the result from the layers below it.

## Ownership and lifetime

- Each `View3DInventorViewer` owns one `ViewContext`.
- Clients receive opaque layer handles through the viewer API and must pop layers they create.
- Deleting a document object removes its entries from every live viewer context.
- Scene-graph gates retain only an object identity used as a context lookup key. They do not retain
  view providers. Viewer-owned gates are removed with their foreground or background roots.

## Scene traversal

`SoFCUnifiedSelection` installs the viewer's context in `SoViewContextElement` at the scene root.
Object selection roots consult that element for render, pick, event, bounding-box, matrix, and
primitive-count actions. Foreground and background provider roots use `SoViewContextGate`; nested
gates inherit the context already installed by the viewer.

A `Visible` override traverses the provider's default display-mode child through
`SoViewContextSwitch`. It never writes `SoSwitch::whichChild`. This matters because a view provider
and its scene graph may be shared by multiple viewers with different contexts. A `Hidden` override
stops traversal for that viewer only, while `Inherit` preserves the provider's persistent state.

## Contract

Viewer-local overrides are presentation state. They must not create document transactions, alter
`ViewProvider::Visibility`, or emit persistent visibility changes. Code that needs durable document
visibility should continue to use the view-provider property instead.
