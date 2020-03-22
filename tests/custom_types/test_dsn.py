#!/usr/bin/env python
import json
from urllib.parse import quote

import pytest

from typic.types.networking import dsn

DSN_RAW = "mysql://foo:bar@foobar.net:3306/db"
DSN = dsn.DSN(DSN_RAW)
DSN_NO_PORT = dsn.DSN("mysql://foo:bar@foobar.net/db")


@pytest.mark.parametrize(
    argnames=("name", "expected"),
    argvalues=[
        ("driver", "mysql"),
        ("host", "foobar.net"),
        ("username", "foo"),
        ("password", "bar"),
        ("port", 3306),
        ("name", "/db"),
        ("address", DSN),
        ("address_encoded", quote(DSN_RAW)),
    ],
)
def test_dsn_info_attrs(name, expected):
    value = getattr(DSN.info, name)
    assert expected == value


def test_get_default_port():
    assert DSN_NO_PORT.info.port == DSN.info.port
    assert DSN_NO_PORT.info.is_default_port


def test_json_dump():
    assert json.dumps(DSN) == json.dumps(DSN_RAW)


@pytest.mark.parametrize(
    argnames=("raw",),
    argvalues=[
        ("mysql://localhost",),
        ("mysql://127.0.0.1",),
        ("mysql://192.168.1.1",),
    ],
)
def test_is_internal(raw):
    assert dsn.DSN(raw).info.is_internal


@pytest.mark.parametrize(
    argnames=("raw",), argvalues=[("mysql://127.0.0.1",), ("mysql://localhost",)]
)
def test_is_private(raw):
    assert dsn.DSN(raw).info.is_private


@pytest.mark.parametrize(
    argnames=("raw",),
    argvalues=[
        ("--wfofj:fou.0.has",),
        ("",),
        ("://127.0.0.1",),
        ("mysql://",),
        ("othersql://192.168.1.1",),
    ],
)
def test_invalid_dsn(raw):
    with pytest.raises(dsn.DSNValueError):
        dsn.DSN(raw)
