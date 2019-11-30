#!/usr/bin/env python
# -*- coding: UTF-8 -*-


class ConstraintSyntaxError(SyntaxError):
    """A generic error indicating an improperly defined constraint."""

    pass


class ConstraintValueError(ValueError):
    """A generic error indicating a value violates a constraint."""

    pass
