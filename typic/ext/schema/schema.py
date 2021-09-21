from __future__ import annotations

import dataclasses
import enum
import warnings
from typing import (
    Union,
    Type,
    Mapping,
    Optional,
    Dict,
    Any,
    List,
    Generic,
    cast,
    AnyStr,
    TYPE_CHECKING,
    MutableMapping,
    Tuple,
)

import inflection  # type: ignore

from typic.common import ReadOnly, WriteOnly
from typic.serde.resolver import resolver
from typic.serde.common import SerdeProtocol, Annotation
from typic.compat import Final, TypedDict, ForwardRef, Literal
from typic.util import get_args, origin, get_name
from typic.checks import istypeddict, isnamedtuple, isliteral, isuniontype
from typic.types.frozendict import FrozenDict

from .field import (  # type: ignore
    MultiSchemaField,
    ObjectSchemaField,
    UndeclaredSchemaField,
    Ref,
    SchemaFieldT,
    SCHEMA_FIELD_FORMATS,
    SchemaType,
    ArraySchemaField,
    NullSchemaField,
)

if TYPE_CHECKING:
    from typic.constraints import ArrayConstraints, MappingConstraints  # noqa: F401

_IGNORE_DOCS = frozenset({Mapping.__doc__, Generic.__doc__, List.__doc__})

__all__ = ("SchemaBuilder", "SchemaDefinitions", "builder")


_KNOWN = (*(f for f in SCHEMA_FIELD_FORMATS.keys() if f not in {AnyStr, object}),)


class SchemaDefinitions(TypedDict):
    """A :py:class:`TypedDict` for JSON Schema Definitions."""

    definitions: Dict[str, Union[ObjectSchemaField, Mapping]]


