from __future__ import annotations

import dataclasses
import os
import uuid
from datetime import date, datetime, timezone

import pytest

from typic.api import _resolve_from_env, environ


class Foo:
    bar: int


class DB:
    port: int


@pytest.mark.parametrize(
    argnames=("kwargs", "value", "name"),
    argvalues=[
        ({"prefix": "", "case_sensitive": False, "aliases": {}}, 1, "bar"),
        ({"prefix": "", "case_sensitive": True, "aliases": {}}, 1, "bar"),
        ({"prefix": "", "case_sensitive": False, "aliases": {}}, 1, "BAR"),
        ({"prefix": "OTHER_", "case_sensitive": False, "aliases": {}}, 1, "OTHER_BAR"),
        ({"prefix": "FAB_", "case_sensitive": False, "aliases": {}}, 1, "FAB_BAR"),
    ],
)
def test__resolve_from_env(kwargs, value, name):
    os.environ.update({name: str(value)})
    resolved = _resolve_from_env(Foo, **kwargs)
    assert resolved.bar.default_factory() == value


def test__resolve_from_env_field():
    DB.port = dataclasses.field()
    os.environ.update({"APP_PORT": "1"})
    _resolve_from_env(DB, "APP_", False, {})
    assert DB.port.default_factory() == 1


class Bar:
    data: dict
    array: list


@pytest.mark.parametrize(
    argnames=("kwargs", "environ"),
    argvalues=[
        (
            {"prefix": "", "case_sensitive": False, "aliases": {}},
            {"data": "{}", "array": "[]"},
        ),
        (
            {"prefix": "OTHER_", "case_sensitive": False, "aliases": {}},
            {"OTHER_DATA": "{}", "OTHER_ARRAY": "[]"},
        ),
    ],
)
def test__resolve_from_env_factory(kwargs, environ):
    os.environ.update(environ)
    resolved = _resolve_from_env(Bar, **kwargs)
    assert resolved.data.default_factory() == {}
    assert resolved.array.default_factory() == []


@pytest.mark.parametrize(
    argnames="getter,name,value",
    argvalues=[
        (environ.bool, "bool", False),
        (environ.bytes, "b", b""),
        (environ.bytearray, "bs", bytearray(b"")),
        (environ.date, "date", date(1970, 1, 1)),
        (environ.datetime, "datetime", datetime(1970, 1, 1, tzinfo=timezone.utc)),
        (environ.dict, "dict", {}),
        (environ.float, "float", 1.0),
        (environ.frozenset, "frozenset", frozenset(())),
        (environ.int, "int", 1),
        (environ.list, "list", []),
        (environ.set, "set", set()),
        (environ.str, "str", ""),
        (environ.UUID, "uuid", uuid.UUID(int=1)),
    ],
)
def test_environ(getter, name, value):
    environ.setenv(name, value)
    assert getter(name) == value
