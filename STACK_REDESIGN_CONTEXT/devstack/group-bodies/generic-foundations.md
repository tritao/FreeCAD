This group makes existing FreeCAD GUI behavior reliable enough for a contextual editing session.

It establishes deterministic camera completion, document-owned task dialogs, safe Coin sensor and scene-node lifetimes, and correct child ViewProvider attachment. These are independent FreeCAD improvements; none contains BIM policy.

Architectural invariant:

> Generic GUI lifetime and ownership behavior is correct before Plan Edit depends on it.
