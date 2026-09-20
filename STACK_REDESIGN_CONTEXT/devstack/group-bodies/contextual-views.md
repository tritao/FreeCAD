This group introduces viewer-local presentation state and its persistent counterpart.

It covers `Gui::ViewContext`, domain-neutral saved view definitions, versioned camera capture, contextual clipping, workbench policy, temporary appearance overrides, dynamic display modes, contextual TaskView actions, and viewer-local representation instances.

Architectural invariant:

> Multiple viewers can present the same document differently without mutating shared document visibility or global preferences.
