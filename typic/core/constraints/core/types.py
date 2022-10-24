from __future__ import annotations

import abc
import dataclasses
import decimal
import enum
import numbers
import re
import reprlib
import sys
import warnings
from typing import (
    Any,
    Callable,
    Collection,
    Generic,
    Hashable,
    Mapping,
    Pattern,
    Text,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import TypeGuard

from typic import types, util
from typic.compat import ForwardRef, Literal, evaluate_forwardref
from typic.core import constants
from typic.core.annotations import TrueOrFalseT
from typic.core.constraints.core import error, validators

_VT = TypeVar("_VT")

__all__ = (
    "AbstractConstraints",
    "AbstractConstraintValidator",
    "AbstractContainerValidator",
    "UndeclaredTypeConstraints",
    "TypeConstraints",
    "ArrayConstraints",
    "NumberConstraints",
    "DecimalConstraints",
    "MappingConstraints",
    "MultiConstraints",
    "TextConstraints",
    "EnumerationConstraints",
    "StructuredObjectConstraints",
    "DelayedConstraintsProxy",
    "DelayedConstraintValidator",
)


empty = constants.empty


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class AbstractConstraints(Generic[_VT]):

    __ignore_repr__ = frozenset(("type", "origin"))

    type: Type[_VT]
    origin: Type = None
    nullable: bool = False
    readonly: bool = False
    writeonly: bool = False
    default: Hashable | Callable[[], _VT] | constants.empty = empty
    type_name: str = dataclasses.field(default=None, repr=False)
    type_qualname: str = dataclasses.field(default=None, repr=False)

    def __init_subclass__(cls, **kwargs):
        cls.__ignore_repr__ = AbstractConstraints.__ignore_repr__ | cls.__ignore_repr__

    def __post_init__(self):
        if self.type_name is None:
            object.__setattr__(self, "type_name", util.get_name(self.type))
        if self.type_qualname is None:
            object.__setattr__(self, "type_qualname", util.get_qualname(self.type))
        if self.origin is None:
            object.__setattr__(self, "origin", util.origin(self.type))

    @reprlib.recursive_repr()
    def __str__(self) -> str:
        fields = [f"type={self.type_qualname}"]
        for f in dataclasses.fields(self):
            if f.name in self.__ignore_repr__:
                continue

            val = getattr(self, f.name)
            if f.repr and (val or val in {False, 0}):
                fields.append(f"{f.name}={val!r}")
        return f"({', '.join(fields)})"

    def __repr__(self):
        return self.__str__()


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class UndeclaredTypeConstraints(AbstractConstraints[constants.empty]):
    """Simple type-constraint when complex validation is unnecessary."""

    type = constants.empty


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class TypeConstraints(AbstractConstraints[_VT]):
    """Simple type-constraint when complex validation is unnecessary."""


_AT = TypeVar("_AT", bound=Collection)


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class ArrayConstraints(AbstractConstraints[_AT]):
    """Specific constraints pertaining to a sized, array-like type."""

    type: Type[_AT] = cast("type[_AT]", list)
    """The type of array the input should be."""
    min_items: int | None = None
    """The minimum number of items which must be present in the array."""
    max_items: int | None = None
    """The maximum number of items which may be present in the array."""
    unique: bool = False
    """Whether this array should only have unique items.

    Notes
    -----
    Rather than reject arrays which are not unique, we will simply make the array unique.
    """
    values: AbstractConstraints | None = None
    """The constraints for which the items in the array must adhere.

    This can be a single type-constraint, or a tuple of multiple constraints.
    """


_NT = TypeVar("_NT", bound=numbers.Number)


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class NumberConstraints(AbstractConstraints[_NT]):
    """Specific constraints pertaining to number-like types.

    Supports any type which follows the :py:class:`numbers.Number` protocol.
    """

    type: Type[_NT] = cast("Type[_NT]", int)
    """The builtin type for this constraint."""
    min: numbers.Real | None = None
    """The value inputs must be greater-than."""
    max: numbers.Real | None = None
    """The value inputs must be greater-than-or-equal-to."""
    inclusive_min: bool = False
    """The value inputs must be less-than."""
    inclusive_max: bool = False
    """The value inputs must be less-than-or-equal-to."""
    mul: numbers.Real | None = None
    """The value inputs must be a multiple-of."""


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class DecimalConstraints(NumberConstraints):
    """An extension of our :py:class:`NumberConstraints` for subclasses of :py:class:`decimal.Decimal`."""

    type = decimal.Decimal
    max_digits: numbers.Real | None = None
    """The maximum allowed digits for the input."""
    decimal_places: numbers.Real | None = None
    """The maximum allowed decimal places for the input."""


_MT = TypeVar("_MT", bound=Mapping)


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class MappingConstraints(AbstractConstraints[_MT]):
    """Constraints pertaining to a `Mapping` type.

    These constraints are for standard mapping types which do not have a pre-defined
    set of keys. If your type has a set of pre-defined keys, consider using a
    :py:class:`typing.TypedDict`.
    """

    type: Type[_MT] = cast("Type[_MT]", Mapping)
    min_items: int | None = None
    """The minimum number of items which must be present in this mapping."""
    max_items: int | None = None
    """The maximum number of items which may be present in this mapping."""
    key_pattern: re.Pattern = None
    """A regex pattern for which all keys must match."""
    values: AbstractConstraints | bool | None = None
    """Whether values not defined as required are allowed.

    May be a boolean, or more constraints which are applied to all additional values.
    """
    keys: AbstractConstraints | None = None
    """Constraints to apply to any additional keys not explicitly defined."""


_TT = TypeVar("_TT", str, bytes, bytearray)


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class TextConstraints(AbstractConstraints[_TT]):
    """Specific constraints pertaining to text-like types (`AnyStr` in Python).

    Currently supports :py:class:`str`, :py:class:`bytes`, :py:class:`bytearray`.
    """

    type: Type[_TT] = cast("Type[_TT]", str)
    """The supported text-types."""
    strip_whitespace: bool | None = None
    """Whether to strip any whitespace from the input."""
    min_length: int | None = None
    """The minimun length this input text must be."""
    max_length: int | None = None
    """The maximum length this input text may be."""
    curtail_length: int | None = None
    """Whether to cut off characters after the defined length."""
    regex: Pattern[Text] | None = None
    """A regex pattern which the input must match."""


_ET = TypeVar("_ET", enum.EnumMeta, Literal[...])  # type: ignore[misc]


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class EnumerationConstraints(AbstractConstraints[_ET]):
    """Constraints pertaining to an enumeration of values.

    May be subclass of :py:class:`enum.Enum` or a subscripted :py:class:`typing.Literal`
    """

    items: tuple[Any, ...] = ()
    """The enumerated values which are allowed."""


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class StructuredObjectConstraints(AbstractConstraints[_VT]):
    """Constraints for an object with a set number of fields.

    Any strongly-typed user-defined class with a set number of attributes is supported.

    Some examples from the standard library:

        - A :py:class:`tuple` of specific length and types (e.g., tuple[str, str]).
        - A :py:class:`collections.namedtuple` or :py:class:`typing.NamedTuple`.
        - A :py:class:`typing.TypedDict`.
        - A :py:class:`dataclasses.dataclass`.
    """

    fields: _FieldsT = dataclasses.field(default_factory=types.FrozenDict)
    """The fields on the user-type which will be validated."""
    required: tuple[str, ...] | tuple[int, ...] = ()


_FieldsT = Union[Mapping[str, AbstractConstraints], Mapping[int, AbstractConstraints]]


@util.slotted(dict=False, weakref=True)
@dataclasses.dataclass(frozen=True, repr=False)
class MultiConstraints(AbstractConstraints):
    constraints: tuple[AbstractConstraints, ...] = ()
    """The type constraints for which a value may be considered valid."""
    tag: util.TaggedUnion | None = None
    """An identifier used to locate the appropriate constraint for validation."""


class AbstractConstraintValidator(abc.ABC, Generic[_VT]):
    constraints: AbstractConstraints[_VT]
    validator: validators.ValidatorProtocol[_VT]

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}"
            f"(constraints={self.constraints!r}, validator={self.validator!r})>"
        )

    @overload
    def validate(
        self, value: Any, *, path: str = None, exhaustive: Literal[False]
    ) -> TypeGuard[_VT]:
        ...

    @overload
    def validate(
        self, value: Any, *, path: str = None, exhaustive: Literal[True]
    ) -> error.ConstraintValueError | TypeGuard[_VT]:
        ...

    @abc.abstractmethod
    def validate(self, value, *, path=None, exhaustive=False):
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
        ...

    def error(
        self,
        value: Any,
        *,
        path: str = None,
        raises: bool = True,
        **errors,
    ) -> error.ConstraintValueError:
        path = f"{path}:" if path is not None else "Given"
        err = error.ConstraintValueError(
            f"{path} value <{value!r}> fails constraints: {self.constraints}",
            path=path or "",
            constraints=self.constraints,
            **errors,
        )
        if raises:
            raise err from None
        return err


