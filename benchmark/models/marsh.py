#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import datetime
from typing import Optional, List

from marshmallow import fields, Schema, validate as mvalidate, ValidationError


class LocationSchema(Schema):
    latitude = fields.Float(allow_none=True)
    longitude = fields.Float(allow_none=True)


class SkillSchema(Schema):
    subject = fields.Str(required=True)
    subject_id = fields.Integer(required=True)
    category = fields.Str(required=True)
    qual_level = fields.Str(required=True)
    qual_level_id = fields.Integer(required=True)
    qual_level_ranking = fields.Float(default=0)


class ModelSchema(Schema):
    id = fields.Integer(required=True)
    client_name = fields.Str(validate=mvalidate.Length(max=255), required=True)
    sort_index = fields.Float(required=True)
    client_phone = fields.Str(validate=mvalidate.Length(max=255), allow_none=True)
    location = fields.Nested(LocationSchema())
    contractor = fields.Integer(validate=mvalidate.Range(min=0), allow_none=True)
    upstream_http_referrer = fields.Str(
        validate=mvalidate.Length(max=1023), allow_none=True
    )
    grecaptcha_response = fields.Str(
        validate=mvalidate.Length(min=20, max=1000), required=True
    )
    last_updated = fields.DateTime(allow_none=True)
    skills = fields.Nested(SkillSchema(many=True))


SCHEMA = ModelSchema()


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
    qual_level_ranking: float = 0.0


@dataclasses.dataclass
class Model:
    id: int
    client_name: str
    sort_index: float
    client_phone: Optional[str] = None
    location: Optional[Location] = None
    contractor: Optional[int] = None
    upstream_http_referrer: Optional[str] = None
    grecaptcha_response: Optional[str] = None
    last_updated: Optional[datetime.datetime] = None
    skills: List[Skill] = dataclasses.field(default_factory=list)


def initialize(**data):
    loc_data = data.pop("location", {})
    skills_data = data.pop("skills", [])
    loc = Location(**loc_data) if loc_data else None
    skills = [Skill(**x) for x in skills_data]
    return Model(**data, location=loc, skills=skills)


def validate(data):
    try:
        result = SCHEMA.load(data)
        return True, initialize(**result)

    except ValidationError as err:
        return False, err.messages


def deserialize(data):
    valid, result = validate(data)
    if valid:
        return valid, initialize(**data)
    return valid, result


def tojson(instance: Model):
    return True, SCHEMA.dumps(instance)  # Implicit filtering of invalid data!
