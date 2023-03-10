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

from typical import checks, classes, inspection
from typical.core import constants
from typical.core.annotations import TrueOrFalseT
from typical.core.constraints.core import error, types, validators

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

    def validate(
        self, value: Any, *, path: str = None, exhaustive: TrueOrFalseT = False
    ):
        # Run the validator on the given value,
        #   If valid is True, return.
        valid, vvalue = self.validator(value)
        if valid:
            return vvalue
        # Otherwise, exit with an error.
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

    def validate(
        self,
        value: Any,
        *,
        path: str = None,
        exhaustive: TrueOrFalseT = False,
        __nullables=constants.NULLABLES,
    ):
        # Determine the root name for this branch of the validation tree.
        name = path or self.constraints.type_qualname
        # Validate the structure and type of the input, but not contained values.
        # If the input is not valid at this stage, exit with an error.
        ivalid, instance = self.validator(value)
        if not ivalid:
            # Only raise an error if
            #   this is the root of the validation tree, or
            #   we don't care about getting an exhaustive error report
            raises = path is None or not exhaustive
            return self.error(value, raises=raises, path=name)

        # If the input is null, exit (only after structural validation).
        if value in __nullables:
            return value
        # Get the field validator iterator.
        #   This will validate each entry against its configured constraints.
        it = self.itervalidate(instance, path=name, exhaustive=exhaustive)
        # If we don't care about exhaustive checks,
        #   eagerly run validation and exit at first error.
        if not exhaustive:
            return self._exhaust(it)
        # Otherwise, track each error as it occurs.
        errors: dict[str, Exception] = {}
        gen = (
            e
            for e in it
            if (
                # If the return value from iteration is an error,
                #   collect it in the errors mapping
                #   rather than in the final output.
                not isinstance(e, error.ConstraintValueError)
                or errors.update(**{e.path: e})
            )
        )
        # We still "exhaust" the validation generator into the container type.
        # This will also fill the errors mapping, as defined above.
        validated = self._exhaust(gen)
        # If we have errors, exit with an error.
        if errors:
            return self.error(value, path=name, raises=not exhaustive, **errors)
        # Otherwise, return the validated value.
        return validated


class ArrayConstraintValidator(
    BaseContainerValidator[_AVT, types.AbstractConstraintValidator[_IVT]]
):
    constraints: types.ArrayConstraints
    validator: validators.ValidatorProtocol

    def itervalidate(
        self,
        value: Collection,
        *,
        path: str,
        exhaustive: TrueOrFalseT = False,
    ):
        # Pin the items validator to the local ns for faster lookup.
        ivalidator = self.items.validate
        # Pin the lazy repr function to the local ns for faster looup.
        irepr = classes.collectionrepr
        # Return an iterator which validates each entry in the array.
        yield from (
            ivalidator(entry, path=irepr(path, i), exhaustive=exhaustive)
            for i, entry in enumerate(value)
        )

    def _exhaust(self, it):
        return [*it]


_MT = TypeVar("_MT", bound=Mapping)


class BaseStructuredObjectConstraintValidator(
    types.AbstractContainerValidator[VT, _ICV]
):
    def validate_fields(
        self, value: Any, *, path: str, exhaustive: TrueOrFalseT = False
    ):
        # Collect the errors into a mapping of path->error
        errors: dict[str, error.ConstraintValueError] = {}
        # Grab the iterator validator for these fields.
        it = self.itervalidate(value, path=path, exhaustive=exhaustive)
        validated = {
            e[0]: e[1]
            for e in it
            if (
                # If the return value from iteration is an error,
                #   collect it in the errors mapping
                #   rather than in the final output.
                not isinstance(e, error.ConstraintValueError)
                or errors.update(**{e.path: e})
            )
        }
        # If we have errors, exit with an error.
        if errors:
            return self.error(value, path=path, raises=not exhaustive, **errors)
        # Otherwise, return the validated field->value map.
        return validated

    def validate(
        self, value: Any, *, path: str = None, exhaustive: TrueOrFalseT = False
    ):
        # Check if this is an instance of the target type. If so, exit.
        ivalid, instance = self.validator(value)
        if ivalid:
            return instance

        # Get the root name for this branch of the validation tree.
        name = path or self.constraints.type_qualname
        # Run the core assertions defined for this type
        #   (validate the structure of the given value, but not contained values)
        # If it doesn't meet structural requirements, exit with an error.
        avalid = self.assertion(value)
        if not avalid:
            # Only raise an error if
            #   this is the root of the validation tree, or
            #   we don't care about getting an exhaustive error report
            raises = path is None or not exhaustive
            return self.error(value, raises=raises, path=name)
        # Validate the contained values for all the pre-defined fields.
        return self.validate_fields(value, path=path, exhaustive=exhaustive)


