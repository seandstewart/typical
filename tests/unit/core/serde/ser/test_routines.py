from __future__ import annotations

import inspect
from typing import Dict, TypeVar

import pytest

from typical.core.interfaces import Annotation
from typical.resolver import Resolver
from typical.serde.ser import routines

_T = TypeVar("_T")


class EQStr(str):
    def equals(self, o):
        return o.__class__ is self.__class__ and self.__eq__(o)


_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class MyDict(Dict[_KT, _VT]): ...


class MyEmptyClass: ...


class MyReqClass:
    def __init__(self, foo: str):
        self.foo = foo


@pytest.fixture
def resolver():
    return Resolver()


@pytest.fixture
def string_annotation() -> Annotation[str]:
    return Annotation(
        str,
        str,
        str,
        inspect.Parameter("_", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    )


@pytest.fixture
def nullstring_annotation() -> Annotation[str | None]:
    return Annotation(
        str,
        str,
        str,
        inspect.Parameter("_", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        optional=True,
    )


@pytest.fixture
def null_annotation() -> Annotation[None]:
    return Annotation(
        None,
        None,
        None,
        inspect.Parameter("_", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        optional=True,
    )


class TestBaseSerializerRoutine:
    @pytest.fixture
    def string(
        self, resolver, string_annotation
    ) -> routines.BaseSerializerRoutine[str]:
        return routines.StringSerializerRoutine(
            annotation=string_annotation,
            resolver=resolver,
        )

    @pytest.fixture
    def nullstring(
        self, resolver, nullstring_annotation
    ) -> routines.BaseSerializerRoutine[str]:
        return routines.StringSerializerRoutine(
            annotation=nullstring_annotation,
            resolver=resolver,
        )

    def test_get_checks_stdlib(self, string):
        # Given
        check = string._get_checks()
        val = "foo"
        # When
        should_return = check(val)
        # Then
        assert should_return is False

    def test_get_checks_stdlib_invalid_value(self, string):
        # Given
        check = string._get_checks()
        val = 1
        # When/The
        with pytest.raises(routines.SerializationValueError):
            check(val)

    @pytest.mark.suite(
        nullval=dict(val=None, expected_should_return=True),
        strval=dict(val="", expected_should_return=False),
    )
    def test_get_checks_stdlib_nullable(self, nullstring, val, expected_should_return):
        # Given
        check = nullstring._get_checks()
        # When
        should_return = check(val)
        # Then
        assert should_return == expected_should_return

    def test_get_checks_stdlib_nullable_invalid_value(self, nullstring):
        # Given
        check = nullstring._get_checks()
        val = 1
        # When/Then
        with pytest.raises(routines.SerializationValueError):
            check(val)


class TestNoopSerializerRoutine:
    @pytest.fixture
    def string(
        self, resolver, string_annotation
    ) -> routines.BaseSerializerRoutine[str]:
        return routines.NoopSerializerRoutine(
            annotation=string_annotation,
            resolver=resolver,
        )

    @pytest.fixture
    def nullstring(
        self, resolver, nullstring_annotation
    ) -> routines.BaseSerializerRoutine[str]:
        return routines.NoopSerializerRoutine(
            annotation=nullstring_annotation,
            resolver=resolver,
        )

    @pytest.fixture
    def null(self, resolver, null_annotation) -> routines.BaseSerializerRoutine[str]:
        return routines.NoopSerializerRoutine(
            annotation=null_annotation,
            resolver=resolver,
        )

    def test_serialize_null(self, null):
        # Given
        val = "foo"
        # When
        serialized = null(val)
        # Then
        assert serialized is None

    @pytest.mark.suite(
        value=dict(val="1", expected_serialized="1"),
        null_value=dict(val=None, expected_serialized=None),
    )
    def test_serialize_nullable(self, nullstring, val, expected_serialized):
        # When
        serialized = nullstring(val)
        # Then
        assert serialized == expected_serialized

    def test_serialize_non_nullable(self, string):
        # Given
        val = 1
        # When/Then
        with pytest.raises(routines.SerializationValueError):
            string(val)
