import dataclasses
import datetime
import enum
import typing


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


class NoParams:
    var: str


UserID = typing.NewType("UserID", int)
DateDict = typing.NewType("DateDict", typing.Dict[datetime.datetime, str])
