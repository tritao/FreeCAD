RFC: Evolution of FreeCAD's rendering subsystem
===============================================

This explores the current architecture of FreeCAD's rendering subsystem, its main current
issues, possible technical solutions to the issues presented as well as an overall analysis
of the feasibility of such changes.

Its main goal is discuss it with the broader FreeCAD community and hopefully come to a
consensus on how to proceed with its evolution.

# Overview

FreeCAD provides rendering via the Coin3D library, which is an OpenGL-based, 3D graphics
library that has its roots in the Open Inventor 2.1 API, which it still is compatible with.

It implements a classically architected scene graph, consisting of a tree with different kinds
of linked nodes, which are mainly representing geometry, grouping, transformation, as well as
setting up rendering state.

Coin is currently used inside FreeCAD for:
 
 1) Geometry provider
 2) Transformation
 3) Math graphics library
 4) Rendering provider
 5) Bounding volume hierarchy functionality

It also provides an event system, which is currently used to handle view-related functionality,
like selection.

# Existing Issues

There are some problems related to Coin itself, as well as to how FreeCAD uses Coin, which we will explore
below.

## 1. Performance

This is probably the main reason that started me on this and its just that FreeCAD's rendering is very slow.

Rendering walks the scene graph multiple times, which is pretty slow, 
Ideally it would be none, but willing to live with single time per frame.

![](coin_profile.png)

### Instancing

Modern GPUs provide instancing support, which allows to render similar objects with a single
draw call, which is a lot more efficient than individually submitting to the GPU, as the geometry
only needs to be submitted once to the GPU, while also sending a buffer with just the instance-specific
attributes.

## 2. Portability

Coin is currently stuck with OpenGL 1.5-level functionality, there is support for shaders but
nothing really uses them, documentation is very scarce.

This is an issue when porting to modern systems which use modern graphical APIs like Vulkan
and Metal. This is both a Coin issue, as well as a FreeCAD issue, because FreeCAD itself uses
immediate mode OpenGL style calls, which are not compatible with modern OpenGL rendering.

## 3. Limited Functionality

Coin does not provide any modern features like integrated shadows and lighting models.
Global and indirect lighting algorithms are 

Coin does not provide advanced lighting models

## Limited Python bindings support

It's not possible to create new Coin nodes from Python, which is a pretty big expressivity
problem since it limits developers using Python to only re-use existing C++-defined Coin nodes.

Coin bindings are provided as part of Pivy project which is mantained and released separately
from the main Coin releases. 

## Architecture problems

Coin supports an action-based system for working with nodes, which is implemented with the
`doAction` callback at the node-level:

```cpp
class SoNode {
    // ...
    virtual void SoNode::doAction(SoAction * action);
    // ...
}
```

This is not ideal as nodes need to know about actions, which heavily limits external users like
FreeCAD to implement their own actions on the scene graph, leading in some for code duplication.

In some cases FreeCAD currently duplicates Coin nodes, like `SoFCWhatever` for this reason.

Additionally, due to this design, nodes need to explicitly enable which elements actions need.

For example here is an example from Coin:

```cpp
void SoSeparator::initClass(void) {
  // ...
  SO_ENABLE(SoGetBoundingBoxAction, SoCacheElement);
  SO_ENABLE(SoGLRenderAction, SoCacheElement);
}
```

This is also a pretty big expressivity issue

# Potential Solutions

This section will present different potential solutions to improve FreeCAD's rendering.

## Using Coin3D as a scene provider and rendering with another library

This solution keeps using Coin3D as the scene graph and primitive geometry provider,
and switches out the internal rendering layer to a modern cross-platform graphics abstraction
library, which there are a few suitable free software options:

