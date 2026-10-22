"""Rows supporting both numeric and named column access."""

from collections.abc import Mapping
from typing import Any


class HybridRow(Mapping):
    def __init__(self, columns, values):
        self._columns = tuple(columns)
        self._values = tuple(values)
        self._mapping = dict(zip(self._columns, self._values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._columns)

    def __len__(self):
        return len(self._columns)

    def keys(self):
        return self._columns


def hybrid_row_factory(cursor):
    description = cursor.description

    if description is None:
        return None

    columns = [column.name for column in description]

    def make_row(values):
        return HybridRow(columns, values)

    return make_row
