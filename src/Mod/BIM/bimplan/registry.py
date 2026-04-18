# SPDX-License-Identifier: LGPL-2.1-or-later

"""Global registry for BIM Plan Edit providers."""

from collections import OrderedDict


class PlanEditRegistry:
    def __init__(self):
        self._providers = OrderedDict()

    def __len__(self):
        return len(self._providers)

    def register_provider(self, provider):
        if provider is None:
            raise ValueError("A provider instance is required.")
        provider_id = str(provider.get_provider_id()).strip()
        if not provider_id:
            raise ValueError("Plan Edit providers must define a non-empty provider id.")
        self._providers[provider_id] = provider
        return provider

    def unregister_provider(self, provider_or_id):
        if provider_or_id is None:
            return None
        provider_id = provider_or_id
        if not isinstance(provider_or_id, str):
            provider_id = provider_or_id.get_provider_id()
        return self._providers.pop(str(provider_id).strip(), None)

    def clear(self):
        self._providers.clear()

    def get_provider(self, provider_id):
        return self._providers.get(str(provider_id or "").strip())

    def provider_ids(self):
        return tuple(self._providers.keys())

    def iter_providers(self):
        return tuple(self._providers.values())


_GLOBAL_PLAN_EDIT_REGISTRY = PlanEditRegistry()


def get_plan_edit_registry():
    return _GLOBAL_PLAN_EDIT_REGISTRY