class StructuredObjectConstraintValidator(
    BaseStructuredObjectConstraintValidator[
        VT, Mapping[str, types.AbstractConstraintValidator[_IVT]]
    ]
):
    constraints: types.StructuredObjectConstraints[VT]
    validator: _StructuredValidatorT[VT]
    items: Mapping[str, types.AbstractConstraintValidator[_IVT]]

    def itervalidate(self, value: Any, *, path: str, exhaustive: TrueOrFalseT = False):
        # Pin the field->validator mapping to the local ns for faster lookup.
        items = self.items
        # Pin the lazy path repr to the local ns for faster lookup.
        irepr = classes.joinedrepr
        # Default to iterating over the input value itself
        #   (handles arrays of field->value pairs)
        it = value
        if checks.ismappingtype(value.__class__):
            # If this is a mapping, use the ItemsView.
            it = value.items()  # type: ignore[attr-defined]
        # Return an iterator which validates the field-value
        #   against its defined constraints (if defined).
        yield from (
            (
                f,
                items[f].validate(v, path=irepr(path, f), exhaustive=exhaustive)
                if f in items
                else v,
            )
            for f, v in it
        )


class StructuredDictConstraintValidator(StructuredObjectConstraintValidator):
    def validate(
        self, value: Any, *, path: str = None, exhaustive: TrueOrFalseT = False
    ):
        # Get the root name for this branch of the validation tree.
        name = path or self.constraints.type_qualname
        # Check if the structure/type of this value
        ivalid, instance = self.validator(value)
        if not ivalid:
            # If the structure/type is invalid, exit with an error.
            # Only raise an error if
            #   this is the root of the validation tree, or
            #   we don't care about getting an exhaustive error report
            raises = path is None or not exhaustive
            return self.error(value, raises=raises, path=name)
        avalid = self.assertion(value)
        if not avalid:
            # Only raise an error if
            #   this is the root of the validation tree, or
            #   we don't care about getting an exhaustive error report
            raises = path is None or not exhaustive
            return self.error(value, raises=raises, path=name)

        # Validate the structure/type for each of the field->value pairs defined.
        return self.validate_fields(value, path=path, exhaustive=exhaustive)


_TT = TypeVar("_TT", bound=tuple)


class StructuredTupleConstraintValidator(
    BaseStructuredObjectConstraintValidator[
        _TT, "tuple[types.AbstractConstraintValidator, ...]"
    ]
):
    constraints: types.StructuredObjectConstraints[_TT]
    validator: _StructuredValidatorT[_TT]
    items: tuple[types.AbstractConstraintValidator, ...]

    def itervalidate(self, value: _TT, *, path: str, exhaustive: TrueOrFalseT = False):
        # Pin the repr for faster local lookup.
        irepr = classes.collectionrepr
        # Get an iterator of joining entries to their validators, if there is one.
        it = zip_longest(value, (cv.validate for cv in self.items), fillvalue=None)
        # Yield the validated entry (or the raw entry if there is no validator).
        yield from (
            (validate(v, path=irepr(path, i), exhaustive=exhaustive) if validate else v)
            for i, (v, validate) in enumerate(it)
        )


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
        self,
        field: _FT,
        value: Any,
        *,
        path: str,
        exhaustive: TrueOrFalseT = False,
    ):
        ...


class CompoundEntryValidator(AbstractEntryConstraintValidator[_FT, VT]):
    __slots__ = ("validators", "error")

    def __init__(self, *validators: AbstractEntryConstraintValidator):
        self.validators = validators
        self.error = self.validators[0].cv.error

    def __call__(
        self,
        field: _FT,
        value: VT,
        *,
        path: str,
        exhaustive: TrueOrFalseT = False,
    ):
        # Pin the default return value
        vfield, vvalue = field, value
        # Branch: exhaustive validation, check all nested values and gather errors.
        if exhaustive:
            # Initialize a mapping of path->error
            errors = {}
            # For each validator associated to this entry...
            for validator in self.validators:
                # Run the validation
                res = validator(vfield, vvalue, path=path, exhaustive=exhaustive)
                # If we have an error, add to the mapping and continue to the next,
                #   but don't re-assign the return value.
                if isinstance(res, error.ConstraintValueError):
                    errors[res.path] = res
                    continue
                # If validation succeeds, re-assign the return value
                #   (and target for the next validation)
                vfield, vvalue = res
            # If there are errors mapped, return (but do no raise!) a compound error.
            if errors:
                return self.error((field, value), path=path, raises=False, **errors)
            # Otherwise, return the fully-validated field and value.
            return vfield, vvalue
        # Branch: Early exit. If there is an error, it will be raised.
        for validator in self.validators:
            vfield, vvalue = validator(vfield, vvalue, path=path, exhaustive=exhaustive)
        return vfield, vvalue


class _KVMappingEntryValidator(AbstractEntryConstraintValidator[_FT, VT]):
    __slots__ = ("cv",)

    def __init__(self, cv: types.AbstractConstraintValidator):
        self.cv = cv


