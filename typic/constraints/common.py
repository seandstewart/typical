#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import abc
import dataclasses
import enum
from inspect import Signature
from typing import (
    Callable,
    Any,
    ClassVar,
    Type,
    Tuple,
    List,
    Dict,
    TypeVar,
    Union,
    TYPE_CHECKING,
    Iterable,
    Iterator,
    Set,
)

from typic import gen, util
from typic.strict import STRICT_MODE
from .error import ConstraintValueError


if TYPE_CHECKING:  # pragma: nocover
    from typic.constraints.factory import ConstraintsT  # noqa: F401


__all__ = (
    "BaseConstraints",
    "MultiConstraints",
    "TypeConstraints",
    "ValidatorT",
)

VT = TypeVar("VT")
"""A generic type-var for values passed to a validator."""
ValidatorT = Callable[[VT], Tuple[bool, VT]]
"""The expected signature of a value validator."""
ChecksT = List[str]
ContextT = Dict[str, Any]
_T = TypeVar("_T")


class __AbstractConstraints(abc.ABC):
    type: ClassVar[Type[Any]]

    def __post_init__(self):
        self.validator

    __repr = util.cached_property(util.filtered_repr)

    def __repr__(self) -> str:
        return self.__repr

    @util.cached_property
    def __str(self) -> str:
        fields = [f"type={self.type_name}"]
        for f in dataclasses.fields(self):
            val = getattr(self, f.name)
            if (val or val in {False, 0}) and f.repr:
                fields.append(f"{f.name}={val}")
        return f"({', '.join(fields)})"

    def __str__(self) -> str:
        return self.__str

    @util.cached_property
    def type_name(self) -> str:
        return util.get_name(self.type)

    def _get_validator_name(self) -> str:
        return f"validator_{util.hexhash(self)}"

    @util.cached_property
    @abc.abstractmethod
    def validator(self) -> ValidatorT:  # pragma: nocover
        ...

    def validate(self, value: VT, *, field: str = None) -> VT:
        """Validate that an incoming value meets the given constraints.

        Notes
        -----
        Some constraints may mutate the incoming value to conform, so the value is always
        returned.

        Raises
        ------
        :py:class:`ConstraintValueError`
            An error inheriting from :py:class:`ValueError` indicating the input is not
            valid.
        :py:class:`ConstraintSyntaxError`
            An error inheriting from :py:class:`SyntaxError` indicating the constraint
            configuration is invalid.
        """
        valid, value = self.validator(value)
        if not valid:
            field = f"{field}:" if field else "Given"
            raise ConstraintValueError(
                f"{field} value <{value!r}> fails constraints: {self}"
            ) from None
        return value

    @abc.abstractmethod
    def for_schema(
        self, *, with_type: bool = False
    ) -> Dict[str, Any]:  # pragma: nocover
        ...


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


@dataclasses.dataclass(frozen=True, repr=False)  # type: ignore
class BaseConstraints(__AbstractConstraints):
    """A base constraints object. Shouldn't be used directly.

    Notes
    -----
    Inheritors of :py:class:`Constraints` should conform to JSON Schema type-constraints.

    See Also
    --------
    :py:class:`~typic.types.constraints.TextConstraints`
    :py:class:`~typic.types.constraints.NumberConstraints`
    :py:class:`~typic.types.constraints.ArrayConstraints`
    :py:class:`~typic.types.constraints.MappingConstraints`
    """

    type: ClassVar[Type[Any]]
    """The target type for this constraint."""
    instancecheck: ClassVar[InstanceCheck] = InstanceCheck.NOT
    """The method to use when short-circuting with instance checks."""
    nullable: bool = False
    """Whether to allow null values."""
    coerce: bool = False
    """Whether additional coercion should be done after validation.

    Even in ``strict`` mode, we may still want to coerce after validation.
    """
    VAL = "val"
    VALTNAME = "valtname"

    def _build_validator(
        self, func: gen.Block
    ) -> Tuple[ChecksT, ContextT]:  # pragma: nocover
        raise NotImplementedError

    def _set_return(self, func: gen.Block, checks: ChecksT, context: ContextT):
        if checks:
            check = " and ".join(checks)
            func.l(f"valid = {check}", **context)
            func.l(f"return valid, {self.VAL}")
        else:
            func.l(f"return True, {self.VAL}", **context)

    def _compile_validator(self) -> ValidatorT:
        func_name = self._get_validator_name()
        origin = util.origin(self.type)
        type_name = self.type_name
        with gen.Block() as main:
            with main.f(func_name, main.param(self.VAL)) as f:
                # This is a signal that -*-anything can happen...-*-
                if origin in {Any, Signature.empty}:
                    f.l(f"return True, {self.VAL}")
                    return main.compile(name=func_name)
                f.l(f"{self.VALTNAME} = {type_name!r}")
                # Short-circuit validation if the value isn't the correct type.
                if self.instancecheck == InstanceCheck.IS:
                    line = f"if isinstance({self.VAL}, {type_name}):"
                    if self.nullable:
                        line = (
                            f"if {self.VAL} is None "
                            f"or isinstance({self.VAL}, {type_name}):"
                        )
                    with f.b(line, **{type_name: self.type}) as b:  # type: ignore
                        b.l(f"return True, {self.VAL}")
                else:
                    if self.nullable:
                        with f.b(f"if {self.VAL} is None:") as b:
                            b.l(f"return True, {self.VAL}")
                    line = f"if not isinstance(val, {type_name}):"
                    with f.b(line, **{type_name: self.type}) as b:  # type: ignore
                        b.l(f"return False, {self.VAL}")
                checks, context = self._build_validator(f)
                # Write the line.
                self._set_return(func=f, checks=checks, context=context)
        return main.compile(name=func_name)

    @util.cached_property
    def validator(self) -> ValidatorT:
        """Accessor for the generated validator.

        Validators are generated code based upon the constraint syntax provided.
        The resulting code is about as optimized as you can get in Python, since
        the constraint values are localized to the validator and only the checks
        that the validator performs are the checks that were set. There is no
        computation time wasted on deciding whether or not to perform a validation.
        """
        validator = self._compile_validator()
        return validator


