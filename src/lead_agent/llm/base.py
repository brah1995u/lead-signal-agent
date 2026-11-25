from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    model: str

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        """Returns the model's answer parsed and validated as `schema`."""
        ...
