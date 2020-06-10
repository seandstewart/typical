import collections
import dataclasses
import datetime
import enum
import typing

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict  # type: ignore

import inflection
import typic
import pandas
import pydantic
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base


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


@dataclasses.dataclass
class DefaultEllipsis:
    ellipsis: str = ...


@dataclasses.dataclass
class Forward:
    foo: "FooNum"


class FooNum(str, enum.Enum):
    bar = "bar"


class Class:
    var: str

    def __init__(self, var: str):
        self.var = var


class NoParams:
    var: str


@dataclasses.dataclass(frozen=True)
class Frozen:
    var: bool


@typic.klass
class Typic:
    var: str


@typic.klass
class SubTypic(Typic):
    sub: str


@typic.klass
class Base:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


@typic.klass
class SuperBase(Base):
    super: str

    def __setattr__(self, key, value):
        super().__setattr__(key, value)


class MetaSlotsClass(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        ...
        cls = typic.klass(cls, slots=True)
        ...
        return cls


@typic.klass(frozen=True)
class FrozenTypic:
    var: str


class Inherited(Typic):
    pass


@typic.klass
class KlassVarSubscripted:
    var: typing.ClassVar[str] = "foo"


@typic.klass
class KlassVar:
    var: typing.ClassVar = "foo"


def func(bar: int):
    return bar


def optional(bar: str = None):
    return bar


def varargs(*args: Data, **kwargs: Data):
    return args + tuple(kwargs.values())


@typic.al(strict=True)
def strictvaradd(*args: int, **kwargs: int):
    return sum(args) + sum(kwargs.values())


class Method:
    def math(self, a: int) -> int:
        return a * a


@typic.klass(delay=True)
class KlassDelayed:
    foo: str


@typic.al(delay=True)
@dataclasses.dataclass
class Delayed:
    foo: str


@typic.al(delay=True)
def delayed(foo: str) -> str:
    return foo


UserID = typing.NewType("UserID", int)
DateDict = typing.NewType("DateDict", typing.Dict[datetime.datetime, str])


@typic.constrained(max_length=5)
class ShortStr(str):
    ...


@typic.constrained(values=ShortStr)
class ShortStrList(list):
    ...


@typic.constrained(gt=1000)
class LargeInt(int):
    ...


@typic.constrained(values=LargeInt, keys=ShortStr)
class LargeIntDict(dict):
    ...


@typic.constrained(keys=ShortStr)
class ShortKeyDict(dict):
    ...


@typic.constrained(items={"foo": LargeInt}, values=ShortStr)
class ItemizedValuedDict(dict):
    ...


@typic.constrained(items={"foo": LargeInt}, keys=ShortStr)
class ItemizedKeyedDict(dict):
    ...


@typic.constrained(items={"foo": LargeInt})
class ItemizedDict(dict):
    ...


@typic.constrained(items={"foo": LargeInt}, keys=ShortStr, values=ShortStr)
class ItemizedKeyedValuedDict(dict):
    ...


ShortStrDictT = typing.Dict[ShortStr, ShortStr]


@typic.klass
class Constrained:
    short: ShortStr
    large: LargeInt


@typic.klass
class NestedConstrained:
    mapping: typing.Mapping[str, Constrained]
    array: typing.List[Constrained]
    constr: LargeIntDict
    other_constr: ShortStrDictT


@typic.klass
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


@typic.klass
class Typical:
    bar: str
    id: typing.Optional[typic.ReadOnly[int]] = None


@typic.klass
class Source:
    test: typing.Optional[str] = typic.field(init=False)
    field_to_ignore: str = "Ignore me"

    def __post_init__(self):
        self.test = "Something"


@typic.klass
class Dest:
    test: typing.Optional[str] = None


@typic.klass
class DFClass:
    df: pandas.DataFrame = None


TYPIC_OBJECTS = [
    Typic,
    Inherited,
    FrozenTypic,
    KlassDelayed,
    KlassVar,
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
