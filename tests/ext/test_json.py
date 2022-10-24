import importlib
import sys
from unittest import mock

import pytest


@pytest.fixture
def drop_orjson():
    import orjson

    del orjson
    with mock.patch.dict(sys.modules, values={"orjson": None}):
        yield


@pytest.fixture
def drop_ujson():
    import ujson

    del ujson
    with mock.patch.dict(sys.modules, values={"ujson": None}):
        yield


def ser(obj, *, lazy=False, name=None):
    return obj


def test_orjson():
    # Given
    from typic.core import json

    # When
    tojson = json.get_tojson(serializer=ser)
    # Then
    assert tojson({"foo": "bar"}) == b'{"foo":"bar"}'
    assert tojson({"foo": "bar"}, indent=2) == b'{\n  "foo": "bar"\n}\n'


def test_ujson(drop_orjson):
    from typic.core import json

    importlib.reload(json)
    # When
    tojson = json.get_tojson(serializer=ser)
    # Then
    assert tojson({"foo": "bar"}) == '{"foo":"bar"}'


def test_native_json(drop_orjson, drop_ujson):
    from typic.core import json

    importlib.reload(json)
    # When
    tojson = json.get_tojson(serializer=ser)
    # Then
    assert tojson({"foo": "bar"}) == '{"foo": "bar"}'
