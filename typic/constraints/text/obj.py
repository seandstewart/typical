#!/usr/bin/env python
import dataclasses
from typing import ClassVar, Type, Pattern, Optional, Union, Text

from .builder import _build_validator
from ..common import BaseConstraints


@dataclasses.dataclass(frozen=True, repr=False)
class TextConstraints(BaseConstraints):
    """Specific constraints pertaining to text-like types (``AnyStr`` in Python).

    Currently supports :py:class:`str` and :py:class:`bytes`.

    See Also
    --------
    :py:class:`~typic.types.constraints.common.Constraints`
    """

    type: ClassVar[Type[Union[str, bytes]]]
    """The supported text-types."""
    builder = _build_validator
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

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema = dict(
            minLength=self.min_length,
            maxLength=self.max_length,
            pattern=self.regex.pattern if self.regex else None,
        )
        if with_type:
            schema["type"] = "string"
        return {x: y for x, y in schema.items() if x is not None}


@dataclasses.dataclass(frozen=True, repr=False)
class StrConstraints(TextConstraints):
    """Constraints specifically for :py:class:`str`."""

    type: ClassVar[Type[str]] = str


@dataclasses.dataclass(frozen=True, repr=False)
class BytesConstraints(TextConstraints):
    """Constraints specifically for :py:class:`bytes`."""

    type: ClassVar[Type[bytes]] = bytes
