import dataclasses
import datetime
import inspect
import re
import typing
from collections import defaultdict
from operator import attrgetter

import pendulum
import pytest

from tests.objects import (
    FromDict,
    Data,
    Nested,
    NestedSeq,
    NestedFromDict,
    DefaultNone,
    Forward,
    FooNum,
    UserID,
    DateDict,
    NoParams,
    Class,
    func,
    Frozen,
    optional,
    varargs,
    Typic,
    FrozenTypic,
    Inherited,
    KlassVar,
    KlassVarSubscripted,
    Method,
    Delayed,
    delayed,
    ShortStr,
    LargeInt,
    Constrained,
    LargeIntDict,
    NTup,
    ntup,
    TDict,
    TDictPartial,
    ItemizedValuedDict,
    ItemizedDict,
    ItemizedKeyedDict,
    ItemizedKeyedValuedDict,
    ShortKeyDict,
    strictvaradd,
    Alchemy,
    Pydantic,
    Typical,
    get_id,
    SubTypic,
    SuperBase,
    Source,
    Dest,
)
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
)
from typic.checks import isbuiltintype, BUILTIN_TYPES
from typic.constraints import ConstraintValueError
from typic.util import safe_eval, resolve_supertype, origin as get_origin, get_args
from typic.types import NetworkAddress

NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.mark.parametrize(argnames="obj", argvalues=BUILTIN_TYPES)
def test_isbuiltintype(obj: typing.Any):
    assert isbuiltintype(obj)


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (dict, [("foo", "bar")], {"foo": "bar"}),
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
        (datetime.datetime, "1970-01-01", pendulum.datetime(1970, 1, 1)),
        (pendulum.DateTime, "1970-01-01", pendulum.datetime(1970, 1, 1)),
        (datetime.datetime, 0, datetime.datetime.fromtimestamp(0)),
        (datetime.datetime, NOW, NOW),
        (pendulum.DateTime, NOW, NOW),
        (datetime.date, "1970-01-01", pendulum.date(1970, 1, 1)),
        (datetime.date, 0, datetime.date.fromtimestamp(0)),
        (datetime.datetime, datetime.date(1980, 1, 1), datetime.datetime(1980, 1, 1)),
        (datetime.date, datetime.datetime(1980, 1, 1), datetime.date(1980, 1, 1)),
        (FromDict, {"foo": "bar!"}, FromDict("bar!")),
        (Data, {"foo": "bar!"}, Data("bar!")),
        (Nested, {"data": {"foo": "bar!"}}, Nested(Data("bar!"))),
        (Nested, {"data": {"foo": "bar!", "something": "else"}}, Nested(Data("bar!"))),
        (NestedFromDict, {"data": {"foo": "bar!"}}, NestedFromDict(Data("bar!"))),
        (FooNum, "bar", FooNum.bar),
        (Data, Data("bar!"), Data("bar!"),),
        (NetworkAddress, "localhost", NetworkAddress("localhost")),
        (typing.Pattern, r"\w+", re.compile(r"\w+")),
        (Data, FromDict("bar!"), Data("bar!")),
        (Nested, NestedFromDict(Data("bar!")), Nested(Data("bar!"))),
        (Nested, NestedFromDict(Data("bar!")), Nested(Data("bar!"))),
        (SubTypic, {"var": "var", "sub": b"sub"}, SubTypic("var", "sub")),  # type: ignore
        (SuperBase, {"super": b"base!"}, SuperBase("base!")),  # type: ignore
        (Dest, Source(), Dest(Source().test)),  # type: ignore
        (MyClass, factory(), MyClass(1)),
        (defaultdict, {}, defaultdict(None)),
    ],
    ids=get_id,
)
def test_transmute_simple(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation)
    assert transmuted == expected


@pytest.mark.parametrize(argnames=("annotation", "value"), argvalues=[(UserID, "1")])
def test_transmute_newtype(annotation, value):
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation.__supertype__)


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (TDict, '{"a": "2"}', {"a": 2}),
        (NTup, '{"a": "2"}', NTup(2)),
        (ntup, '{"a": "2"}', ntup("2")),
        (TDictPartial, "{}", {}),
    ],
    ids=get_id,
)
def test_transmute_collection_metas(annotation, value, expected):
    transmuted = transmute(annotation, value)
    assert transmuted == expected


def test_default_none():
    transmuted = transmute(DefaultNone, {})
    assert transmuted.none is None


