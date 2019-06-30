import dataclasses
import datetime
import inspect
import typing

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
)
from typic.checks import isbuiltintype, BUILTIN_TYPES, resolve_supertype
from typic.eval import safe_eval
from typic.klass import klass
from typic.typed import coerce, typed


@pytest.mark.parametrize(argnames="obj", argvalues=BUILTIN_TYPES)
def test_isbuiltintype(obj: typing.Any):
    assert isbuiltintype(obj)


@pytest.mark.parametrize(
    argnames=("annotation", "value"),
    argvalues=[
        (dict, [("foo", "bar")]),
        (typing.Dict, [("foo", "bar")]),
        (list, set()),
        (typing.List, set()),
        (set, list()),
        (typing.Set, list()),
        (tuple, list()),
        (typing.Tuple, list()),
        (str, 1),
        (typing.Text, 1),
        (float, 1),
        (bool, 1),
        (datetime.datetime, "1970-01-01"),
        (datetime.datetime, 0),
        (datetime.date, "1970-01-01"),
        (datetime.date, 0),
        (datetime.datetime, datetime.date(1980, 1, 1)),
        (datetime.date, datetime.datetime(1980, 1, 1)),
        (FromDict, {"foo": "bar!"}),
        (Data, {"foo": "bar!"}),
        (Nested, {"data": {"foo": "bar!"}}),
        (NestedFromDict, {"data": {"foo": "bar!"}}),
        (FooNum, "bar"),
        (Data, Data("bar!")),
    ],
)
def test_coerce_simple(annotation, value):
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation)


@pytest.mark.parametrize(argnames=("annotation", "value"), argvalues=[(UserID, "1")])
def test_coerce_newtype(annotation, value):
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation.__supertype__)


def test_default_none():
    coerced = coerce({}, DefaultNone)
    assert coerced.none is None


@pytest.mark.parametrize(
    argnames=("annotation", "value", "expected"),
    argvalues=[
        (typing.Optional[str], 1, "1"),
        (typing.Optional[str], None, None),
        (typing.ClassVar[str], 1, "1"),
    ],
)
def test_coerce_supscripted(annotation, value, expected):
    assert coerce(value, annotation) == expected


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
)
def test_coerce_collections_subscripted(annotation, value):
    arg = annotation.__args__[0]
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation.__origin__) and all(
        isinstance(x, arg) for x in coerced
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
    ],
)
def test_coerce_mapping_subscripted(annotation, value):
    annotation = resolve_supertype(annotation)
    key_arg, value_arg = annotation.__args__
    coerced = coerce(value, annotation)
    assert isinstance(coerced, annotation.__origin__)
    assert all(isinstance(x, key_arg) for x in coerced.keys())
    assert all(isinstance(x, value_arg) for x in coerced.values())


def test_coerce_nested_sequence():
    coerced = coerce({"datum": [{"foo": "bar"}]}, NestedSeq)
    assert isinstance(coerced, NestedSeq)
    assert all(isinstance(x, Data) for x in coerced.datum)


def test_wrap_callable():
    @coerce.wrap
    def foo(bar: str):
        return bar

    assert isinstance(foo(1), str)


def test_wrap_class():
    @coerce.wrap_cls
    class Foo:
        def __init__(self, bar: str):
            self.bar = bar

    assert isinstance(Foo(1).bar, str)
    assert inspect.isclass(Foo)


def test_wrap_dataclass():
    @coerce.wrap_cls
    @dataclasses.dataclass
    class Foo:
        bar: str

    assert isinstance(Foo(1).bar, str)
    assert inspect.isclass(Foo)


def test_ensure_callable():
    @typed
    def foo(bar: str):
        return bar

    assert isinstance(foo, typing.Callable)
    assert isinstance(foo(1), str)


def test_ensure_class():
    @typed
    @dataclasses.dataclass
    class Foo:
        bar: str

    assert inspect.isclass(Foo)
    assert isinstance(Foo(1).bar, str)


def test_ensure_default_none():
    assert typed(DefaultNone)().none is None


def test_ensure_invalid():
    with pytest.raises(TypeError):
        typed(1)


def test_ensure_enum():
    @typed
    @dataclasses.dataclass
    class Foo:
        bar: FooNum

    assert isinstance(Foo("bar").bar, FooNum)


def test_forward_ref():
    with pytest.raises(NameError):
        typed(Forward)("ref")


def test_varargs():
    @typed
    def foo(*args: Data, **kwargs: Data):
        return args + tuple(kwargs.values())

    datum = foo({"foo": "bar"}, bar={"foo": "blah"})

    assert all(isinstance(x, Data) for x in datum)


@pytest.mark.parametrize(
    argnames=("annotation", "origin"),
    argvalues=[
        (typing.Mapping[int, str], dict),
        (typing.Mapping, dict),
        (DateDict, dict),
        (UserID, int),
    ],
)
def test_get_origin_returns_origin(annotation, origin):
    detected = coerce.get_origin(annotation)
    assert detected is origin


def test_eval_invalid():
    processed, result = safe_eval("{")
    assert not processed
    assert result == "{"


@pytest.mark.parametrize(
    argnames=("annotation",), argvalues=[(typing.Any,), (typing.Union,)]
)
def test_special_form(annotation):
    param = inspect.Parameter(
        "foo", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation
    )
    assert coerce.should_coerce(param, "foo") is False


@pytest.mark.parametrize(
    argnames=("instance", "attr", "value", "type"),
    argvalues=[(typed(Data)("foo"), "foo", 1, str), (typed(NoParams)(), "var", 1, str)],
)
def test_setattr(instance, attr, value, type):
    setattr(instance, attr, value)
    assert isinstance(getattr(instance, attr), type)


def test_register():
    class MyCustomClass:
        def __init__(self, value: str):
            self.value = value

    class MyOtherCustomClass:
        def __init__(self, value: int):
            self.value = value

    MyCustomType = typing.Union[MyCustomClass, MyOtherCustomClass]

    def custom_class_coercer(value, annotation: MyCustomType):
        return annotation(value)

    def ismycustomclass(obj) -> bool:
        return obj in set(MyCustomType.__args__)

    coerce.register(custom_class_coercer, ismycustomclass)
    assert isinstance(coerce("foo", MyCustomClass), MyCustomClass)
    assert isinstance(coerce("foo", MyOtherCustomClass), MyOtherCustomClass)


def test_no_coercer():

    assert isinstance(coerce("foo", lambda x: 1), str)


def test_typed_class_inheritance():
    @typed
    @dataclasses.dataclass
    class Foo:
        bar: str

    class Foob(Foo):
        pass

    assert isinstance(Foob(1).bar, str)


def test_typic_klass():
    @klass
    class Foo:
        bar: str

    assert Foo(1).bar == "1"


def test_typic_klass_is_dataclass():
    @klass
    class Foo:
        bar: str

    assert dataclasses.is_dataclass(Foo)


def test_typic_klass_passes_params():
    @klass(frozen=True)
    class Foo:
        bar: str

    with pytest.raises(dataclasses.FrozenInstanceError):
        Foo(1).bar = 2


def test_typic_klass_inheritance():
    @klass
    class Foo:
        bar: str

    class Foob(Foo):
        pass

    assert isinstance(Foob(1).bar, str)
