from __future__ import annotations

import dataclasses
import datetime
import enum
import inspect
import pathlib
import re
import typing
import uuid
from collections import defaultdict
from operator import attrgetter

import pendulum
import pytest

import typic
from tests import objects
from tests.module.index import MyClass
from tests.module.other import factory
from typic.api import (
    transmute,
    typed,
    resolve,
    register,
    resolver,
    wrap,
    wrap_cls,
    constrained,
    strict_mode,
    is_strict_mode,
    StrictStrT,
    Strict,
    validate,
    translate,
    primitive,
)
from typic.checks import isbuiltintype, BUILTIN_TYPES, istypeddict
from typic.compat import Literal
from typic.constraints import ConstraintValueError
from typic.util import safe_eval, resolve_supertype, origin as get_origin, get_args
from typic.types import NetworkAddress, DirectoryPath
from typic.klass import klass

NOW = datetime.datetime.now(datetime.timezone.utc)


class SubUUID(uuid.UUID):
    ...


@pytest.mark.parametrize(argnames="obj", argvalues=BUILTIN_TYPES)
def test_isbuiltintype(obj: typing.Any):
    assert isbuiltintype(obj)


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (dict, [("foo", "bar")], {"foo": "bar"}),
        (dict, [1], {0: 1}),
        (typing.Dict, [("foo", "bar")], {"foo": "bar"}),
        (list, set(), []),
        (typing.List, set(), []),
        (set, list(), set()),
        (typing.Set, list(), set()),
        (tuple, list(), ()),
        (typing.Tuple, list(), ()),
        (str, 1, "1"),
        (typing.Text, 1, "1"),
        (float, 1, 1.0),
        (bool, 1, True),
        (bool, "1", True),
        (bool, "true", True),
        (bool, "True", True),
        (bool, "false", False),
        (bool, "False", False),
        (bool, "0", False),
        (bool, 0, False),
        (
            datetime.datetime,
            "1970-01-01",
            datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc),
        ),
        (pendulum.DateTime, "1970-01-01", pendulum.datetime(1970, 1, 1)),
        (datetime.datetime, 0, datetime.datetime.fromtimestamp(0)),
        (datetime.datetime, NOW, NOW),
        (pendulum.DateTime, NOW, NOW),
        (datetime.date, "1970-01-01", datetime.date(1970, 1, 1)),
        (datetime.date, 0, datetime.date.fromtimestamp(0)),
        (datetime.datetime, datetime.date(1980, 1, 1), datetime.datetime(1980, 1, 1)),
        (datetime.date, datetime.datetime(1980, 1, 1), datetime.date(1980, 1, 1)),
        (pendulum.Time, "01:00:00", pendulum.time(1)),
        (datetime.time, "01:00:00", datetime.time(1)),
        (datetime.time, pendulum.time(1), datetime.time(1)),
        (datetime.time, datetime.datetime(1980, 1, 1, 1), datetime.time(1)),
        (datetime.time, datetime.date(1980, 1, 1), datetime.time(0)),
        (datetime.time, 0, datetime.time(0)),
        (uuid.UUID, 1, uuid.UUID(int=1)),
        (uuid.UUID, uuid.UUID(int=1).bytes, uuid.UUID(int=1)),
        (uuid.UUID, str(uuid.UUID(int=1)), uuid.UUID(int=1)),
        (uuid.UUID, uuid.UUID(int=1).fields, uuid.UUID(int=1)),
        (SubUUID, uuid.UUID(int=1), SubUUID(int=1)),
        (DirectoryPath, pathlib.Path.cwd(), DirectoryPath.cwd()),
        (pathlib.Path, DirectoryPath.cwd(), pathlib.Path.cwd()),
        (objects.FromDict, {"foo": "bar!"}, objects.FromDict("bar!")),
        (objects.Data, {"foo": "bar!"}, objects.Data("bar!")),
        (dict, objects.Data("bar!"), {"foo": "bar!"}),
        (list, objects.Data("bar!"), ["bar!"]),
        (objects.TDict, objects.TClass(1), objects.TDict(a=1)),
        (objects.NTup, objects.TClass(1), objects.NTup(a=1)),
        (objects.TDict, objects.NTup(1), objects.TDict(a=1)),
        (
            objects.Nested,
            {"data": {"foo": "bar!"}},
            objects.Nested(objects.Data("bar!")),
        ),
        (
            objects.Nested,
            {"data": {"foo": "bar!", "something": "else"}},
            objects.Nested(objects.Data("bar!")),
        ),
        (
            objects.NestedFromDict,
            {"data": {"foo": "bar!"}},
            objects.NestedFromDict(objects.Data("bar!")),
        ),
        (objects.FooNum, "bar", objects.FooNum.bar),
        (
            objects.Data,
            objects.Data("bar!"),
            objects.Data("bar!"),
        ),
        (NetworkAddress, "localhost", NetworkAddress("localhost")),
        (typing.Pattern, r"\w+", re.compile(r"\w+")),
        (objects.Data, objects.FromDict("bar!"), objects.Data("bar!")),
        (
            objects.Nested,
            objects.NestedFromDict(objects.Data("bar!")),
            objects.Nested(objects.Data("bar!")),
        ),
        (
            objects.Nested,
            objects.NestedFromDict(objects.Data("bar!")),
            objects.Nested(objects.Data("bar!")),
        ),
        (objects.SubTypic, {"var": "var", "sub": b"sub"}, objects.SubTypic("var", "sub")),  # type: ignore
        (objects.SuperBase, {"super": b"base!"}, objects.SuperBase("base!")),  # type: ignore
        (objects.Dest, objects.Source(), objects.Dest(objects.Source().test)),  # type: ignore
        (MyClass, factory(), MyClass(1)),
        (defaultdict, {}, defaultdict(None)),
        (list, (x for x in range(10)), [*range(10)]),
    ],
)
def test_transmute_simple(annotation, value, expected):
    transmuted = transmute(annotation, value)
    t = dict if istypeddict(annotation) else annotation
    assert isinstance(transmuted, t)
    assert transmuted == expected


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (Literal[1], 1, 1),
        (Literal[1], "1", 1),
        (Literal[1], b"1", 1),
        (typing.Optional[Literal[1]], b"1", 1),
        (typing.Optional[Literal[1]], None, None),
        (Literal[1, None], None, None),
        (Literal[1, None], "1", 1),
        (Literal[1, 2, None], "1", 1),
        (Literal[1, 2, None], "null", None),
    ],
)
def test_transmute_literal(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert transmuted == expected


@pytest.mark.parametrize(
    argnames=("annotation", "value"),
    argvalues=[
        (Literal[1], 2),
        (Literal[1], "2"),
        (Literal[1], b"2"),
        (typing.Optional[Literal[1]], 2),
        (Literal[1, None], 2),
        (Literal[1, None], "2"),
        (Literal[1, 2, None], 3),
        (Literal[1, 2, None], "3"),
    ],
)
def test_transmute_literal_invalid(annotation, value):
    with pytest.raises(ConstraintValueError):
        transmute(annotation, value)


def test_invalid_literal():
    with pytest.raises(TypeError):
        transmute(Literal[datetime.date.today()], [1])


def test_translate_literal():
    with pytest.raises(TypeError):
        translate(1, Literal[1])
    with pytest.raises(TypeError):
        resolver.translator.factory(resolver.annotation(int), Literal[1])


@pytest.mark.parametrize(
    argnames=("annotation", "value"), argvalues=[(objects.UserID, "1")]
)
def test_transmute_newtype(annotation, value):
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation.__supertype__)


