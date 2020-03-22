import dataclasses
from typing import (
    Sequence,
    Type,
    Union,
    Set,
    Hashable,
    Any,
    Iterator,
    List,
    Dict,
    Tuple,
)

from typic import checks, util, gen
from typic.types.frozendict import freeze
from ..common import ChecksT, ContextT


def unique_fast(
    seq: Sequence, *, ret_type: Type[Union[list, tuple]] = list
) -> Sequence:
    """Fastest order-preserving method for (hashable) uniques in Python >= 3.6.

    Notes
    -----
    Values of seq must be hashable!

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    return ret_type(dict.fromkeys(seq))


def unique_slow(
    seq: Sequence, *, ret_type: Type[Union[list, tuple]] = list
) -> Sequence:
    """Fastest order-preserving method for (unhashable) uniques in Python >= 3.6.

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    seen: Set[Hashable] = set()
    return ret_type(_unique_slow(seq, seen))


def _get_hash(obj: Any):
    if checks.ishashable(obj):
        return hash(obj)
    if dataclasses.is_dataclass(obj):
        obj = dataclasses.asdict(obj)
    return hash(freeze(obj))


def _unique_slow(seq: Sequence, seen: set) -> Iterator[Any]:
    add = seen.add
    for x in seq:
        h = _get_hash(x)
        if h in seen:
            continue
        add(h)
        yield x


def unique(seq: Sequence, *, ret_type: Type[Union[list, tuple]] = list) -> Sequence:
    """Fastest, order-preserving method for uniques in Python >= 3.6.

    See Also
    --------
    `Uniquify List in Python 3.6 <https://www.peterbe.com/plog/fastest-way-to-uniquify-a-list-in-python-3.6>`_
    """
    try:
        return unique_fast(seq, ret_type=ret_type)
    except TypeError:
        return unique_slow(seq, ret_type=ret_type)


def _build_validator(self, func: gen.Block) -> Tuple[ChecksT, ContextT]:
    # No need to sanity check the config.
    # Build the code.
    # Only make it unique if we have to. This preserves order as well.
    if self.unique is True and util.origin(self.type) not in {set, frozenset}:
        func.l(f"{self.VAL} = __unique({self.VAL})", __unique=unique)
    # Only get the size if we have to.
    if {self.max_items, self.min_items} != {None, None}:
        func.l(f"size = len({self.VAL})")
    # Get the validation checks and context
    asserts: List[str] = []
    context: Dict[str, Any] = {}
    if self.min_items is not None:
        asserts.append(f"size >= {self.min_items}")
    if self.max_items is not None:
        asserts.append(f"size <= {self.max_items}")
    # Validate the items if necessary.
    if self.values:
        o = util.origin(self.type)
        itval = "__item_validator"
        ctx = {itval: self.values.validate, o.__name__: o}
        field = f"'.'.join(({self.VALTNAME}, str(i)))"
        func.l(
            f"{self.VAL} = "
            f"{o.__name__}("
            f"({itval}(x, field={field}) for i, x in enumerate({self.VAL}))"
            f")",
            **ctx,
        )
    return asserts, context
