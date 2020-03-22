#!/usr/bin/env python
import dataclasses

import pytest

from typic.api import _resolve_from_env


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
    resolved = _resolve_from_env(Foo, **kwargs, environ={name: value})
    assert resolved.bar.default == value


def test__resolve_from_env_field():
    DB.port = dataclasses.field()
    _resolve_from_env(DB, "APP_", False, {}, environ={"APP_PORT": "1"})
    assert DB.port.default == 1


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
    resolved = _resolve_from_env(Bar, **kwargs, environ=environ)
    assert resolved.data.default_factory() == {}
    assert resolved.array.default_factory() == []
