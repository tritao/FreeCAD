# SPDX-License-Identifier: LGPL-2.1-or-later

"""Aggregate BIM Plan Edit GUI workflow test suite."""

from .TestBimPlanEditGuiBase import BimPlanEditGuiBase
from .TestBimPlanEditGuiOpenings import BimPlanEditGuiOpeningsMixin
from .TestBimPlanEditGuiProvider import BimPlanEditGuiProviderMixin
from .TestBimPlanEditGuiSpaces import BimPlanEditGuiSpacesMixin
from .TestBimPlanEditGuiSymbols import BimPlanEditGuiSymbolsMixin
from .TestBimPlanEditGuiWalls import BimPlanEditGuiWallsMixin


class TestBimPlanEditGui(
    BimPlanEditGuiProviderMixin,
    BimPlanEditGuiSymbolsMixin,
    BimPlanEditGuiOpeningsMixin,
    BimPlanEditGuiWallsMixin,
    BimPlanEditGuiSpacesMixin,
    BimPlanEditGuiBase,
):
    """Compose the split Plan Edit GUI workflow suites under one stable entrypoint."""

    pass
