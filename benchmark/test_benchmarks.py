#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import json
import pathlib
from copy import deepcopy

import pytest
import typic

from benchmark.models import apisch, drf, functional, klass, marsh, protocol, pyd

THIS_DIR = pathlib.Path(__file__).parent.resolve()


VALID_RAW = json.loads((THIS_DIR / "valid.json").read_text())
VALID_DESER = dataclasses.asdict(typic.transmute(functional.Model, VALID_RAW))
INVALID = json.loads((THIS_DIR / "invalid.json").read_text())

_MODS = {
    "typic-object-api": klass,
    "typic-protocol-api": protocol,
    "typic-functional-api": functional,
    "pydantic": pyd,
    "marshmallow": marsh,
    "djangorestframework": drf,
    "apischema": apisch,
}


_TRANSLATE_FROM_MODS = {
    "typic-object-api": klass,
    "typic-protocol-api": protocol,
    "typic-functional-api": functional,
    "pydantic": pyd,
}


_TRANSLATE_TO_MODS = {
    "typic-object-api": klass,
    "typic-protocol-api": protocol,
    "typic-functional-api": functional,
}


@dataclasses.dataclass
class NotASkill:
    ...


@pytest.mark.parametrize(argnames="mod", argvalues=(*reversed([*_MODS]),))
def test_benchmarks_validate_valid_data(benchmark, mod):
    benchmark.group = "Validate Valid Data"
    benchmark.name = mod
    raw = VALID_RAW if mod in ("marshmallow", "apischema") else VALID_DESER
    validate = _MODS[mod].validate
    valid, data = benchmark(validate, deepcopy(raw))
    assert valid, data


@pytest.mark.parametrize(argnames="mod", argvalues=(*reversed([*_MODS]),))
def test_benchmarks_validate_invalid_data(benchmark, mod):
    benchmark.group = "Validate Invalid Data"
    benchmark.name = mod
    validate = _MODS[mod].validate
    valid, data = benchmark(validate, deepcopy(INVALID))
    assert not valid, data


@pytest.mark.parametrize(argnames="mod", argvalues=(*reversed([*_MODS]),))
def test_benchmarks_deserialize_valid_data(benchmark, mod):
    benchmark.group = "Deserialize Valid Data"
    benchmark.name = mod
    deserialize = _MODS[mod].deserialize
    valid, data = benchmark(deserialize, deepcopy(VALID_RAW))
    assert valid, data


@pytest.mark.parametrize(argnames="mod", argvalues=(*reversed([*_MODS]),))
def test_benchmarks_deserialize_invalid_data(benchmark, mod):
    benchmark.group = "Deserialize Invalid Data"
    benchmark.name = mod
    deserialize = _MODS[mod].deserialize
    valid, data = benchmark(deserialize, deepcopy(INVALID))
    assert not valid, data


@pytest.mark.parametrize(argnames="mod", argvalues=(*reversed([*_MODS]),))
def test_benchmarks_serialize_valid_data(benchmark, mod):
    benchmark.group = "Serialize Valid Data"
    benchmark.name = mod
    serialize = _MODS[mod].tojson
    model = _MODS[mod].Model
    if mod == "pydantic":
        instance = model(**VALID_RAW)
    elif mod == "apischema":
        _, instance = _MODS[mod].deserialize(deepcopy(VALID_RAW))
    else:
        instance = typic.transmute(model, VALID_RAW)
    valid, data = benchmark(serialize, instance)
    assert valid, data


@pytest.mark.parametrize(argnames="mod", argvalues=(*reversed([*_MODS]),))
def test_benchmarks_serialize_invalid_data(benchmark, mod):
    benchmark.group = "Serialize Invalid Data"
    benchmark.name = mod
    serialize = _MODS[mod].tojson
    model = _MODS[mod].Model
    if mod == "pydantic":
        instance = model(**VALID_RAW)
    elif mod == "apischema":
        _, instance = _MODS[mod].deserialize(deepcopy(VALID_RAW))
    else:
        instance = typic.transmute(model, VALID_RAW)
    instance.skills.append(NotASkill())
    valid, data = benchmark(serialize, instance)
    # Marshmallow implicitly filters invalid data, and pydantic doesn't care at all.
    if mod in {"marshmallow", "pydantic"}:
        assert valid, data
    else:
        assert not valid, data


@pytest.mark.parametrize(argnames="mod", argvalues=(*reversed([*_TRANSLATE_TO_MODS]),))
def test_benchmarks_translate_to_class(benchmark, mod):
    benchmark.group = "Translate to Arbitrary Class"
    benchmark.name = mod
    translate = _MODS[mod].translate_to
    model = _MODS[mod].Model
    instance = typic.transmute(model, VALID_RAW)
    valid, data = benchmark(translate, instance, marsh.Model)
    assert valid, data


@pytest.mark.parametrize(
    argnames="mod", argvalues=(*reversed([*_TRANSLATE_FROM_MODS]),)
)
def test_benchmarks_translate_from_class(benchmark, mod):
    benchmark.group = "Translate from Arbitrary Class"
    benchmark.name = mod
    translate = _MODS[mod].translate_from
    instance = typic.transmute(marsh.Model, VALID_RAW)
    valid, data = benchmark(translate, instance)
    assert valid, data