@dataclasses.dataclass(frozen=True, repr=False)
class MultiConstraints(__AbstractConstraints):
    """A container for multiple constraints for a single field."""

    constraints: Tuple["ConstraintsT", ...]
    coerce: bool = False

    @util.cached_property
    def nullable(self) -> bool:
        return any(x.nullable for x in self.constraints)

    @util.cached_property
    def __str(self) -> str:  # type: ignore
        constraints = f"({', '.join((str(c) for c in self.constraints))})"
        return f"(constraints={constraints}, nullable={self.nullable})"

    def __str__(self) -> str:
        return self.__str

    def __type(self) -> Iterator[Type]:
        to_flatten: Set[Union[Type, Iterable[Type]]]
        to_flatten = {x.type for x in self.constraints}
        while to_flatten:
            t: Union[Type, Iterable[Type]] = to_flatten.pop()
            if isinstance(t, Iterable):
                to_flatten.update(t)
                continue
            yield t

    @util.cached_property
    def type(self) -> Tuple[Type, ...]:  # type: ignore
        return (*self.__type(),)

    @util.cached_property
    def validator(self) -> ValidatorT:
        """Accessor for the generated multi-validator.

        Validators are keyed by the origin-type of :py:class:`BaseConstraints` inheritors.

        If a value does not match any origin-type, as reported by :py:func:`typic.origin`,
        then we will report the value as invalid.
        """
        vmap: Dict[Type, ValidatorT] = {
            util.origin(c.type): c.validator for c in self.constraints
        }
        if vmap:
            if self.nullable:

                def multi_validator(val: VT) -> Tuple[bool, VT]:
                    if val is None:
                        return True, val
                    t = type(val)
                    return vmap[t](val) if t in vmap else (False, val)

            else:

                def multi_validator(val: VT) -> Tuple[bool, VT]:
                    t = type(val)
                    return vmap[t](val) if t in vmap else (False, val)

        else:

            def multi_validator(val: VT) -> Tuple[bool, VT]:
                return True, val

        return multi_validator

    def for_schema(self, *, with_type: bool = False) -> dict:
        return dict(anyOf=[x.for_schema(with_type=True) for x in self.constraints])


@dataclasses.dataclass(frozen=True, repr=False)
class TypeConstraints(__AbstractConstraints):
    """A container for simple types. Validation is limited to instance checks.

    Examples
    --------
    >>> import typic
    >>> tc = typic.get_constraints(typic.AbsoluteURL)
    >>> tc.validate("http://foo.bar")
    'http://foo.bar'
    >>> tc = typic.get_constraints(typic.AbsoluteURL, nullable=True)
    >>> tc.validate(None)

    >>>
    """

    type: Type[Any]  # type: ignore
    """The type to check for."""
    nullable: bool = False
    """Whether this constraint can allow null values."""

    __str = util.cached_property(util.filtered_str)

    def __str__(self) -> str:
        return self.__str

    @property
    def coerce(self) -> bool:
        """Whether coercion can be used in lieu of validation.

        There are a large number of types provided by the standard lib which are much
        more strict than primitives. These can be relied upon to error out if given
        invalid inputs, so we can signal upstream to use this method.
        """
        return not STRICT_MODE

    @util.cached_property
    def validator(self) -> ValidatorT:
        ns = dict(__t=self.type, VT=VT)
        func_name = self._get_validator_name()
        with gen.Block(ns) as main:
            with main.f(func_name, main.param("value", annotation="VT")) as f:
                # Standard instancecheck is default.
                check = "isinstance(value, __t)"
                retval = "value"
                # This is just a pass-through, the coercer does the real work.
                if self.coerce:
                    check = "True"
                # Have to allow nulls if its nullable.
                elif self.nullable:
                    check = "(value is None or isinstance(value, __t))"
                f.l(f"{gen.Keyword.RET} {check}, {retval}")

        validator: ValidatorT = main.compile(name=func_name, ns=ns)
        return validator

    def for_schema(self, *, with_type: bool = False) -> Dict[str, Any]:
        return {}