def test_transmute_subclassed_enum_with_default():
    class MyNum(enum.IntEnum):
        YES = 1

    @klass
    class Foo:
        bar: MyNum = MyNum.YES

    assert Foo(1).bar.__class__ is MyNum


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (objects.TDict, '{"a": "2"}', {"a": 2}),
        (objects.NTup, '{"a": "2"}', objects.NTup(2)),
        (objects.ntup, '{"a": "2"}', objects.ntup("2")),
        (objects.TDictPartial, "{}", {}),
    ],
    ids=objects.get_id,
)
def test_transmute_collection_metas(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert transmuted == expected


def test_default_none():
    transmuted = transmute(objects.DefaultNone, {})
    assert transmuted.none is None


def test_default_ellipsis():
    transmuted = transmute(objects.DefaultEllipsis, {})
    assert transmuted.ellipsis is ...


@pytest.mark.parametrize(
    argnames=("annotation", "origin"),
    argvalues=[
        (typing.List, list),
        (typing.ClassVar, typing.ClassVar),
        (typing.List[str], list),
    ],
    ids=objects.get_id,
)
def test_get_origin(annotation, origin):
    assert get_origin(annotation) is origin


T = typing.TypeVar("T")


@pytest.mark.parametrize(
    argnames=("annotation", "args"),
    argvalues=[
        (typing.List, ()),
        (typing.List[T], ()),
        (typing.List[str], (str,)),
        (typing.Optional[str], (str, type(None))),
    ],
    ids=objects.get_id,
)
def test_get_args(annotation, args):
    assert get_args(annotation) == args


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (typing.Optional[str], 1, "1"),
        (typing.Optional[str], None, None),
        (typing.ClassVar[str], 1, "1"),
    ],
    ids=objects.get_id,
)
def test_transmute_supscripted(annotation, value, expected):
    assert transmute(annotation, value) == expected


