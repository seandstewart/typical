from __future__ import annotations

import enum
import inspect
from functools import partial
from typing import Union, Type, Any, TypeVar, Callable, Generic, Mapping

import inflection

DEFAULT_ENCODING = "utf-8"
EMPTY = inspect.Signature.empty
ORIG_SETTER_NAME = "__setattr_original__"
POSITIONAL_ONLY = inspect.Parameter.POSITIONAL_ONLY
POSITIONAL_OR_KEYWORD = inspect.Parameter.POSITIONAL_OR_KEYWORD
KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY
RETURN_KEY = "return"
SCHEMA_NAME = "__json_schema__"
SELF_NAME = "self"
SERDE_ATTR = "__serde__"
SERDE_FLAGS_ATTR = "__serde_flags__"
TOO_MANY_POS = "too many positional arguments"
TYPIC_ANNOS_NAME = "__typic_annotations__"
VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL
VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD
KWD_KINDS = {VAR_KEYWORD, KEYWORD_ONLY}
POS_KINDS = {VAR_POSITIONAL, POSITIONAL_ONLY}
AnyOrTypeT = Union[Type, Any]
ObjectT = TypeVar("ObjectT")
"""A generic alias for an object."""
OriginT = TypeVar("OriginT")
"""A type alias for an instance of the type associated to a Coercer."""
CaseTransformerT = Callable[[str], str]
"""A callable which transforms a string from one case-style to another."""


class Case(str, enum.Enum):
    """An enumeration of the supported case-styles for field names."""

    CAMEL = "camelCase"
    SNAKE = "snake_case"
    PASCAL = "PascalCase"
    KEBAB = "kebab-case"
    DOT = "dot.case"
    UPPER_KEBAB = "UPPER-KEBAB-CASE"
    UPPER_DOT = "UPPER.DOTA.CASE"

    @property
    def transformer(self) -> CaseTransformerT:
        return _TRANSFORMERS[self]


def upper_kebab_case(s: str) -> str:
    return inflection.dasherize(s).upper()


def upper_dot_case(s: str) -> str:
    return inflection.parameterize(s, separator=".").upper()


_TRANSFORMERS: Mapping[Case, CaseTransformerT] = {
    Case.CAMEL: partial(inflection.camelize, uppercase_first_letter=False),
    Case.SNAKE: inflection.underscore,
    Case.PASCAL: inflection.camelize,
    Case.KEBAB: inflection.dasherize,
    Case.DOT: partial(inflection.parameterize, separator="."),
    Case.UPPER_KEBAB: upper_kebab_case,
    Case.UPPER_DOT: upper_dot_case,
}
T = TypeVar("T")


class ReadOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be read-only."""

    pass


class WriteOnly(Generic[T]):
    """A type annotation to indicate a field is meant to be write-only."""

    pass
