#!/usr/bin/env python
import json
from urllib.parse import quote

import pytest

from typic.types.networking import email

EMAIL_RAW = "foo.bar@foobar.net"
EMAIL = email.Email(EMAIL_RAW)
PRETTY_EMAIL_RAW = f"Foo Bar <{EMAIL_RAW}>"
PRETTY_EMAIL = email.Email(PRETTY_EMAIL_RAW)


@pytest.mark.parametrize(
    argnames=("name", "expected", "eml"),
    argvalues=[
        ("username", "foo.bar", EMAIL),
        ("host", "foobar.net", EMAIL),
        ("address", EMAIL_RAW, EMAIL),
        ("address_encoded", quote(EMAIL_RAW), EMAIL),
        ("username", "foo.bar", PRETTY_EMAIL),
        ("name", "Foo Bar", PRETTY_EMAIL),
        ("address", PRETTY_EMAIL_RAW, PRETTY_EMAIL),
        ("address_encoded", f"Foo Bar <{quote(EMAIL_RAW)}>", PRETTY_EMAIL),
    ],
)
def test_email_info_attrs(name, expected, eml):
    value = getattr(eml.info, name)
    assert value == expected


def test_json_dump():
    assert json.dumps(EMAIL) == json.dumps(EMAIL_RAW)


@pytest.mark.parametrize(
    argnames=("raw",),
    argvalues=[
        ("foo.bar@localhost",),
        ("foo.bar@127.0.0.1",),
        ("foo.bar@192.168.1.1",),
    ],
)
def test_is_internal(raw):
    assert email.Email(raw).info.is_internal


@pytest.mark.parametrize(
    argnames=("raw",), argvalues=[("foo.bar@127.0.0.1",), ("foo.bar@localhost",)]
)
def test_is_private(raw):
    assert email.Email(raw).info.is_private


def test_is_ip():
    assert email.Email("foo@127.0.0.1").info.is_ip


@pytest.mark.parametrize(
    argnames=("raw",),
    argvalues=[
        ("--wfofj:fou.0.has",),
        ("",),
        ("foo.bar",),
        ("@foobar.net",),
        (".@foobar.net",),
        ("foo.@foobar.net",),
    ],
)
def test_invalid_email(raw):
    with pytest.raises(email.EmailValueError):
        email.Email(raw)


def test_is_named():
    assert PRETTY_EMAIL.info.is_named
