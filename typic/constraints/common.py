#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import re
from typing import Callable, Any, ClassVar, Type, Tuple, List, Dict, TypeVar

from typic import gen, util
from .error import ConstraintValueError

__all__ = ("BaseConstraints", "Validator")

VT = TypeVar("VT")
"""A generic type-var for values passed to a validator."""
Validator = Callable[[VT], Tuple[bool, VT]]
"""The expected signature of a value validator."""
Checks = List[str]
Context = Dict[str, Any]


@dataclasses.dataclass(frozen=True, repr=False)
class BaseConstraints:
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

    def __post_init__(self):
        # Compile the validator
        self.validator

    __repr = util.cached_property(util.filtered_repr)

    def __repr__(self) -> str:
        return self.__repr

    @util.cached_property
    def __str(self) -> str:
        fields = [f"type={self.type.__name__}"]
        for f in dataclasses.fields(self):
            val = getattr(self, f.name)
            if (val or val in {False, 0}) and f.repr:
                fields.append(f"{f.name}={val!r}")
        return f"({', '.join(fields)})"

    def __str__(self) -> str:
        return self.__str

    def _build_validator(
        self, func: gen.Block
    ) -> Tuple[Checks, Context]:  # pragma: nocover
        raise NotImplementedError

    def _get_validator_name(self) -> str:
        return re.sub(r"\W+", "_", f"validator_{self}")

    @staticmethod
    def _set_return(func: gen.Block, checks: Checks, context: Context):
        if checks:
            check = " and ".join(checks)
            func.l(f"valid = {check}", **context)
            func.l("return valid, val")
        else:
            func.l("return True, val", **context)

    def _compile_validator(self) -> Validator:
        func_name = self._get_validator_name()
        with gen.Block() as main:
            with main.f(func_name, main.param("val", annotation=self.type)) as f:
                # Short-circuit validation if the value isn't the correct type.
                line = f"if not isinstance(val, {util.origin(self.type).__name__}):"
                with f.b(line) as b:
                    b.l("return False, val")
                checks, context = self._build_validator(f)
                # Write the line.
                self._set_return(func=f, checks=checks, context=context)
        return main.compile(name=func_name)

    @util.cached_property
    def validator(self) -> Validator:
        """Accessor for the generated validator.

        Validators are generated code based upon the constraint syntax provided.
        The resulting code is about as optimized as you can get in Python, since
        the constraint values are localized to the validator and only the checks
        that the validator performs are the checks that were set. There is no
        computation time wasted on deciding whether or not to perform a validation.
        """
        validator = self._compile_validator()
        return validator

    def validate(self, value: VT) -> VT:
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
            raise ConstraintValueError(
                f"Given value <{value!r}> fails constraints: {self}"
            ) from None
        return value

    def for_schema(self, *, with_type: bool = False) -> dict:  # pragma: nocover
        """Output the configured constraints in JSON Schema syntax.

        Notes
        -----
        Inheritors should exclude fields which are not set.
        """
        raise NotImplementedError
