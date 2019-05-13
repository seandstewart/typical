#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import ast
import functools
from typing import Tuple, Any


def _get_loader():  # nocover
    try:
        import yaml
        import re

        yaml.reader.Reader.NON_PRINTABLE = re.compile(
            r"[^\x09\x0A\x0D\x20-\x7E\x85\xA0-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]"
        )
        loads = getattr(yaml, "full_load", getattr(yaml, "load"))
        return loads, yaml.error.YAMLError

    except ImportError:
        import json

        return json.loads, json.JSONDecodeError


load, LoaderError = _get_loader()


@functools.lru_cache(typed=True)
def safe_eval(string: str) -> Tuple[bool, Any]:
    """Try a few methods to evaluate a string and get the correct Python data-type.

    Return the result and an indicator for whether we could do anything with it.

    Examples
    --------
    >>> safe_eval('{"foo": null}')
    {'foo': None}

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
            result, processed = load(string), True
        except (TypeError, ValueError, SyntaxError, LoaderError):
            result, processed = string, False

    return processed, result
