from __future__ import annotations

import abc
import dataclasses
from typing import TYPE_CHECKING, Generic, TypeVar

from typical import classes
from typical.core.interfaces import Annotation

if TYPE_CHECKING:
    from typical.resolver import Resolver

_T = TypeVar("_T")
_SerDesT = TypeVar("_SerDesT")


@classes.slotted(dict=False, weakref=True)
@dataclasses.dataclass(init=False)
class AbstractSerDesRoutine(abc.ABC, Generic[_T, _SerDesT]):
    annotation: Annotation[type[_T]]
    resolver: Resolver
    namespace: type | None
    __call__: _SerDesT
    __name__: str
    __qualname__: str

    def __repr__(self) -> str:
        return (
            f"<({self.__class__.__name__} "
            f"annotation={self.annotation}, "
            f"namespace={self.namespace})>"
        )

    def __init__(
        self,
        annotation: Annotation[type[_T]],
        resolver: Resolver,
        namespace: type | None = None,
    ):
        self.annotation = annotation
        self.resolver = resolver
        self.namespace = namespace
        self._bind_closure()

    def _bind_closure(self):
        self.__call__ = self._get_closure()
        self.__name__ = self.__call__.__name__
        self.__qualname__ = self.__call__.__qualname__

    def __hash__(self) -> int:
        return self.__call__.__hash__()

    @abc.abstractmethod
    def _get_closure(self) -> _SerDesT:
        ...
