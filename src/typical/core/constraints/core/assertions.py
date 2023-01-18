import abc
from typing import Any, TypeVar

from typical.compat import Generic, Protocol, TypeGuard

_VT = TypeVar("_VT")
_VT_co = TypeVar("_VT_co", covariant=True)

__all__ = ("AssertionProtocol", "AbstractAssertions")


class AssertionProtocol(Protocol[_VT_co]):
    def __call__(self, val: Any) -> TypeGuard[_VT]:
        ...


class AbstractAssertions(abc.ABC, Generic[_VT]):
    __call__: AssertionProtocol[_VT]

    __slots__ = ("__call__",)

    def __init__(self):
        self.__call__ = self._get_closure()

    @abc.abstractmethod
    def _get_closure(self) -> AssertionProtocol[_VT]:
        ...
