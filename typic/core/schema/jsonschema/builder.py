from __future__ import annotations

import dataclasses
import re
from typing import Any, cast

import inflection

from typic import checks, util
from typic.compat import TypedDict
from typic.core import constraints
from typic.core.schema import abc
from typic.core.schema.jsonschema import field
from typic.types import frozendict

__all__ = ("JSONSchemaBuilder", "JSONSchemaPackage")


class JSONSchemaPackage(TypedDict):
    definitions: dict[str, field.BaseSchemaField]
    oneOf: tuple[field.Ref, ...]


class JSONSchemaBuilder(
    abc.AbstractSchemaBuilder[field.SchemaFieldT, JSONSchemaPackage]
):
    def _from_structured_object_constraint(
        self, c: constraints.StructuredObjectConstraints
    ) -> field.ObjectSchemaField | field.ArraySchemaField:
        items = {prop: self.build(f) for prop, f in c.fields.items()}
        if isinstance(next(iter(c.fields), None), int):
            return field.ArraySchemaField(
                title=c.type_name,
                description=self._get_description(c),
                prefixItems=(*items.values(),),
                default=c.default,
            )

        refs = {prop: field.Ref(f.title) for prop, f in items.items()}
        definitions = {f.title: f for f in items.values()}
        title, description = self._get_field_meta(c)
        return field.ObjectSchemaField(
            title=title,
            description=description,
            properties=frozendict.FrozenDict(refs),
            additionalProperties=False,
            definitions=frozendict.FrozenDict(definitions),
            required=c.required,
            default=c.default,
        )

    def _from_mapping_constraint(
        self, c: constraints.MappingConstraints
    ) -> field.ObjectSchemaField:
        additional_ref = None
        definitions = None
        title, description = self._get_field_meta(c)
        if isinstance(c.values, constraints.AbstractConstraints):
            additional = self.build(c.values)
            definitions = {additional.title: additional}
            additional_ref = field.Ref(additional.title)
            if title.startswith(additional.title) is False:
                title = additional.title + title
        names = None
        if c.key_pattern:
            names = frozendict.FrozenDict(pattern=c.key_pattern)
        return field.ObjectSchemaField(
            title=title,
            description=description,
            default=c.default,
            additionalProperties=additional_ref,
            maxProperties=c.max_items,
            minProperties=c.min_items,
            propertyNames=names,
            definitions=frozendict.FrozenDict(definitions),
        )

    def _from_array_constraint(
        self, c: constraints.ArrayConstraints
    ) -> field.ArraySchemaField:
        items = self.build(c.values) if c.values else None
        title, description = self._get_field_meta(c)
        if items and title.startswith(items.title) is False:
            title = items.title + title
        return field.ArraySchemaField(
            title=title,
            description=description,
            default=c.default,
            items=items,
            minItems=c.min_items,
            maxItems=c.max_items,
            uniqueItems=c.unique or None,
        )

    def _from_text_constraint(
        self, c: constraints.TextConstraints
    ) -> field.StrSchemaField:
        title, description = self._get_field_meta(c)

        return field.StrSchemaField(
            title=title,
            description=description,
            default=c.default,
            pattern=c.regex,
            minLength=c.min_length,
            maxLength=c.max_length,
        )

    def _from_decimal_constraint(
        self, c: constraints.DecimalConstraints
    ) -> field.NumberSchemaField:
        title, description = self._get_field_meta(c)
        kwargs = {
            "title": title,
            "description": description,
            "default": c.default,
            "multipleOf": c.mul,
            "minimum" if c.inclusive_min else "exclusiveMinimum": c.min,
            "maximum" if c.inclusive_max else "exclusiveMaximum": c.max,
        }

        return field.NumberSchemaField(**kwargs)  # type: ignore[arg-type]

    def _from_number_constraint(
        self, c: constraints.NumberConstraints
    ) -> field.IntSchemaField:
        if issubclass(c.type, float):
            return self._from_decimal_constraint(
                cast(constraints.DecimalConstraints, c)
            )

        title, description = self._get_field_meta(c)

        kwargs = {
            "title": title,
            "description": description,
            "default": c.default,
            "multipleOf": c.mul,
            "minimum" if c.inclusive_min else "exclusiveMinimum": c.min,
            "maximum" if c.inclusive_max else "exclusiveMaximum": c.max,
        }
        return field.IntSchemaField(**kwargs)  # type: ignore[arg-type]

    def _from_enumeration_constraint(
        self, c: constraints.EnumerationConstraints
    ) -> field.BaseSchemaField:
        types = {it.__class__ for it in c.items}
        t = object
        if len(types) == 1:
            t = types.pop()
        base = field.SCHEMA_FIELD_FORMATS.get_by_parent(
            t, field.UndeclaredSchemaField()
        )
        title, description = self._get_field_meta(c)

        return dataclasses.replace(
            base,
            enum=c.items,
            default=c.default,
            title=title,
            description=description,
        )

    def _from_type_constraint(
        self, c: constraints.TypeConstraints
    ) -> field.BaseSchemaField:
        base = field.SCHEMA_FIELD_FORMATS.get_by_parent(
            c.type, default=field.UndeclaredSchemaField()
        )
        title, description = self._get_field_meta(c)
        return dataclasses.replace(
            base,
            default=c.default,
            title=title,
            description=description,
        )

    def _from_multi_constraint(
        self, c: constraints.MultiConstraints
    ) -> field.MultiSchemaField:
        field_schemas = (*(self.build(fc) for fc in c.constraints),)
        return field.MultiSchemaField(
            default=c.default,
            anyOf=field_schemas,
            title="Or".join(f.title for f in field_schemas),
        )

    def _from_delayed_constraint(
        self, c: constraints.DelayedConstraintsProxy
    ) -> field.Ref:
        return field.Ref(util.get_name(c.ref))

    def _handle_cyclic_constraint(self, c: abc.CT) -> field.Ref:
        return field.Ref(c.type_name)

    def _gather_definitions(self) -> JSONSchemaPackage:
        unprocessed = {schema.title: schema for schema in self._cache.values()}
        definitions = {}
        refs = []
        while unprocessed:
            title, schema = unprocessed.popitem()
            if isinstance(schema, field.Ref):
                continue
            # Process nested schemas for container types
            # region: JSON Objects (dicts and classes)
            if isinstance(schema, field.ObjectSchemaField):
                to_replace: dict[str, Any] = {}
                if schema.definitions:
                    to_replace["definitions"] = None
                    unprocessed.update(schema.definitions)
                    schema = dataclasses.replace(schema, definitions=None)
                if isinstance(schema.additionalProperties, field.BaseSchemaField):
                    props = schema.additionalProperties
                    to_replace["additionalProperties"] = field.Ref(props.title)
                    unprocessed[props.title] = props
                if to_replace:
                    schema = dataclasses.replace(schema, **to_replace)
            # endregion
            # region: JSON Arrays (lists, tuples, sets, etc)
            elif isinstance(schema, field.ArraySchemaField):
                to_replace = {}
                if schema.items:
                    unprocessed[schema.items.title] = schema.items
                    to_replace["items"] = field.Ref(schema.items.title)
                if schema.prefixItems:
                    unprocessed.update((sch.title, sch) for sch in schema.prefixItems)
                    srefs = tuple(field.Ref(sch.title) for sch in schema.prefixItems)
                    to_replace["prefixItems"] = srefs
                if to_replace:
                    schema = dataclasses.replace(schema, **to_replace)
            # endregion
            definitions[title] = schema
            refs.append(field.Ref(schema.title))
        return {"definitions": definitions, "oneOf": (*refs,)}

    def _wrap_nullable(self, definition: field.SchemaFieldT) -> field.SchemaFieldT:
        return field.MultiSchemaField(
            title=f"Nullable{definition.title}",
            oneOf=(definition, field.NullSchemaField()),
        )

    @staticmethod
    def _get_description(t) -> str:
        doc = t.__doc__
        desc = doc and doc.split("\n", maxsplit=1)[0]
        return desc

    @staticmethod
    def _get_defname(t, tname: str) -> str | None:
        name = inflection.camelize(inflection.underscore(tname))
        if t in (Any, Ellipsis, type(Ellipsis), None, type(None)):
            return None
        if checks.isgeneric(t):
            match = re.match(r"(?:.*\[)(?P<args>.*)(?:\])", str(t))
            argstring = (match and match.group("args")) or ""
            argname = "".join(
                inflection.camelize(a.replace("'", "").replace('"', ""))
                for a in argstring.split(", ")
                if a not in ("None", "Ellipsis", "_Empty", "_Any")
            )
            name = f"{argname}{name}"
        return name

    def _get_field_meta(self, c) -> tuple[str, str]:
        title, doc = self._get_defname(c.type, c.type_name), self._get_description(
            c.type
        )
        if checks.isgeneric(c.type) or checks.isstdlibtype(c.type):
            doc = None
        return title, doc
