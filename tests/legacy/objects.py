from __future__ import annotations

import collections
import dataclasses
import datetime
import enum
import numbers
import typing

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict  # type: ignore

import inflection

# import pandas
import pydantic
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base

import typical
from typical.compat import Literal


def get_id(x) -> str:
    return inflection.underscore(str(x))


@dataclasses.dataclass
class FromDict:
    foo: typing.Optional[str] = None

    @classmethod
    def from_dict(cls, dikt: typing.Mapping):
        return cls(**dikt)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class Data:
    foo: str


@dataclasses.dataclass
class Nested:
    data: Data


@dataclasses.dataclass
class NestedSeq:
    datum: typing.List[Data]


@dataclasses.dataclass
class NestedFromDict:
    data: Data

    @classmethod
    def from_dict(cls, dikt: typing.Mapping):
        data = Data(**dikt["data"])
        return cls(data)


@dataclasses.dataclass
class DefaultNone:
    none: typing.Optional[str] = None


@typical.klass
class Forward:
    foo: "FooNum"


class FooNum(str, enum.Enum):
    bar = "bar"


@dataclasses.dataclass
class NestedDoubleReference:
    first: Data
    second: Data | None = None


@typical.klass
class A:
    b: B | None = None


@typical.klass
class B:
    a: A | None = None


@typical.klass
class ABs:
    a: A | None = None
    bs: typing.Iterable[B] | None = None


@typical.klass
class C:
    c: C | None = None


@dataclasses.dataclass
class D:
    d: D | None = None


@dataclasses.dataclass
class E:
    d: D | None = None
    f: F | None = None


@dataclasses.dataclass
class F:
    g: G


@typical.klass
class G:
    h: int | None = None


@typical.klass
class H:
    hs: typing.Iterable[H]


@dataclasses.dataclass
class J:
    js: typing.Iterable[J]


@dataclasses.dataclass
class ThreeOptionals:
    a: str | None
    b: str | None = None
    c: str | None = None


class Class:
    var: str

    def __init__(self, var: str):
        self.var = var


class NoParams:
    var: str


@dataclasses.dataclass(frozen=True)
class Frozen:
    var: bool


@typical.klass
class Typic:
    var: str


@typical.klass
class SubTypic(Typic):
    sub: str


@typical.klass
class Base:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


@typical.klass
class SuperBase(Base):
    super: str

    def __setattr__(self, key, value):
        super().__setattr__(key, value)


class MetaSlotsClass(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        ...
        cls = typical.klass(cls, slots=True)
        ...
        return cls


@typical.klass(frozen=True)
class FrozenTypic:
    var: str


class Inherited(Typic):
    pass


@typical.klass
class KlassVarSubscripted:
    var: typing.ClassVar[str] = "foo"


def func(bar: int):
    return bar


def optional(bar: str = None):
    return bar


def varargs(*args: Data, **kwargs: Data):
    return args + tuple(kwargs.values())


@typical.al(strict=True)
def strictvaradd(*args: int, **kwargs: int):
    return sum(args) + sum(kwargs.values())


class Method:
    def math(self, a: int) -> int:
        return a * a


@typical.klass(always=False)
class KlassDelayed:
    foo: str


@typical.al(always=False)
@dataclasses.dataclass
class Delayed:
    foo: str


@typical.al
def delayed(foo: str) -> str:
    return foo


UserID = typing.NewType("UserID", int)
DateDict = typing.NewType("DateDict", typing.Dict[datetime.datetime, str])


@typical.constrained(max_length=5)
class ShortStr(str):
    ...


@typical.constrained(values=ShortStr)
class ShortStrList(list):
    ...


@typical.constrained(min=1000)
class LargeInt(int):
    ...


@typical.constrained(min=1000)
class LargeFloat(float):
    ...


@typical.constrained(values=LargeInt, keys=ShortStr)
class LargeIntDict(dict):
    ...


@typical.constrained(keys=ShortStr)
class ShortKeyDict(dict):
    ...


@typical.constrained(values=ShortStr)
class ValuedDict(dict):
    ...


@typical.constrained(keys=ShortStr)
class KeyedDict(dict):
    ...


@typical.constrained(keys=ShortStr, values=ShortStr)
class KeyedValuedDict(dict):
    ...


ShortStrDictT = typing.Dict[ShortStr, ShortStr]


@typical.klass
class Constrained:
    short: ShortStr
    large: LargeInt


@typical.klass
class NestedConstrained:
    mapping: typing.Mapping[str, Constrained]
    array: typing.List[Constrained]
    constr: LargeIntDict
    other_constr: ShortStrDictT


@typical.klass
class TClass:
    a: int


class TDict(TypedDict):
    a: int


class TDictPartial(TypedDict, total=False):
    a: int


class NTup(typing.NamedTuple):
    a: int


ntup = collections.namedtuple("ntup", ["a"])


Base = declarative_base()


class Alchemy(Base):
    __tablename__ = "alchemy"
    id = sqlalchemy.Column(sqlalchemy.BigInteger, primary_key=True, autoincrement=True)
    bar = sqlalchemy.Column(sqlalchemy.Text, nullable=False)


class Pydantic(pydantic.BaseModel):
    bar: str
    id: typing.Optional[int] = None


@typical.klass
class Typical:
    bar: str
    id: typing.Optional[typical.ReadOnly[int]] = None


@typical.klass
class Source:
    test: typing.Optional[str] = typical.field(init=False)
    field_to_ignore: str = "Ignore me"

    def __post_init__(self):
        self.test = "Something"


@typical.klass
class Dest:
    test: typing.Optional[str] = None


@typical.klass
class ABlah:
    key: Literal[3]
    field: "typing.Union[AFoo, ABar, ABlah, None]"


@typical.klass
class AFoo:
    key: Literal[1]
    field: str


@typical.klass
class ABar:
    key: Literal[2]
    field: bytes


@typical.klass
class CBlah:
    key: typing.ClassVar[int] = 3
    field: typing.Union[CFoo, CBar, CBlah, None]


@typical.klass
class CFoo:
    key: typing.ClassVar[int] = 1
    field: str


@typical.klass
class CBar:
    key: typing.ClassVar[int] = 2
    field: bytes


@dataclasses.dataclass
class DBlah:
    key: typing.ClassVar[int] = 3
    field: "typing.Union[DFoo, DBar, DBlah, None]"


@dataclasses.dataclass
class DFoo:
    key: typing.ClassVar[int] = 1
    field: str


@dataclasses.dataclass
class DBar:
    key: typing.ClassVar[int] = 2
    field: bytes


@typical.klass
class MutableClassVar:
    f: typing.ClassVar[typing.List[str]] = []


@dataclasses.dataclass
class Pep585:
    data: dict[str, int]


@dataclasses.dataclass
class Pep604:
    union: DFoo | DBar


@typical.al
def pep585(data: dict[str, int]) -> dict[str, int]:
    return data


@typical.al
def pep604(union: DFoo | DBar) -> DFoo | DBar:
    return union


@typical.al
def number(n: numbers.Number) -> numbers.Number:
    return n


TYPIC_OBJECTS = [
    Typic,
    Inherited,
    FrozenTypic,
    KlassDelayed,
    KlassVarSubscripted,
    Delayed,
    Constrained,
    NestedConstrained,
]


STD_OBJECTS = [
    FromDict,
    Data,
    Nested,
    NestedSeq,
    NestedFromDict,
    DefaultNone,
    Forward,
    FooNum,
    Class,
    NoParams,
    UserID,
    DateDict,
    ShortStr,
    LargeInt,
    TDict,
    NTup,
    ntup,
]
