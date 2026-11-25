from typing import Protocol

from ..models import Signal


class Source(Protocol):
    name: str

    def search(self, query: str, days: int, limit: int) -> list[Signal]: ...
