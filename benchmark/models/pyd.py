#!/usr/bin/env python
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConstrainedStr, PositiveInt, BaseConfig, ValidationError


class DBString(ConstrainedStr):
    max_length = 255


class HTTPReferer(ConstrainedStr):
    max_length = 1023


class GReCaptchaResponse(ConstrainedStr):
    min_length = 20
    max_length = 1000


class Location(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Skill(BaseModel):
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
