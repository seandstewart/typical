from __future__ import annotations

import abc
from itertools import zip_longest
from typing import (
    Any,
    Collection,
    Generic,
    Iterable,
    Literal,
    Mapping,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from typic import checks, util
from typic.core.annotations import TrueOrFalseT
from typic.core.constraints.core import error, types, validators

__all__ = (
    # ABCs
    "AbstractEntryConstraintValidator",
    "AbstractMultiConstraintValidator",
    # Top-level ConstraintValidators
    "ConstraintValidator",
    "ArrayConstraintValidator",
    "MappingConstraintValidator",
    "SimpleMultiConstraintValidator",
    "NullableMultiConstraintValidator",
    "TaggedMultiConstraintValidator",
    "TaggedNullableMultiConstraintValidator",
    # Entry/Nested ConstraintValidators
    "CompoundEntryValidator",
    "FieldEntryValidator",
    "ValueEntryValidator",
)

# region: interface

VT = TypeVar("VT")

_ICV = TypeVar("_ICV")

_ET = TypeVar("_ET", bound=error.ConstraintValueError)

# endregion
# region: simple constraint validation


class ConstraintValidator(types.AbstractConstraintValidator[VT]):
    __slots__ = ("constraints", "validator")

    def __init__(
        self,
        *,
        constraints: types.AbstractConstraints,
        validator: validators.ValidatorProtocol,
    ):
        self.constraints = constraints
        self.validator = validator

    def validate(self, value, *, path=None, exhaustive=False):
        valid, vvalue = self.validator(value)
        if valid:
            return vvalue

        return self.error(value, path=path, raises=not exhaustive)


# endregion
# region: container-type constraint validation

_IV = TypeVar("_IV")
_IVT = TypeVar("_IVT")
_AVT = TypeVar("_AVT", bound=Collection)


class BaseContainerValidator(types.AbstractContainerValidator[_AVT, _IV]):
    @abc.abstractmethod
    def _exhaust(self, it: Iterable) -> _AVT:
        ...

    def validate(self, value, *, path=None, exhaustive=False):
        name = path or self.constraints.type_qualname
        ivalid, instance = self.validator(value)
        if not ivalid:
            return self.error(value, raises=path is None or not exhaustive, path=name)
        it = self.itervalidate(instance, path=name, exhaustive=exhaustive)
        if not exhaustive:
            return self._exhaust(it)

        errors: dict[str, Exception] = {}
        validated = self._exhaust(
            e
            for e in it
            if (
                not isinstance(e, error.ConstraintValueError)
                or errors.update(**{e.path: e})
            )
        )
        if errors:
            return self.error(value, path=name, raises=not exhaustive, **errors)
        return validated


class ArrayConstraintValidator(
    BaseContainerValidator[_AVT, types.AbstractConstraintValidator[_IVT]]
):
    constraints: types.ArrayConstraints
    validator: validators.ValidatorProtocol

    def itervalidate(
        self, value: Collection, *, path: str, exhaustive: Literal[True, False] = False
    ):
        ivalidator = self.items.validate
        irepr = util.collectionrepr
        entry: Any
        yield from (
            ivalidator(entry, path=irepr(path, i), exhaustive=exhaustive)
            for i, entry in enumerate(value)
        )

    def _exhaust(self, it):
        return [*it]


_MT = TypeVar("_MT", bound=Mapping)


class StructuredObjectConstraintValidator(
    types.AbstractContainerValidator[
        VT, Mapping[str, types.AbstractConstraintValidator[_IVT]]
    ]
):
    constraints: types.StructuredObjectConstraints[VT]
    validator: _StructuredValidatorT[VT]
    items: Mapping[str, types.AbstractConstraintValidator[_IVT]]

    def itervalidate(self, value, *, path: str, exhaustive: TrueOrFalseT = False):
        items = self.items
        irepr = util.joinedrepr
        it = value
        if checks.ismappingtype(value.__class__):
            it = value.items()  # type: ignore[attr-defined]
        yield from (
            (
                f,
                items[f].validate(v, path=irepr(path, f), exhaustive=exhaustive)
                if f in items
                else v,
            )
            for f, v in it
        )

    def validate(self, value, *, path=None, exhaustive=False):
        name = path or self.constraints.type_qualname
        ivalid, instance = self.validator(value)
        if ivalid:
            return instance
        avalid = self.assertion(value)
        if not avalid:
            return self.error(value, raises=path is None or not exhaustive, path=name)

        errors = {}
        it = self.itervalidate(value, path=path, exhaustive=exhaustive)
        validated = {
            e[0]: e[1]
            for e in it
            if (
                not isinstance(e, error.ConstraintValueError)
                or errors.update(**{e.path: e})
            )
        }
        if errors:
            return self.error(value, path=name, exhaustive=exhaustive, **errors)
        return validated


_TT = TypeVar("_TT", bound=tuple)


class StructuredTupleConstraintValidator(
    types.AbstractContainerValidator[
        _TT, "tuple[types.AbstractConstraintValidator, ...]"
    ]
):
    constraints: types.StructuredObjectConstraints[_TT]
    validator: _StructuredValidatorT[_TT]
    items: tuple[types.AbstractConstraintValidator, ...]

    def itervalidate(self, value: _TT, *, path: str, exhaustive: TrueOrFalseT = False):
        irepr = util.collectionrepr
        it = zip_longest(value, (cv.validate for cv in self.items), fillvalue=None)
        yield from (
            (validate(v, path=irepr(path, i), exhaustive=exhaustive) if validate else v)
            for i, (v, validate) in enumerate(it)
        )

    def validate(self, value, *, path=None, exhaustive=False):
        name = path or self.constraints.type_qualname
        ivalid, instance = self.validator(value)
        if not ivalid:
            return self.error(value, raises=path is None or not exhaustive, path=name)
        avalid = self.assertion(instance)
        if not avalid:
            return self.error(value, raises=path is None or not exhaustive, path=name)

        errors = {}
        it = (
            e
            for e in self.itervalidate(instance, path=path, exhaustive=exhaustive)
            if (
                not isinstance(e, error.ConstraintValueError)
                or errors.update(**{e.path: e})
            )
        )
        validated = (*it,)
        if errors:
            return self.error(value, path=name, exhaustive=exhaustive, **errors)
        return validated


_StructuredValidatorT = Union[
    validators.IsInstanceValidator[VT], validators.NullableIsInstanceValidator[VT]
]


# endregion
# region: container-type entry constraint validation

_FT = TypeVar("_FT", str, int)


class AbstractEntryConstraintValidator(abc.ABC, Generic[_FT, VT]):
    cv: types.AbstractConstraintValidator

    @overload
    def __call__(self, field: _FT, value: Any, *, path: str) -> tuple[_FT, VT]:
        ...

    @overload
    def __call__(
        self, field: _FT, value: Any, *, path: str, exhaustive: Literal[False]
    ) -> tuple[_FT, VT]:
        ...

    @overload
    def __call__(
        self, field: _FT, value: Any, *, path: str, exhaustive: Literal[True]
    ) -> _EntryCVReturnT:
        ...

    @abc.abstractmethod
    def __call__(
        self, field: _FT, value: Any, *, path: str, exhaustive: TrueOrFalseT = False
    ):
        ...


class CompoundEntryValidator(AbstractEntryConstraintValidator[_FT, VT]):
    __slots__ = ("validators", "error")

    def __init__(self, *validators: AbstractEntryConstraintValidator):
        self.validators = validators
        self.error = self.validators[0].cv.error

    def __call__(
        self, field: _FT, value: VT, *, path: str, exhaustive: TrueOrFalseT = False
    ):
        vfield, vvalue = field, value
        if exhaustive:
            errors = {}
            for validator in self.validators:
                res = validator(vfield, vvalue, path=path, exhaustive=exhaustive)
                if isinstance(res, error.ConstraintValueError):
                    errors[res.path] = res
                    continue
                vfield, vvalue = res
            if errors:
                return self.error((field, value), path=path, raises=False, **errors)
            return vfield, vvalue

        for validator in self.validators:
            vfield, vvalue = validator(vfield, vvalue, path=path, exhaustive=exhaustive)
        return vfield, vvalue


class _KVMappingEntryValidator(AbstractEntryConstraintValidator[_FT, VT]):
    __slots__ = ("cv",)

    def __init__(self, cv: types.AbstractConstraintValidator):
        self.cv = cv


class FieldEntryValidator(_KVMappingEntryValidator[_FT, VT]):
    def __call__(
        self, field: _FT, value: VT, *, path: str, exhaustive: TrueOrFalseT = False
    ):
        vfield = self.cv.validate(field, path=path, exhaustive=exhaustive)
        if exhaustive and isinstance(vfield, error.ConstraintValueError):
            return vfield
        return vfield, value


class ValueEntryValidator(_KVMappingEntryValidator[_FT, VT]):
    def __call__(
        self, field: _FT, value: VT, *, path: str, exhaustive: TrueOrFalseT = False
    ):
        vvalue = self.cv.validate(value, path=path, exhaustive=exhaustive)
        if exhaustive and isinstance(vvalue, error.ConstraintValueError):
            return vvalue
        return field, vvalue


_EntryCVReturnT = Union[Tuple[_FT, VT], _ET]


class MappingConstraintValidator(
    BaseContainerValidator[_MT, AbstractEntryConstraintValidator[_FT, _IVT]]
):
    constraints: types.MappingConstraints[_MT]
    validator: validators.ValidatorProtocol[_MT]

    def _exhaust(self, it):
        return dict(it)

    def itervalidate(self, value: _MT, *, path: str, exhaustive: TrueOrFalseT = False):
        ivalidator = self.items
        irepr = util.collectionrepr
        yield from (
            ivalidator(f, v, path=irepr(path, f), exhaustive=exhaustive)
            for f, v in value.items()
        )


# endregion
# region: type-union constraint validation


class AbstractMultiConstraintValidator(types.AbstractConstraintValidator, Generic[VT]):
    __slots__ = (
        "constraints",
        "cvs",
        "cvs_by_type",
        "cvs_by_tag",
    )

    def __init__(
        self,
        constraints: types.MultiConstraints,
        constraint_validators: tuple[types.AbstractConstraintValidator, ...],
    ):
        self.constraints = constraints
        self.cvs = constraint_validators
        self.cvs_by_type = util.TypeMap(
            (util.origin(c.constraints.type), c) for c in self.cvs
        )
        self.cvs_by_tag = None
        if self.constraints.tag:
            self.cvs_by_tag = {
                value: self.cvs_by_type[util.origin(t)]
                for value, t in self.constraints.tag.types_by_values
            }


class SimpleMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(self, value, *, path=None, exhaustive=False):
        cv: ConstraintValidator = self.cvs_by_type.get_by_parent(value.__class__)
        return cv.validate(value, path=path, exhaustive=exhaustive)


class NullableMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(self, value, *, path=None, exhaustive=False):
        if value is None:
            return value
        cv: ConstraintValidator = self.cvs_by_type.get_by_parent(value.__class__)
        return cv.validate(value, path=path, exhaustive=exhaustive)


class TaggedMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(self, value, *, path=None, exhaustive=False):
        tag_value = (
            value.get(self.constraints.tag, ...)
            if isinstance(value, Mapping)
            else getattr(value, self.constraints.tag, ...)
        )
        if tag_value is ... or tag_value not in self.cvs_by_tag:
            return self.error(value, path=path, raises=not exhaustive)

        cv: ConstraintValidator = self.cvs_by_tag[tag_value]
        return cv.validate(value, path=path, exhaustive=exhaustive)


class TaggedNullableMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(self, value, *, path=None, exhaustive=False):
        if value is None:
            return value

        tag_value = (
            value.get(self.constraints.tag, ...)
            if isinstance(value, Mapping)
            else getattr(value, self.constraints.tag, ...)
        )
        if tag_value is ... or tag_value not in self.cvs_by_tag:
            return self.error(value, path=path, raises=not exhaustive)

        cv: ConstraintValidator = self.cvs_by_tag[tag_value]
        return cv.validate(value, path=path, exhaustive=exhaustive)


# endregion