@pytest.mark.parametrize(
    argnames=("annotation", "value"),
    argvalues=[
        (typing.List[int], '["1"]'),
        (typing.List[bool], '["1"]'),
        (typing.List[int], ("1",)),
        (typing.Set[int], '["1"]'),
        (typing.Set[bool], '["1"]'),
        (typing.Set[int], ("1",)),
        (typing.Tuple[int], '["1"]'),
        (typing.Tuple[bool], '["1"]'),
        (typing.Tuple[int], {"1"}),
        (typing.Sequence[int], '["1"]'),
        (typing.Sequence[bool], '["1"]'),
        (typing.Sequence[int], {"1"}),
        (typing.Collection[int], '["1"]'),
        (typing.Collection[bool], '["1"]'),
        (typing.Collection[int], {"1"}),
        (typing.Collection[objects.FromDict], [{"foo": "bar!"}]),
        (typing.Collection[objects.Data], [{"foo": "bar!"}]),
        (typing.Collection[objects.Nested], [{"data": {"foo": "bar!"}}]),
        (typing.Collection[objects.NestedFromDict], [{"data": {"foo": "bar!"}}]),
        (typing.Collection[objects.NestedFromDict], ["{'data': {'foo': 'bar!'}}"]),
        (typing.Collection[str], objects.TClass(1)),
    ],
    ids=objects.get_id,
)
def test_transmute_collections_subscripted(annotation, value):
    arg = annotation.__args__[0]
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation.__origin__) and all(
        isinstance(x, arg) for x in transmuted
    )


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (typing.Tuple[str, int], '["1", "2"]', ("1", 2)),
        (typing.Tuple[int, str], '["1", "2"]', (1, "2")),
        (typing.Tuple[int, str], '["1", "2", "ignore"]', (1, "2")),
        (typing.Tuple[str, int, bytes], '["1", "2", "foo"]', ("1", 2, b"foo")),
    ],
)
def test_transmute_tuple_subscripted(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert transmuted == expected


@pytest.mark.parametrize(
    argnames=("annotation", "value"),
    argvalues=[
        (typing.Mapping[int, str], '{"1": 0}'),
        (typing.Mapping[int, bool], '{"1": false}'),
        (typing.Mapping[str, int], {1: "0"}),
        (typing.Mapping[str, bool], {1: "0"}),
        (typing.Mapping[datetime.datetime, datetime.datetime], {0: "1970"}),
        (typing.Dict[int, str], '{"1": 0}'),
        (typing.Dict[str, int], {1: "0"}),
        (typing.Dict[str, bool], {1: "0"}),
        (typing.Dict[datetime.datetime, datetime.datetime], {0: "1970"}),
        (typing.Dict[str, objects.FromDict], {"blah": {"foo": "bar!"}}),
        (typing.Mapping[int, objects.Data], {"0": {"foo": "bar!"}}),
        (
            typing.Dict[datetime.date, objects.Nested],
            {"1970": {"data": {"foo": "bar!"}}},
        ),
        (typing.Mapping[bool, objects.NestedFromDict], {0: {"data": {"foo": "bar!"}}}),
        (typing.Dict[bytes, objects.NestedFromDict], {0: "{'data': {'foo': 'bar!'}}"}),
        (objects.DateDict, '{"1970": "foo"}'),
        (typing.DefaultDict[str, int], {}),
        (
            typing.DefaultDict[str, typing.DefaultDict[str, int]],
            {"foo": {}},
        ),
        (
            typing.DefaultDict[str, objects.DefaultNone],
            {"foo": {}},
        ),
        (
            typing.DefaultDict[str, objects.DefaultEllipsis],
            {"foo": {}},
        ),
        (typing.Mapping[str, str], objects.TClass(1)),
    ],
    ids=objects.get_id,
)
def test_transmute_mapping_subscripted(annotation, value):
    annotation = resolve_supertype(annotation)
    key_arg, value_arg = annotation.__args__
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation.__origin__)
    assert all(isinstance(x, get_origin(key_arg)) for x in transmuted.keys())
    assert all(isinstance(x, get_origin(value_arg)) for x in transmuted.values())


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (typing.Optional[typing.List[int]], '["1"]', [1]),
        (typing.Optional[typing.List[int]], None, None),
        (typing.List[typing.Optional[int]], [None], [None]),
        (typing.List[typing.Optional[int]], ["1"], [1]),
        (typing.List[typing.Optional[Strict[int]]], [1], [1]),
        (typing.List[typing.Optional[Strict[int]]], [None], [None]),
        (typing.Optional[typing.Mapping[str, int]], '{"foo":"1"}', {"foo": 1}),
        (typing.Optional[typing.Mapping[str, int]], None, None),
        (
            typing.Mapping[typing.Optional[str], typing.Optional[int]],
            '{"foo":null}',
            {"foo": None},
        ),
        (
            typing.Mapping[typing.Optional[str], typing.Optional[int]],
            "{None:None}",
            {None: None},
        ),
        (
            typing.Mapping[typing.Optional[str], typing.Optional[int]],
            "{None:1}",
            {None: 1},
        ),
        (typing.Mapping[typing.Optional[str], typing.Optional[int]], "{1:1}", {"1": 1}),
    ],
    ids=objects.get_id,
)
def test_transmute_optional(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert transmuted == expected


def test_transmute_nested_sequence():
    transmuted = transmute(objects.NestedSeq, {"datum": [{"foo": "bar"}]})
    assert isinstance(transmuted, objects.NestedSeq)
    assert all(isinstance(x, objects.Data) for x in transmuted.datum)


@pytest.mark.parametrize(
    argnames=("func", "input", "type"),
    argvalues=[
        (objects.func, "1", int),
        (objects.Method().math, "4", int),
        (objects.number, 1, int),
    ],
)
def test_wrap_callable(func, input, type):
    wrapped = wrap(func)
    assert isinstance(wrapped(input), type)


@pytest.mark.parametrize(
    argnames=("klass", "var", "type"),
    argvalues=[(objects.Class, "var", str), (objects.Data, "foo", str)],
    ids=objects.get_id,
)
def test_wrap_class(klass, var, type):
    Wrapped = wrap_cls(klass)
    assert isinstance(getattr(Wrapped(1), var), type)
    assert inspect.isclass(Wrapped)


@pytest.mark.parametrize(
    argnames=("obj", "input", "getter", "type", "check"),
    argvalues=[
        (objects.func, "1", None, int, inspect.isfunction),
        (objects.optional, 1, None, str, inspect.isfunction),
        (objects.optional, None, None, type(None), inspect.isfunction),
        (objects.Data, 1, attrgetter("foo"), str, inspect.isclass),
        (objects.DefaultNone, None, attrgetter("none"), type(None), inspect.isclass),
        (
            objects.DefaultEllipsis,
            ...,
            attrgetter("ellipsis"),
            type(...),
            inspect.isclass,
        ),
        (objects.Forward, "bar", attrgetter("foo"), objects.FooNum, inspect.isclass),
        (objects.Frozen, "0", attrgetter("var"), bool, inspect.isclass),
    ],
    ids=objects.get_id,
)
def test_typed(obj, input, getter, type, check):
    wrapped = typed(obj)
    result = wrapped(input)
    if getter:
        result = getter(result)
    assert check(wrapped)
    assert isinstance(result, type)


def test_ensure_invalid():
    with pytest.raises(TypeError):
        typed(1)


@pytest.mark.parametrize(
    argnames=("func", "args", "kwargs", "check"),
    argvalues=[
        (
            objects.varargs,
            ({"foo": "bar"},),
            {"bar": {"foo": "bar"}},
            lambda res: all(isinstance(x, objects.Data) for x in res),
        )
    ],
    ids=objects.get_id,
)
def test_typed_varargs(func, args, kwargs, check):
    wrapped = typed(func)
    result = wrapped(*args, **kwargs)

    assert check(result)


@pytest.mark.parametrize(
    argnames=("annotation", "origin"),
    argvalues=[
        (typing.Mapping[int, str], dict),
        (typing.Mapping, dict),
        (objects.DateDict, dict),
        (objects.UserID, int),
    ],
    ids=objects.get_id,
)
def test_get_origin_returns_origin(annotation, origin):
    detected = get_origin(annotation)
    assert detected is origin


def test_eval_invalid():
    processed, result = safe_eval("{")
    assert not processed
    assert result == "{"


@pytest.mark.parametrize(
    argnames=("instance", "attr", "value", "type"),
    argvalues=[
        (typed(objects.Data)("foo"), "foo", 1, str),
        (typed(objects.NoParams)(), "var", 1, str),
    ],
    ids=objects.get_id,
)
def test_setattr(instance, attr, value, type):
    setattr(instance, attr, value)
    assert isinstance(getattr(instance, attr), type)


def test_register():
    class MyCustomClass:  # pragma: nocover
        def __init__(self, value: str):
            self.value = value

    class MyOtherCustomClass:  # pragma: nocover
        def __init__(self, value: int):
            self.value = value

    MyCustomType = typing.Union[MyCustomClass, MyOtherCustomClass]

    def ismycustomclass(obj) -> bool:
        args = set(getattr(obj, "__args__", [obj]))
        return args.issubset({*MyCustomType.__args__})

    register(MyCustomClass, ismycustomclass)
    assert resolver.resolve(MyCustomType).deserialize is MyCustomClass


@pytest.mark.parametrize(argnames=("val",), argvalues=[(1,), ("foo",)])
def test_no_transmuter(val):
    class NoTransmuter:
        def __init__(self, x):
            self.x = x

    assert transmute(NoTransmuter, val).x == val


def test_typic_klass():
    assert objects.Typic(1).var == "1"


def test_typic_klass_is_dataclass():
    assert dataclasses.is_dataclass(objects.Typic)


def test_typic_klass_passes_params():
    with pytest.raises(dataclasses.FrozenInstanceError):
        objects.FrozenTypic(1).var = 2


def test_typic_klass_inheritance():
    assert isinstance(objects.Inherited(1).var, str)


def test_typic_frozen():
    assert isinstance(objects.FrozenTypic(1).var, str)


@pytest.mark.parametrize(
    argnames=("instance", "attr", "type"),
    argvalues=[
        (objects.KlassVarSubscripted(), "var", str),
    ],
    ids=objects.get_id,
)
def test_classvar(instance, attr, type):
    setattr(instance, attr, 1)
    assert isinstance(getattr(instance, attr), type)


def test_typic_callable_delayed():
    assert isinstance(objects.delayed(1), str)


def test_typic_resolve():
    resolve()
    assert objects.Delayed(1).foo == "1"


@pytest.mark.parametrize(
    argnames=("type", "value", "expected"),
    argvalues=[
        (objects.ShortStr, "foo", "foo"),
        (objects.ShortStr, 1, "1"),
        (objects.LargeInt, "1001", 1001),
        (objects.LargeIntDict, [("foo", 1001)], {"foo": 1001}),
        (objects.ShortKeyDict, {"foo": ""}, {"foo": ""}),
    ],
    ids=objects.get_id,
)
def test_cast_constrained(type, value, expected):
    assert type(value) == expected


@pytest.mark.parametrize(
    argnames=("type", "value"),
    argvalues=[
        (objects.ShortStr, "fooooo"),
        (objects.LargeInt, 500),
        (objects.LargeIntDict, {"foo": 1}),
        (objects.LargeIntDict, {"fooooo": 1001}),
        (objects.ItemizedValuedDict, {"foo": 1}),
        (objects.ItemizedDict, {"foo": 1}),
        (objects.ItemizedKeyedValuedDict, {"foo": 1}),
        (objects.ItemizedKeyedDict, {"foo": 1}),
        (objects.ItemizedValuedDict, {"blah": "foooooooo"}),
        (objects.ItemizedKeyedValuedDict, {"blah": "foooooooo"}),
        (objects.ItemizedKeyedDict, {"foooooooo": "blah"}),
        (objects.ShortKeyDict, {"fooooooo": "blah"}),
    ],
    ids=objects.get_id,
)
def test_cast_constrained_invalid(type, value):
    with pytest.raises(ConstraintValueError):
        transmute(type, value)


def test_typic_klass_constrained():
    inst = objects.Constrained(1, "1001")
    assert inst.short == "1"
    assert inst.large == 1001


def test_bad_constraint_class():
    with pytest.raises(TypeError):

        @constrained
        class Foo:
            ...


def test_strict_mode():
    assert not is_strict_mode()
    strict_mode()
    assert is_strict_mode()
    resolver.STRICT._unstrict_mode()
    assert not is_strict_mode()


def test_enforce_strict_mode():
    strict_mode()

    @typed
    @dataclasses.dataclass
    class Foo:
        bar: str

    with pytest.raises(ConstraintValueError):
        Foo(1)

    resolver.STRICT._unstrict_mode()


def test_constrained_any():
    strict_mode()

    @typed
    @dataclasses.dataclass
    class Foo:
        bar: typing.Any

    assert Foo(1).bar == 1
    assert Foo("bar").bar == "bar"

    resolver.STRICT._unstrict_mode()


@pytest.mark.parametrize(
    argnames=("anno", "val"),
    argvalues=[
        (Strict[typing.List[int]], ["1"]),
        (Strict[typing.List[int]], [1.0]),
        (Strict[typing.List[int]], [None]),
        (Strict[typing.List[int]], {1}),
        (Strict[typing.Optional[typing.List[int]]], {None}),
        (Strict[typing.Optional[typing.List[int]]], [1.0]),
        (typing.Optional[Strict[str]], 1.0),
        (Strict[typing.Union[int, str]], 1.0),
        (Strict[typing.Union[int, str]], None),
        (StrictStrT, b""),
    ],
    ids=objects.get_id,
)
def test_strict_anno_fails(anno, val):
    with pytest.raises(ConstraintValueError):
        transmute(anno, val)


@pytest.mark.parametrize(
    argnames=("anno", "val"),
    argvalues=[
        (Strict[typing.List[int]], [1]),
        (Strict[typing.Optional[typing.List[int]]], None),
        (Strict[typing.Optional[typing.List[int]]], [1]),
        (typing.Optional[Strict[str]], None),
        (typing.Optional[Strict[str]], "foo"),
        (Strict[typing.Optional[str]], "foo"),
        (Strict[typing.Optional[str]], None),
        (Strict[typing.Union[int, str]], 1),
        (Strict[typing.Union[int, str]], "foo"),
        (StrictStrT, "foo"),
    ],
    ids=objects.get_id,
)
def test_strict_anno_passes(anno, val):
    assert transmute(anno, val) == val


@pytest.mark.parametrize(
    argnames=("func", "args", "kwargs"),
    argvalues=[
        (objects.strictvaradd, ("1", 2), {"foo": 3}),
        (objects.strictvaradd, (1, None), {"foo": 3}),
        (objects.strictvaradd, (1, 2), {"foo": b"4"}),
    ],
    ids=objects.get_id,
)
def test_strict_varargs_fails(func, args, kwargs):
    with pytest.raises(ConstraintValueError):
        func(*args, **kwargs)


@pytest.mark.parametrize(
    argnames=("func", "args", "kwargs", "expected"),
    argvalues=[(objects.strictvaradd, (1, 2), {"foo": 3}, 6)],
    ids=objects.get_id,
)
def test_strict_varargs_passes(func, args, kwargs, expected):
    assert func(*args, **kwargs) == expected


@constrained(values=NetworkAddress)
class Addresses(list):
    ...


@constrained(values=NetworkAddress)
class AddresseMap(dict):
    ...


@pytest.mark.parametrize(
    argnames=("anno", "val", "expected"),
    argvalues=[
        (
            Addresses,
            {"tcp://foo"},
            Addresses((NetworkAddress("tcp://foo"),)),
        ),
        (
            AddresseMap,
            {"foo": "tcp://foo"},
            AddresseMap(foo=NetworkAddress("tcp://foo")),
        ),
    ],
    ids=objects.get_id,
)
def test_transmute_nested_constrained(anno, val, expected):
    c = transmute(anno, val)
    assert c == expected


@pytest.mark.parametrize(
    argnames="t, v",
    argvalues=[
        (objects.Typic, {"var": "foo"}),
        (objects.TDict, {"a": 1}),
        (objects.DefaultEllipsis, {"ellipsis": ...}),
        (objects.DefaultNone, {"none": None}),
        (typing.Union[str, pathlib.Path], pathlib.Path(".")),
        (typing.Union[str, pathlib.Path], "."),
    ],
    ids=objects.get_id,
)
def test_validate(t, v):
    assert validate(t, v) == v


@pytest.mark.parametrize(
    argnames="t, v",
    argvalues=[(objects.Typic, {"var": "foo"}), (objects.TDict, {"a": 1})],
    ids=objects.get_id,
)
def test_validate_transmute(t, v):
    assert validate(t, v, transmute=True) == t(**v)


@pytest.mark.parametrize(
    argnames="t, v",
    argvalues=[
        (int, ""),
        (str, 0),
        (bytes, ""),
        (float, 1),
        (list, set()),
        (dict, []),
        (objects.Typic, {"var": 1}),
        (objects.TDict, {"a": ""}),
        (typing.Mapping[int, str], {"b": ""}),
        (
            typing.Mapping[pathlib.Path, str],
            {1: ""},
        ),
        (typing.Union[str, pathlib.Path], 1),
    ],
    ids=objects.get_id,
)
def test_validate_invalid(t, v):
    with pytest.raises(ConstraintValueError):
        validate(t, v)


@pytest.mark.parametrize(
    argnames="target",
    argvalues=[
        dict,
        list,
        tuple,
        typing.Iterator,
        objects.Alchemy,
        objects.Pydantic,
        objects.Typical,
    ],
)
@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        objects.Alchemy(bar="bar"),
        objects.Pydantic(bar="bar"),
        objects.Typical(bar="bar"),
    ],
    ids=objects.get_id,
)
def test_translate(target, value):
    t = translate(value, target)
    assert isinstance(t, target)


