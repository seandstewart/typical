from __future__ import annotations

import ast
import datetime
from typing import Any, Tuple

import pendulum

from typical.compat import lru_cache
from typical.core import json

__all__ = (
    "fromstr",
    "isoformat",
    "safe_eval",
)


@lru_cache(maxsize=2_000)
def safe_eval(string: str) -> Tuple[bool, Any]:
    """Try a few methods to evaluate a string and get the correct Python data-type.

    Return the result and an indicator for whether we could do anything with it.

    Examples:
        >>> safe_eval('{"foo": null}')
        (True, {'foo': None})

    Args:
        string: The string to attempt to evaluate into a valid Python data-structure or object

    Returns:
        processed: Whether we successfully evaluated the string
        result: The final result of the operation
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
def isoformat(t: datetime.date | datetime.time | datetime.timedelta) -> str:
    """Format any date/time object into an ISO-8601 string.

    Notes:
        While the standard library includes `isoformat()` methods for
        :py:class:`datetime.date`, :py:class:`datetime.time`, &
        :py:class:`datetime.datetime`, they do not include a method for serializing
        :py:class:`datetime.timedelta`, even though durations are included in the
        ISO 8601 specification. This function fills that gap.

    Examples:
        >>> import datetime
        >>> from typical.core import desers
        >>> desers.isoformat(datetime.date(1970, 1, 1))
        '1970-01-01'
        >>> desers.isoformat(datetime.time())
        '00:00:00'
        >>> desers.isoformat(datetime.datetime(1970, 1, 1))
        '1970-01-01T00:00:00'
        >>> desers.isoformat(datetime.timedelta())
        'P0Y0M0DT0H0M0.000000S'
    """
    if isinstance(t, (datetime.date, datetime.time)):
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
    period = (
        f"P{d.years}Y{d.months}M{d.remaining_days}D"
        f"T{d.hours}H{d.minutes}M{d.remaining_seconds}.{d.microseconds:06}S"
    )
    return period
