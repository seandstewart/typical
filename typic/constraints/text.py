from __future__ import annotations

import dataclasses
from typing import ClassVar, Type, Pattern, Optional, Union, Text

from typic import gen, util
from .common import BaseConstraints, ContextT, AssertionsT


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class TextConstraints(BaseConstraints):
    """Specific constraints pertaining to text-like types (`AnyStr` in Python).

    Currently supports :py:class:`str` and :py:class:`bytes`.

    See Also
    --------
    :py:class:`~typic.types.constraints.common.Constraints`
    """

    type: ClassVar[Type[Union[str, bytes]]]
    """The supported text-types."""
    strip_whitespace: Optional[bool] = None
    """Whether to strip any whitespace from the input."""
    min_length: Optional[int] = None
    """The minimun length this input text must be."""
    max_length: Optional[int] = None
    """The maximum length this input text may be."""
    curtail_length: Optional[int] = None
    """Whether to cut off characters after the defined length."""
    regex: Optional[Pattern[Text]] = None
    """A regex pattern which the input must match."""

    def _get_assertions(self) -> AssertionsT:
        asserts = []
        if self.max_length is not None:
            asserts.append(f"size <= {self.max_length}")
        if self.min_length is not None:
            asserts.append(f"size >= {self.min_length}")
        if self.regex is not None:
            asserts.append(f"__pattern.match({self.VALUE})")
        return asserts

    def _build_validator(
        self, func: gen.Block, context: ContextT, assertions: AssertionsT
    ) -> ContextT:
        # Set up the local env.
        if self.curtail_length is not None:
            func.l(f"{self.VALUE} = {self.VALUE}[:{self.curtail_length}]")
        if self.strip_whitespace:
            func.l(f"{self.VALUE} = {self.VALUE}.strip()")
        if {self.min_length, self.max_length} != {None, None}:
            func.l(f"size = len({self.VALUE})")
        BaseConstraints._build_validator(
            self, func, context=context, assertions=assertions
        )
        # Build the validation.
        if self.regex is not None:
            context.update(__pattern=self.regex)

        return context

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema = dict(
            title=self.name,
            minLength=self.min_length,
            maxLength=self.max_length,
            pattern=self.regex.pattern if self.regex else None,
        )
        if with_type:
            schema["type"] = "string"
        return {x: y for x, y in schema.items() if x is not None}


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class StrConstraints(TextConstraints):
    """Constraints specifically for :py:class:`str`."""

    type: ClassVar[Type[str]] = str


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class BytesConstraints(TextConstraints):
    """Constraints specifically for :py:class:`bytes`."""

    type: ClassVar[Type[bytes]] = bytes
