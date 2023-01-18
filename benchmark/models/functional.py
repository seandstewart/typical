from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import List, Optional, Type

import typical


@typical.constrained(max_length=255)
class DBString(str):
    """A string with a max len of 255."""


@typical.constrained(max_length=1023)
class HTTPReferer(str):
    """A string representing an HTTP referer."""


@typical.constrained(min_length=10, max_length=1000)
class GReCaptchaResponse(str):
    """A string representing a re-captcha response."""


@typical.constrained(min=0, inclusive_min=True)
class PositiveInt(int):
    """A positive integer."""


@dataclasses.dataclass
class Location:
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclasses.dataclass
class Skill:
    subject: str
    subject_id: int
    category: str
    qual_level: str
    qual_level_id: int
    qual_level_ranking: float = 0


@dataclasses.dataclass
class Model:
    id: int
    client_name: DBString
    sort_index: float
    client_phone: Optional[DBString] = None
    grecaptcha_response: Optional[GReCaptchaResponse] = None
    location: Optional[Location] = None
    contractor: Optional[PositiveInt] = None
    upstream_http_referrer: Optional[HTTPReferer] = None
    last_updated: Optional[datetime] = None
    skills: List[Skill] = dataclasses.field(default_factory=list)


def validate(data):
    try:
        return True, typical.validate(Model, data)
    except ValueError as err:
        return False, err


def deserialize(data):
    try:
        return True, typical.transmute(Model, data)
    except (TypeError, ValueError) as err:
        return False, err


def transmute(instance):
    return True, typical.transmute(Model, instance)


def tojson(instance: Model):
    try:
        return True, typical.tojson(instance)
    except ValueError as err:
        return False, err


def translate_to(instance: Model, target: Type):
    try:
        return True, typical.translate(instance, target)
    except (ValueError, TypeError) as err:
        return False, err


def translate_from(instance: Model):
    try:
        return True, typical.translate(instance, Model)
    except (ValueError, TypeError) as err:
        return False, err