class DelayedConstraintValidator(AbstractConstraintValidator[_VT]):
    __slots__ = (
        "ref",
        "module",
        "localns",
        "nullable",
        "readonly",
        "writeonly",
        "name",
        "factory",
        "_cv" "_config",
    )

    def __init__(
        self,
        ref: ForwardRef | type,
        module: str,
        localns: Mapping,
        nullable: bool,
        readonly: bool,
        writeonly: bool,
        name: str | None,
        factory: Callable,
        **config,
    ):
        self.ref = ref
        self.module = module
        self.localns = localns
        self.nullable = nullable
        self.readonly = readonly
        self.writeonly = writeonly
        self.name = name
        self.factory = factory
        self._cv: AbstractConstraintValidator[_VT] = None
        self._config: dict = config
        self.constraints = cast(AbstractConstraints, DelayedConstraintsProxy(self))

    def _evaluate_reference(self) -> AbstractConstraintValidator[_VT]:
        type = self.ref
        if isinstance(self.ref, ForwardRef):
            globalns = sys.modules[self.module].__dict__.copy()
            try:
                type = evaluate_forwardref(self.ref, globalns or {}, self.localns or {})
            except NameError as e:  # pragma: nocover
                warnings.warn(
                    f"Counldn't resolve forward reference: {e}. "
                    f"Make sure this type is available in {self.module}."
                )
                type = Any  # type: ignore

        c = self.factory(type, nullable=self.nullable, name=self.name, **self._config)
        return c

    @property
    def cv(self) -> AbstractConstraintValidator[_VT]:
        if self._cv is None:
            self._cv = self._evaluate_reference()
        return self._cv

    def validate(self, value, *, path=None, exhaustive=False):
        return self.cv.validate(value, path=path, exhaustive=exhaustive)

    def __getattr__(self, item):
        return self.cv.__getattribute__(item)


