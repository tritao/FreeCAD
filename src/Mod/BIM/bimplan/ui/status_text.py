# SPDX-License-Identifier: LGPL-2.1-or-later

"""Context-sensitive feedback for BIM Plan Edit."""


class PlanStatusTextAPI:
    """Own feedback messages and invalidate them when the edit context shifts."""

    __slots__ = ("_session", "_integration_message", "_integration_context_key")

    def __init__(self, session):
        self._session = session
        self._integration_message = ""
        self._integration_context_key = None

    @property
    def session(self):
        return self._session

    def get_integration_feedback_context_key(self):
        session = self.session
        selection = getattr(session, "selection", None)
        selected_handle = getattr(selection, "selected_handle", None)
        request_api = getattr(session, "representation_request", None)
        request = getattr(request_api, "request", None)
        return (
            str(getattr(session, "current_tool", "") or ""),
            getattr(request, "source", None),
            selected_handle,
        )

    def get_integration_feedback_message(self):
        if not self._integration_message:
            return ""
        if self._integration_context_key != self.get_integration_feedback_context_key():
            self.clear_integration_feedback_message()
            return ""
        return self._integration_message

    def set_integration_feedback_message(self, message):
        normalized = str(message or "").strip()
        if not normalized:
            self.clear_integration_feedback_message()
            return ""
        self._integration_message = normalized
        self._integration_context_key = self.get_integration_feedback_context_key()
        return normalized

    def clear_integration_feedback_message(self):
        self._integration_message = ""
        self._integration_context_key = None
