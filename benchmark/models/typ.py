#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from datetime import datetime
from dataclasses import field
from typing import List, Optional

import typic


@typic.constrained(max_length=255)
class DBString(str):
    """A string with a max len of 255."""


@typic.constrained(max_length=1023)
class HTTPReferer(str):
    """A string representing an HTTP referer."""


@typic.constrained(min_length=10, max_length=1000)
class GReCaptchaResponse(str):
    """A string representing a re-captcha response."""


@typic.constrained(ge=0)
class PositiveInt(int):
    """A positive integer."""


@typic.klass
class Location:
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@typic.klass
class Skill:
    subject: str
    subject_id: int
    category: str
    qual_level: str
    qual_level_id: int
    qual_level_ranking: float = 0


@typic.klass
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
    skills: List[Skill] = field(default_factory=list)


def validate(data):
    try:
        return True, Model.transmute(data)
    except (TypeError, ValueError) as err:
        return False, err
