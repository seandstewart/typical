import enum
import functools
from inspect import Signature
from typing import (
    TYPE_CHECKING,
    TypeVar,
    Callable,
    Tuple,
    List,
    Dict,
    Any,
    NoReturn,
    Union,
)

from typic import gen, util

if TYPE_CHECKING:
    from .obj import BaseConstraints, TypeConstraints, MultiConstraints  # noqa: 401

_T = TypeVar("_T")
VT = TypeVar("VT")
"""A generic type-var for values passed to a validator."""
ValidatorT = Callable[[VT], Tuple[bool, VT]]
"""The expected signature of a value validator."""

ChecksT = List[str]
ContextT = Dict[str, Any]
BuilderT = Callable[[_T, gen.Block], Tuple[ChecksT, ContextT]]
ReturnerT = Callable[[_T, gen.Block, ChecksT, ContextT], NoReturn]


class InstanceCheck(enum.IntEnum):
    """Flags for instance check methods.

    See Also
    --------
    :py:class:`~typic.constraints.mapping.MappingConstraints`
    """

    IS = 0
    """Allows for short-circuiting validation if ``isinstance(value, <type>) is True``.

    Otherwise, perform additional checks to see if we can treat this as valid.
    """
    NOT = 1
    """Allows for short-circuiting validation if ``isinstance(value, <type>) is False``.

    Otherwise, we must perform additional checks.
    """


def _get_validator_name(
    constr: Union["BaseConstraints", "TypeConstraints", "MultiConstraints"]
) -> str:
    return f"validator_{util.hexhash(constr)}"


def _set_return(
    constr: "BaseConstraints", func: gen.Block, checks: ChecksT, context: ContextT
):
    if checks:
        check = " and ".join(checks)
        func.l(f"valid = {check}", **context)
        func.l(f"return valid, {constr.VAL}")
    else:
        func.l(f"return True, {constr.VAL}", **context)


@functools.lru_cache(maxsize=None)
def _compile_validator(constr: "BaseConstraints") -> ValidatorT:
    func_name = _get_validator_name(constr)
    origin = util.origin(constr.type)
    type_name = constr.type_name
    with gen.Block() as main:
        with main.f(func_name, main.param(constr.VAL)) as f:
            # This is a signal that -*-anything can happen...-*-
            if origin in {Any, Signature.empty}:
                f.l(f"return True, {constr.VAL}")
                return main.compile(name=func_name)
            f.l(f"{constr.VALTNAME} = {type_name!r}")
            # Short-circuit validation if the value isn't the correct type.
            if constr.instancecheck == InstanceCheck.IS:
                line = f"if isinstance({constr.VAL}, {type_name}):"
                if constr.nullable:
                    line = (
                        f"if {constr.VAL} is None "
                        f"or isinstance({constr.VAL}, {type_name}):"
                    )
                with f.b(line, **{type_name: constr.type}) as b:  # type: ignore
                    b.l(f"return True, {constr.VAL}")
            else:
                if constr.nullable:
                    with f.b(f"if {constr.VAL} is None:") as b:
                        b.l(f"return True, {constr.VAL}")
                line = f"if not isinstance(val, {type_name}):"
                with f.b(line, **{type_name: constr.type}) as b:  # type: ignore
                    b.l(f"return False, {constr.VAL}")
            checks, context = constr.builder(f)
            # Write the line.
            constr._returner(func=f, checks=checks, context=context)

    return main.compile(name=func_name)
