from __future__ import annotations

import ast
from datetime import date, datetime, time, timedelta
from typing import Any, Tuple

import pendulum

from typical.compat import lru_cache
from typical.core import json

__all__ = (
    "fromstr",
    "isoformat",
    "safe_eval",
)


# @lru_cache(maxsize=2000, typed=True)
def safe_eval(string: str) -> Tuple[bool, Any]:
    """Try a few methods to evaluate a string and get the correct Python data-type.

    Return the result and an indicator for whether we could do anything with it.

    Examples
    --------
    >>> safe_eval('{"foo": null}')
    (True, {'foo': None})

    Parameters
    ----------
    string
        The string to attempt to evaluate into a valid Python data-structure or object

    Returns
    -------
    processed :
        Whether we successfully evaluated the string
    result :
        The final result of the operation
    """
    try:
        result, processed = ast.literal_eval(string), True
    except (TypeError, ValueError, SyntaxError):
        try:
            result, processed = json.loads(string), True
        except (TypeError, ValueError, SyntaxError):
            result, processed = string, False

    return processed, result


@lru_cache(maxsize=2_000)
def fromstr(string: str | bytes) -> Any:
    try:
        return json.loads(string)
    except (TypeError, ValueError, SyntaxError):
        return string


@lru_cache(maxsize=100_000)
def isoformat(t: date | datetime | time | timedelta) -> str:
    if isinstance(t, (date, datetime, time)):
        return t.isoformat()
    d: pendulum.Duration = (
        t
        if isinstance(t, pendulum.Duration)
        else pendulum.duration(
            days=t.days,
            seconds=t.seconds,
            microseconds=t.microseconds,
        )
    )

    periods: list[tuple[str, int]] = [
        ("Y", d.years),
        ("M", d.months),
        ("D", d.remaining_days),
    ]
    period: str = "P"
    for sym, val in periods:
        period += f"{val}{sym}"
    times: list[tuple[str, int]] = [
        ("H", d.hours),
        ("M", d.minutes),
        ("S", d.remaining_seconds),
    ]
    time_: str = "T"
    for sym, val in times:
        time_ += f"{val}{sym}"
    if d.microseconds:
        time_ = time_[:-1]
        time_ += f".{d.microseconds:06}S"
    return period + time_