@pytest.mark.parametrize(
    argnames=("annotation", "origin"),
    argvalues=[
        (typing.List, list),
        (typing.ClassVar, typing.ClassVar),
        (typing.List[str], list),
    ],
    ids=get_id,
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
    ids=get_id,
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
    ids=get_id,
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
        (typing.Collection[FromDict], [{"foo": "bar!"}]),
        (typing.Collection[Data], [{"foo": "bar!"}]),
        (typing.Collection[Nested], [{"data": {"foo": "bar!"}}]),
        (typing.Collection[NestedFromDict], [{"data": {"foo": "bar!"}}]),
        (typing.Collection[NestedFromDict], ["{'data': {'foo': 'bar!'}}"]),
    ],
    ids=get_id,
)
def test_transmute_collections_subscripted(annotation, value):
    arg = annotation.__args__[0]
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation.__origin__) and all(
        isinstance(x, arg) for x in transmuted
    )


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
        (typing.Dict[str, FromDict], {"blah": {"foo": "bar!"}}),
        (typing.Mapping[int, Data], {"0": {"foo": "bar!"}}),
        (typing.Dict[datetime.date, Nested], {"1970": {"data": {"foo": "bar!"}}}),
        (typing.Mapping[bool, NestedFromDict], {0: {"data": {"foo": "bar!"}}}),
        (typing.Dict[bytes, NestedFromDict], {0: "{'data': {'foo': 'bar!'}}"}),
        (DateDict, '{"1970": "foo"}'),
        (typing.DefaultDict[str, int], {}),
        (typing.DefaultDict[str, typing.DefaultDict[str, int]], {"foo": {}},),
        (typing.DefaultDict[str, DefaultNone], {"foo": {}},),
    ],
    ids=get_id,
)
def test_transmute_mapping_subscripted(annotation, value):
    annotation = resolve_supertype(annotation)
    key_arg, value_arg = annotation.__args__
    transmuted = transmute(annotation, value)
    assert isinstance(transmuted, annotation.__origin__)
    assert all(isinstance(x, get_origin(key_arg)) for x in transmuted.keys())
    assert all(isinstance(x, get_origin(value_arg)) for x in transmuted.values())


def test_transmute_nested_sequence():
    transmuted = transmute(NestedSeq, {"datum": [{"foo": "bar"}]})
    assert isinstance(transmuted, NestedSeq)
    assert all(isinstance(x, Data) for x in transmuted.datum)


@pytest.mark.parametrize(
    argnames=("func", "input", "type"),
    argvalues=[(func, "1", int), (Method().math, "4", int)],
)
def test_wrap_callable(func, input, type):
    wrapped = wrap(func)
    assert isinstance(wrapped(input), type)


@pytest.mark.parametrize(
    argnames=("klass", "var", "type"),
    argvalues=[(Class, "var", str), (Data, "foo", str)],
    ids=get_id,
)
def test_wrap_class(klass, var, type):
    Wrapped = wrap_cls(klass)
    assert isinstance(getattr(Wrapped(1), var), type)
    assert inspect.isclass(Wrapped)


@pytest.mark.parametrize(
    argnames=("obj", "input", "getter", "type", "check"),
    argvalues=[
        (func, "1", None, int, inspect.isfunction),
        (optional, 1, None, str, inspect.isfunction),
        (optional, None, None, type(None), inspect.isfunction),
        (Data, 1, attrgetter("foo"), str, inspect.isclass),
        (DefaultNone, None, attrgetter("none"), type(None), inspect.isclass),
        (Forward, "bar", attrgetter("foo"), FooNum, inspect.isclass),
        (Frozen, "0", attrgetter("var"), bool, inspect.isclass),
    ],
    ids=get_id,
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
            varargs,
            ({"foo": "bar"},),
            {"bar": {"foo": "bar"}},
            lambda res: all(isinstance(x, Data) for x in res),
        )
    ],
    ids=get_id,
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
        (DateDict, dict),
        (UserID, int),
    ],
    ids=get_id,
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
    argvalues=[(typed(Data)("foo"), "foo", 1, str), (typed(NoParams)(), "var", 1, str)],
    ids=get_id,
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
    assert resolver.resolve(MyCustomType).deserializer is MyCustomClass


@pytest.mark.parametrize(argnames=("val",), argvalues=[(1,), ("foo",)])
def test_no_transmuter(val):
    class NoTransmuter:
        def __init__(self, x):
            self.x = x

    assert transmute(NoTransmuter, val).x == val


def test_typic_klass():
    assert Typic(1).var == "1"


def test_typic_klass_is_dataclass():
    assert dataclasses.is_dataclass(Typic)


def test_typic_klass_passes_params():
    with pytest.raises(dataclasses.FrozenInstanceError):
        FrozenTypic(1).var = 2


def test_typic_klass_inheritance():
    assert isinstance(Inherited(1).var, str)


def test_typic_frozen():
    assert isinstance(FrozenTypic(1).var, str)


@pytest.mark.parametrize(
    argnames=("instance", "attr", "type"),
    argvalues=[(KlassVar(), "var", str), (KlassVarSubscripted(), "var", str)],
    ids=get_id,
)
def test_classvar(instance, attr, type):
    setattr(instance, attr, 1)
    assert isinstance(getattr(instance, attr), type)


