#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from datetime import datetime
from typing import List, Tuple, Set, Union, Mapping, Dict, Any, DefaultDict

import pytest
import typic
import typic.common
from typic.ext.schema import (
    MultiSchemaField,
    UndeclaredSchemaField,
    get_field_type,
)
from typic.compat import Final, Literal
from tests import objects


@pytest.mark.parametrize(
    argnames=("obj",), argvalues=[(x,) for x in objects.TYPIC_OBJECTS]
)
def test_typic_objects_schema(obj):
    if hasattr(obj, "resolve"):
        obj.resolve()
    assert obj.schema() is typic.schema(obj)


class MySet(set):
    ...


class MyURL(typic.URL):
    ...


class MyDateTime(datetime):
    ...


@typic.klass
class Container:
    data: DefaultDict[str, int]


@pytest.mark.parametrize(
    argnames=("obj", "expected"),
    argvalues=[
        (str, typic.StrSchemaField()),
        (int, typic.IntSchemaField()),
        (bool, typic.BooleanSchemaField()),
        (float, typic.NumberSchemaField()),
        (list, typic.ArraySchemaField()),
        (set, typic.ArraySchemaField(uniqueItems=True)),
        (frozenset, typic.ArraySchemaField(uniqueItems=True, additionalItems=False)),
        (tuple, typic.ArraySchemaField(additionalItems=False)),
        (Any, typic.UndeclaredSchemaField()),
        (List[str], typic.ArraySchemaField(items=typic.StrSchemaField())),
        (
            List[objects.LargeInt],
            typic.ArraySchemaField(items=typic.IntSchemaField(exclusiveMinimum=1000)),
        ),
        (
            Mapping[str, objects.LargeInt],
            typic.ObjectSchemaField(
                additionalProperties=typic.IntSchemaField(exclusiveMinimum=1000)
            ),
        ),
        (
            objects.FromDict,
            typic.ObjectSchemaField(
                description=objects.FromDict.__doc__,
                title=objects.FromDict.__name__,
                properties=typic.FrozenDict(
                    foo=typic.MultiSchemaField(
                        title="Foo",
                        anyOf=(typic.StrSchemaField(), typic.NullSchemaField()),
                    )
                ),
                required=(),
                additionalProperties=False,
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            objects.LargeInt,
            typic.IntSchemaField(**objects.LargeInt.__constraints__.for_schema()),
        ),
        (typic.common.ReadOnly[str], typic.StrSchemaField(readOnly=True)),
        (Final[str], typic.StrSchemaField(readOnly=True)),
        (typic.common.WriteOnly[str], typic.StrSchemaField(writeOnly=True)),
        (
            Union[str, int],
            typic.MultiSchemaField(
                anyOf=(typic.StrSchemaField(), typic.IntSchemaField())
            ),
        ),
        (
            Mapping[str, int],
            typic.ObjectSchemaField(additionalProperties=typic.IntSchemaField()),
        ),
        (
            Mapping[str, objects.LargeInt],
            typic.ObjectSchemaField(
                additionalProperties=typic.IntSchemaField(exclusiveMinimum=1000)
            ),
        ),
        (
            objects.ShortStrList,
            typic.ArraySchemaField(items=typic.StrSchemaField(maxLength=5)),
        ),
        (
            objects.TDict,
            typic.ObjectSchemaField(
                description=objects.TDict.__doc__,
                title=objects.TDict.__name__,
                properties=typic.FrozenDict(a=typic.IntSchemaField()),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            objects.TDictPartial,
            typic.ObjectSchemaField(
                description=objects.TDictPartial.__doc__,
                title=objects.TDictPartial.__name__,
                properties=typic.FrozenDict(a=typic.IntSchemaField()),
                required=(),
                additionalProperties=False,
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            objects.NTup,
            typic.ObjectSchemaField(
                description=objects.NTup.__doc__,
                title=objects.NTup.__name__,
                properties=typic.FrozenDict(a=typic.IntSchemaField()),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            objects.ntup,
            typic.ObjectSchemaField(
                description=objects.ntup.__doc__,
                title=objects.ntup.__name__.title(),
                properties=typic.FrozenDict(a=typic.UndeclaredSchemaField()),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            Dict[str, Union[str, int]],
            typic.ObjectSchemaField(
                additionalProperties=MultiSchemaField(
                    anyOf=(typic.StrSchemaField(), typic.IntSchemaField())
                )
            ),
        ),
        (
            Tuple[Union[str, int], ...],
            typic.ArraySchemaField(
                items=MultiSchemaField(
                    anyOf=(typic.StrSchemaField(), typic.IntSchemaField())
                )
            ),
        ),
        (MySet, typic.ArraySchemaField(uniqueItems=True)),
        (MyURL, typic.StrSchemaField(format=typic.StringFormat.URI)),
        (MyDateTime, typic.StrSchemaField(format=typic.StringFormat.DTIME)),
        (MyDateTime, typic.StrSchemaField(format=typic.StringFormat.DTIME)),
        (
            Container,
            typic.ObjectSchemaField(
                title="Container",
                description="Container(data: DefaultDict[str, int])",
                properties={"data": typic.Ref(ref="#/definitions/Data")},
                additionalProperties=False,
                required=("data",),
                definitions=typic.FrozenDict(
                    {
                        "Data": typic.ObjectSchemaField(
                            title="Data", additionalProperties=typic.IntSchemaField()
                        )
                    }
                ),
            ),
        ),
        (
            objects.KlassVar,
            typic.ObjectSchemaField(
                title="KlassVar",
                description="KlassVar()",
                properties={
                    "var": typic.StrSchemaField(
                        enum=("foo",), default="foo", readOnly=True
                    )
                },
                additionalProperties=False,
                required=(),
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            objects.KlassVarSubscripted,
            typic.ObjectSchemaField(
                title="KlassVarSubscripted",
                description="KlassVarSubscripted()",
                properties={
                    "var": typic.StrSchemaField(
                        enum=("foo",), default="foo", readOnly=True
                    )
                },
                additionalProperties=False,
                required=(),
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            objects.ThreeOptionals,
            typic.ObjectSchemaField(
                title=objects.ThreeOptionals.__name__,
                description=objects.ThreeOptionals.__doc__,
                properties=typic.FrozenDict(
                    a=typic.MultiSchemaField(
                        title="A",
                        anyOf=(typic.StrSchemaField(), typic.NullSchemaField()),
                    ),
                    b=typic.MultiSchemaField(
                        title="B",
                        anyOf=(typic.StrSchemaField(), typic.NullSchemaField()),
                    ),
                    c=typic.MultiSchemaField(
                        title="C",
                        anyOf=(typic.StrSchemaField(), typic.NullSchemaField()),
                    ),
                ),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            objects.A,
            typic.ObjectSchemaField(
                title="A",
                description="A(b: Union[ForwardRef('B'), NoneType] = None)",
                properties={
                    "b": typic.MultiSchemaField(
                        title="OptionalB",
                        anyOf=(
                            typic.Ref(ref="#/definitions/B"),
                            typic.NullSchemaField(),
                        ),
                    )
                },
                additionalProperties=False,
                required=(),
                definitions=typic.FrozenDict(
                    {
                        "A": typic.ObjectSchemaField(
                            title="A",
                            description="A(b: Union[ForwardRef('B'), NoneType] = "
                            "None)",
                            properties={
                                "b": typic.MultiSchemaField(
                                    title="OptionalB",
                                    anyOf=(
                                        typic.Ref(ref="#/definitions/B"),
                                        typic.NullSchemaField(),
                                    ),
                                )
                            },
                            additionalProperties=False,
                            required=(),
                        ),
                        "B": typic.ObjectSchemaField(
                            title="B",
                            description="B(a: Union[ForwardRef('A'), NoneType] = None)",
                            properties={
                                "a": typic.MultiSchemaField(
                                    title="OptionalA",
                                    anyOf=(
                                        typic.Ref(ref="#/definitions/A"),
                                        typic.NullSchemaField(),
                                    ),
                                )
                            },
                            additionalProperties=False,
                            required=(),
                        ),
                    }
                ),
            ),
        ),
        (
            Union[int, str, None],
            typic.MultiSchemaField(
                anyOf=(
                    typic.IntSchemaField(),
                    typic.StrSchemaField(),
                    typic.NullSchemaField(),
                )
            ),
        ),
        (
            objects.ItemizedKeyedValuedDict,
            typic.ObjectSchemaField(
                title="ItemizedKeyedValuedDict",
                properties={"foo": typic.IntSchemaField()},
                additionalProperties=typic.StrSchemaField(maxLength=5),
            ),
        ),
        (
            objects.ShortStrList,
            typic.ArraySchemaField(items=typic.StrSchemaField(maxLength=5)),
        ),
        (Literal[1, 2], typic.IntSchemaField(enum=(1, 2))),
        (
            Literal[1, 2, None],
            typic.MultiSchemaField(
                anyOf=(
                    typic.IntSchemaField(enum=(1, 2)),
                    typic.NullSchemaField(),
                )
            ),
        ),
        (
            Literal[1, "foo", None],
            typic.MultiSchemaField(
                anyOf=(
                    typic.BaseSchemaField(enum=(1, "foo")),
                    typic.NullSchemaField(),
                )
            ),
        ),
    ],
    ids=repr,
)
def test_typic_schema(obj, expected):
    assert typic.schema(obj) == expected


@pytest.mark.parametrize(
    argnames=("obj", "expected"),
    argvalues=[
        (str, {"type": "string"}),
        (int, {"type": "integer"}),
        (bool, {"type": "boolean"}),
        (float, {"type": "number"}),
        (list, {"type": "array"}),
        (set, {"type": "array", "uniqueItems": True}),
        (frozenset, {"type": "array", "uniqueItems": True, "additionalItems": False}),
        (tuple, {"type": "array", "additionalItems": False}),
        (List[str], {"type": "array", "items": {"type": "string"}}),
        (
            Set[str],
            {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        ),
        (
            Tuple[str],
            {"type": "array", "items": {"type": "string"}, "additionalItems": False},
        ),
        (Tuple[str, ...], {"type": "array", "items": {"type": "string"}}),
        (
            objects.FromDict,
            dict(
                description=objects.FromDict.__doc__,
                title=objects.FromDict.__name__,
                properties={
                    "foo": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "title": "Foo",
                    }
                },
                required=[],
                additionalProperties=False,
                definitions={},
                type="object",
            ),
        ),
        (
            objects.LargeInt,
            dict(type="integer", **objects.LargeInt.__constraints__.for_schema()),
        ),
    ],
)
def test_typic_schema_primitive(obj, expected):
    assert typic.schema(obj, primitive=True) == expected


@pytest.mark.parametrize(
    argnames=("type", "expected"),
    argvalues=[
        (NotImplemented, UndeclaredSchemaField),
        (None, MultiSchemaField),
        ("string", typic.StrSchemaField),
    ],
)
def test_get_field_type(type, expected):
    assert get_field_type(type) is expected


def test_ref_primitive():
    assert typic.Ref("foo").primitive() == {"$ref": "foo"}
