import collections
import dataclasses
import datetime
import enum
import typing

try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict  # type: ignore

import typic


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
        return cls(**dikt)


@dataclasses.dataclass
class DefaultNone:
    none: typing.Optional[str] = None


@dataclasses.dataclass
class Forward:
    foo: "FooNum"


class FooNum(str, enum.Enum):
    bar = "bar"


class Class:
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


@typic.constrained(values=LargeInt)
class LargeIntDict(dict):
    ...


ShortStrDict = typing.Dict[str, ShortStr]


@typic.klass
class Constrained:
    short: ShortStr
    large: LargeInt


@typic.klass
class NestedConstrained:
    mapping: typing.Mapping[str, Constrained]
    array: typing.List[Constrained]
    constr: LargeIntDict
    other_constr: ShortStrDict


class TDict(TypedDict):
    a: int


class NTup(typing.NamedTuple):
    a: int


ntup = collections.namedtuple("ntup", ["a"])


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
