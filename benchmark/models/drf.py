#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import django
from django.conf import settings

settings.configure(
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes"]
)
django.setup()

from rest_framework import serializers  # noqa: E402

from benchmark.models import marsh  # noqa: E402
from benchmark.models.marsh import Model  # noqa: F401,E402


class LocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)


class SkillSerializer(serializers.Serializer):
    subject = serializers.CharField()
    subject_id = serializers.IntegerField()
    category = serializers.CharField()
    qual_level = serializers.CharField()
    qual_level_id = serializers.IntegerField()
    qual_level_ranking = serializers.FloatField(default=0)


class ModelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    client_name = serializers.CharField(max_length=255)
    sort_index = serializers.FloatField()
    client_email = serializers.EmailField(required=False, allow_null=True)
    client_phone = serializers.CharField(
        max_length=255, required=False, allow_null=True
    )
    location = LocationSerializer(required=False, allow_null=True)
    contractor = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    upstream_http_referrer = serializers.CharField(
        max_length=1023, required=False, allow_null=True
    )
    grecaptcha_response = serializers.CharField(min_length=20, max_length=1000)
    last_updated = serializers.DateTimeField(required=False, allow_null=True)
    skills = serializers.ListField(child=SkillSerializer())


def validate(data):
    result = ModelSerializer(data=data)
    if result.is_valid():
        return True, data
    return False, result.errors


def deserialize(data):
    valid, result = validate(data)
    if valid:
        return valid, marsh.initialize(**data)
    return valid, result


def tojson(instance):
    result = ModelSerializer(instance=instance)
    try:
        return True, result.data
    except AttributeError as err:
        return False, err
