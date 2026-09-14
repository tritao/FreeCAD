# SPDX-License-Identifier: LGPL-2.1-or-later

"""Transaction helpers for BIM Plan Edit integrations."""


class PlanEditTransaction:
    def __init__(self, doc, label):
        self.doc = doc
        self.label = str(label or "").strip()
        self._opened = False

    def __enter__(self):
        if self.doc is not None and self.label:
            self.doc.openTransaction(self.label)
            self._opened = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        del exc_value, traceback
        if not self._opened or self.doc is None:
            return False
        if exc_type is None:
            self.doc.commitTransaction()
        else:
            self.doc.abortTransaction()
        return False
