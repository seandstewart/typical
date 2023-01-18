from __future__ import annotations

import dataclasses
from typing import Any, Collection, Hashable, Iterator, Sequence, TypeVar

from typical import checks
from typical.types.frozendict import freeze

__all__ = (
    "unique_fast",
    "unique_slow",
    "UniquePrecheck",
)


_ST = TypeVar("_ST", bound=Collection)


class UniquePrecheck:
    __slots__ = ("cls",)

    def __init__(self, cls: type[Collection] = list):
        self.cls = cls

    def __call__(self, value: _ST) -> _ST:
        """Fastest, order-preserving method for uniques in Python >= 3.6.

        See Also
        --------
        `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
        """
        try:
            return unique_fast(value, ret_type=self.cls)  # type: ignore
        except TypeError:
            return unique_slow(value, ret_type=self.cls)  # type: ignore


def unique_fast(seq: Sequence, *, ret_type: type[_ST]) -> _ST:
    """Fastest order-preserving method for (hashable) uniques in Python >= 3.6.

    Notes
    -----
    Values of seq must be hashable!

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    return ret_type(dict.fromkeys(seq))  # type: ignore[call-arg]


def unique_slow(seq: Sequence, *, ret_type: type[_ST]) -> _ST:
    """Fastest order-preserving method for (unhashable) uniques in Python >= 3.6.

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    return ret_type(_unique_slow(seq))  # type: ignore[call-arg]


def _get_hash(
    obj: Any,
    *,
    __hash=hash,
    __ishash=checks.ishashable,
    __isdatacls=dataclasses.is_dataclass,
    __asdict=dataclasses.asdict,
    __freeze=freeze,
):
    if __isdatacls(obj):
        return __hash(obj)
    if __isdatacls(obj):
        obj = __asdict(obj)
    return __hash(__freeze(obj))


def _unique_slow(seq: Sequence, *, __hash=_get_hash) -> Iterator:
    seen: set[Hashable] = set()
    add = seen.add
    for x in seq:
        h = __hash(x)
        if h in seen:
            continue
        add(h)
        yield x
