from __future__ import annotations

import dataclasses
import datetime
import inspect
import re
import sys
import uuid
from collections import defaultdict
from typing import (
    ClassVar,
    Collection,
    DefaultDict,
    Dict,
    FrozenSet,
    Iterable,
    List,
    NamedTuple,
    Set,
    Tuple,
    TypeVar,
    Union,
)

import pendulum
import pytest

from typical.compat import Literal, TypedDict
from typical.core.interfaces import Annotation
from typical.resolver import Resolver
from typical.serde.des import routines

_T = TypeVar("_T")


class NoopDeserializerRoutine(routines.BaseDeserializerRoutine[_T]):
    def _get_deserializer(self):
        return lambda val: val


class EQStr(str):
    def equals(self, o):
        return o.__class__ is self.__class__ and self.__eq__(o)


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class MyDict(Dict[_KT, _VT]): ...


class MyEmptyClass: ...


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

    class MyStr(str): ...

    @pytest.mark.suite(
        string=dict(val="foo", expected=("foo", True)),
        user_string=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
    )
    def test_get_standard_eq_checks(self, string, resolver, val, expected):
        # Given
        check = string._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        string_default=dict(val="foo", expected=("foo", True)),
        string_non_default=dict(val="bar", expected=("bar", True)),
        user_string=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
    )
    def test_get_standard_eq_checks_default(self, string, resolver, val, expected):
        # Given
        string.annotation = resolver.annotation(str, default="foo")
        check = string._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        string=dict(val="foo", expected=("foo", True)),
        none=dict(val=None, expected=(None, True)),
        ellipsis=dict(val=..., expected=(..., True)),
        user_string=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
    )
    def test_get_standard_eq_checks_nullable(self, string, resolver, val, expected):
        # Given
        string.annotation = resolver.annotation(str, is_optional=True)
        check = string._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        string_default=dict(val="foo", expected=("foo", True)),
        string_non_default=dict(val="bar", expected=("bar", True)),
        none=dict(val=None, expected=(None, True)),
        ellipsis=dict(val=..., expected=(..., True)),
        user_string=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
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

    @pytest.mark.suite(
        string=dict(val=["foo"], expected=(["foo"], False)),
        bytes=dict(val=[b"foo"], expected=([b"foo"], False)),
        int=dict(val=[1], expected=([1], False)),
    )
    def test_get_subscripted_eq_checks(self, strlist, resolver, val, expected):
        # Given
        check = strlist._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        string_default=dict(val=["foo"], expected=(["foo"], True)),
        string_non_default=dict(val=["bar"], expected=(["bar"], False)),
        bytes=dict(val=[b"foo"], expected=([b"foo"], False)),
        int=dict(val=[1], expected=([1], False)),
    )
    def test_get_subscripted_eq_checks_default(self, strlist, resolver, val, expected):
        # Given
        strlist.annotation = resolver.annotation(List[str], default=["foo"])
        check = strlist._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        none=dict(val=None, expected=(None, True)),
        ellipsis=dict(val=..., expected=(..., True)),
        string=dict(val=["foo"], expected=(["foo"], False)),
        bytes=dict(val=[b"foo"], expected=([b"foo"], False)),
        int=dict(val=[1], expected=([1], False)),
    )
    def test_get_subscripted_eq_checks_nullable(self, strlist, resolver, val, expected):
        # Given
        strlist.annotation = resolver.annotation(List[str], is_optional=True)
        check = strlist._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        none=dict(val=None, expected=(None, True)),
        ellipsis=dict(val=..., expected=(..., True)),
        string_default=dict(val=["foo"], expected=(["foo"], True)),
        string_non_default=dict(val=["bar"], expected=(["bar"], False)),
        bytes=dict(val=[b"foo"], expected=([b"foo"], False)),
        int=dict(val=[1], expected=([1], False)),
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

    @pytest.mark.suite(
        eqstr=dict(val=EQStr("foo"), expected=(EQStr("foo"), True)),
        std_str=dict(val="foo", expected=("foo", False)),
        user_str=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
    )
    def test_get_custom_eq_checks(self, eqstr, resolver, val, expected):
        # Given
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        eqstr_default=dict(val=EQStr("foo"), expected=(EQStr("foo"), True)),
        eqstr_non_default=dict(val=EQStr("bar"), expected=(EQStr("bar"), True)),
        std_str=dict(val="foo", expected=("foo", True)),
        user_str=dict(val=MyStr("foo"), expected=(MyStr("foo"), True)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
    )
    def test_get_custom_eq_checks_default(self, eqstr, resolver, val, expected):
        # Given
        eqstr.annotation = resolver.annotation(EQStr, default="foo")
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        eqstr_default=dict(val=EQStr("foo"), expected=(EQStr("foo"), True)),
        eqstr_non_default=dict(val=EQStr("bar"), expected=(EQStr("bar"), True)),
        std_str=dict(val="foo", expected=("foo", False)),
        user_str=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
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

    @pytest.mark.suite(
        none=dict(val=None, expected=(None, True)),
        ellipsis=dict(val=..., expected=(..., True)),
        eqstr=dict(val=EQStr("foo"), expected=(EQStr("foo"), True)),
        std_str=dict(val="foo", expected=("foo", False)),
        user_str=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
    )
    def test_get_custom_eq_checks_nullable(self, eqstr, resolver, val, expected):
        # Given
        eqstr.annotation = resolver.annotation(EQStr, is_optional=True)
        check = eqstr._get_checks()
        # When
        result = check(val)
        # Then
        assert result == expected

    @pytest.mark.suite(
        none=dict(val=None, expected=(None, True)),
        ellipsis=dict(val=..., expected=(..., True)),
        eqstr_default=dict(val=EQStr("foo"), expected=(EQStr("foo"), True)),
        eqstr_non_default=dict(val=EQStr("bar"), expected=(EQStr("bar"), True)),
        std_str=dict(val="foo", expected=("foo", True)),
        user_str=dict(val=MyStr("foo"), expected=(MyStr("foo"), True)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
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

    @pytest.mark.suite(
        none=dict(val=None, expected=(None, True)),
        ellipsis=dict(val=..., expected=(..., True)),
        eqstr_default=dict(val=EQStr("foo"), expected=(EQStr("foo"), True)),
        eqstr_non_default=dict(val=EQStr("bar"), expected=(EQStr("bar"), True)),
        std_str=dict(val="foo", expected=("foo", False)),
        user_str=dict(val=MyStr("foo"), expected=(MyStr("foo"), False)),
        bytes=dict(val=b"foo", expected=(b"foo", False)),
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
        # When
        d = num("1")
        # Then
        assert d == 1


class TestSimpleDeserializerRoutine:
    @pytest.mark.suite(
        int_str=dict(t=int, v="1"),
        int_float=dict(t=int, v=1.0),
        defaultdict_str=dict(t=defaultdict, v="{}"),
    )
    def test_deserializer(self, t, v, resolver):
        # Given
        routine = routines.SimpleDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        # When
        d = routine(v)
        # Then
        assert d.__class__ is t


class TestTextDeserializerRoutine:
    @pytest.fixture(params=[str, bytes, bytearray])
    def routine(self, request, resolver):
        return routines.TextDeserializerRoutine(
            annotation=resolver.annotation(request.param), resolver=resolver
        )

    @pytest.mark.parametrize(argnames="v", argvalues=["1", b"1", 1])
    def test_deserializer(self, v, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin


class TestDateDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.DateDeserializerRoutine(
            annotation=resolver.annotation(datetime.date), resolver=resolver
        )

    @pytest.mark.suite(
        int=dict(v=1),
        float=dict(v=1.0),
        iso_year=dict(v="1970"),
        iso_date=dict(v="1970-01-01"),
        iso_date_bytes=dict(v=b"1970-01-01"),
        date_object=dict(v=datetime.date(1970, 1, 1)),
        datetime_object=dict(v=datetime.datetime(1970, 1, 1)),
        pendulum_datetime=dict(v=pendulum.DateTime.today()),
    )
    def test_deserializer(self, v, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is datetime.date


class TestDateTimeDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.DateTimeDeserializerRoutine(
            annotation=resolver.annotation(datetime.datetime), resolver=resolver
        )

    @pytest.mark.suite(
        int=dict(v=1),
        float=dict(v=1.0),
        iso_year=dict(v="1970"),
        iso_date=dict(v="1970-01-01"),
        iso_date_bytes=dict(v=b"1970-01-01"),
        date_object=dict(v=datetime.date(1970, 1, 1)),
        datetime_object=dict(v=datetime.datetime(1970, 1, 1)),
        pendulum_datetime=dict(v=pendulum.DateTime.today()),
    )
    def test_deserializer(self, v, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is datetime.datetime


class TestTimeDeltaDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.TimeDeltaDeserializerRoutine(
            annotation=resolver.annotation(datetime.timedelta), resolver=resolver
        )

    @pytest.mark.suite(
        int=dict(v=1),
        float=dict(v=1.0),
        iso_string=dict(v="P0Y0M0DT0H0M0S"),
        iso_string_bytes=dict(v=b"P0Y0M0DT0H0M0S"),
        timedelta=dict(v=datetime.timedelta()),
        duration=dict(v=pendulum.Duration()),
    )
    def test_deserializer(self, v, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is datetime.timedelta


class TestTimeDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.TimeDeserializerRoutine(
            annotation=resolver.annotation(datetime.time), resolver=resolver
        )

    @pytest.mark.suite(
        int=dict(v=1),
        float=dict(v=1.0),
        iso_string=dict(v="00:00:00"),
        iso_string_bytes=dict(v=b"00:00:00"),
        time=dict(v=datetime.time()),
        datetime=dict(v=datetime.datetime(1970, 1, 1)),
        date=dict(v=datetime.date(1970, 1, 1)),
        pendulum_time=dict(v=pendulum.Time()),
    )
    def test_deserializer(self, v, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is datetime.time


class TestUUIDDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.UUIDDeserializerRoutine(
            annotation=resolver.annotation(uuid.UUID), resolver=resolver
        )

    @pytest.mark.suite(
        int=dict(v=0),
        hex=dict(v=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"),
        parts=dict(v=(0, 0, 0, 0, 0, 0)),
        uuid=dict(v=uuid.UUID(int=0)),
        string=dict(v="00000000-0000-0000-0000-000000000000"),
    )
    def test_deserializer(self, v, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is uuid.UUID


class TestPatternDeserializerRoutine:
    @pytest.fixture
    def routine(self, resolver):
        return routines.PatternDeserializerRoutine(
            annotation=resolver.annotation(re.Pattern), resolver=resolver
        )

    @pytest.mark.suite(string=dict(v=".*"), pattern=dict(v=re.compile(".*")))
    def test_deserializer(self, v, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is re.Pattern


class TestMappingDeserializerRoutine:
    @pytest.fixture(
        params=[
            pytest.param(dict, id="dict"),
            pytest.param(MyDict[str, int], id="user_dict"),
            pytest.param(DefaultDict[str, int], id="default_dict_args"),
            pytest.param(DefaultDict[str, "int"], id="default_dict_args_string"),
        ]
    )
    def routine(self, request, resolver):
        return routines.MappingDeserializerRoutine(
            annotation=resolver.annotation(request.param), resolver=resolver
        )

    @pytest.mark.suite(
        empty_str=dict(v="{}", expected={}),
        json_str_int=dict(v='{"foo":1}', expected={"foo": 1}),
        json_str_float=dict(v='{"foo":1.0}', expected={"foo": 1}),
        json_str_str=dict(v='{"foo":"1"}', expected={"foo": 1}),
        json_bytes_str=dict(v=b'{"foo":"1"}', expected={"foo": 1}),
        user_cls_str=dict(v=MyReqClass(foo="1"), expected={"foo": 1}),
    )
    def test_deserializer(self, v, expected, routine):
        # When
        d = routine(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin
        if routine.annotation.args:
            assert d == expected

    @pytest.mark.suite(
        empty_str=dict(v="{}", expected={}),
        json_str_int=dict(v='{"foo":1}', expected={"bar": 1}),
        json_str_float=dict(v='{"foo":1.0}', expected={"bar": 1}),
        json_str_str=dict(v='{"foo":"1"}', expected={"bar": 1}),
        json_bytes_str=dict(v=b'{"foo":"1"}', expected={"bar": 1}),
        user_cls_str=dict(v=MyReqClass(foo="1"), expected={"bar": 1}),
    )
    def test_deserializer_aliased(self, v, expected, routine):
        # Given
        routine.annotation.serde.fields_in = {"foo": "bar"}
        routine._bind_closure()
        # When
        d = routine(v)
        # Then
        assert d.__class__ is routine.annotation.resolved_origin
        if routine.annotation.args:
            assert d == expected

    @pytest.mark.suite(
        no_args=dict(t=DefaultDict, v={}, expected=defaultdict(None)),
        int=dict(t=DefaultDict[str, int], v={}, expected=defaultdict(int)),
        user_cls=dict(
            t=DefaultDict[str, MyEmptyClass], v={}, expected=defaultdict(MyEmptyClass)
        ),
        invalid_user_cls=dict(
            t=DefaultDict[str, MyReqClass], v={}, expected=defaultdict(None)
        ),
    )
    def test_defaultdict_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.MappingDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        # When
        d = routine(v)
        # Then
        assert isinstance(d, expected.__class__) and d == expected

    def test_defaultdict_nested_deserializer(self, resolver):
        # Given
        routine = routines.MappingDeserializerRoutine(
            annotation=resolver.annotation(DefaultDict[str, DefaultDict]),
            resolver=resolver,
        )
        # When
        d = routine({})
        # Then
        assert isinstance(d, defaultdict) and isinstance(d["foo"], defaultdict)


class TestCollectionDeserializerRoutine:
    @pytest.mark.suite(
        list=dict(t=List[int], v='["1"]', expected=[1]),
        set=dict(t=Set[int], v='["1"]', expected={1}),
        frozenset=dict(t=FrozenSet[int], v='["1"]', expected=frozenset([1])),
        tuple=dict(t=Tuple[int, ...], v='["1"]', expected=(1,)),
        iterable=dict(t=Iterable[int], v='["1"]', expected=[1]),
        collection=dict(t=Collection[int], v='["1"]', expected=[1]),
        collection_usr_cls=dict(t=Collection[int], v=MyReqClass(foo="1"), expected=[1]),
    )
    def test_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.CollectionDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        # When
        d = routine(v)
        # Then
        assert isinstance(d, expected.__class__) and d == expected


if sys.version_info < (3, 9):
    MyTup = Tuple.__class__(tuple, (), inst=False, special=True)  # type: ignore[call-arg]

else:

    class MyTup(Tuple[_VT]): ...


class TestFixedTupleDeserializerRoutine:
    @pytest.mark.suite(
        tuple=dict(t=Tuple[int, str]),
        user_tuple=dict(t=MyTup[int, str]),
    )
    def test_deserializer(self, t, resolver):
        # Given
        v, expected = '["1", 1]', (1, "1")
        routine = routines.FixedTupleDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        # When
        d = routine(v)
        # Then
        assert isinstance(d, expected.__class__) and d == expected


@dataclasses.dataclass
class Foo:
    bar: str


class FooTup(NamedTuple):
    bar: str


class FooDict(TypedDict):
    bar: int


class TestFieldsDeserializerRoutine:
    @pytest.mark.suite(
        from_tuple=dict(t=Foo, v=(1,), expected=Foo("1")),
        from_str=dict(t=Foo, v="foo", expected=Foo("foo")),
        from_dict=dict(t=Foo, v={"bar": 1}, expected=Foo("1")),
        from_ntuple=dict(t=Foo, v=FooTup("1"), expected=Foo("1")),
        to_ntuple=dict(t=FooTup, v=Foo("1"), expected=FooTup("1")),
    )
    def test_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.FieldsDeserializerRoutine(
            annotation=resolver.annotation(t), resolver=resolver
        )
        # When
        d = routine(v)
        # Then
        assert isinstance(d, t) and d == expected

    @pytest.mark.suite(
        from_tuple=dict(t=Foo, v=(1,), expected=Foo("1")),
        from_str=dict(t=Foo, v="foo", expected=Foo("foo")),
        from_dict=dict(t=Foo, v={"foo": 1}, expected=Foo("1")),
        from_ntuple=dict(t=Foo, v=FooTup("1"), expected=Foo("1")),
        to_ntuple=dict(t=FooTup, v=Foo("1"), expected=FooTup("1")),
    )
    def test_aliased_deserializer(self, t, v, expected, resolver):
        # Given
        routine = routines.FieldsDeserializerRoutine(
            annotation=resolver.annotation(t, flags={"fields": {"bar": "foo"}}),
            resolver=resolver,
        )
        # When
        d = routine(v)
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

    @pytest.mark.suite(
        int=dict(v=1, expected=1),
        int_str=dict(v="2", expected=2),
        int_json_str=dict(v='"3"', expected=3),
        str=dict(v="foo", expected="foo"),
    )
    def test_generic_deserializer(self, v, expected, groutine):
        # When
        d = groutine(v)
        # Then
        assert d == expected

    @pytest.mark.suite(
        a_class=dict(v={"tag": "a"}, expected=AClass()),
        b_class=dict(v={"tag": "b"}, expected=BClass()),
        c_class=dict(v={"tag": "c"}, expected=CClass()),
    )
    def test_tagged_deserializer(self, v, expected, troutine):
        # When
        d = troutine(v)
        # Then
        assert d == expected

    def test_generic_error(self, groutine):
        # When/Then
        with pytest.raises(ValueError):
            groutine(NoStr())

    def test_tagged_error(self, troutine):
        # When/Then
        with pytest.raises(ValueError):
            troutine({"tag": "d"})


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
        # When
        d = routine(v)
        # Then
        assert d == expected

    def test_deserializer_error(self, routine):
        # When/Then
        with pytest.raises(ValueError):
            routine(3)
