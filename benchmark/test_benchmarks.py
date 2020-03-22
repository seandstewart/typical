#!/usr/bin/env python
import json
import pathlib
import os
from copy import deepcopy

import pytest

from benchmark.models import drf, typ, marsh, pyd

NO_CYTHON = bool(int(os.getenv("NO_CYTHON", "1")))
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
    benchmark.group = f"Valid Data (Cython: {not NO_CYTHON})"
    benchmark.name = mod
    validate = _MODS[mod].validate
    valid, data = benchmark(validate, deepcopy(VALID))
    assert valid


@pytest.mark.parametrize(
    argnames=("mod",), argvalues=[(x,) for x in reversed([*_MODS])]
)
def test_benchmarks_invalid_data(benchmark, mod):
    benchmark.group = f"Invalid Data (Cython: {not NO_CYTHON}"
    benchmark.name = mod
    validate = _MODS[mod].validate
    valid, data = benchmark(validate, deepcopy(INVALID))
    assert not valid
