from __future__ import annotations

import abc
import functools
from typing import AnyStr, NamedTuple

__all__ = (
    "get_precheck_cls",
    "TextPrecheckSelector",
    "BaseTextPrecheck",
    "StripPrecheck",
    "ShortenPrecheck",
    "ShortenAndStripPrecheck",
)


@functools.lru_cache(maxsize=4)
def get_precheck_cls(
    *, should_curtail_length: bool, should_strip_whitespace: bool
) -> type[BaseTextPrecheck] | None:
    selector = TextPrecheckSelector(
        should_curtail_length=should_curtail_length,
        should_strip_whitespace=should_strip_whitespace,
    )
    if not any(selector):
        return None
    return _PRECHECK_TRUTH_TABLE[selector]


class TextPrecheckSelector(NamedTuple):
    should_curtail_length: bool
    should_strip_whitespace: bool


class BaseTextPrecheck(abc.ABC):
    selector: TextPrecheckSelector

    __slots__ = ("max_length",)

    def __init__(self, *, max_length: int = None):
        self.max_length = max_length

    @abc.abstractmethod
    def __call__(self, value: AnyStr) -> AnyStr:
        ...


class ShortenAndStripPrecheck(BaseTextPrecheck):
    selector = TextPrecheckSelector(
        should_curtail_length=True,
        should_strip_whitespace=True,
    )

    def __call__(self, value: AnyStr) -> AnyStr:
        retval = value.strip()
        if len(retval) <= self.max_length:
            return retval
        retval = retval[: self.max_length]
        return retval


class StripPrecheck(BaseTextPrecheck):
    selector = TextPrecheckSelector(
        should_curtail_length=False,
        should_strip_whitespace=True,
    )

    def __call__(self, value: AnyStr) -> AnyStr:
        retval = value.strip()
        return retval


class ShortenPrecheck(BaseTextPrecheck):
    selector = TextPrecheckSelector(
        should_curtail_length=True,
        should_strip_whitespace=False,
    )

    def __call__(self, value: AnyStr) -> AnyStr:
        if len(value) <= self.max_length:
            return value
        retval = value[: self.max_length]
        return retval


_PRECHECK_TRUTH_TABLE: dict[TextPrecheckSelector, type[BaseTextPrecheck]] = {
    ShortenAndStripPrecheck.selector: ShortenAndStripPrecheck,
    StripPrecheck.selector: StripPrecheck,
    ShortenPrecheck.selector: ShortenPrecheck,
}
