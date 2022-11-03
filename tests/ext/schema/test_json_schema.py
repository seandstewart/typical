from __future__ import annotations

from datetime import datetime
from typing import Any, DefaultDict, Dict, List, Mapping, Set, Tuple, Union

import pytest

import typic
from tests import objects
from typic.compat import Final, Literal
from typic.core.annotations import ReadOnly, WriteOnly
from typic.core.schema import jsonschema


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


schema_test_matrix = {
    "str": (str, jsonschema.StrSchemaField(title="Str")),
    "int": (int, jsonschema.IntSchemaField(title="Int")),
    "bool": (bool, jsonschema.BooleanSchemaField(title="Bool")),
    "float": (float, jsonschema.NumberSchemaField(title="Float")),
    "list": (list, jsonschema.ArraySchemaField(title="List")),
    "set": (set, jsonschema.ArraySchemaField(title="Set", uniqueItems=True)),
    "frozenset": (
        frozenset,
        jsonschema.ArraySchemaField(title="Frozenset", uniqueItems=True),
    ),
    "tuple": (tuple, jsonschema.ArraySchemaField(title="Tuple")),
    "Any": (Any, jsonschema.UndeclaredSchemaField()),
    "list-str": (
        List[str],
        jsonschema.ArraySchemaField(
            title="StrList", items=jsonschema.StrSchemaField(title="Str")
        ),
    ),
    "list-nested-constrained": (
        List[objects.LargeInt],
        jsonschema.ArraySchemaField(
            title="LargeIntList",
            items=jsonschema.IntSchemaField(title="LargeInt", exclusiveMinimum=1000),
        ),
    ),
    "mapping-nested-constrained": (
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
    "user-cls-nullable-field": (
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
                        jsonschema.Ref(title="Str"),
                        jsonschema.NullSchemaField(),
                    ),
                    default=None,
                ),
                Str=jsonschema.StrSchemaField(title="Str"),
            ),
        ),
    ),
    "read-only": (
        ReadOnly[str],
        jsonschema.StrSchemaField(title="ReadOnlyStr", readOnly=True),
    ),
    "final-read-only": (
        Final[str],
        jsonschema.StrSchemaField(title="ReadOnlyStr", readOnly=True),
    ),
    "write-only": (
        WriteOnly[str],
        jsonschema.StrSchemaField(title="WriteOnlyStr", writeOnly=True),
    ),
    "union": (
        Union[int, str],
        jsonschema.MultiSchemaField(
            title="IntOrStr",
            anyOf=(
                jsonschema.IntSchemaField(title="Int"),
                jsonschema.StrSchemaField(title="Str"),
            ),
        ),
    ),
    "simple-mapping": (
        Mapping[str, int],
        jsonschema.ObjectSchemaField(
            title="IntDict",
            additionalProperties=jsonschema.Ref(title="Int"),
            definitions=typic.FrozenDict(Int=jsonschema.IntSchemaField(title="Int")),
        ),
    ),
    "constrained-list": (
        objects.ShortStrList,
        jsonschema.ArraySchemaField(
            title="ShortStrList",
            items=jsonschema.StrSchemaField(title="ShortStr", maxLength=5),
        ),
    ),
    "typed-dict": (
        objects.TDict,
        jsonschema.ObjectSchemaField(
            description=objects.TDict.__doc__,
            title=objects.TDict.__name__,
            properties=typic.FrozenDict(a=jsonschema.Ref(title="Int")),
            required=("a",),
            additionalProperties=False,
            definitions=typic.FrozenDict(Int=jsonschema.IntSchemaField(title="Int")),
        ),
    ),
    "typed-dict-partial": (
        objects.TDictPartial,
        jsonschema.ObjectSchemaField(
            description=objects.TDictPartial.__doc__,
            title=objects.TDictPartial.__name__,
            properties=typic.FrozenDict(a=jsonschema.Ref(title="Int")),
            required=(),
            additionalProperties=False,
            definitions=typic.FrozenDict(Int=jsonschema.IntSchemaField(title="Int")),
        ),
    ),
    "named-typed-tuple": (
        objects.NTup,
        jsonschema.ObjectSchemaField(
            description=objects.NTup.__doc__,
            title=objects.NTup.__name__,
            properties=typic.FrozenDict(a=jsonschema.Ref(title="Int")),
            required=("a",),
            additionalProperties=False,
            definitions=typic.FrozenDict(Int=jsonschema.IntSchemaField(title="Int")),
        ),
    ),
    "named-untyped-tuple": (
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
    "dict-nested-union": (
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
    "tuple-nested-union": (
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
    "nested-double-reference": (
        objects.NestedDoubleReference,
        jsonschema.ObjectSchemaField(
            title=objects.NestedDoubleReference.__name__,
            description=objects.NestedDoubleReference.__doc__,
            properties=typic.FrozenDict(
                first=jsonschema.Ref(title="Data"),
                second=jsonschema.Ref(title="NullableData"),
            ),
            required=("first",),
            additionalProperties=False,
            definitions=typic.FrozenDict(
                Data=jsonschema.ObjectSchemaField(
                    title=objects.Data.__name__,
                    description=objects.Data.__doc__,
                    properties={"foo": jsonschema.Ref(title="Str")},
                    additionalProperties=False,
                    required=("foo",),
                ),
                Str=jsonschema.StrSchemaField(title="Str"),
                NullableData=jsonschema.MultiSchemaField(
                    title="NullableData",
                    oneOf=(jsonschema.Ref(title="Data"), jsonschema.NullSchemaField()),
                ),
            ),
        ),
    ),
    "set-subclass": (
        MySet,
        jsonschema.ArraySchemaField(title="MySet", uniqueItems=True),
    ),
    "url-subclass": (
        MyURL,
        jsonschema.StrSchemaField(title="MyUrl", format=jsonschema.StringFormat.URI),
    ),
    "datetime-subclass": (
        MyDateTime,
        jsonschema.StrSchemaField(
            title="MyDateTime", format=jsonschema.StringFormat.DTIME
        ),
    ),
    "nested-container": (
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
                ),
                Int=jsonschema.IntSchemaField(title="Int"),
            ),
        ),
    ),
    "classvar": (
        objects.KlassVarSubscripted,
        jsonschema.ObjectSchemaField(
            title=objects.KlassVarSubscripted.__name__,
            description=objects.KlassVarSubscripted.__doc__,
            properties={"var": jsonschema.Ref(title="ReadOnlyStr")},
            additionalProperties=False,
            required=(),
            definitions=typic.FrozenDict(
                ReadOnlyStr=jsonschema.StrSchemaField(
                    title="ReadOnlyStr", enum=("foo",), default="foo", readOnly=True
                )
            ),
        ),
    ),
    "all-optional-fields": (
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
                        jsonschema.Ref(title="Str"),
                        jsonschema.NullSchemaField(),
                    ),
                    default=None,
                ),
                Str=jsonschema.StrSchemaField(title="Str"),
            ),
        ),
    ),
    "cyclic-reference": (
        objects.A,
        jsonschema.ObjectSchemaField(
            title=objects.A.__name__,
            description=objects.A.__doc__,
            properties={
                "b": jsonschema.Ref(title="NullableB"),
            },
            additionalProperties=False,
            required=(),
            definitions=typic.FrozenDict(
                {
                    "NullableB": jsonschema.MultiSchemaField(
                        title=f"Nullable{objects.B.__name__}",
                        oneOf=(
                            jsonschema.Ref(title="B"),
                            jsonschema.NullSchemaField(),
                        ),
                    ),
                    "NullableA": jsonschema.MultiSchemaField(
                        title=f"Nullable{objects.A.__name__}",
                        oneOf=(
                            jsonschema.Ref(title="A"),
                            jsonschema.NullSchemaField(),
                        ),
                    ),
                    "A": jsonschema.ObjectSchemaField(
                        title=objects.A.__name__,
                        description=objects.A.__doc__,
                        properties={
                            "b": jsonschema.Ref(title="NullableB"),
                        },
                        additionalProperties=False,
                        required=(),
                    ),
                    "B": jsonschema.ObjectSchemaField(
                        title=objects.B.__name__,
                        description=objects.B.__doc__,
                        properties={"a": jsonschema.Ref(title="NullableA")},
                        additionalProperties=False,
                        required=(),
                    ),
                }
            ),
        ),
    ),
    "nullable-union": (
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
    "constrained-mapping-keys-and-values": (
        objects.KeyedValuedDict,
        jsonschema.ObjectSchemaField(
            title="ShortStrKeyedValuedDict",
            additionalProperties=jsonschema.Ref(title="ShortStr"),
            definitions=typic.FrozenDict(
                ShortStr=jsonschema.StrSchemaField(title="ShortStr", maxLength=5)
            ),
        ),
    ),
    "int-literal": (
        Literal[1, 2],
        jsonschema.IntSchemaField(title="12Literal", enum=(1, 2)),
    ),
    "nullable-int-literal": (
        Literal[1, 2, None],
        jsonschema.MultiSchemaField(
            title="Nullable12Literal",
            oneOf=(
                jsonschema.IntSchemaField(title="12Literal", enum=(1, 2)),
                jsonschema.NullSchemaField(),
            ),
        ),
    ),
    "multi-type-nullable-literal": (
        Literal[1, "foo", None],
        jsonschema.MultiSchemaField(
            title="Nullable1FooLiteral",
            oneOf=(
                jsonschema.UndeclaredSchemaField(title="1FooLiteral", enum=(1, "foo")),
                jsonschema.NullSchemaField(),
            ),
        ),
    ),
}


