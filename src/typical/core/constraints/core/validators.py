from __future__ import annotations

import abc
import functools
import types
from typing import (
    Any,
    Callable,
    Literal,
    Mapping,
    NamedTuple,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from typical import checks, inspection
from typical.compat import Generic, Protocol

__all__ = (
    "get_validator_cls",
    "ValidatorProtocol",
    "AbstractValidator",
    "InstanceValidatorSelector",
    "NoOpInstanceValidator",
    "NotInstanceValidator",
    "IsInstanceValidator",
    "IsInstanceAssertionsValidator",
    "NotInstanceAssertionsValidator",
    "NullableIsInstanceValidator",
    "NullableNotInstanceValidator",
    "NullableNotInstanceAssertionsValidator",
    "NullableIsInstanceAssertionsValidator",
)

from typical.compat import TypeGuard
from typical.core import constants

# region: interface

VT = TypeVar("VT")
VT_co = TypeVar("VT_co", covariant=True)


@overload
def get_validator_cls(
    *,
    no_op: Literal[True],
    return_if_instance: bool,
    nullable: bool,
    has_assertion: bool,
) -> type[NoOpInstanceValidator]:
    ...


@overload
def get_validator_cls(
    *,
    no_op: Literal[False],
    return_if_instance: bool,
    nullable: bool,
    has_assertion: bool,
) -> type[AbstractInstanceValidator]:
    ...


@overload
def get_validator_cls(
    *,
    return_if_instance: bool,
    nullable: bool,
    has_assertion: bool,
) -> type[AbstractInstanceValidator]:
    ...


@functools.lru_cache(maxsize=None)
def get_validator_cls(
    *,
    no_op=False,
    return_if_instance,
    nullable,
    has_assertion,
):
    if no_op:
        return NoOpInstanceValidator
    selector = InstanceValidatorSelector(
        return_if_instance=return_if_instance,
        nullable=nullable,
        has_assertion=has_assertion,
    )
    return _VALIDATOR_TRUTH_TABLE[selector]


class ValidatorProtocol(Protocol[VT_co]):
    """The required signature for a type-validator."""

    def __call__(self, value: Any) -> ValidatorReturnT[VT_co]:
        ...


ValidatorReturnT = Tuple[TypeGuard[VT_co], Union[VT_co, Any]]


class AbstractValidator(abc.ABC, Generic[VT]):
    """The minimum interface for a Validator class.

    All validators should derive from this ABC.

    Due to the cost of attribute and global namespace lookups, Validators generate a
    closure on initialization which localizes all the necessary context for running
    validation into a single function, which is assigned to `__call__` on the
    validator instance. This results in significant performance optimization with
    minimal zero loss of debugging context.
    """

    NULLABLES = constants.NULLABLES
    __call__: ValidatorProtocol[VT]

    __slots__ = (
        "type",
        "__call__",
        "_type_name",
    )

    def __init__(self, type: Type[VT]):
        self.type = type
        self._type_name = inspection.get_name(type)
        self.__call__ = self._get_closure()

    @abc.abstractmethod
    def _get_closure(self) -> ValidatorProtocol[VT]:
        ...


# endregion
# region: instance validation


class InstanceValidatorSelector(NamedTuple):
    """A truth-table selector for the various instance-validator implementations."""

    return_if_instance: bool
    nullable: bool
    has_assertion: bool


class AbstractInstanceValidator(AbstractValidator[VT]):
    """The interface for all type-instance validators.

    Instance validators expect a "pre-check" routine and an "assertion" routine.
    These routines may be no-ops or null, which will determine the final behavior of the
    validator. The order of operations:

        1. If the type is nullable, check if the value is a null value. If null, return.
        2. Run the pre-check routine on the value.
           - This may result in a new output value.
        3. If an assertion is provided, run the assertion routine on the value.
    """

    selector: InstanceValidatorSelector

    __slots__ = (
        "precheck",
        "assertion",
    )

    def __repr__(self):
        return (
            "<("
            f"{self.__class__.__name__} "
            f"type={self._type_name}, "
            f"precheck={self.precheck!r}, "
            f"assertion={self.assertion!r}"
            ")>"
        )

    def __init__(
        self,
        *,
        type: Type[VT],
        precheck: Callable[[Any], VT],
        assertion: Callable[[VT], bool] = None,
    ):
        self.precheck = precheck
        self.assertion = assertion
        super().__init__(type=type)


class NullableIsInstanceAssertionsValidator(
    AbstractInstanceValidator[VT]
):  # what is this, Java?
    """Run the assigned "assertions" for this validation.

    Short-circuit if the item is null or *is* an instance of the assigned type.
    """

    selector = InstanceValidatorSelector(
        return_if_instance=True, nullable=True, has_assertion=True
    )

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def nullable_isinstance_assertions_validator(
            value: Any,
            *,
            __precheck=self.precheck,
            __nullables=self.NULLABLES,
            __type=self.type,
            __assertion=self.assertion,
            __isinstance=isinstance,
        ) -> ValidatorReturnT[VT]:
            if value in __nullables or __isinstance(value, __type):
                return True, value
            retval = __precheck(value)
            return __assertion(retval), retval

        return nullable_isinstance_assertions_validator


class NullableNotInstanceAssertionsValidator(AbstractInstanceValidator[VT]):
    """Run the assigned "assertions" for this validation.

    Short-circuit if the item is null or *is not* an instance of the assigned type.
    """

    selector = InstanceValidatorSelector(
        return_if_instance=False, nullable=True, has_assertion=True
    )

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def nullable_not_isinstance_assertions_validator(
            value: Any,
            *,
            __precheck=self.precheck,
            __nullables=self.NULLABLES,
            __type=self.type,
            __assertion=self.assertion,
            __isinstance=isinstance,
        ) -> ValidatorReturnT[VT]:
            if value in __nullables:
                return True, value

            if not __isinstance(value, __type):
                return False, value

            retval = __precheck(value)
            return __assertion(retval), retval

        return nullable_not_isinstance_assertions_validator


class IsInstanceAssertionsValidator(AbstractInstanceValidator[VT]):
    """Run the assigned "assertions" for this validation.

    Short-circuit if the item *is* an instance of the assigned type.
    """

    selector = InstanceValidatorSelector(
        return_if_instance=True, nullable=False, has_assertion=True
    )

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def isinstance_assertions_validator(
            value: Any,
            *,
            __precheck=self.precheck,
            __type=self.type,
            __assertion=self.assertion,
            __isinstance=isinstance,
        ) -> ValidatorReturnT[VT]:
            if __isinstance(value, __type):
                return True, value

            retval = __precheck(value)
            return __assertion(retval), retval

        return isinstance_assertions_validator


class NullableIsInstanceValidator(AbstractInstanceValidator[VT]):
    """Check if the item is null (None or ...) or an instance of the assigned type."""

    selector = InstanceValidatorSelector(
        return_if_instance=True, nullable=True, has_assertion=False
    )

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def nullable_isinstance_assertions_validator(
            value: Any,
            *,
            __precheck=self.precheck,
            __nullables=self.NULLABLES,
            __type=self.type,
            __isinstance=isinstance,
        ) -> ValidatorReturnT[VT]:
            if value in __nullables:
                return True, value

            retval = __precheck(value)
            return __isinstance(retval, __type), retval

        return nullable_isinstance_assertions_validator


class NotInstanceAssertionsValidator(AbstractInstanceValidator[VT]):
    """Run the assigned "assertions" for this validation.

    Short-circuit if the item *is not* an instance of the assigned type.
    """

    selector = InstanceValidatorSelector(
        return_if_instance=False, nullable=False, has_assertion=True
    )

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def not_instance_assertions_validator(
            value: Any,
            *,
            __precheck=self.precheck,
            __type=self.type,
            __assertion=self.assertion,
            __isinstance=isinstance,
        ) -> ValidatorReturnT[VT]:
            if not __isinstance(value, self.type):
                return False, value

            retval = __precheck(value)
            return __assertion(retval), retval

        return not_instance_assertions_validator


# This check is commutative with IS.
class NullableNotInstanceValidator(NullableIsInstanceValidator[VT]):
    """Check if the item is null (None or ...) or an instance of the assigned type."""

    selector = InstanceValidatorSelector(
        return_if_instance=False, nullable=True, has_assertion=False
    )


class IsInstanceValidator(AbstractInstanceValidator[VT]):
    """Simply check whether an item is an instance of the assigned type."""

    selector = InstanceValidatorSelector(
        return_if_instance=True, nullable=False, has_assertion=False
    )

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def isinstance_validator(
            value: Any,
            *,
            __precheck=self.precheck,
            __type=self.type,
            __isinstance=isinstance,
        ) -> ValidatorReturnT[VT]:
            if __isinstance(value, __type):
                retval = __precheck(value)
                return True, retval

            return False, value

        return isinstance_validator


# This check is commutative with IS.
class NotInstanceValidator(IsInstanceValidator[VT]):
    """Simply check whether an item is an instance of the assigned type."""

    selector = InstanceValidatorSelector(
        return_if_instance=False, nullable=False, has_assertion=False
    )


class NoOpInstanceValidator(NotInstanceValidator[VT]):
    """A No-Op Validator performs no validation beyond running the assigned pre-check."""

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def no_op_validator(
            value: Any, *, __precheck=self.precheck
        ) -> ValidatorReturnT[VT]:
            return True, __precheck(value)

        return no_op_validator


# endregion
# region: one-of validation


class OneOfValidator(AbstractValidator[VT]):
    """A One-Of Validator checks whether the given value is a member of a set of values."""

    __slots__ = ("type", "items", "items_tuple")
    items: frozenset | tuple
    items_tuple: tuple

    def __repr__(self) -> str:
        return (
            "<("
            f"{self.__class__.__name__} "
            f"type={self._type_name}, "
            f"items={self.items_tuple!r}"
            f")>"
        )

    def __init__(self, *items: VT, type: Type[VT]):

        try:
            self.items = frozenset(items)
        except TypeError:
            self.items = items
        self.items_tuple = items
        super().__init__(type=type)

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def items_validator(
            value: Any,
            *,
            __hashable=checks.ishashable,
            __items=self.items,
            __items_tuple=self.items_tuple,
        ) -> ValidatorReturnT[VT]:
            if __hashable(value):
                return value in __items, value
            return value in __items_tuple, value

        return items_validator


class NullableOneOfValidator(OneOfValidator[VT]):
    """Similar to the :py:class:`~typic.constraints.core.validators.OneOfValidator,

    but allows for "nullable" (e.g., None).
    """

    def _get_closure(self) -> ValidatorProtocol[VT]:
        def nullable_items_validator(
            value: Any,
            *,
            __hashable=checks.ishashable,
            __items=self.items,
            __items_tuple=self.items_tuple,
            __nullable=self.NULLABLES,
        ) -> ValidatorReturnT[VT]:
            if value in __nullable:
                return True, value
            if __hashable(value):
                return value in __items, value
            return value in __items_tuple, value

        return nullable_items_validator


# endregion


class NoOpPrecheck(types.SimpleNamespace):
    """The No-Op pre-check is a zero-operation passthrough."""

    def __call__(self, value: VT) -> VT:
        return value


_VALIDATOR_TRUTH_TABLE: Mapping[InstanceValidatorSelector, type[AbstractValidator]] = {
    NullableIsInstanceAssertionsValidator.selector: NullableIsInstanceAssertionsValidator,
    NullableNotInstanceAssertionsValidator.selector: NullableNotInstanceAssertionsValidator,
    IsInstanceAssertionsValidator.selector: IsInstanceAssertionsValidator,
    NotInstanceAssertionsValidator.selector: NotInstanceAssertionsValidator,
    NullableIsInstanceValidator.selector: NullableIsInstanceValidator,
    NullableNotInstanceValidator.selector: NullableNotInstanceValidator,
    IsInstanceValidator.selector: IsInstanceValidator,
    NotInstanceValidator.selector: NotInstanceValidator,
}
