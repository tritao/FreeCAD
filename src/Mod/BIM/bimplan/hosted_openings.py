# SPDX-License-Identifier: LGPL-2.1-or-later

"""Hosted opening mutation helpers for BIM Plan Edit."""

from contextlib import nullcontext

from bimplan.transactions import PlanEditTransaction


def has_built_opening_shape(opening):
    """Return True when an opening has a usable shape before it is hosted."""

    shape = getattr(opening, "Shape", None)
    if not shape:
        return False
    try:
        return not shape.isNull()
    except Exception:
        return False


def _host_opening(opening, host):
    import Arch

    Arch.addComponents(opening, host)
    return opening


def create_hosted_opening(
    session,
    host,
    build_opening,
    transaction_label,
    add_to_active_storey=True,
):
    """Create, build, host, and recompute an opening in the safe Plan Edit order.

    Hosted Arch windows touch their hosts when their shape changes. Build the
    opening before assigning its host so creation does not schedule a second
    host/opening recompute pass.
    """

    doc = getattr(session, "doc", None)
    if doc is None:
        return None

    opening = None
    defer_updates = getattr(session, "defer_document_visual_updates", None)
    update_scope = defer_updates() if defer_updates else nullcontext()
    with update_scope:
        with PlanEditTransaction(doc, transaction_label):
            opening = build_opening()
            if opening is None:
                raise RuntimeError("Unable to create opening")

            doc.recompute()
            if not has_built_opening_shape(opening):
                raise RuntimeError("Opening did not build before hosting")

            _host_opening(opening, host)
            if add_to_active_storey and hasattr(session, "_add_object_to_active_storey"):
                session._add_object_to_active_storey(opening)
            doc.recompute()

            if host not in (getattr(opening, "Hosts", None) or ()):
                raise RuntimeError("Opening was not hosted")

    return opening
