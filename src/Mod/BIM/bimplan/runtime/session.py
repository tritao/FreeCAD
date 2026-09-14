# SPDX-License-Identifier: LGPL-2.1-or-later

"""Initial session state for BIM Plan Edit."""

from bimplan.representation_request import PlanRepresentationRequestAPI


class PlanEditSession:
    """Hold Plan's storey-scoped representation request."""

    def __init__(self, active_storey=None):
        self.active_storey = None
        self.representation_request = PlanRepresentationRequestAPI(self)
        if active_storey is not None:
            self.representation_request.set_source(active_storey, refresh=False)

    @property
    def request(self):
        return self.representation_request.request

    def set_source(self, source):
        return self.representation_request.set_source(source, refresh=False)

    def includes_object(self, obj):
        return self.representation_request.includes_object(obj)
