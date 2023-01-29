from __future__ import annotations

import collections
import datetime
import decimal
import ipaddress
import pathlib
import types
import typing as t
import uuid

import pytest

from typical import checks


@pytest.mark.suite(
    int=dict(given_type=int),
    bool=dict(given_type=bool),
    float=dict(given_type=float),
    str=dict(given_type=str),
    bytes=dict(given_type=bytes),
    bytearray=dict(given_type=bytearray),
    list=dict(given_type=list),
    set=dict(given_type=set),
    frozenset=dict(given_type=frozenset),
    tuple=dict(given_type=tuple),
    dict=dict(given_type=dict),
    none=dict(given_type=type(None)),
    new_type=dict(given_type=t.NewType("foo", int)),
)
def test_isbuiltintype(given_type):
    # When
    is_valid = checks.isbuiltintype(given_type)
    # Then
    assert is_valid


@pytest.mark.suite(
    int=dict(given_type=int),
    bool=dict(given_type=bool),
    float=dict(given_type=float),
    str=dict(given_type=str),
    bytes=dict(given_type=bytes),
    bytearray=dict(given_type=bytearray),
    list=dict(given_type=list),
    set=dict(given_type=set),
    frozenset=dict(given_type=frozenset),
    tuple=dict(given_type=tuple),
    dict=dict(given_type=dict),
    none=dict(given_type=type(None)),
    new_type=dict(given_type=t.NewType("foo", int)),
    datetime=dict(given_type=datetime.datetime),
    date=dict(given_type=datetime.datetime),
    timedelta=dict(given_type=datetime.timedelta),
    time=dict(given_type=datetime.time),
    decimal=dict(given_type=decimal.Decimal),
    ipv4=dict(given_type=ipaddress.IPv4Address),
    ipv6=dict(given_type=ipaddress.IPv6Address),
    path=dict(given_type=pathlib.Path),
    uuid=dict(given_type=uuid.UUID),
    defaultdict=dict(given_type=collections.defaultdict),
    deque=dict(given_type=collections.deque),
    mapping_proxy=dict(given_type=types.MappingProxyType),
)
def test_isstdlibtype(given_type):
    # When
    is_valid = checks.isstdlibtype(given_type)
    # Then
    assert is_valid


def test_isstdlibsubtype():
    # Given

    class SuperStr(str):
        ...

    # When
    is_valid = checks.isstdlibsubtype(SuperStr)
    # Then
    assert is_valid


@pytest.mark.suite(
    int=dict(given_type=int),
    bool=dict(given_type=bool),
    float=dict(given_type=float),
    str=dict(given_type=str),
    bytes=dict(given_type=bytes),
    bytearray=dict(given_type=bytearray),
    list=dict(given_type=list),
    set=dict(given_type=set),
    frozenset=dict(given_type=frozenset),
    tuple=dict(given_type=tuple),
    dict=dict(given_type=dict),
    none=dict(given_type=type(None)),
)
def test_isbuiltinstance(given_type):
    # Given
    instance = given_type()
    # When
    is_valid = checks.isbuiltininstance(instance)
    # Then
    assert is_valid


@pytest.mark.suite(
    int=dict(instance=1),
    bool=dict(instance=True),
    float=dict(instance=1.0),
    str=dict(instance=""),
    bytes=dict(instance=b""),
    bytearray=dict(instance=bytearray()),
    list=dict(instance=[]),
    set=dict(instance=set()),
    frozenset=dict(instance=frozenset([])),
    tuple=dict(instance=()),
    dict=dict(instance={}),
    none=dict(instance=None),
    datetime=dict(instance=datetime.datetime(1970, 1, 1)),
    date=dict(instance=datetime.date(1970, 1, 1)),
    timedelta=dict(instance=datetime.timedelta()),
    time=dict(instance=datetime.time()),
    decimal=dict(instance=decimal.Decimal(1)),
    ipv4=dict(instance=ipaddress.IPv4Address("0.0.0.0")),
    ipv6=dict(instance=ipaddress.IPv6Address("2001:db8::")),
    path=dict(instance=pathlib.Path()),
    uuid=dict(instance=uuid.UUID(int=0)),
    defaultdict=dict(instance=collections.defaultdict()),
    deque=dict(instance=collections.deque()),
    mapping_proxy=dict(instance=types.MappingProxyType({})),
)
def test_isstdlibinstance(instance):
    # When
    is_valid = checks.isstdlibinstance(instance)
    # Then
    assert is_valid
