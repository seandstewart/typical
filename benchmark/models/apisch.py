from dataclasses import dataclass, field
from datetime import datetime
from typing import List, NewType, Optional

from apischema import (
    ValidationError,
    deserialization_method,
    schema,
    serialization_method,
)
import orjson

PositiveInt = NewType("PositiveInt", int)
schema(exc_min=0)(PositiveInt)


@dataclass
class Location:
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class Skill:
    subject: str
    subject_id: int
    category: str
    qual_level: str
    qual_level_id: int
    qual_level_ranking: float = 0


@dataclass
class Model:
    id: int
    client_name: str = field(metadata=schema(max_len=255))
    sort_index: float
    # must be before fields with default value
    grecaptcha_response: str = field(metadata=schema(min_len=20, max_len=1000))
    client_phone: Optional[str] = field(default=None, metadata=schema(max_len=255))
    location: Optional[Location] = None
    contractor: Optional[PositiveInt] = None
    upstream_http_referrer: Optional[str] = field(
        default=None, metadata=schema(max_len=1023)
    )
    last_updated: Optional[datetime] = None
    skills: List[Skill] = field(default_factory=list)


deserialization_method = deserialization_method(Model, coerce=True)  # type: ignore
serialization_method = serialization_method(Model)  # type: ignore


def validate(data):
    return deserialize(data)


def deserialize(data):
    try:
        return True, deserialization_method(data)
    except ValidationError as err:
        return False, err


def tojson(instance: Model):
    try:
        return True, orjson.dumps(serialization_method(instance)).decode()
    except Exception as err:
        return False, err
