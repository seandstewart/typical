from __future__ import annotations

import dataclasses
import datetime
import inspect
import re
import uuid
from collections import defaultdict
from typing import (
    Dict,
    TypeVar,
    List,
    DefaultDict,
    Set,
    FrozenSet,
    Tuple,
    Iterable,
    Collection,
    NamedTuple,
    Union,
    ClassVar,
)

import pendulum
import pytest

from typic.compat import TypedDict, Literal
from typic.serde.common import Annotation
from typic.serde.des import routines
from typic.serde.resolver import Resolver


class NoopDeserializerRoutine(routines.BaseDeserializerRoutine):
    def _get_deserializer(self):
        return lambda val: val


class EQStr(str):
    def equals(self, o):

        return o.__class__ is self.__class__ and self.__eq__(o)


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class MyDict(Dict[_KT, _VT]):
    ...


class MyEmptyClass:
    ...


class MyReqClass:
    def __init__(self, foo: str):
        self.foo = foo


@pytest.fixture
def resolver():
    return Resolver()


class TestBaseDeserializerRoutine:
    @pytest.fixture
    def string(self, resolver) -> NoopDeserializerRoutine[str]:
        return NoopDeserializerRoutine(
            annotation=Annotation(
                str,
                str,
                str,
                inspect.Parameter("_", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            ),
            resolver=resolver,
        )

    @pytest.fixture
    def num(self, resolver) -> NoopDeserializerRoutine[int]:
        return NoopDeserializerRoutine(
            annotation=Annotation(
                int,
                int,
                int,
                inspect.Parameter("_", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            ),
            resolver=resolver,
        )

    @pytest.fixture
    def strlist(self, resolver) -> NoopDeserializerRoutine[list[str]]:
        return NoopDeserializerRoutine(
            annotation=Annotation(
                List[str],
                list,
                List[str],
                inspect.Parameter("_", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            ),
            resolver=resolver,
        )

    @pytest.fixture
    def eqstr(self, resolver) -> NoopDeserializerRoutine[EQStr]:
        return NoopDeserializerRoutine(
            annotation=Annotation(
                EQStr,
                EQStr,
                EQStr,
                inspect.Parameter("_", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            ),
            resolver=resolver,
        )

    def test_get_evaluate_str(self, string):
        # Given
        evaluate = string._get_evaluate()
        val = "foo"
        # When
        e = evaluate(val)
        # Then
        assert e is val

    def test_get_evaluate_non_str(self, num):
        # Given
        evaluate = num._get_evaluate()
        val = "1"
        # When
        e = evaluate(val)
        # Then
        assert e == 1

    class MyStr(str):
        ...

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            ("foo", ("foo", True)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_standard_eq_checks(self, string, resolver, val, expected):
        # Given
        check = string._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            ("foo", ("foo", True)),
            ("bar", ("bar", True)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_standard_eq_checks_default(self, string, resolver, val, expected):
        # Given
        string.annotation = resolver.annotation(str, default="foo")
        check = string._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            ("foo", ("foo", True)),
            (None, (None, True)),
            (..., (..., True)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_standard_eq_checks_nullable(self, string, resolver, val, expected):
        # Given
        string.annotation = resolver.annotation(str, is_optional=True)
        check = string._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            ("foo", ("foo", True)),
            ("bar", ("bar", True)),
            (None, (None, True)),
            (..., (..., True)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_standard_eq_checks_nullable_default(
        self, string, resolver, val, expected
    ):
        # Given
        string.annotation = resolver.annotation(str, is_optional=True, default="foo")
        check = string._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (["foo"], (["foo"], False)),
            ([b"foo"], ([b"foo"], False)),
            ([1], ([1], False)),
        ],
    )
    def test_get_subscripted_eq_checks(self, strlist, resolver, val, expected):
        # Given
        check = strlist._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (["foo"], (["foo"], True)),
            (["bar"], (["bar"], False)),
            ([b"foo"], ([b"foo"], False)),
            ([1], ([1], False)),
        ],
    )
    def test_get_subscripted_eq_checks_default(self, strlist, resolver, val, expected):
        # Given
        strlist.annotation = resolver.annotation(List[str], default=["foo"])
        check = strlist._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (None, (None, True)),
            (..., (..., True)),
            (["bar"], (["bar"], False)),
            ([b"foo"], ([b"foo"], False)),
            ([1], ([1], False)),
        ],
    )
    def test_get_subscripted_eq_checks_nullable(self, strlist, resolver, val, expected):
        # Given
        strlist.annotation = resolver.annotation(List[str], is_optional=True)
        check = strlist._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (None, (None, True)),
            (..., (..., True)),
            (["foo"], (["foo"], True)),
            (["bar"], (["bar"], False)),
            ([b"foo"], ([b"foo"], False)),
            ([1], ([1], False)),
        ],
    )
    def test_get_subscripted_eq_checks_nullable_default(
        self, resolver, strlist, val, expected
    ):
        # Given
        strlist.annotation = resolver.annotation(
            List[str], is_optional=True, default=["foo"]
        )
        check = strlist._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (EQStr("foo"), (EQStr("foo"), True)),
            ("foo", ("foo", False)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_custom_eq_checks(self, eqstr, resolver, val, expected):
        # Given
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (EQStr("foo"), (EQStr("foo"), True)),
            ("foo", ("foo", True)),
            (MyStr("foo"), (MyStr("foo"), True)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_custom_eq_checks_default(self, eqstr, resolver, val, expected):
        # Given
        eqstr.annotation = resolver.annotation(EQStr, default="foo")
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (EQStr("foo"), (EQStr("foo"), True)),
            (EQStr("bar"), (EQStr("bar"), True)),
            ("foo", ("foo", False)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_custom_eq_checks_default_custom_eq(
        self, eqstr, resolver, val, expected
    ):
        # Given
        eqstr.annotation = resolver.annotation(EQStr, default=EQStr("foo"))
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (EQStr("foo"), (EQStr("foo"), True)),
            (None, (None, True)),
            (..., (..., True)),
            ("foo", ("foo", False)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_custom_eq_checks_nullable(self, eqstr, resolver, val, expected):
        # Given
        eqstr.annotation = resolver.annotation(EQStr, is_optional=True)
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (EQStr("foo"), (EQStr("foo"), True)),
            (EQStr("bar"), (EQStr("bar"), True)),
            ("foo", ("foo", True)),
            (None, (None, True)),
            (..., (..., True)),
            (MyStr("foo"), (MyStr("foo"), True)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_custom_eq_checks_nullable_default(
        self, eqstr, resolver, val, expected
    ):
        # Given
        eqstr.annotation = resolver.annotation(EQStr, is_optional=True, default="foo")
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.parametrize(
        argnames="val,expected",
        argvalues=[
            (EQStr("foo"), (EQStr("foo"), True)),
            (EQStr("bar"), (EQStr("bar"), True)),
            ("foo", ("foo", False)),
            (None, (None, True)),
            (..., (..., True)),
            (MyStr("foo"), (MyStr("foo"), False)),
            (b"foo", (b"foo", False)),
        ],
    )
    def test_get_custom_eq_checks_nullable_default_custom_eq(
        self, eqstr, resolver, val, expected
    ):
        # Given
        eqstr.annotation = resolver.annotation(
            EQStr, is_optional=True, default=EQStr("foo")
        )
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    def test_deserializer(self, num):
        # Given
        deserializer = num.deserializer()
        # When
        d = deserializer("1")
        # Then
        assert d == 1


class TestSimpleDeserializerRoutine:
    @pytest.mark.parametrize(
        argnames="t,v", argvalues=[(int, "1"), (int, 1.0), (defaultdict, "{}")]
    )
    def test_deserializer(self, t, v, resolver):
        # Given
        routine = routines.SimpleDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestTextDeserializerRoutine:
    @pytest.fixture(params=[str, bytes, bytearray])
    def routine(self, request, resolver):
        return routines.TextDeserializerRoutine(
            annotation=resolver.annotation(request.param), resolver=resolver
        )

    @pytest.mark.parametrize(argnames="v", argvalues=["1", b"1", 1])
    def test_deserializer(self, v, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestDateDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.DateDeserializerRoutine(
            annotation=resolver.annotation(datetime.date), resolver=resolver
        )

    @pytest.mark.parametrize(
        argnames="v",
        argvalues=[
            1,
            1.0,
            "1970",
            "1970-01-01",
            b"1970-01-01",
            datetime.date(1970, 1, 1),
            datetime.datetime(1970, 1, 1),
        ],
    )
    def test_deserializer(self, v, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestDateTimeDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.DateTimeDeserializerRoutine(
            annotation=resolver.annotation(datetime.datetime), resolver=resolver
        )

    @pytest.mark.parametrize(
        argnames="v",
        argvalues=[
            1,
            1.0,
            "1970",
            "1970-01-01",
            b"1970-01-01",
            datetime.date(1970, 1, 1),
            datetime.datetime(1970, 1, 1),
            pendulum.DateTime.today(),
        ],
    )
    def test_deserializer(self, v, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestTimeDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.TimeDeltaDeserializerRoutine(
            annotation=resolver.annotation(datetime.timedelta), resolver=resolver
        )

    @pytest.mark.parametrize(
        argnames="v",
        argvalues=[
            1,
            1.0,
            "P0Y0M0DT0H0M0S",
            b"P0Y0M0DT0H0M0S",
            datetime.timedelta(),
            pendulum.Duration(),
        ],
    )
    def test_deserializer(self, v, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestUUIDDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.UUIDDeserializerRoutine(
            annotation=resolver.annotation(uuid.UUID), resolver=resolver
        )

    @pytest.mark.parametrize(
        argnames="v",
        argvalues=[
            0,
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
            (0, 0, 0, 0, 0, 0),
            uuid.UUID(int=0),
            "00000000-0000-0000-0000-000000000000",
        ],
    )
    def test_deserializer(self, v, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestPatternDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.PatternDeserializerRoutine(
            annotation=resolver.annotation(re.Pattern), resolver=resolver
        )

    @pytest.mark.parametrize(
        argnames="v",
        argvalues=[".*", re.compile(".*")],
    )
    def test_deserializer(self, v, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestMappingDeserializerRoutine:
    @pytest.fixture(
        params=[
            dict,
            MyDict[str, int],
            DefaultDict,
            DefaultDict[str, int],
            DefaultDict[str, "int"],
        ]
    )
    def routine(self, request, resolver):
        return routines.MappingDeserializerRoutine(
            annotation=resolver.annotation(request.param), resolver=resolver
        )

    @pytest.mark.parametrize(
        argnames="v,expected",
        argvalues=[
            ("{}", {}),
            ('{"foo":1}', {"foo": 1}),
            ('{"foo":1.0}', {"foo": 1}),
            ('{"foo":"1"}', {"foo": 1}),
            (b'{"foo":"1"}', {"foo": 1}),
            (MyReqClass(foo="1"), {"foo": 1}),
        ],
    )
    def test_deserializer(self, v, expected, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin
        if routine.annotation.args:
            assert d == expected

    @pytest.mark.parametrize(
        argnames="v,expected",
        argvalues=[
            ("{}", {}),
            ('{"foo":1}', {"bar": 1}),
            ('{"foo":1.0}', {"bar": 1}),
            ('{"foo":"1"}', {"bar": 1}),
            (b'{"foo":"1"}', {"bar": 1}),
        ],
    )
    def test_deserializer_aliased(self, v, expected, routine):
        # Given
        routine.annotation.serde.fields_in = {"foo": "bar"}
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin
        if routine.annotation.args:
            assert d == expected

    @pytest.mark.parametrize(
        argnames="t,v,expected",
        argvalues=[
            (DefaultDict, {}, defaultdict(None)),
            (DefaultDict[str, int], {}, defaultdict(int)),
            (DefaultDict[str, "int"], {}, defaultdict(int)),
            (DefaultDict[str, MyEmptyClass], {}, defaultdict(MyEmptyClass)),
            (DefaultDict[str, MyReqClass], {}, defaultdict(None)),
        ],
    )
    def test_defaultdict_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.MappingDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert isinstance(d, routine.annotation.resolved_origin) and d == expected

    def test_defaultdict_nested_deserializer(self, resolver):
        # Given
        routine = routines.MappingDeserializerRoutine(
            annotation=resolver.annotation(DefaultDict[str, DefaultDict]),
            resolver=resolver,
        )
        deserializer = routine.deserializer()
        # When
        d = deserializer({})
        # Then
        assert isinstance(d, defaultdict) and isinstance(d["foo"], defaultdict)


class TestCollectionDeserializerRoutine:
    @pytest.mark.parametrize(
        argnames="t,v,expected",
        argvalues=[
            (List[int], '["1"]', [1]),
            (Set[int], '["1"]', {1}),
            (FrozenSet[int], '["1"]', frozenset({1})),
            (Tuple[int, ...], '["1"]', (1,)),
            (Iterable[int], '["1"]', [1]),
            (Collection[int], '["1"]', [1]),
            (Collection[int], MyReqClass(foo="1"), [1]),
        ],
    )
    def test_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.CollectionDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert isinstance(d, routine.annotation.resolved_origin) and d == expected


class MyTup(Tuple[_VT]):
    ...


class TestFixedTupleDeserializerRoutine:
    @pytest.mark.parametrize(
        argnames="t",
        argvalues=[Tuple[int, str], MyTup[int, str]],
    )
    def test_deserializer(self, t, resolver):
        # Given
        v, expected = '["1", 1]', (1, "1")
        routine = routines.FixedTupleDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert isinstance(d, routine.annotation.resolved_origin) and d == expected


@dataclasses.dataclass
class Foo:
    bar: str


class FooTup(NamedTuple):
    bar: str


class FooDict(TypedDict):
    bar: int


class TestFieldsDeserializerRoutine:
    @pytest.mark.parametrize(
        argnames="t,v,expected",
        argvalues=[
            (Foo, (1,), Foo("1")),
            (Foo, "foo", Foo("foo")),
            (Foo, {"bar": 1}, Foo("1")),
            (Foo, FooTup("1"), Foo("1")),
            (FooTup, Foo("1"), FooTup("1")),
        ],
    )
    def test_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.FieldsDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert isinstance(d, t) and d == expected

    @pytest.mark.parametrize(
        argnames="t,v,expected",
        argvalues=[
            (Foo, (1,), Foo("1")),
            (Foo, "foo", Foo("foo")),
            (Foo, {"foo": 1}, Foo("1")),
            (Foo, FooTup("1"), Foo("1")),
            (FooTup, Foo("1"), FooTup("1")),
        ],
    )
    def test_aliased_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.FieldsDeserializerRoutine(
            annotation=resolver.annotation(t, flags={"fields": {"bar": "foo"}}),
            resolver=resolver,
        )
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert isinstance(d, t) and d == expected


@dataclasses.dataclass
class AClass:
    tag: ClassVar[str] = "a"


@dataclasses.dataclass
class BClass:
    tag: ClassVar[str] = "b"


@dataclasses.dataclass
class CClass:
    tag: ClassVar[str] = "c"


class TestUnionDeserializerRoutine:
    @pytest.fixture
    def groutine(self, resolver):
        return routines.UnionDeserializerRoutine(
            annotation=resolver.annotation(Union[int, str]), resolver=resolver
        )

    @pytest.fixture
    def troutine(self, resolver):
        return routines.UnionDeserializerRoutine(
            annotation=resolver.annotation(Union[AClass, BClass, CClass]),
            resolver=resolver,
        )

    @pytest.mark.parametrize(
        argnames="v,expected",
        argvalues=[
            (1, 1),
            ("2", 2),
            ('"3"', "3"),
            ("foo", "foo"),
        ],
    )
    def test_generic_deserializer(self, v, expected, groutine):
        # Given
        deserializer = groutine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d == expected

    @pytest.mark.parametrize(
        argnames="v,expected",
        argvalues=[
            ({"tag": "a"}, AClass()),
            ({"tag": "b"}, BClass()),
            ({"tag": "c"}, CClass()),
        ],
    )
    def test_tagged_deserializer(self, v, expected, troutine):
        # Given
        deserializer = troutine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d == expected

    def test_generic_error(self, groutine):
        # Given
        deserializer = groutine.deserializer()
        # When/Then
        with pytest.raises(ValueError):
            deserializer(NoStr())

    def test_tagged_error(self, troutine):
        # Given
        deserializer = troutine.deserializer()
        # When/Then
        with pytest.raises(ValueError):
            deserializer({"tag": "d"})


class NoStr:
    def __str__(self):
        raise TypeError("Not today, satan.")

    def __repr__(self):
        return NoStr.__class__.__name__


class TestLiteralDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.LiteralDeserializerRoutine(
            annotation=resolver.annotation(Literal[1, 2]),
            resolver=resolver,
        )

    @pytest.mark.parametrize(argnames="v,expected", argvalues=[(1, 1), ("2", 2)])
    def test_deserializer(self, v, expected, routine):
        # Given
        deserializer = routine.deserializer()
        # When
        d = deserializer(v)
        # Then
        assert d == expected

    def test_deserializer_error(self, routine):
        # Given
        deserializer = routine.deserializer()
        # When/Then
        with pytest.raises(ValueError):
            deserializer(3)
