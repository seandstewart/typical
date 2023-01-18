from __future__ import annotations

import copy

import pytest

from typical.types.frozendict import FrozenDict


def test_frozendict():
    mydict = {"foo": {"bar": ["baz"], "blah": {"shmeh"}}}
    frozen = FrozenDict(mydict)
    assert isinstance(frozen["foo"], FrozenDict)
    assert isinstance(frozen["foo"]["bar"], tuple)
    assert isinstance(frozen["foo"]["blah"], frozenset)
    assert len(frozen) == len(mydict)
    assert frozen.keys() == mydict.keys()


test_dict = FrozenDict(foo=1, loo={"boo": 3})


@pytest.mark.parametrize(
    argnames=("args", "op"),
    argvalues=[
        (("foo",), test_dict.__delitem__),
        ((), test_dict.popitem),
        ((), test_dict.clear),
        (("foo",), test_dict.pop),
        (({"foo": 2},), test_dict.update),
        (({"bar": 2},), test_dict.setdefault),
        (("foo", 3), test_dict.__setitem__),
    ],
)
def test_frozendict_immutable(args, op):
    with pytest.raises(TypeError):
        op(*args)


def test_copy():
    assert copy.copy(test_dict) == test_dict
    assert copy.copy(test_dict) is not test_dict
    assert copy.copy(test_dict)["loo"] is test_dict["loo"]


def test_deepcopy():
    assert copy.deepcopy(test_dict) == test_dict
    assert copy.deepcopy(test_dict) is not test_dict
    assert copy.deepcopy(test_dict)["loo"] is not test_dict["loo"]