class Cls:
    ...


@pytest.mark.parametrize(
    argnames="target,value,exc",
    argvalues=[
        (objects.Typic, objects.Alchemy(bar="bar"), ValueError),
        (Cls, objects.Alchemy(bar="bar"), TypeError),
    ],
    ids=objects.get_id,
)
def test_translate_error(target, value, exc):
    with pytest.raises(exc):
        translate(value, target)


def test_prevent_recursion_with_slots():

    with pytest.raises(TypeError):

        class SubMeta(metaclass=objects.MetaSlotsClass):
            a: int


@pytest.mark.parametrize(
    argnames="annotation,value,expected",
    argvalues=[
        (objects.A, {}, objects.A()),
        (objects.B, {"a": {"b": None}}, objects.B(objects.A())),
        (objects.C, {"c": None}, objects.C()),
        (objects.C, {"c": {}}, objects.C(objects.C())),
        (objects.D, {"d": None}, objects.D()),
        (objects.D, {"d": {}}, objects.D(objects.D())),
        (objects.E, {}, objects.E()),
        (
            objects.E,
            {"d": {}, "f": {"g": {"h": "1"}}},
            objects.E(objects.D(), objects.F(objects.G(1))),
        ),
        (
            objects.ABs,
            {"a": {}, "bs": [{}]},
            objects.ABs(a=objects.A(), bs=[objects.B()]),
        ),
        (
            objects.H,
            {"hs": [{"hs": []}]},
            objects.H(hs=[objects.H(hs=[])]),
        ),
        (
            objects.J,
            {"js": [{"js": []}]},
            objects.J(js=[objects.J(js=[])]),
        ),
    ],
)
def test_recursive_transmute(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation)
    assert transmuted == expected


