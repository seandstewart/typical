#!/usr/bin/env python
# -*- coding: UTF-8 -*-


class ConstraintSyntaxError(SyntaxError):
    """A generic error indicating an improperly defined constraint."""

    pass


class ConstraintValueError(ValueError):
    """A generic error indicating a value violates a constraint."""

    pass


def raise_exc(exc: Exception, *, _from: Exception = None):
    raise exc from _from
