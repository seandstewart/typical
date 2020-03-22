#!/usr/bin/env python
# flake8: noqa
try:
    import fastjsonschema  # type: ignore
except ImportError:  # pragma: nocover
    fastjsonschema = False
