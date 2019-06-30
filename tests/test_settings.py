#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses

import pytest

from typic.api import _resolve_from_env


class Foo:
    bar: int


@pytest.mark.parametrize(
    argnames=("kwargs", "value", "name"),
    argvalues=[
        ({"prefix": "", "case_sensitive": False, "aliases": {}}, 1, "bar"),
        ({"prefix": "", "case_sensitive": True, "aliases": {}}, 1, "bar"),
        ({"prefix": "", "case_sensitive": False, "aliases": {}}, 1, "BAR"),
        ({"prefix": "OTHER_", "case_sensitive": False, "aliases": {}}, 1, "OTHER_BAR"),
    ],
)
def test__resolve_from_env(kwargs, value, name):
    resolved = _resolve_from_env(Foo, **kwargs, environ={name: value})
    assert resolved.bar.default == value


def test__resolve_from_env_field():
    Foo.bar = dataclasses.field()
    _resolve_from_env(Foo, "", False, {}, environ={"bar": "1"})
    assert Foo.bar.default == 1


class Bar:
    data: dict


@pytest.mark.parametrize(
    argnames=("kwargs", "value", "name"),
    argvalues=[
        ({"prefix": "", "case_sensitive": False, "aliases": {}}, "{}", "data"),
        (
            {"prefix": "OTHER_", "case_sensitive": False, "aliases": {}},
            "{}",
            "OTHER_DATA",
        ),
    ],
)
def test__resolve_from_env_factory(kwargs, value, name):
    resolved = _resolve_from_env(Bar, **kwargs, environ={name: value})
    assert resolved.data.default_factory() == {}