@pytest.mark.parametrize(
    argnames="annotation,value",
    argvalues=[
        (objects.A, {}),
        (objects.B, {"a": {"b": None}}),
        (objects.C, {"c": None}),
        (objects.C, {"c": {}}),
        (objects.D, {"d": None}),
        (objects.D, {"d": {}}),
        (objects.E, {}),
        (
            objects.E,
            {"d": {}, "f": {"g": {"h": 1}}},
        ),
        (
            objects.ABs,
            {"a": {}, "bs": [{}]},
        ),
        (
            objects.H,
            {"hs": [{"hs": []}]},
        ),
        (
            objects.J,
            {"js": [{"js": []}]},
        ),
    ],
)
def test_recursive_validate(annotation, value):
    validated = validate(annotation, value)
    assert validated == value


@pytest.mark.parametrize(
    argnames="value,expected",
    argvalues=[
        (objects.A(), {"b": None}),
        (objects.B(objects.A()), {"a": {"b": None}}),
        (objects.C(), {"c": None}),
        (objects.C(objects.C()), {"c": {"c": None}}),
        (objects.D(), {"d": None}),
        (objects.D(objects.D()), {"d": {"d": None}}),
        (objects.E(), {"d": None, "f": None}),
        (
            objects.E(objects.D(), objects.F(objects.G(1))),
            {"d": {"d": None}, "f": {"g": {"h": 1}}},
        ),
        (
            objects.ABs(a=objects.A(), bs=[objects.B()]),
            {"a": {"b": None}, "bs": [{"a": None}]},
        ),
        (
            objects.H(hs=[objects.H(hs=[])]),
            {"hs": [{"hs": []}]},
        ),
        (
            objects.J(js=[objects.J(js=[])]),
            {"js": [{"js": []}]},
        ),
    ],
)
def test_recursive_primitive(value, expected):
    prim = primitive(value)
    assert prim == expected


