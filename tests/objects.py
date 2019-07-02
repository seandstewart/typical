import dataclasses
import datetime
import enum
import typing

import typic


@dataclasses.dataclass
class FromDict:
    foo: str = None

    @classmethod
    def from_dict(cls, dikt: typing.Mapping):
        return cls(**dikt)


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
    none: str = None


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


UserID = typing.NewType("UserID", int)
DateDict = typing.NewType("DateDict", typing.Dict[datetime.datetime, str])
