from __future__ import annotations

from datetime import datetime
from typing import List, Tuple, Set, Union, Mapping, Dict, Any, DefaultDict

import pytest
import typic
from typic.core.annotations import ReadOnly, WriteOnly
from typic.core.schema import jsonschema
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
        (str, jsonschema.StrSchemaField(title="Str")),
        (int, jsonschema.IntSchemaField(title="Int")),
        (bool, jsonschema.BooleanSchemaField(title="Bool")),
        (float, jsonschema.NumberSchemaField(title="Float")),
        (list, jsonschema.ArraySchemaField(title="List")),
        (set, jsonschema.ArraySchemaField(title="Set", uniqueItems=True)),
        (frozenset, jsonschema.ArraySchemaField(title="Frozenset", uniqueItems=True)),
        (tuple, jsonschema.ArraySchemaField(title="Tuple")),
        (Any, jsonschema.UndeclaredSchemaField()),
        (
            List[str],
            jsonschema.ArraySchemaField(
                title="StrList", items=jsonschema.StrSchemaField(title="Str")
            ),
        ),
        (
            List[objects.LargeInt],
            jsonschema.ArraySchemaField(
                title="LargeIntList",
                items=jsonschema.IntSchemaField(
                    title="LargeInt", exclusiveMinimum=1000
                ),
            ),
        ),
        (
            Mapping[str, objects.LargeInt],
            jsonschema.ObjectSchemaField(
                title="LargeIntDict",
                additionalProperties=jsonschema.Ref(title="LargeInt"),
                definitions=typic.FrozenDict(
                    LargeInt=jsonschema.IntSchemaField(
                        title="LargeInt", exclusiveMinimum=1000
                    ),
                ),
            ),
        ),
        (
            objects.FromDict,
            jsonschema.ObjectSchemaField(
                description=objects.FromDict.__doc__,
                title=objects.FromDict.__name__,
                properties=typic.FrozenDict(
                    foo=jsonschema.Ref(title="NullableStr"),
                ),
                required=(),
                additionalProperties=False,
                definitions=typic.FrozenDict(
                    NullableStr=jsonschema.MultiSchemaField(
                        title="NullableStr",
                        oneOf=(
                            jsonschema.StrSchemaField(title="Str"),
                            jsonschema.NullSchemaField(),
                        ),
                    ),
                ),
            ),
        ),
        (ReadOnly[str], jsonschema.StrSchemaField(readOnly=True)),
        (Final[str], jsonschema.StrSchemaField(readOnly=True)),
        (WriteOnly[str], jsonschema.StrSchemaField(writeOnly=True)),
        (
            Union[int, str],
            jsonschema.MultiSchemaField(
                title="IntOrStr",
                anyOf=(
                    jsonschema.IntSchemaField(title="Int"),
                    jsonschema.StrSchemaField(title="Str"),
                ),
            ),
        ),
        (
            Mapping[str, int],
            jsonschema.ObjectSchemaField(
                title="IntDict",
                additionalProperties=jsonschema.Ref(title="Int"),
                definitions=typic.FrozenDict(
                    Int=jsonschema.IntSchemaField(title="Int")
                ),
            ),
        ),
        (
            Mapping[str, objects.LargeInt],
            jsonschema.ObjectSchemaField(
                title="LargeIntDict",
                additionalProperties=jsonschema.Ref(title="LargeInt"),
                definitions=typic.FrozenDict(
                    LargeInt=jsonschema.IntSchemaField(
                        title="LargeInt", exclusiveMinimum=1000
                    )
                ),
            ),
        ),
        (
            objects.ShortStrList,
            jsonschema.ArraySchemaField(
                title="ShortStrList",
                items=jsonschema.StrSchemaField(title="ShortStr", maxLength=5),
            ),
        ),
        (
            objects.TDict,
            jsonschema.ObjectSchemaField(
                description=objects.TDict.__doc__,
                title=objects.TDict.__name__,
                properties=typic.FrozenDict(a=jsonschema.Ref(title="Int")),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(
                    Int=jsonschema.IntSchemaField(title="Int")
                ),
            ),
        ),
        (
            objects.TDictPartial,
            jsonschema.ObjectSchemaField(
                description=objects.TDictPartial.__doc__,
                title=objects.TDictPartial.__name__,
                properties=typic.FrozenDict(a=jsonschema.Ref(title="Int")),
                required=(),
                additionalProperties=False,
                definitions=typic.FrozenDict(
                    Int=jsonschema.IntSchemaField(title="Int")
                ),
            ),
        ),
        (
            objects.NTup,
            jsonschema.ObjectSchemaField(
                description=objects.NTup.__doc__,
                title=objects.NTup.__name__,
                properties=typic.FrozenDict(a=jsonschema.Ref(title="Int")),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(
                    Int=jsonschema.IntSchemaField(title="Int")
                ),
            ),
        ),
        (
            objects.ntup,
            jsonschema.ObjectSchemaField(
                description=objects.ntup.__doc__,
                title=objects.ntup.__name__.title(),
                properties=typic.FrozenDict(a=jsonschema.UndeclaredSchemaField()),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(),
            ),
        ),
        (
            Dict[str, Union[int, str]],
            jsonschema.ObjectSchemaField(
                title="IntOrStrDict",
                additionalProperties=jsonschema.Ref(title="IntOrStr"),
                definitions=typic.FrozenDict(
                    IntOrStr=jsonschema.MultiSchemaField(
                        title="IntOrStr",
                        anyOf=(
                            jsonschema.IntSchemaField(title="Int"),
                            jsonschema.StrSchemaField(title="Str"),
                        ),
                    )
                ),
            ),
        ),
        (
            Tuple[Union[int, str], ...],
            jsonschema.ArraySchemaField(
                title="IntOrStrTuple",
                items=jsonschema.MultiSchemaField(
                    title="IntOrStr",
                    anyOf=(
                        jsonschema.IntSchemaField(title="Int"),
                        jsonschema.StrSchemaField(title="Str"),
                    ),
                ),
            ),
        ),
        (
            objects.NestedDoubleReference,
            jsonschema.ObjectSchemaField(
                title=objects.NestedDoubleReference.__name__,
                description=objects.NestedDoubleReference.__doc__,
                properties=typic.FrozenDict(
                    first=jsonschema.Ref(title="Data"),
                    second=jsonschema.Ref(title="Data"),
                ),
                required=("first",),
                additionalProperties=False,
                definitions=typic.FrozenDict(
                    {
                        "Data": jsonschema.ObjectSchemaField(
                            title=objects.Data.__name__,
                            description=objects.Data.__doc__,
                            properties={"foo": jsonschema.Ref(title="Str")},
                            additionalProperties=False,
                            required=("foo",),
                            definitions=typic.FrozenDict(
                                Str=jsonschema.StrSchemaField(title="Str")
                            ),
                        )
                    }
                ),
            ),
        ),
        (MySet, jsonschema.ArraySchemaField(title="MySet", uniqueItems=True)),
        (
            MyURL,
            jsonschema.StrSchemaField(
                title="MyURL", format=jsonschema.StringFormat.URI
            ),
        ),
        (
            MyDateTime,
            jsonschema.StrSchemaField(
                title="MyDateTime", format=jsonschema.StringFormat.DTIME
            ),
        ),
        (
            MyDateTime,
            jsonschema.StrSchemaField(
                title="MyDateTime", format=jsonschema.StringFormat.DTIME
            ),
        ),
        (
            Container,
            jsonschema.ObjectSchemaField(
                title=Container.__name__,
                description=Container.__doc__,
                properties={"data": jsonschema.Ref(title="IntDefaultdict")},
                additionalProperties=False,
                required=("data",),
                definitions=typic.FrozenDict(
                    IntDefaultdict=jsonschema.ObjectSchemaField(
                        title="IntDefaultdict",
                        additionalProperties=jsonschema.Ref("Int"),
                        definitions=typic.FrozenDict(
                            Int=jsonschema.IntSchemaField(title="Int")
                        ),
                    )
                ),
            ),
        ),
        (
            objects.KlassVarSubscripted,
            jsonschema.ObjectSchemaField(
                title=objects.KlassVarSubscripted.__name__,
                description=objects.KlassVarSubscripted.__doc__,
                properties={
                    "var": jsonschema.StrSchemaField(
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
            jsonschema.ObjectSchemaField(
                title=objects.ThreeOptionals.__name__,
                description=objects.ThreeOptionals.__doc__,
                properties=typic.FrozenDict(
                    a=jsonschema.Ref(title="NullableStr"),
                    b=jsonschema.Ref(title="NullableStr"),
                    c=jsonschema.Ref(title="NullableStr"),
                ),
                required=("a",),
                additionalProperties=False,
                definitions=typic.FrozenDict(
                    NullableStr=jsonschema.MultiSchemaField(
                        title="NullableStr",
                        oneOf=(
                            jsonschema.StrSchemaField(title="Str"),
                            jsonschema.NullSchemaField(),
                        ),
                    )
                ),
            ),
        ),
        (
            objects.A,
            jsonschema.ObjectSchemaField(
                title=objects.A.__name__,
                description=objects.A.__doc__,
                properties={
                    "b": jsonschema.MultiSchemaField(
                        title=f"Optional{objects.B.__name__}",
                        anyOf=(
                            jsonschema.Ref(title="B"),
                            jsonschema.NullSchemaField(),
                        ),
                    )
                },
                additionalProperties=False,
                required=(),
                definitions=typic.FrozenDict(
                    {
                        "A": jsonschema.ObjectSchemaField(
                            title=objects.A.__name__,
                            description=objects.A.__doc__,
                            properties={
                                "b": jsonschema.MultiSchemaField(
                                    title=f"Optional{objects.B.__name__}",
                                    anyOf=(
                                        jsonschema.Ref(title="B"),
                                        jsonschema.NullSchemaField(),
                                    ),
                                )
                            },
                            additionalProperties=False,
                            required=(),
                        ),
                        "B": jsonschema.ObjectSchemaField(
                            title=objects.B.__name__,
                            description=objects.B.__doc__,
                            properties={
                                "a": jsonschema.MultiSchemaField(
                                    title=f"Optional{objects.A.__name__}",
                                    anyOf=(
                                        jsonschema.Ref(title="A"),
                                        jsonschema.NullSchemaField(),
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
            jsonschema.MultiSchemaField(
                title="NullableIntOrStr",
                oneOf=(
                    jsonschema.MultiSchemaField(
                        title="IntOrStr",
                        anyOf=(
                            jsonschema.IntSchemaField(title="Int"),
                            jsonschema.StrSchemaField(title="Str"),
                        ),
                    ),
                    jsonschema.NullSchemaField(),
                ),
            ),
        ),
        (
            objects.KeyedValuedDict,
            jsonschema.ObjectSchemaField(
                title="ShortStrKeyedValuedDict",
                additionalProperties=jsonschema.Ref(title="ShortStr"),
                definitions=typic.FrozenDict(
                    ShortStr=jsonschema.StrSchemaField(title="ShortStr", maxLength=5)
                ),
            ),
        ),
        (
            objects.ShortStrList,
            jsonschema.ArraySchemaField(
                title="ShortStrList",
                items=jsonschema.StrSchemaField(title="ShortStr", maxLength=5),
            ),
        ),
        (Literal[1, 2], jsonschema.IntSchemaField(title="12Literal", enum=(1, 2))),
        (
            Literal[1, 2, None],
            jsonschema.MultiSchemaField(
                title="Nullable12Literal",
                oneOf=(
                    jsonschema.IntSchemaField(title="12Literal", enum=(1, 2)),
                    jsonschema.NullSchemaField(),
                ),
            ),
        ),
        (
            Literal[1, "foo", None],
            jsonschema.MultiSchemaField(
                title="Nullable1FooLiteral",
                oneOf=(
                    jsonschema.UndeclaredSchemaField(
                        title="1FooLiteral", enum=(1, "foo")
                    ),
                    jsonschema.NullSchemaField(),
                ),
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
    ],
)
def test_typic_schema_primitive(obj, expected):
    assert typic.schema(obj, primitive=True) == expected
