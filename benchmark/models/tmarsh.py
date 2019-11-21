#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import toastedmarshmallow

from benchmark.models import marsh

SCHEMA = marsh.ModelSchema()
SCHEMA.jit = toastedmarshmallow.Jit


def validate(data):
    result = SCHEMA.load(data)
    if result.errors:
        return False, result.errors

    return True, marsh.initialize(**data)