@pytest.mark.parametrize(
    argnames="annotation,value",
    argvalues=[
        (objects.B, {"a": {"b": {"a": 1}}}),
        (
            objects.E,
            {"d": {}, "f": {"g": {"h": "1"}}},
        ),
    ],
)
def test_recursive_validate_invalid(annotation, value):
    with pytest.raises(ConstraintValueError):
        validate(annotation, value)


# Note - we're testing with recursive tagged unions.
@pytest.mark.parametrize(
    argnames="annotation,value,expected",
    argvalues=[
        (
            objects.ABlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": 0}}},
            objects.ABlah(
                key=3, field=objects.ABlah(key=3, field=objects.ABar(key=2, field=b""))
            ),
        ),
        (
            objects.CBlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": 0}}},
            objects.CBlah(field=objects.CBlah(field=objects.CBar(field=b""))),
        ),
        (
            objects.DBlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": 0}}},
            objects.DBlah(field=objects.DBlah(field=objects.DBar(field=b""))),
        ),
    ],
)
def test_tagged_union_transmute(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation)
    assert transmuted == expected


@pytest.mark.parametrize(
    argnames="annotation,value",
    argvalues=[
        (
            objects.ABlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": b""}}},
        ),
        (
            objects.CBlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": b""}}},
        ),
        (
            objects.DBlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": b""}}},
        ),
    ],
)
def test_tagged_union_validate(annotation, value):
    validated = validate(annotation, value)
    assert validated == value


