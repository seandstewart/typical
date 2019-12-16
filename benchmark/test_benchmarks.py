#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import pathlib
from copy import deepcopy

import pytest

from benchmark.models import drf, typ, marsh, pyd

THIS_DIR = pathlib.Path(__file__).parent.resolve()


VALID = json.loads((THIS_DIR / "valid.json").read_text())
INVALID = json.loads((THIS_DIR / "invalid.json").read_text())

_MODS = {
    "typical": typ,
    "pydantic": pyd,
    "marshmallow": marsh,
    "djangorestframework": drf,
}


@pytest.mark.parametrize(
    argnames=("mod",), argvalues=[(x,) for x in reversed([*_MODS])]
)
def test_benchmarks_valid_data(benchmark, mod):
    benchmark.group = "Valid Data"
    benchmark.name = mod
    validate = _MODS[mod].validate
    valid, data = benchmark(validate, deepcopy(VALID))
    assert valid


@pytest.mark.parametrize(
    argnames=("mod",), argvalues=[(x,) for x in reversed([*_MODS])]
)
def test_benchmarks_invalid_data(benchmark, mod):
    benchmark.group = "Invalid Data"
    benchmark.name = mod
    validate = _MODS[mod].validate
    valid, data = benchmark(validate, deepcopy(INVALID))
    assert not valid