class DelayedConstraintsProxy:
    __slots__ = ("dcv", "ref", "nullable", "_resolved")

    def __init__(self, dcv: DelayedConstraintValidator[_VT]):
        self.dcv = dcv
        self.ref = dcv.ref
        self.nullable = dcv.nullable
        self._resolved: AbstractConstraints[_VT] | None = None

    def __repr__(self):
        if not self._resolved:
            tname = getattr(self.ref, "__forward_arg__", self.ref)
            return f"(type={tname}, nullable={self.nullable})"
        return self._resolved.__repr__()

    @property
    def resolved(self) -> AbstractConstraints[_VT]:
        if self._resolved is None:
            self._resolved = self.dcv.cv.constraints
        return self._resolved

    @property
    def type(self):
        return self.ref


_ICV = TypeVar("_ICV")


class AbstractContainerValidator(AbstractConstraintValidator[_VT], Generic[_VT, _ICV]):
    __slots__ = ("constraints", "validator", "assertion", "items")
    items: _ICV

    def __init__(
        self,
        *,
        constraints: AbstractConstraints,
        validator: validators.ValidatorProtocol,
        assertion: Callable[[_VT], bool],
        items: _ICV,
    ):
        self.constraints = constraints
        self.validator = validator
        self.assertion = assertion
        self.items = items

    @abc.abstractmethod
    def itervalidate(self, value, *, path: str, exhaustive: TrueOrFalseT = False):
        ...