@pytest.mark.parametrize(
    argnames=("obj", "expected"),
    argvalues=[*schema_test_matrix.values()],
    ids=[*schema_test_matrix.keys()],
)
def test_typic_schema(obj, expected):
    schema = typic.schema(obj)
    assert schema == expected


@pytest.mark.parametrize(
    argnames=("obj", "expected"),
    argvalues=[
        (str, {"title": "Str", "type": "string"}),
        (int, {"title": "Int", "type": "integer"}),
        (bool, {"title": "Bool", "type": "boolean"}),
        (float, {"title": "Float", "type": "number"}),
        (list, {"title": "List", "type": "array"}),
        (set, {"title": "Set", "type": "array", "uniqueItems": True}),
        (frozenset, {"title": "Frozenset", "type": "array", "uniqueItems": True}),
        (tuple, {"title": "Tuple", "type": "array"}),
        (
            List[str],
            {
                "items": {"title": "Str", "type": "string"},
                "title": "StrList",
                "type": "array",
            },
        ),
        (
            Set[str],
            {
                "items": {"title": "Str", "type": "string"},
                "title": "StrSet",
                "type": "array",
            },
        ),
        (
            Tuple[str],
            {
                "items": {"title": "Str", "type": "string"},
                "title": "StrTuple",
                "type": "array",
            },
        ),
        (
            Tuple[str, ...],
            {
                "items": {"title": "Str", "type": "string"},
                "title": "StrTuple",
                "type": "array",
            },
        ),
        (
            objects.FromDict,
            {
                "additionalProperties": False,
                "definitions": {
                    "NullableStr": {
                        "oneOf": [{"$ref": "#/definitions/Str"}, {"type": "null"}],
                        "title": "NullableStr",
                    },
                    "Str": {"title": "Str", "type": "string"},
                },
                "description": "FromDict(foo: 'typing.Optional[str]' = None)",
                "properties": {"foo": {"$ref": "#/definitions/NullableStr"}},
                "required": [],
                "title": "FromDict",
                "type": "object",
            },
        ),
    ],
)
def test_typic_schema_primitive(obj, expected):
    assert typic.schema(obj, primitive=True) == expected
