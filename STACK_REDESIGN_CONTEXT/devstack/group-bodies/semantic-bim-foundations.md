This group establishes the renderer-neutral BIM model required by contextual views.

It introduces the canonical representation contract, generic plan-footprint behavior, object-owned footprint providers, and explicit wall-relation semantics. Wall joins are persistent semantic relations rather than inferred display artifacts.

Architectural invariant:

> BIM providers produce semantic geometry and identity without depending on Coin, Qt, or a particular viewer.