class FieldEntryValidator(_KVMappingEntryValidator[_FT, VT]):
    def __call__(
        self,
        field: _FT,
        value: VT,
        *,
        path: str,
        exhaustive: TrueOrFalseT = False,
    ):
        # Validate the field name.
        vfield = self.cv.validate(field, path=path, exhaustive=exhaustive)
        # If we got an error, return that
        if isinstance(vfield, error.ConstraintValueError):
            return vfield
        # Otherwise, return the validated field name.
        return vfield, value


class ValueEntryValidator(_KVMappingEntryValidator[_FT, VT]):
    def __call__(
        self,
        field: _FT,
        value: VT,
        *,
        path: str,
        exhaustive: TrueOrFalseT = False,
    ):
        # Validate the field value.
        vvalue = self.cv.validate(value, path=path, exhaustive=exhaustive)
        # If we got an error, return it.
        if isinstance(vvalue, error.ConstraintValueError):
            return vvalue
        # Otherwise, return the validated value.
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
        # Pin the validator to the localns for faster access.
        ivalidator = self.items
        # Pin the lazy repr to the localns for faster access.
        irepr = classes.collectionrepr
        # Yield the validation results for each field->value pair.
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
    constraints: types.MultiConstraints[VT]

    def __init__(
        self,
        constraints: types.MultiConstraints,
        constraint_validators: tuple[types.AbstractConstraintValidator, ...],
    ):
        self.constraints = constraints
        self.cvs = constraint_validators
        self.cvs_by_type = inspection.TypeMap(
            (inspection.origin(c.constraints.type), c) for c in self.cvs
        )
        self.cvs_by_tag = None
        if self.constraints.tag:
            self.cvs_by_tag = {
                value: self.cvs_by_type[inspection.origin(t)]
                for value, t in self.constraints.tag.types_by_values
            }

    def __repr__(self):
        return f"<{self.__class__.__name__}(constraints={self.constraints})>"


class SimpleMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(
        self, value: Any, *, path: str = None, exhaustive: TrueOrFalseT = False
    ) -> error.ConstraintValueError | VT:
        # Lookup the correct type validator with the input value's type.
        cv: types.AbstractConstraintValidator | None = self.cvs_by_type.get_by_parent(
            value.__class__
        )
        # If there is no validator, this is an error.
        if cv is None:
            return self.error(value, path=path, raises=not exhaustive)
        # Run the constraint validation for the value.
        return cv.validate(value, path=path, exhaustive=exhaustive)


class NullableMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(
        self, value: Any, *, path: str = None, exhaustive: TrueOrFalseT = False
    ) -> error.ConstraintValueError | VT:
        # If this value is null, we can exit early.
        if value is None:
            return value
        # Lookup the correct type validator with the input value's type.
        cv: types.AbstractConstraintValidator | None = self.cvs_by_type.get_by_parent(
            value.__class__
        )
        # If there is no validator, this is an error.
        if cv is None:
            return self.error(value, path=path, raises=not exhaustive)
        # Run the constraint validation for the value.
        return cv.validate(value, path=path, exhaustive=exhaustive)


class TaggedMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(
        self, value: Any, *, path: str = None, exhaustive: TrueOrFalseT = False
    ) -> error.ConstraintValueError | VT:
        # Attempt to retrieve the value associated to this union's "tag"
        #   (type-identifier attribute)
        tag = self.constraints.tag.tag
        tag_value = (
            value.get(tag, constants.empty)
            if isinstance(value, Mapping)
            else getattr(value, tag, constants.empty)
        )
        # If we got nothing, or an unrecognized value for the tagged union,
        #   return an error.
        if tag_value is constants.empty or tag_value not in self.cvs_by_tag:
            return self.error(value, path=path, raises=not exhaustive)

        # Otherwise, get the constraint validator associated to the tag value.
        cv: types.AbstractConstraintValidator[VT] = self.cvs_by_tag[tag_value]
        # And return the results of the validation.
        return cv.validate(value, path=path, exhaustive=exhaustive)


class TaggedNullableMultiConstraintValidator(AbstractMultiConstraintValidator[VT]):
    def validate(
        self, value: Any, *, path: str = None, exhaustive: TrueOrFalseT = False
    ) -> error.ConstraintValueError | VT:
        # Early return if the value is null.
        if value is None:
            return value
        # Attempt to retrieve the value associated to this union's "tag"
        #   (type-identifier attribute)
        tag = self.constraints.tag.tag
        tag_value = (
            value.get(tag, constants.empty)
            if isinstance(value, Mapping)
            else getattr(value, tag, constants.empty)
        )
        # If we got nothing, or an unrecognized value for the tagged union,
        #   return an error.
        if tag_value is constants.empty or tag_value not in self.cvs_by_tag:
            return self.error(value, path=path, raises=not exhaustive)

        # Otherwise, get the constraint validator associated to the tag value.
        cv: types.AbstractConstraintValidator[VT] = self.cvs_by_tag[tag_value]
        # And return the results of the validation.
        return cv.validate(value, path=path, exhaustive=exhaustive)


# endregion