@pytest.mark.parametrize(
    argnames="annotation,value,expected,t",
    argvalues=[
        (typing.Union[int, str], "1", 1, int),
        (typing.Union[int, str], "foo", "foo", str),
        (typing.Union[int, datetime.date], "1", 1, int),
        (
            typing.Union[int, datetime.date],
            "1970-01-01",
            datetime.date(1970, 1, 1),
            datetime.date,
        ),
        (
            typing.Union[objects.LargeFloat, objects.LargeInt],
            "1001",
            1001,
            objects.LargeInt,
        ),
        (
            typing.Union[objects.LargeFloat, objects.LargeInt],
            "1001.0",
            1001.0,
            objects.LargeFloat,
        ),
        (
            typing.Union[objects.LargeFloat, objects.LargeInt],
            1001.0,
            1001.0,
            objects.LargeFloat,
        ),
    ],
)
def test_union_transmute(annotation, value, expected, t):
    transmuted = transmute(annotation, value)
    assert transmuted == expected
    assert isinstance(transmuted, t)


@pytest.mark.parametrize(
    argnames="annotation,value",
    argvalues=[
        (
            objects.ABlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": None}}},
        ),
        (
            objects.CBlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": None}}},
        ),
        (
            objects.DBlah,
            {"key": 3, "field": {"key": 3, "field": {"key": 2, "field": None}}},
        ),
    ],
)
def test_tagged_union_validate_invalid(annotation, value):
    with pytest.raises(ConstraintValueError):
        validate(annotation, value)


def test_local_namespace():
    @dataclasses.dataclass
    class Inner:
        field: str

    @dataclasses.dataclass
    class Outer:
        inner: Inner

    proto = resolver.resolve(Outer)

    obj = proto.transmute({"inner": {"field": "value"}})
    assert isinstance(obj.inner, Inner)


def test_pep_585():
    assert typic.transmute(objects.Pep585, {"data": {"foo": "1"}}) == objects.Pep585(
        data={"foo": 1}
    )
    assert objects.pep585({"foo": "1"}) == {"foo": 1}


def test_pep_604():
    assert typic.transmute(
        objects.Pep604, {"union": {"key": 1, "field": "blah"}}
    ) == objects.Pep604(union=objects.DFoo("blah"))
    assert objects.pep604({"key": 2, "field": "blah"}) == objects.DBar(b"blah")