def test_typic_callable_delayed():
    assert isinstance(delayed(1), str)


def test_typic_resolve():
    resolve()
    assert Delayed(1).foo == "1"


@pytest.mark.parametrize(
    argnames=("type", "value", "expected"),
    argvalues=[
        (ShortStr, "foo", "foo"),
        (ShortStr, 1, "1"),
        (LargeInt, "1001", 1001),
        (LargeIntDict, [("foo", 1001)], {"foo": 1001}),
        (ShortKeyDict, {"foo": ""}, {"foo": ""}),
    ],
    ids=get_id,
)
def test_cast_constrained(type, value, expected):
    assert type(value) == expected


@pytest.mark.parametrize(
    argnames=("type", "value"),
    argvalues=[
        (ShortStr, "fooooo"),
        (LargeInt, 500),
        (LargeIntDict, {"foo": 1}),
        (LargeIntDict, {"fooooo": 1001}),
        (ItemizedValuedDict, {"foo": 1}),
        (ItemizedDict, {"foo": 1}),
        (ItemizedKeyedValuedDict, {"foo": 1}),
        (ItemizedKeyedDict, {"foo": 1}),
        (ItemizedValuedDict, {"blah": "foooooooo"}),
        (ItemizedKeyedValuedDict, {"blah": "foooooooo"}),
        (ItemizedKeyedDict, {"foooooooo": "blah"}),
        (ShortKeyDict, {"fooooooo": "blah"}),
    ],
    ids=get_id,
)
def test_cast_constrained_invalid(type, value):
    with pytest.raises(ConstraintValueError):
        transmute(type, value)


def test_typic_klass_constrained():
    inst = Constrained(1, "1001")
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
        (Strict[typing.Union[str, int]], 1.0),
        (Strict[typing.Union[str, int]], None),
        (StrictStrT, b""),
    ],
    ids=get_id,
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
        (Strict[typing.Union[str, int]], 1),
        (Strict[typing.Union[str, int]], "foo"),
        (StrictStrT, "foo"),
    ],
    ids=get_id,
)
def test_strict_anno_passes(anno, val):
    assert transmute(anno, val) == val


@pytest.mark.parametrize(
    argnames=("func", "args", "kwargs"),
    argvalues=[
        (strictvaradd, ("1", 2), {"foo": 3}),
        (strictvaradd, (1, None), {"foo": 3}),
        (strictvaradd, (1, 2), {"foo": b"4"}),
    ],
    ids=get_id,
)
def test_strict_varargs_fails(func, args, kwargs):
    with pytest.raises(ConstraintValueError):
        func(*args, **kwargs)


@pytest.mark.parametrize(
    argnames=("func", "args", "kwargs", "expected"),
    argvalues=[(strictvaradd, (1, 2), {"foo": 3}, 6)],
    ids=get_id,
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
        (Addresses, {"tcp://foo"}, Addresses((NetworkAddress("tcp://foo"),)),),
        (
            AddresseMap,
            {"foo": "tcp://foo"},
            AddresseMap(foo=NetworkAddress("tcp://foo")),
        ),
    ],
    ids=get_id,
)
def test_transmute_nested_constrained(anno, val, expected):
    c = transmute(anno, val)
    assert c == expected


@pytest.mark.parametrize(
    argnames="t, v", argvalues=[(Typic, {"var": "foo"}), (TDict, {"a": 1})], ids=get_id,
)
def test_validate(t, v):
    assert validate(t, v) == v


@pytest.mark.parametrize(
    argnames="t, v", argvalues=[(Typic, {"var": "foo"}), (TDict, {"a": 1})], ids=get_id,
)
def test_validate_transmute(t, v):
    assert validate(t, v, transmute=True) == t(**v)


@pytest.mark.parametrize(
    argnames="t, v", argvalues=[(Typic, {"var": 1}), (TDict, {"a": ""})], ids=get_id,
)
def test_validate_invalid(t, v):
    with pytest.raises(ConstraintValueError):
        validate(t, v)


@pytest.mark.parametrize(argnames="target", argvalues=[Alchemy, Pydantic, Typical])
@pytest.mark.parametrize(
    argnames="value",
    argvalues=[Alchemy(bar="bar"), Pydantic(bar="bar"), Typical(bar="bar")],
    ids=get_id,
)
def test_translate(target, value):
    t = translate(value, target)
    assert isinstance(t, target)


class Cls:
    ...


@pytest.mark.parametrize(
    argnames="target,value,exc",
    argvalues=[
        (Typic, Alchemy(bar="bar"), ValueError),
        (Cls, Alchemy(bar="bar"), TypeError),
    ],
    ids=get_id,
)
def test_translate_error(target, value, exc):
    with pytest.raises(exc):
        translate(value, target)
