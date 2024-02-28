from __future__ import annotations

import enum
import functools
from typing import Callable, Mapping

import inflection

__all__ = ("Case", "transformer", "transform")


def transformer(*, case: Case) -> CaseTransformerT:
    return _TRANSFORMERS[case]


def transform(string: str, *, case: Case) -> str:
    return transformer(case=case)(string)


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
        return transformer(case=self)


def upper_kebab_case(s: str) -> str:
    return inflection.dasherize(s).upper()


def upper_dot_case(s: str) -> str:
    return inflection.parameterize(s, separator=".").upper()


CaseTransformerT = Callable[[str], str]
"""A callable which transforms a string from one case-style to another."""


_TRANSFORMERS: Mapping[Case, CaseTransformerT] = {
    Case.CAMEL: functools.partial(inflection.camelize, uppercase_first_letter=False),
    Case.SNAKE: inflection.underscore,
    Case.PASCAL: inflection.camelize,
    Case.KEBAB: inflection.dasherize,
    Case.DOT: functools.partial(inflection.parameterize, separator="."),
    Case.UPPER_KEBAB: upper_kebab_case,
    Case.UPPER_DOT: upper_dot_case,
}
