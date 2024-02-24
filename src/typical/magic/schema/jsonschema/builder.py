from __future__ import annotations

import dataclasses
import re
from typing import Any, cast

import inflection

from typical import checks, constraints
from typical.compat import TypedDict
from typical.core import constants
from typical.magic.schema import abc
from typical.magic.schema.jsonschema import field
from typical.types import frozendict

__all__ = ("JSONSchemaBuilder", "JSONSchemaPackage")


class JSONSchemaPackage(TypedDict):
    definitions: dict[str, field.BaseSchemaField]
    oneOf: tuple[field.Ref, ...]


class JSONSchemaBuilder(
    abc.AbstractSchemaBuilder[field.SchemaFieldT, JSONSchemaPackage]
):
    def _from_structured_object_constraint(
        self,
        c: constraints.StructuredObjectConstraints,
        *,
        field_name: str = None,
    ) -> field.ObjectSchemaField | field.ArraySchemaField:
        items = {
            prop: self.build(f, field_name=str(prop)) for prop, f in c.fields.items()
        }
        if isinstance(next(iter(c.fields), None), int):
            return field.ArraySchemaField(
                title=c.type_name,
                description=self._get_description(c),
                prefixItems=(*items.values(),),
                default=c.default,
            )

        refs = {}
        definitions = {}
        for prop, f in items.items():
            if f.title is None:
                refs[prop] = f
                continue

            f, fdefs = self._unnest_definitions(f)
            definitions.update(fdefs)
            definitions[f.title] = f
            refs[prop] = field.Ref(f.title)

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

    def _unnest_definitions(self, f: field.SchemaFieldT):
        definitions: dict[str, field.SchemaFieldT] = {}
        if isinstance(f, field.MultiSchemaField):
            attribs: dict[str, list[field.SchemaFieldT]] = {
                "oneOf": [],
                "allOf": [],
                "anyOf": [],
            }
            replacements = {}
            for attrname, replaces in attribs.items():
                value: tuple[field.SchemaFieldT, ...] | None = (
                    getattr(f, attrname) or ()
                )
                if not value:
                    continue
                replaces = []
                for _f in value:
                    if not _f.title:
                        replaces.append(_f)
                        continue

                    _f, fdefs = self._unnest_definitions(_f)
                    definitions[_f.title] = _f
                    definitions.update(fdefs)
                    replaces.append(field.Ref(_f.title))
                if replaces:
                    replacements[attrname] = (*replaces,)

            if replacements:
                f = dataclasses.replace(f, **replacements)  # type: ignore[arg-type]
            return f, definitions

        if isinstance(f, field.ObjectSchemaField):
            if f.definitions:
                definitions.update(f.definitions)
                f = definitions[f.title] = dataclasses.replace(f, definitions=None)
            return f, definitions

        if isinstance(f, field.ArraySchemaField):
            to_replace: dict[
                str, field.SchemaFieldT | tuple[field.SchemaFieldT, ...]
            ] = {}
            if f.items and f.items.title:
                definitions[f.items.title] = f.items
                to_replace["items"] = field.Ref(f.items.title)
            if f.prefixItems:
                prefix_refs: list[field.SchemaFieldT] = []
                for _f in f.prefixItems:
                    if not _f.title:
                        prefix_refs.append(_f)
                        continue

                    _f, fdefs = self._unnest_definitions(_f)
                    definitions.update(fdefs)
                    prefix_refs.append(field.Ref(_f.title))
                to_replace["prefixItems"] = (*prefix_refs,)

            if to_replace:
                f = dataclasses.replace(f, **to_replace)  # type: ignore[arg-type]
        return f, definitions

    def _from_mapping_constraint(
        self, c: constraints.MappingConstraints, *, field_name: str = None
    ) -> field.ObjectSchemaField:
        additional_ref = None
        definitions = None
        title, description = self._get_field_meta(c, field_name=field_name)
        if isinstance(c.values, constraints.AbstractConstraints):
            additional = self.build(c.values, field_name=f"{title}Items")
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
        self, c: constraints.ArrayConstraints, *, field_name: str = None
    ) -> field.ArraySchemaField:
        items = self.build(c.values) if c.values else None
        title, description = self._get_field_meta(c, field_name=field_name)
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
        self,
        c: constraints.TextConstraints,
        *,
        field_name: str = None,
    ) -> field.StrSchemaField:
        base: field.StrSchemaField | None = cast(
            "field.StrSchemaField | None",
            field.SCHEMA_FIELD_FORMATS.get_by_parent(t=c.type, default=None),
        )
        title, description = self._get_field_meta(c, field_name=field_name)
        if base:
            return dataclasses.replace(
                base,
                title=title,
                description=description,
                default=c.default,
                pattern=c.regex,
                minLength=c.min_length,
                maxLength=c.max_length,
            )

        return field.StrSchemaField(
            title=title,
            description=description,
            default=c.default,
            pattern=c.regex,
            minLength=c.min_length,
            maxLength=c.max_length,
        )

    def _from_decimal_constraint(
        self, c: constraints.DecimalConstraints, *, field_name: str = None
    ) -> field.NumberSchemaField:
        title, description = self._get_field_meta(c, field_name=field_name)
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
        self,
        c: constraints.NumberConstraints,
        *,
        field_name: str = None,
    ) -> field.IntSchemaField:
        if issubclass(c.type, float):
            return self._from_decimal_constraint(
                cast(constraints.DecimalConstraints, c)
            )

        title, description = self._get_field_meta(c, field_name=field_name)

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
        self,
        c: constraints.EnumerationConstraints,
        *,
        field_name: str = None,
    ) -> field.BaseSchemaField:
        types = {it.__class__ for it in c.items}
        t = object
        if len(types) == 1:
            t = types.pop()
        base = field.SCHEMA_FIELD_FORMATS.get_by_parent(
            t, field.UndeclaredSchemaField()
        )
        title, description = self._get_field_meta(c, field_name=field_name)

        return dataclasses.replace(
            base,
            enum=c.items,
            default=c.default,
            title=title,
            description=description,
        )

    def _from_type_constraint(
        self,
        c: constraints.TypeConstraints,
        *,
        field_name: str = None,
    ) -> field.BaseSchemaField:
        base = field.SCHEMA_FIELD_FORMATS.get_by_parent(
            c.type, default=field.UndeclaredSchemaField()
        )
        title, description = self._get_field_meta(c, field_name=field_name)
        return dataclasses.replace(
            base,
            default=c.default,
            title=title,
            description=description,
        )

    def _from_multi_constraint(
        self,
        c: constraints.MultiConstraints,
        *,
        field_name: str = None,
    ) -> field.MultiSchemaField:
        field_schemas = (
            *(self.build(fc, field_name=field_name) for fc in c.constraints),
        )
        return field.MultiSchemaField(
            default=c.default,
            anyOf=field_schemas,
            title="Or".join(f.title for f in field_schemas),
        )

    def _from_undeclared_constraint(
        self, c: constraints.UndeclaredTypeConstraints, *, field_name: str = None
    ) -> field.UndeclaredSchemaField:
        title = self._get_defname(..., "", field_name=field_name)
        return field.UndeclaredSchemaField(title=title, default=c.default)

    def _handle_cyclic_constraint(
        self, c: abc.CT, *, field_name: str = None
    ) -> field.Ref:
        title = self._get_defname(c.type, c.type_name, field_name=field_name)
        return field.Ref(title)

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
        if (
            isinstance(definition, field.MultiSchemaField)
            and definition.oneOf
            and isinstance(definition.oneOf[-1], field.NullSchemaField)
        ):
            return definition
        # If we've assigned a default to the definition, bubble that up to the multi.
        default = constants.empty
        if (
            isinstance(definition, field.BaseSchemaField)
            and definition is not constants.empty
        ):
            default = definition.default
            definition = dataclasses.replace(definition, default=constants.empty)

        return field.MultiSchemaField(
            title=f"Nullable{definition.title}",
            oneOf=(definition, field.NullSchemaField()),
            default=default,
        )

    def _handle_readonly(self, definition: field.SchemaFieldT) -> field.SchemaFieldT:
        if isinstance(definition, field.Ref):
            return definition
        replacements: dict[str, Any] = dict(
            readOnly=True,
            title=f"ReadOnly{definition.title}",
        )
        if definition.default is not constants.empty:
            replacements["enum"] = (definition.default,)

        return dataclasses.replace(definition, **replacements)

    def _handle_writeonly(self, definition: field.SchemaFieldT) -> field.SchemaFieldT:
        if isinstance(definition, field.Ref):
            return definition
        return dataclasses.replace(
            definition, writeOnly=True, title=f"WriteOnly{definition.title}"
        )

    @staticmethod
    def _get_description(t) -> str:
        doc = t.__doc__
        desc = doc and doc.split("\n", maxsplit=1)[0]
        return desc

    @staticmethod
    def _get_defname(t, tname: str, *, field_name: str = None) -> str | None:
        name = inflection.camelize(inflection.underscore(tname))
        if t in (Any, Ellipsis, type(Ellipsis), None, type(None)):
            if field_name:
                return inflection.camelize(field_name)
            return None
        if checks.isgeneric(t):
            match = re.match(r"(?:.*\[)(?P<args>.*)(?:\])", str(t))
            argstring = (match and match.group("args")) or ""
            argname = "".join(
                inflection.camelize(a.replace("'", "").replace('"', ""))
                for a in argstring.split(", ")
                if a not in ("None", "Ellipsis", "empty", "_Any", "Any")
            )
            name = f"{argname}{name}"
        return name

    def _get_field_meta(self, c, *, field_name: str = None) -> tuple[str, str]:
        title, doc = self._get_defname(
            c.type, c.type_name, field_name=field_name
        ), self._get_description(c.type)
        if checks.isgeneric(c.type) or checks.isstdlibtype(c.type):
            doc = None
        return title, doc
