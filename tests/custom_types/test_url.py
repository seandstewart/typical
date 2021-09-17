from __future__ import annotations

import json
import copy
from urllib.parse import quote

import pytest

from typic.types import url

OREL = "/path;attr=value?query=string#frag"
REL = f"www.foo.bar{OREL}"
ABS = f"http://{REL}"
PORT = f"http://www.foo.bar:100{OREL}"
DOTL = "foo"
HOST = "foo.bar"
FRAG = "#frag"


def test_net_address_eq():
    address = url.NetworkAddress(ABS)
    assert ABS == address
    assert json.dumps(ABS) == json.dumps(address)


_abs = url.NetworkAddress(ABS)
_rel = url.NetworkAddress(REL)
_orel = url.NetworkAddress(OREL)
_dotl = url.NetworkAddress(DOTL)
_frag = url.NetworkAddress(FRAG)
_port = url.NetworkAddress(PORT)


@pytest.mark.parametrize(
    argnames=("addr", "name", "expected"),
    argvalues=[
        (_abs, "scheme", "http"),
        (_abs, "host", "www.foo.bar"),
        (_abs, "port", 80),
        (_abs, "base", "http://www.foo.bar"),
        (_abs, "path", "/path"),
        (_abs, "qs", "query=string"),
        (_abs, "params", "attr=value"),
        (_port, "fragment", "frag"),
        (_port, "scheme", "http"),
        (_port, "host", "www.foo.bar"),
        (_port, "port", 100),
        (_port, "base", "http://www.foo.bar:100"),
        (_port, "path", "/path"),
        (_port, "qs", "query=string"),
        (_abs, "params", "attr=value"),
        (_abs, "fragment", "frag"),
        (_rel, "scheme", ""),
        (_rel, "host", "www.foo.bar"),
        (_rel, "port", 0),
        (_rel, "path", "/path"),
        (_rel, "qs", "query=string"),
        (_rel, "params", "attr=value"),
        (_rel, "fragment", "frag"),
        (_orel, "scheme", ""),
        (_orel, "host", ""),
        (_orel, "port", 0),
        (_orel, "path", "/path"),
        (_orel, "qs", "query=string"),
        (_orel, "params", "attr=value"),
        (_orel, "fragment", "frag"),
        (_dotl, "host", DOTL),
        (_frag, "fragment", "frag"),
    ],
)
def test_net_address_attrs(addr, name, expected):
    value = getattr(addr.info, name)
    assert value == expected


@pytest.mark.parametrize(
    argnames=("value",), argvalues=[(_abs,), (_rel,), (_orel,), (_dotl,)]
)
def test_default_port(value: url.NetworkAddress):
    assert value.info.is_default_port


@pytest.mark.parametrize(
    argnames=("value",), argvalues=[(_abs,), (_rel,), (_orel,), (_dotl,)]
)
@pytest.mark.parametrize(
    argnames=("copier",),
    argvalues=[(copy.copy,), (copy.deepcopy,)],
    ids=lambda x: x.__qualname__,
)
def test_copying(value: url.NetworkAddress, copier):
    assert copier(value) == value


@pytest.mark.parametrize(argnames=("value",), argvalues=[(_rel,), (_orel,), (_dotl,)])
def test_relative(value: url.NetworkAddress):
    assert value.info.is_relative and not value.info.is_absolute


def test_private():
    assert url.NetworkAddress("localhost").info.is_private


def test_internal():
    assert url.NetworkAddress("0.0.0.0").info.is_internal


@pytest.mark.parametrize(argnames=("value",), argvalues=[(_abs,), (_rel,), (_orel,)])
def test_query(value: url.NetworkAddress):
    assert value.info.query == {"query": ["string"]}


@pytest.mark.parametrize(argnames=("value",), argvalues=[(_abs,), (_rel,), (_orel,)])
def test_parameters(value: url.NetworkAddress):
    assert value.info.parameters == {"attr": ["value"]}


@pytest.mark.parametrize(
    argnames=("value", "base"),
    argvalues=[
        (_abs, "http://www.foo.bar"),
        (_rel, "www.foo.bar"),
        (_orel, ""),
        (_dotl, _dotl),
    ],
)
def test_info_url(value: url.NetworkAddress, base):
    assert value.info.base == base
    assert value.info.address == value
    assert value.info.address_encoded == quote(value)


@pytest.mark.parametrize(
    argnames=("value", "path", "expected"),
    argvalues=[
        (url.URL("/foo"), "bar", "/foo/bar"),
        (url.URL("http://foo.bar/bar"), "foo", "http://foo.bar/bar/foo"),
        (url.URL("http://foo.bar:8080/bar"), "foo", "http://foo.bar:8080/bar/foo"),
    ],
)
def test_url_join(value, path, expected):
    assert value / path == expected


def test_url_join_chaining():
    assert url.URL("/foo") / "bar" / "foo" / "bar" == "/foo/bar/foo/bar"


def test_rdiv_url():
    assert "/foo" / url.URL("/bar") == "/foo/bar"


@pytest.mark.parametrize(
    argnames=("value", "cls", "error"),
    argvalues=[
        ("/foo", url.AbsoluteURL, url.AbsoluteURLValueError),
        ("http://foo.bar", url.RelativeURL, url.RelativeURLValueError),
        ("", url.NetworkAddress, url.NetworkAddressValueError),
        ("http:///", url.NetworkAddress, url.NetworkAddressValueError),
        ("--", url.NetworkAddress, url.NetworkAddressValueError),
    ],
)
def test_invalid_value(value, cls, error):
    with pytest.raises(error):
        cls(value)


def test_immutable():
    with pytest.raises(AttributeError):
        _abs.foo = "bar"

    with pytest.raises(AttributeError):
        del _abs.__doc__


@pytest.mark.parametrize(argnames=("val",), argvalues=[(DOTL,), (HOST,)])
def test_hostname(val):
    host = url.HostName(val)
    assert host == val
    assert host.info.host == val


@pytest.mark.parametrize(argnames=("val",), argvalues=[(OREL,), (REL,), (ABS,)])
def test_hostname_invalid(val):
    with pytest.raises(url.HostNameValueError):
        url.HostName(val)
