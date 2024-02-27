from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import orjson
from pydantic import (
    BaseConfig,
    BaseModel,
    PositiveInt,
    StringConstraints,
    ValidationError,
)


def orjson_dumps(v, *, default):
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=default).decode()


class DBString(StringConstraints):
    max_length = 255


class HTTPReferer(StringConstraints):
    max_length = 1023


class GReCaptchaResponse(StringConstraints):
    min_length = 20
    max_length = 1000


class Location(BaseModel):
    class Config(BaseConfig):
        validate_all = True
        validate_assignment = True
        orm_mode = True
        json_loads = orjson.loads
        json_dumps = orjson_dumps

    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Skill(BaseModel):
    class Config(BaseConfig):
        validate_all = True
        validate_assignment = True
        orm_mode = True
        json_loads = orjson.loads
        json_dumps = orjson_dumps

    subject: str
    subject_id: int
    category: str
    qual_level: str
    qual_level_id: int
    qual_level_ranking: float = 0


class Model(BaseModel):
    class Config(BaseConfig):
        validate_all = True
        validate_assignment = True
        orm_mode = True
        json_loads = orjson.loads
        json_dumps = orjson_dumps

    id: int
    client_name: DBString
    sort_index: float
    client_phone: Optional[DBString] = None
    grecaptcha_response: Optional[GReCaptchaResponse] = None
    location: Optional[Location] = None
    contractor: Optional[PositiveInt] = None
    upstream_http_referrer: Optional[HTTPReferer] = None
    last_updated: Optional[datetime] = None
    skills: List[Skill] = []


def validate(data):
    try:
        return True, Model(**data)
    except ValidationError as err:
        return False, err


def deserialize(data):
    return validate(data)


def tojson(instance: Model):
    return True, instance.json()  # No validation!


def translate_from(other: Any):
    try:
        return True, Model.from_orm(other)
    except ValidationError as err:
        return False, err