class SchemaBuilder:
    """Build a JSON schema from an object.

    Notes
    -----
    This shouldn't be used directly.
    Schema generation is handled automatically when a class is wrapped.

    See Also
    --------
    :py:func:`~typic.typed.glob.wrap_cls`
    :py:func:`~typic.klass.klass`
    """

    def __init__(self):
        self.__cache = {}
        self.__attached = set()
        self.__stack = set()

    def attach(self, t: Type):
        self.__attached.add(t)

    def _handle_mapping(
        self, proto: SerdeProtocol, parent: Type = None, *, name: str = None, **extra
    ) -> MutableMapping:
        anno = proto.annotation
        args = anno.args
        config = extra
        config["title"] = self.defname(anno.resolved, name=name)
        doc = getattr(anno.resolved, "__doc__", None)
        if doc not in _IGNORE_DOCS:
            config["description"] = doc

        constraints = cast("MappingConstraints", proto.constraints)
        attrs = (
            ("items", "properties"),
            ("patterns", "patternProperties"),
            ("key_dependencies", "dependencies"),
        )
        for src, target in attrs:
            items = getattr(constraints, src)
            if items:
                config[target] = {
                    nm: self.get_field(
                        resolver.resolve(
                            it.type, is_optional=it.nullable, namespace=parent
                        ),
                        parent=parent,
                    )
                    for nm, it in items.items()
                }
        config["additionalProperties"] = not constraints.total
        if args:
            config["additionalProperties"] = self.get_field(
                resolver.resolve(args[-1], namespace=parent), parent=parent
            )

        return config

    def _handle_array(
        self, proto: SerdeProtocol, parent: Type = None, **extra
    ) -> MutableMapping:
        anno = proto.annotation
        args = anno.args
        has_ellipsis = args[-1] is Ellipsis if args else False
        config = extra
        if has_ellipsis:
            args = args[:-1]
        if args:
            constrs = set(
                self.get_field(resolver.resolve(x, namespace=parent), parent=parent)
                for x in args
            )
            config["items"] = (*constrs,) if len(constrs) > 1 else constrs.pop()
            if anno.origin in {tuple, frozenset}:
                config["additionalItems"] = False if not has_ellipsis else None
            if anno.origin in {set, frozenset}:
                config["uniqueItems"] = True
        return config

    def _check_optional(
        self,
        annotation: Annotation,
        schema: SchemaFieldT,
        ro: Optional[bool],
        wo: Optional[bool],
        name: Optional[str],
    ) -> SchemaFieldT:
        if annotation.optional and annotation.parameter.default is not ...:
            null = NullSchemaField()
            if isinstance(schema, MultiSchemaField):
                anyOf = schema.anyOf or ()
                if null not in {*anyOf}:
                    schema = dataclasses.replace(schema, anyOf=(*anyOf, null))
                return schema
            # Primitives are generally defined as anonymous types
            title = subtitle = schema.title or self.defname(annotation.resolved, name)
            # If we have an object with this name, make this an 'Optional' reference.
            if isinstance(schema, (Ref, ObjectSchemaField)):
                title = subtitle and f"Optional{subtitle}"
            default = getattr(schema, "default", None)
            child: SchemaFieldT = (
                schema
                if isinstance(schema, Ref)
                else dataclasses.replace(
                    schema, default=None, readOnly=ro, writeOnly=wo
                )
            )
            return MultiSchemaField(
                title=title,
                default=default,
                readOnly=ro,
                writeOnly=wo,
                anyOf=(child, NullSchemaField()),
            )
        return schema

    def _handle_union(
        self,
        anno: Annotation,
        ro: Optional[bool],
        wo: Optional[bool],
        name: Optional[str],
        parent: Optional[Type],
    ):
        fields: List[SchemaFieldT] = []
        args = get_args(anno.un_resolved)
        for t in args:
            if t.__class__ is ForwardRef or t is parent:
                n = name or get_name(t)
                fields.append(Ref(f"#/definitions/{n}"))
                continue
            fields.append(
                self.get_field(resolver.resolve(t, namespace=parent), parent=parent)
            )
        schema = self._check_optional(
            anno,
            MultiSchemaField(
                title=name and self.defname(anno.resolved, name=name),
                anyOf=(*fields,),
            ),
            ro,
            wo,
            name,
        )
        self.__cache[anno] = schema
        return schema

    def _build_field(
        self,
        use: Type,
        protocol: SerdeProtocol,
        parent: Optional[Type],
        enum_: Optional[Tuple[Any, ...]],
        default: Optional[Any],
        ro: Optional[bool],
        wo: Optional[bool],
        name: Optional[str],
    ) -> SchemaFieldT:
        # If we've got a base object, use it
        base: Optional[SchemaFieldT]
        if use is object:
            base = UndeclaredSchemaField()
        elif istypeddict(use) or isnamedtuple(use):
            base = None
        else:
            base = cast(SchemaFieldT, SCHEMA_FIELD_FORMATS.get_by_parent(use))
        if base:
            config: MutableMapping = (
                protocol.constraints.for_schema() if protocol.constraints else {}
            )
            config.update(enum=enum_, default=default, readOnly=ro, writeOnly=wo)
            # `use` should always be a dict if the annotation is a Mapping,
            # thanks to `origin()` & `resolve()`.
            if isinstance(base, ObjectSchemaField):
                config = self._handle_mapping(
                    protocol, parent=parent, name=name, **config
                )
            elif isinstance(base, ArraySchemaField):
                config = self._handle_array(protocol, parent=parent, **config)
            schema = dataclasses.replace(base, **config)
        else:
            try:
                schema = self.build_schema(use)
            except (ValueError, TypeError) as e:
                warnings.warn(f"Couldn't build schema for {use}: {e}")
                schema = UndeclaredSchemaField(
                    enum=enum_,
                    title=self.defname(use, name=name),
                    default=default,
                    readOnly=ro,
                    writeOnly=wo,
                )
        schema = self._check_optional(protocol.annotation, schema, ro, wo, name)
        return schema

    def get_field(
        self,
        protocol: SerdeProtocol,
        *,
        ro: bool = None,
        wo: bool = None,
        name: str = None,
        parent: Type = None,
    ) -> "SchemaFieldT":
        """Get a field definition for a JSON Schema."""
        if protocol.annotation in self.__stack:
            name = self.defname(protocol.annotation.resolved_origin, name)
            return self._check_optional(
                protocol.annotation, Ref(f"#/definitions/{name}"), ro, wo, name
            )
        anno = protocol.annotation
        if anno in self.__cache:
            return self.__cache[anno]
        # Get the default value
        # `None` gets filtered out down the line. this is okay.
        # If a field isn't required an empty default is functionally the same
        # as a default to None for the JSON schema.
        default = anno.parameter.default if anno.has_default else None
        # `use` is the based annotation we will use for building the schema
        use = getattr(anno.origin, "__parent__", anno.origin)
        # This is a flat optional, handle it separately from the Union block.
        use = anno.resolved if isuniontype(use) and not anno.args else use
        # If there's not a static annotation, short-circuit the rest of the checks.
        schema: SchemaFieldT
        if use in {Any, anno.EMPTY}:
            schema = self._check_optional(anno, UndeclaredSchemaField(), ro, wo, name)
            self.__cache[anno] = schema
            return schema

        # Unions are `anyOf`, get a new field for each arg and return.
        # {'type': ['string', 'integer']} ==
        #   {'anyOf': [{'type': 'string'}, {'type': 'integer'}]}
        # We don't care about syntactic sugar if it's functionally the same.
        if isuniontype(use):
            return self._handle_union(anno=anno, ro=ro, wo=wo, name=name, parent=parent)

        self.__stack.add(anno)

        # Check if this should be ro/wo
        if use in {ReadOnly, WriteOnly, Final}:
            ro = (use in {ReadOnly, Final}) or None
            wo = (use is WriteOnly) or None
            use = origin(anno.resolved)
            use = getattr(use, "__parent__", use)

        # Check for an enumeration
        enum_ = None
        # Functionally, literals are enumerations.
        if isliteral(use):
            enum_ = (*(a for a in anno.args if a is not None),)
            ts = {a.__class__ for a in enum_}
            use = Literal
            if len(ts) == 1:
                use = ts.pop()

        elif issubclass(use, enum.Enum):
            use = cast(Type[enum.Enum], use)
            enum_ = tuple(x.value for x in use)
            use = getattr(use._member_type_, "__parent__", use._member_type_)  # type: ignore

        # If this is ro with a default, we can consider this a const
        # Which is an enum with a single value -
        # we don't currently honor `{'const': <val>}` since it's just syntactic sugar.
        if ro and default:
            enum_ = (default.value if isinstance(default, enum.Enum) else default,)

        schema = self._build_field(
            use=use,
            protocol=protocol,
            parent=parent,
            enum_=enum_,
            default=default,
            ro=ro,
            wo=wo,
            name=name,
        )
        self.__cache[anno] = schema
        self.__stack.clear()
        return schema

    @staticmethod
    def _flatten_object_definitions(
        definitions: Dict[str, Any], field: ObjectSchemaField
    ):
        definitions.update(**(field.definitions or {}))  # type: ignore
        field = dataclasses.replace(field, definitions=None)
        definitions[field.title] = field  # type: ignore
        return Ref(f"#/definitions/{field.title}")

    def _flatten_array_definitions(
        self, definitions: Dict[str, Any], field: ArraySchemaField
    ):
        replace = {}
        for field_name in ("items", "contains", "additionalItems"):
            it = getattr(field, field_name)
            if isinstance(it, (ObjectSchemaField, ArraySchemaField, MultiSchemaField)):
                ref = self._flatten_definitions(definitions, it)
                replace[field_name] = ref
        return dataclasses.replace(field, **replace) if replace else field

    def _flatten_multi_definitions(
        self, definitions: Dict[str, Any], field: MultiSchemaField
    ) -> MultiSchemaField:
        replace = {}
        for field_name in ("anyOf", "allOf", "oneOf"):
            it = getattr(field, field_name)
            if it:
                flattened = []
                for f in it:
                    nf = self._flatten_definitions(definitions, f)
                    flattened.append(nf)
                replace[field_name] = (*flattened,)
        return dataclasses.replace(field, **replace) if replace else field

    def _flatten_definitions(self, definitions: Dict[str, Any], field: SchemaFieldT):
        if isinstance(field, ObjectSchemaField):
            return self._flatten_object_definitions(definitions, field)
        elif isinstance(field, ArraySchemaField):
            return self._flatten_array_definitions(definitions, field)
        elif isinstance(field, MultiSchemaField):
            return self._flatten_multi_definitions(definitions, field)
        return field

    @classmethod
    def defname(cls, obj, name: str = None) -> Optional[str]:
        """Get the definition name for an object."""
        defname = name or getattr(obj, "__name__", None)
        if defname in cls._IGNORE_NAME:
            defname = None
        if (obj is dict or origin(obj) is dict) and name:
            defname = name
        return inflection.camelize(defname) if defname else None

    # FIXME: This isn't sustainable. Figure out a better way to ignore generics.
    _IGNORE_NAME = {"Mapping", "MutableMapping", "Dict", "Literal"}

    def build_schema(self, obj: Type, *, name: str = None) -> ObjectSchemaField:
        """Build a valid JSON Schema, including nested schemas."""
        if obj in self.__cache:  # pragma: nocover
            return self.__cache[obj]

        protocols: Dict[str, SerdeProtocol] = resolver.protocols(obj)
        definitions: Dict[str, Any] = {}
        properties: Dict[str, Any] = {}
        required: List[str] = []
        total: bool = getattr(obj, "__total__", True)
        for nm, protocol in protocols.items():
            if protocol.annotation.resolved_origin is obj:
                flattened = Ref(f"#/definitions/{self.defname(obj)}")
            else:
                ro = protocol.annotation.is_class_var or None
                field = self.get_field(protocol, name=nm, parent=obj, ro=ro)
                # If we received an object schema,
                # figure out a name and inherit the definitions.
                flattened = self._flatten_definitions(definitions, field)
            properties[nm] = flattened
            # Check for required field(s)
            if not protocol.annotation.has_default:
                required.append(nm)
        schema = ObjectSchemaField(
            title=name or self.defname(obj),
            description=obj.__doc__,
            properties=FrozenDict(properties),
            additionalProperties=False,
            required=(*required,) if total else (),
            definitions=FrozenDict(definitions),
        )
        self.__cache[obj] = schema
        return schema

    def all(self, primitive: bool = False) -> SchemaDefinitions:
        """Get all of the JSON Schema objects which have been defined.

        `typical` maintains a register of all resolved schema definitions.
        This method give high-level, immediate read access to that registry.

        Parameters
        ----------
        primitive

        Examples
        --------
        >>> import json
        >>> import typic
        >>> schemas = typic.schemas(primitive=True)
        >>> print(json.dumps(schemas["definitions"]["Duck"], indent=2))
        {
          "type": "object",
          "title": "Duck",
          "description": "Duck(color: str)",
          "properties": {
            "color": {
              "type": "string"
            }
          },
          "additionalProperties": false,
          "required": [
            "color"
          ]
        }
        """
        definitions = SchemaDefinitions(definitions={})
        schm: ObjectSchemaField
        while self.__attached:
            self.build_schema(self.__attached.pop())
        for obj, schm in self.__cache.items():
            if schm.type != SchemaType.OBJ:
                continue
            definitions["definitions"].update(
                {
                    x: dataclasses.replace(y, definitions=None)
                    for x, y in (schm.definitions or {}).items()
                }
            )
            definitions["definitions"][
                schm.title  # type: ignore
            ] = dataclasses.replace(schm, definitions=None)
        if primitive:
            definitions["definitions"] = {
                x: y.primitive() if isinstance(y, ObjectSchemaField) else y
                for x, y in definitions["definitions"].items()
            }
        return definitions


builder = SchemaBuilder()
