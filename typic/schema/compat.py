#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# flake8: noqa
try:
    import fastjsonschema  # type: ignore
except ImportError:  # pragma: nocover
    fastjsonschema = False