* [bgfx](https://github.com/bkaradzic/bgfx)
* [sokol](https://github.com/floooh/sokol)
* [SDL 3.0 GPU](https://wiki.libsdl.org/SDL3/CategoryGPU)
* [DiligentEngine](https://github.com/DiligentGraphics/DiligentEngine)
* [Qt Rendering Hardware Interface](https://doc.qt.io/qt-6/qrhi.html)

There are certain tradeoffs to be discussed for each option, but overall it does not matter
much which particular one is used regarding this overall approach.

FreeCAD would still use Coin as the main scene rendering layer, but convert the representation inside
Coin3D tree into the equivalent representation for the graphics abstraction library, which would be
cached, and thus be submitted into the GPU much more efficiently.

We'll explore this in more detail below in the integration section.

## Extending FreeCAD's object model to a scene graph





## Using an high level rendering engine for scene and rendering providers

There are higher level rendering engines, which sit a layer above graphics abstractions libraries
as discussed above, that provide higher level rendering functionality, usually supporting high
fidelity rendering features:

* Physically-based rendering
* Real-time lighting models (with area lights)
* Shadow mapping
* Global illumination with indirect lighting
* Antialiasing

As well as the following, which while not as directly applicable to CAD use cases, could be very useful
for more advanced robotics simulation, BIM visualization, as well as VR use cases:

* Reflections
* Decals
* Sky
* Fog
* Volumetric fog
* Particles
* Post-processing

And given they don't typically have any performance drawbacks unless they're enabled, then it's
hard to argue against having them available as a potential option for those more advanced use cases.

Upon an initial analysis, follows an analysis of suitable free software higher-level engines:

* [OGRE3D](https://www.ogre3d.org/about/features)
* [Godot](https://docs.godotengine.org/en/stable/about/list_of_features.html#id1)
* [filament](https://github.com/google/filament)
* [Panda3D](https://www.panda3d.org/features/)
* [rbfx](https://github.com/rbfx/rbfx)
* [DiligentEngine (High-level Rendering components)](https://github.com/DiligentGraphics/DiligentEngine#high-level-rendering-components)

Special shoutout to Godot engine, which has established itself recently as a very popular open source
game and rendering engine, and has recently made steps towards supporting the use case described here
as in https://github.com/godotengine/godot/pull/90510.

Again, we'll explore this in more detail as well below.

## Integration

This section explores how each approach dicussed above can be integrated in the current
FreeCAD's rendering architecture, which is based on the `ViewProvider` class.

Each instance provides a set of overloads that provide the associated Coin3D nodes:

```cpp
class ViewProvider : public App::TransactionalObject
{
    // ...

    // returns the root node of the Provider (3D)
    virtual SoSeparator* getRoot() const {return pcRoot;}
    // return the mode switch node of the Provider (3D)
    SoSwitch *getModeSwitch() const {return pcModeSwitch;}
    SoTransform *getTransformNode() const {return pcTransform;}
    // returns the root for the Annotations.
    SoSeparator* getAnnotation();
    // returns the root node of the Provider (3D)
    virtual SoSeparator* getFrontRoot() const;
    // returns the root node where the children gets collected(3D)
    virtual SoGroup* getChildRoot() const;
    // returns the root node of the Provider (3D)
    virtual SoSeparator* getBackRoot() const;
    ///Indicate whether to be added to scene graph or not
    virtual bool canAddToSceneGraph() const {return true;}
    // Indicate whether to be added to object group (true) or only to scene graph (false)
    virtual bool isPartOfPhysicalObject() const {return true;}

    // ...
}
```





Modern rendering pipelines are designed so submitting geometry to the GPU is done as fast
as possible, typically by using simple lists of draw calls, which can be linearly iterated
and processed, which is much faster than typical pointer-based tree iteration.

A draw call is a command issued by the CPU to the GPU instructing it to render a set of primitives (such as triangles, lines, or points) with specific state settings (like shaders, textures, blending, and transformation parameters). Here’s a breakdown of the concept:

**Communication from CPU to GPU:**
The CPU sends a draw call to the GPU. This call tells the GPU, "Render this batch of vertices (or primitives) using these current settings."

**State and Resource Binding:**
Before a draw call is made, various rendering states are set (for example, which shader to use, what textures are bound, blending modes, depth and stencil tests, etc.). The draw call then uses these settings to process the vertex and fragment data.

**Batching and Performance:**
Each draw call incurs some overhead as it involves communication between the CPU and GPU. Minimizing the number of draw calls—by batching similar objects together—is a common performance optimization in graphics programming.

**Rendering Pipeline Execution:**
When the draw call is executed, the GPU processes the vertex data through its graphics pipeline (vertex processing, clipping, rasterization, fragment shading, etc.), ultimately producing pixels on the screen.


Allocate an id in the rendering list and give it to view provider

```cpp
class ViewProvider {
    // ...
    SoNode *node;

    void submitGeometry(bgfx::DrawCallBuilder& b) {
        b.submitCoinNode(node)
    }
    // ...
}
```


Let's take `bgfx` as an example, 


## Rendering State

Each view provider would 

### Render State Settings
* **Channel Write Control**: Toggle writing to color channels (R, G, B, A) and depth.
* **Depth Testing**: Choose a comparison function (e.g., less, equal, greater) to determine pixel visibility.
* **Blending**:
    * **Factors**: Select source and destination blend factors (e.g., zero, one, source color, destination alpha).
    * **Equations**: Decide how colors are combined (e.g., add, subtract, min, max).
* **Culling**: Specify which faces of primitives (clockwise or counter-clockwise) to ignore.
* **Primitive Types**: Define how vertices are interpreted (e.g., triangle strips, lines, points).
* **Miscellaneous Options**: Enable features like independent blending, alpha-to-coverage, multisample anti-aliasing, and line anti-aliasing.

### **Stencil State Settings**
* Stencil Testing: Configure stencil tests separately for front-facing and back-facing primitives (or use one setting for both).

### **Scissor Settings**
* Custom Scissor Rectangle: Define a drawing region using coordinates and dimensions, with a mechanism to cache and quickly reuse these settings.
* Cached Scissor Use: Reapply or unset a cached scissor region using its index.




# REST


Decoupling selection system from the scene graph

Overriding view display mode mutates the scene graph, invalidates caches

    Hack it around for now

Concurrency when calculating bounding boxes

Links are being updated on sensor callbacks

Inefficient handling of links in Coin3D / instancing

    Done in low level Coin3D level instead of higher level

LinkViewPy?

ViewProviderGeometryObject inherits from ViewProviderDragger

Draggers have no highlight

Transform of grouped selection
