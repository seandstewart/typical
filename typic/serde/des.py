from __future__ import annotations

import dataclasses
import datetime
import functools
import inspect
import pathlib
import re
import uuid
from collections import deque, defaultdict, abc
from operator import attrgetter
from typing import (
    Mapping,
    Any,
    Union,
    Callable,
    Type,
    Dict,
    Tuple,
    List,
    Pattern,
    Match,
    cast,
    TYPE_CHECKING,
    Optional,
    Set,
    NoReturn,
)

from pendulum import parse as dateparse, DateTime, instance

from typic import checks, gen
from typic.strict import STRICT_MODE
from typic.util import (
    safe_eval,
    cached_issubclass,
    cached_signature,
    get_defname,
    get_tag_for_types,
    get_unique_name,
    get_name,
    slotted,
)
from typic.checks import ismappingtype
from typic.common import DEFAULT_ENCODING, ObjectT
from typic.compat import TypeGuard, Literal
from .common import (
    DeserializerT,
    DeserializerRegistryT,
    SerdeConfig,
    Annotation,
    DelayedAnnotation,
    ForwardDelayedAnnotation,
    AnnotationT,
)

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver

_ORIG_SETTER_NAME = "__setattr_original__"
_origsettergetter = attrgetter(_ORIG_SETTER_NAME)
_TYPIC_ANNOS_NAME = "__typic_annotations__"
_annosgetter = attrgetter(_TYPIC_ANNOS_NAME)
_TOO_MANY_POS = "too many positional arguments"
_VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL
_VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD
_KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY
_POSITIONAL_ONLY = inspect.Parameter.POSITIONAL_ONLY
_POSITIONAL_OR_KEYWORD = inspect.Parameter.POSITIONAL_OR_KEYWORD
_KWD_KINDS = {_VAR_KEYWORD, _KEYWORD_ONLY}
_POS_KINDS = {_VAR_POSITIONAL, _POSITIONAL_ONLY}
_empty = inspect.Signature.empty
_RETURN_KEY = "return"
_SELF_NAME = "self"
_TO_RESOLVE: List[Union[Type, Callable]] = []
_SCHEMA_NAME = "__json_schema__"


class DesFactory:
    """A callable class for ``des``erialzing values.

    Checks for:

            - builtin types
            - :py:mod:`typing` type annotations
            - :py:class:`datetime.date`
            - :py:class:`datetime.datetime`
            - :py:class:`typing.TypedDict`
            - :py:class:`typing.NamedTuple`
            - :py:func:`collections.namedtuple`
            - User-defined classes (limited)

    Examples
    --------
    >>> import typic
    >>> typic.transmute(bytes, "foo")
    b'foo'
    >>> typic.transmute(dict, "{'foo': 'bar'}")
    {'foo': 'bar'}
    """

    STRICT = STRICT_MODE
    DEFAULT_BYTE_ENCODING = "utf-8"
    UNRESOLVABLE = frozenset(
        (
            Any,
            Match,
            re.Match,  # type: ignore
            type(None),
            _empty,
            Callable,
            abc.Callable,
        )
    )
    VNAME = "val"
    VTYPE = "vtype"
    __DES_CACHE: Dict[str, DeserializerT] = {}
    __USER_DESS: DeserializerRegistryT = deque()

    def __init__(self, resolver: Resolver):
        self.resolver = resolver

    def register(self, deserializer: DeserializerT, check: DeserializerT):
        """Register a user-defined coercer.

        In the rare case where typic can't figure out how to coerce your annotation
        correctly, a custom coercer may be registered alongside a check function which
        returns a simple boolean indicating whether this is the correct coercer for an
        annotation.
        """
        self.__USER_DESS.appendleft((check, deserializer))

    def _set_checks(self, func: gen.Block, anno_name: str, annotation: Annotation):
        _ctx = {}
        # run a safe eval if input is text and anno isn't
        if inspect.isclass(annotation.resolved_origin) and issubclass(
            annotation.resolved_origin, (str, bytes)
        ):
            self._add_vtype(func)
        else:
            self._add_eval(func)
        # Equality checks for defaults and optionals
        custom_equality = hasattr(annotation.resolved_origin, "equals")
        if custom_equality and (annotation.optional or annotation.has_default):
            func.l(f"custom_equality = hasattr({self.VNAME}, 'equals')")
        null = ""
        if annotation.optional:
            null = f"{self.VNAME} in {self.resolver.OPTIONALS}"
            if custom_equality:
                null = (
                    f"(any({self.VNAME}.equals(o) for o in {self.resolver.OPTIONALS}) "
                    "if custom_equality "
                    f"else {null})"
                )
        eq = ""
        if (
            annotation.has_default
            and annotation.parameter.default not in self.resolver.OPTIONALS
        ):
            eq = f"{self.VNAME} == __default"
            if custom_equality:
                if hasattr(annotation.parameter.default, "equals"):
                    eq = f"__default.equals({self.VNAME})"
                eq = f"{self.VNAME}.equals(__default) if custom_equality else {eq}"
            _ctx["__default"] = annotation.parameter.default
        if eq or null:
            # Add a type-check for anything that isn't a builtin.
            if eq and not checks.isbuiltintype(annotation.resolved_origin):
                eq = f"{self.VTYPE} is {anno_name} and {eq}"
            check = " or ".join(c for c in (null, eq) if c)
            with func.b(f"if {check}:", **_ctx) as b:  # type: ignore
                b.l(f"return {self.VNAME}")

    @staticmethod
    def _get_name(annotation: Annotation) -> str:
        return get_defname("deserializer", annotation)

    def _build_date_des(self, context: BuildContext):
        func, annotation, anno_name = (
            context.func,
            context.annotation,
            context.anno_name,
        )
        origin = annotation.resolved_origin
        # From an int
        with func.b(f"if isinstance({self.VNAME}, (int, float)):") as b:
            b.l(f"{self.VNAME} = {anno_name}.fromtimestamp({self.VNAME})")
        # From a string
        with func.b(f"elif isinstance({self.VNAME}, (str, bytes)):") as b:
            line = f"{self.VNAME} = dateparse({self.VNAME})"
            b.l(line, dateparse=dateparse)
        if issubclass(origin, datetime.datetime):
            with func.b(
                f"if isinstance({self.VNAME}, datetime):", datetime=datetime.datetime
            ) as b:
                # Use pendulum's helper if possible.
                if origin is DateTime:
                    b.l(f"{self.VNAME} = instance({self.VNAME})", instance=instance)
                else:
                    b.l(
                        f"{self.VNAME} = "
                        f"{anno_name}("
                        f"{self.VNAME}.year, "
                        f"{self.VNAME}.month, "
                        f"{self.VNAME}.day, "
                        f"{self.VNAME}.hour, "
                        f"{self.VNAME}.minute, "
                        f"{self.VNAME}.second, "
                        f"{self.VNAME}.microsecond, "
                        f"{self.VNAME}.tzinfo"
                        f")",
                    )
            with func.b(
                f"elif isinstance({self.VNAME}, date):", date=datetime.date
            ) as b:
                b.l(
                    f"{self.VNAME} = "
                    f"{anno_name}("
                    f"{self.VNAME}.year, "
                    f"{self.VNAME}.month, "
                    f"{self.VNAME}.day"
                    f")",
                )
        elif issubclass(origin, datetime.date):
            with func.b(
                f"if isinstance({self.VNAME}, datetime):", datetime=datetime.datetime
            ) as b:
                b.l(f"{self.VNAME} = {self.VNAME}.date()")
        with func.b(f"elif isinstance({self.VNAME}, (int, float)):") as b:
            b.l(f"{self.VNAME} = {anno_name}.fromtimestamp({self.VNAME})")
        with func.b(f"elif isinstance({self.VNAME}, (str, bytes)):") as b:
            line = f"{self.VNAME} = dateparse({self.VNAME}, exact=True)"
            b.l(line, dateparse=dateparse)

    def _build_time_des(self, context: BuildContext):
        func, anno_name = context.func, context.anno_name
        # From an int
        with func.b(f"if isinstance({self.VNAME}, (int, float)):") as b:
            b.l(f"{self.VNAME} = {anno_name}(int({self.VNAME}))")
        # From a string
        with func.b(f"elif isinstance({self.VNAME}, (str, bytes)):") as b:
            line = f"{self.VNAME} = dateparse({self.VNAME}, exact=True)"
            b.l(line, dateparse=dateparse)
        # From a datetime
        with func.b(
            f"if isinstance({self.VNAME}, datetime):", datetime=datetime.datetime
        ) as b:
            b.l(f"{self.VNAME} = {self.VNAME}.time()")
        # From a date
        with func.b(f"if isinstance({self.VNAME}, date):", date=datetime.date) as b:
            b.l(f"{self.VNAME} = {anno_name}(0)")

    def _build_timedelta_des(self, context: BuildContext):
        func, anno_name = context.func, context.anno_name
        # From an int
        with func.b(f"if isinstance({self.VNAME}, (int, float)):") as b:
            b.l(f"{self.VNAME} = {anno_name}(int({self.VNAME}))")
        # From a string
        with func.b(f"elif isinstance({self.VNAME}, (str, bytes)):") as b:
            line = f"{self.VNAME} = dateparse({self.VNAME}, exact=True)"
            b.l(line, dateparse=dateparse)

    def _build_uuid_des(self, context: BuildContext):
        func, anno_name = context.func, context.anno_name
        self._add_type_check(func, anno_name)
        with func.b(f"if issubclass({self.VTYPE}, UUID):", UUID=uuid.UUID) as b:
            b.l(f"{self.VNAME} = {anno_name}(int={self.VNAME}.int)")

        with func.b(f"elif isinstance({self.VNAME}, str):") as b:
            b.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

        with func.b(f"elif isinstance({self.VNAME}, bytes):") as b:
            b.l(f"{self.VNAME} = {anno_name}(bytes={self.VNAME})")

        with func.b(f"elif isinstance({self.VNAME}, int):") as b:
            b.l(f"{self.VNAME} = {anno_name}(int={self.VNAME})")

        with func.b(f"elif isinstance({self.VNAME}, tuple):") as b:
            b.l(f"{self.VNAME} = {anno_name}(fields={self.VNAME})")

    def _add_eval(self, func: gen.Block):
        func.l(
            f"_, {self.VNAME} = __eval({self.VNAME}) "
            f"if isinstance({self.VNAME}, (str, bytes)) "
            f"else (False, {self.VNAME})",
            __eval=safe_eval,
        )
        self._add_vtype(func)

    def _add_type_check(self, func: gen.Block, anno_name: str):
        with func.b(f"if {self.VTYPE} is {anno_name}:") as b:
            b.l(f"{gen.Keyword.RET} {self.VNAME}")

    def _add_vtype(self, func: gen.Block):
        func.l(f"{self.VTYPE} = {self.VNAME}.__class__")

    def _get_default_factory(self, annotation: "AnnotationT"):
        factory: Union[Type, Callable[..., Any], None] = None
        args: Tuple = annotation.args if isinstance(annotation, Annotation) else tuple()
        if args:
            factory_anno = self.resolver.annotation(args[-1])
            if isinstance(factory_anno, ForwardDelayedAnnotation):
                return factory
            elif isinstance(factory_anno, DelayedAnnotation):
                use = factory_anno.type
                raw = use
            else:
                use = factory_anno.resolved_origin
                raw = factory_anno.un_resolved
            factory = use
            if issubclass(use, defaultdict):
                factory_nested = self._get_default_factory(factory_anno)

                def factory():
                    return defaultdict(factory_nested)

                factory.__qualname__ = f"factory({repr(raw)})"  # type: ignore

            if not checks.isbuiltinsubtype(use):  # type: ignore

                params: Mapping[str, inspect.Parameter] = cached_signature(
                    use
                ).parameters
                if not any(p.default is p.empty for p in params.values()):

                    def factory(*, __origin=use):
                        return __origin()

                    factory.__qualname__ = f"factory({repr(raw)})"  # type: ignore

        return factory

    def _build_text_des(self, context: BuildContext):
        func, annotation, anno_name = (
            context.func,
            context.annotation,
            context.anno_name,
        )
        origin = annotation.resolved_origin
        # Encode for bytes
        if issubclass(origin, bytes):
            with func.b(f"if isinstance({self.VNAME}, str):") as b:
                b.l(
                    f"{self.VNAME} = {anno_name}("
                    f"{self.VNAME}, encoding={DEFAULT_ENCODING!r})"
                )
        # Decode for str
        elif issubclass(origin, str):
            with func.b(f"if isinstance({self.VNAME}, (bytes, bytearray)):") as b:
                b.l(f"{self.VNAME} = {self.VNAME}.decode({DEFAULT_ENCODING!r})")
        func.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

    def _build_builtin_des(self, context: BuildContext):
        func, annotation, anno_name = (
            context.func,
            context.annotation,
            context.anno_name,
        )
        origin = annotation.resolved_origin
        if issubclass(origin, (str, bytes)):
            self._build_text_des(context)
        elif checks.ismappingtype(origin):
            self._build_mapping_des(context)
        elif checks.iscollectiontype(origin):
            self._build_collection_des(context)
        # bool, int, float...
        else:
            func.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

    def _build_pattern_des(self, context: BuildContext):
        func, anno_name = context.func, context.anno_name
        func.l(
            f"{self.VNAME} = {self.VNAME} "
            f"if issubclass({self.VTYPE}, {anno_name}) "
            f"else __re_compile({self.VNAME})",
            __re_compile=re.compile,
        )

    def _build_fromdict_des(self, func: gen.Block, anno_name: str):
        self._add_type_check(func, anno_name)
        func.l(f"{self.VNAME} = {anno_name}.from_dict({self.VNAME})")

    def _build_typeddict_des(self, context: BuildContext):
        func, annotation, namespace, anno_name = (
            context.func,
            context.annotation,
            context.namespace,
            context.anno_name,
        )
        total = getattr(context.annotation.resolved_origin, "__total__", True)
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping) as b:
            fields_deser = {
                x: self.resolver._resolve_from_annotation(
                    y, namespace=namespace
                ).transmute
                for x, y in annotation.serde.fields.items()
            }
            x = "fields_in[x]"
            y = (
                f"fields_deser[x]({self.VNAME}[x])"
                if fields_deser
                else f"{self.VNAME}[x]"
            )
            line = f"{{{x}: {y} for x in fields_in.keys()"
            tail = "}" if total else f"& {self.VNAME}.keys()}}"
            b.l(
                f"{self.VNAME} = {anno_name}(**{line}{tail})", fields_deser=fields_deser
            )
        with func.b("else:") as b:
            b.l(
                f"{self.VNAME} = translate({self.VNAME}, {anno_name})",
                translate=self.resolver.translate,
            )

    def _build_typedtuple_des(self, context: BuildContext):
        func, annotation, anno_name = (
            context.func,
            context.annotation,
            context.anno_name,
        )
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping) as b:
            if annotation.serde.fields:
                ctx = dataclasses.replace(context, func=b)
                self._build_typeddict_des(ctx)
            else:
                b.l(
                    f"{self.VNAME} = {anno_name}(**{self.VNAME})",
                )
        with func.b(
            f"elif isinstance({self.VNAME}, (list, set, frozenset, tuple)):"
        ) as b:
            if annotation.serde.fields:
                b.l(
                    f"{self.VNAME} = __bind({anno_name}, *{self.VNAME}).eval()",
                    __bind=self.resolver.bind,
                )
            else:
                b.l(
                    f"{self.VNAME} = {anno_name}(*{self.VNAME})",
                )
        with func.b("else:") as b:
            b.l(
                f"{self.VNAME} = translate({self.VNAME}, {anno_name})",
                translate=self.resolver.translate,
            )

    def _build_mapping_des(self, context: BuildContext):
        func, annotation, namespace, anno_name = (
            context.func,
            context.annotation,
            context.namespace,
            context.anno_name,
        )
        key_des, item_des = None, None
        args = annotation.args
        if args:
            args = cast(Tuple[Type, Type], args)
            key_type, item_type = args
            key_des = self.resolver.resolve(
                key_type, flags=annotation.serde.flags, namespace=namespace
            )
            item_des = self.resolver.resolve(
                item_type, flags=annotation.serde.flags, namespace=namespace
            )
        if issubclass(annotation.resolved_origin, defaultdict):
            factory = self._get_default_factory(annotation)
            func.namespace[anno_name] = functools.partial(defaultdict, factory)
        kd_name = f"{anno_name}_key_des"
        it_name = f"{anno_name}_item_des"
        iterate = f"iterate({self.VNAME})"
        iterate_values = f"iterate({self.VNAME}, values=True)"
        line = f"{anno_name}({iterate})"
        line_values = f"{anno_name}({iterate_values})"
        if args or annotation.serde.fields_in:
            x, y = "x", "y"
            # If there are args & field mapping, get the correct field name
            # AND serialize the key.
            if args and annotation.serde.fields_in:
                x = f"{kd_name}(fields_in.get(x, x))"
            # If there is only a field mapping, get the correct name for the field.
            elif annotation.serde.fields_in:
                x = "fields_in.get(x, x)"
            # If there are only serializers, get the serialized value
            elif args:
                x = f"{kd_name}(x)"
                y = f"{it_name}(y)"
            line = f"{anno_name}({{{x}: {y} for x, y in {iterate}}})"
            line_values = f"{anno_name}({{{x}: {y} for x, y in {iterate_values}}})"
        # If we don't have nested annotations, we can short-circuit on valid inputs
        else:
            self._add_type_check(func, anno_name)
        # Write the lines.
        with func.b(f"if ismappingtype({self.VTYPE}):") as b:
            b.l(f"{self.VNAME} = {line}")
        with func.b("else:") as ob:
            with ob.b("try:") as b:
                b.l(f"{self.VNAME} = {line_values}")
            with ob.b("except (TypeError, ValueError):") as b:
                b.l(f"{self.VNAME} = {line}")
        func.namespace.update(
            {
                kd_name: key_des,
                it_name: item_des,
                "Mapping": abc.Mapping,
                "iterate": self.resolver.iterate,
                "ismappingtype": ismappingtype,
            }
        )

    def _build_tuple_des(self, context: BuildContext):
        func, annotation, namespace, anno_name = (
            context.func,
            context.annotation,
            context.namespace,
            context.anno_name,
        )
        if annotation.args and annotation.args[-1] is not ...:
            item_des = {
                ix: self.resolver.resolve(
                    t, flags=annotation.serde.flags, namespace=namespace
                )
                for ix, t in enumerate(annotation.args)
            }
            item_des_name = "item_des"
            iterate = f"iterate({self.VNAME}, values=True)"
            line = (
                f"{anno_name}"
                f"({item_des_name}[ix](v) for ix, v in enumerate({iterate})"
                f"if ix in {item_des_name})"
            )
            func.l(
                f"{self.VNAME} = {line}",
                level=None,
                **{
                    item_des_name: item_des,
                    "iterate": self.resolver.iterate,
                },
            )
        else:
            self._build_collection_des(context)

    def _build_collection_des(self, context: BuildContext):
        func, annotation, namespace, anno_name = (
            context.func,
            context.annotation,
            context.namespace,
            context.anno_name,
        )
        item_des = None
        it_name = f"{anno_name}_item_des"
        iterate = f"iterate({self.VNAME}, values=True)"
        line = f"{self.VNAME} = {anno_name}({iterate})"
        if annotation.args:
            item_type = annotation.args[0]
            item_des = self.resolver.resolve(
                item_type, flags=annotation.serde.flags, namespace=namespace
            )
            line = (
                f"{self.VNAME} = "
                f"{anno_name}({it_name}(x) for x in parent({iterate}))"
            )
        else:
            self._add_type_check(func, anno_name)
        func.l(
            line,
            level=None,
            **{
                it_name: item_des,
                "Collection": abc.Collection,
                "iterate": self.resolver.iterate,
            },
        )

    def _build_path_des(self, context: BuildContext):
        func, anno_name = context.func, context.anno_name
        self._add_type_check(func, anno_name)
        func.l(f"{self.VNAME} = {anno_name}({self.VNAME})")

    def _build_user_type_des(self, context: BuildContext):
        func, annotation, namespace, anno_name = (
            context.func,
            context.annotation,
            context.namespace,
            context.anno_name,
        )
        serde = annotation.serde
        resolved = annotation.resolved
        self._add_type_check(func, anno_name)
        # Main branch - we have a mapping for a user-defined class.
        # This is where the serde configuration comes in.
        # WINDY PATH AHEAD
        func.l("# Happy path - deserialize a mapping into the object.")
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping) as b:
            # Universal line - transform input to known keys/values.
            # Specific values may change.
            def mainline(k, v):
                return f"{{{k}: {v} for x in fields_in.keys() & {self.VNAME}.keys()}}"

            # The "happy path" - e.g., no guesswork needed.
            def happypath(k, v, **ns):
                b.l(f"{self.VNAME} = {anno_name}(**{mainline(k, v)})", **ns)

            # Default X - translate given `x` to known input `x`
            x = "fields_in[x]"
            # No field name translation needs to happen.
            if {*serde.fields_in.keys()} == {*serde.fields_in.values()}:
                x = "x"

            # Default Y - get the given `y` with the given `x`
            y = f"{self.VNAME}[x]"
            # Get the intersection of known input fields and annotations.
            matched = {*serde.fields_in.values()} & serde.fields.keys()
            # Happy path! This is a `@typic.al` wrapped class.
            if self.resolver.known(resolved) or self.resolver.delayed(resolved):
                happypath(x, y)
            # Secondary happy path! We know how to deserialize already.
            else:
                fields_in = serde.fields_in
                fnamespace = namespace or resolved
                if serde.fields and len(matched) == len(serde.fields_in):
                    desers = {
                        f: self.resolver._resolve_from_annotation(
                            serde.fields[f], namespace=fnamespace
                        ).transmute
                        for f in matched
                    }
                else:
                    protocols = self.resolver.protocols(annotation.resolved_origin)
                    fields_in = {x: x for x in protocols}
                    desers = {f: p.transmute for f, p in protocols.items()}
                y = f"desers[{x}]({self.VNAME}[x])"
                happypath(x, y, desers=desers, fields_in=fields_in)

        # Secondary branch - we have some other input for a user-defined class
        func.l("# Unknown path, just try casting it directly.")
        with func.b(
            f"elif isbuiltinsubtype({self.VTYPE}):",
            isbuiltinsubtype=checks.isbuiltinsubtype,
        ) as b:
            b.l(f"{self.VNAME} = {anno_name}({self.VNAME})")
        # Final branch - user-defined class for another user-defined class
        func.l(
            "# Two user-defined types, "
            "try to translate the input into the desired output."
        )
        with func.b("else:") as b:
            b.l(
                f"{self.VNAME} = translate({self.VNAME}, {anno_name})",
                translate=self.resolver.translate,
            )

    def _build_literal_des(
        self, annotation: Annotation, func_name: str, namespace: Type = None
    ):
        args = annotation.args
        types: Set[Type] = {a.__class__ for a in args}
        t = types.pop() if len(types) == 1 else Union[tuple(types)]
        t_anno = cast(
            Annotation,
            self.resolver.annotation(
                t,  # type: ignore
                name=annotation.parameter.name,
                # parameter=annotation.parameter,
                is_optional=annotation.optional,
                is_strict=annotation.strict,
                flags=annotation.serde.flags,
                default=annotation.parameter.default,
            ),
        )
        return self._build_des(t_anno, func_name, namespace)

    def _build_union_des(self, context: BuildContext):
        func, annotation, namespace = (
            context.func,
            context.annotation,
            context.namespace,
        )
        # Get all types which we may coerce to.
        args = (*(a for a in annotation.args if a not in {None, Ellipsis, type(None)}),)
        if not args:
            return
        # Add a type-check, but exclude str|bytes, since those are too permissive.
        types = {a for a in args if a not in {str, bytes}}
        if types:
            with func.b(f"if {self.VTYPE} in types:", types=types) as b:
                b.l(f"return {self.VNAME}")
        # Get all custom types, which may have discriminators
        targets = (*(a for a in args if not checks.isstdlibtype(a)),)
        # We can only build a tagged union deserializer if all args are valid
        if args != targets:
            return self._build_generic_union_des(context)

        # Try to collect the field which will be the discriminator.
        # First, get a mapping of Type -> Proto & Type -> Fields
        tagged = get_tag_for_types(targets)
        # Just bail out if we can't find a key.
        if not tagged:
            return self._build_generic_union_des(context)
        # If we got a key, re-map the protocols to the value for each type.
        deserializers = {
            value: self.resolver.resolve(t, namespace=namespace).transmute
            for value, t in tagged.types_by_values
        }
        # Finally, build the deserializer
        func.namespace.update(
            tag=tagged.tag,
            desers=deserializers,
            empty=_empty,
        )
        with func.b(f"if issubclass({self.VTYPE}, Mapping):", Mapping=abc.Mapping) as b:
            b.l(f"tag_value = {self.VNAME}.get(tag, empty)")
        with func.b("else:") as b:
            b.l(f"tag_value = getattr({self.VNAME}, tag, empty)")
        with func.b("if tag_value in desers:") as b:
            b.l(f"{self.VNAME} = desers[tag_value]({self.VNAME})")
        with func.b("else:") as b:
            b.l(
                "raise ValueError("
                'f"Value is missing field {tag!r} with one of '
                '{(*desers,)}: {val!r}"'
                ")"
            )

    def _build_generic_union_des(self, context: BuildContext):
        annotation, namespace, func = (
            context.annotation,
            context.namespace,
            context.func,
        )
        annos = {
            get_name(a): self.resolver.resolve(a, namespace=namespace)
            for a in annotation.args
            if a not in {None, Ellipsis, type(None)}
        }
        if annos:
            desers = {f"{n}_des": p.transmute for n, p in annos.items()}
            types = {n: p.annotation.resolved_origin for n, p in annos.items()}
            ctx: Mapping[str, Union[Type, DeserializerT]] = {**types, **desers}
            for name in annos:
                # Can't do subclass checks with these...
                if name in {"Literal", "Final"}:
                    continue
                with func.b(f"if issubclass({name}, {self.VTYPE}):") as b:
                    b.l(f"return {name}_des({self.VNAME})")
            for name in desers:
                with func.b("try:") as b:
                    b.l(f"return {name}({self.VNAME})")
                with func.b("except (TypeError, ValueError, KeyError):") as b:
                    b.l("pass")
            func.namespace.update(ctx)
            func.l(
                "raise ValueError("
                f'f"Value could not be deserialized into one of {(*annos,)}: {{val!r}}"'
                ")",
            )
            return False

    def _build_des(  # noqa: C901
        self,
        annotation: Annotation[Type[ObjectT]],
        func_name: str,
        namespace: Type = None,
    ) -> DeserializerT[ObjectT]:
        args = annotation.args
        # Get the "origin" of the annotation.
        # For natives and their typing.* equivs, this will be a builtin type.
        # For SpecialForms (Union, mainly) this will be the un-subscripted type.
        # For custom types or classes, this will be the same as the annotation.
        origin = annotation.resolved_origin
        anno_name = get_unique_name(origin)
        ns = {
            anno_name: origin,
            "parent": getattr(origin, "__parent__", origin),
            "issubclass": cached_issubclass,
            **annotation.serde.asdict(),
        }
        if checks.isliteral(origin):
            return self._build_literal_des(annotation, func_name, namespace)
        with gen.Block(ns) as main:
            with main.f(func_name, main.param(f"{self.VNAME}")) as func:
                needs_return = None
                context = BuildContext(annotation, ns, anno_name, func, namespace)
                if origin not in self.UNRESOLVABLE:
                    # Set our top-level sanity checks.
                    self._set_checks(func, anno_name, annotation)
                    # Move through our queue.
                    for check, handler in self._HANDLERS.items():
                        # If this is a valid type for this handler,
                        #   write the deserializer.
                        if check(origin, args):
                            needs_return = handler(self, context)
                            break
                # If the deserializer doesn't contain a return statement, add one.
                if needs_return is not False:
                    func.l(f"{gen.Keyword.RET} {self.VNAME}")
        deserializer = main.compile(ns=ns, name=func_name)
        return deserializer

    # Order is IMPORTANT! This is a FIFO queue.
    _HANDLERS: Mapping[HandlerCheckT, BuildHandlerT] = {
        # Special handler for Unions...
        lambda origin, args: checks.isuniontype(origin): _build_union_des,
        # Non-intersecting types (order doesn't matter here.
        lambda origin, args: checks.isdatetype(origin): _build_date_des,
        lambda origin, args: checks.istimetype(origin): _build_time_des,
        lambda origin, args: checks.istimedeltatype(origin): _build_timedelta_des,
        lambda origin, args: checks.isuuidtype(origin): _build_uuid_des,
        lambda origin, args: origin in {Pattern, re.Pattern}: _build_pattern_des,
        lambda origin, args: issubclass(origin, pathlib.Path): _build_path_des,
        # MUST come before subtype check.
        lambda origin, args: (
            not args and checks.isbuiltintype(origin)
        ): _build_builtin_des,
        # Psuedo-structured containers, should check before generics.
        lambda origin, args: checks.istypeddict(origin): _build_typeddict_des,
        lambda origin, args: checks.istypedtuple(origin): _build_typedtuple_des,
        lambda origin, args: checks.isnamedtuple(origin): _build_typedtuple_des,
        lambda origin, args: (
            not args and checks.isbuiltinsubtype(origin)
        ): _build_builtin_des,
        # A mapping is a collection so must come before that check.
        lambda origin, args: checks.ismappingtype(origin): _build_mapping_des,
        # A tuple is a collection so must come before that check.
        lambda origin, args: checks.istupletype(origin): _build_tuple_des,
        # Generic collection handler
        lambda origin, args: checks.iscollectiontype(origin): _build_collection_des,
        # Catch-all for custom user types (user-defined classes).
        lambda origin, args: True: _build_user_type_des,
    }

    def factory(
        self,
        annotation: Annotation[Type[ObjectT]],
        namespace: Type = None,
    ) -> DeserializerT[ObjectT]:
        annotation.serde = annotation.serde or SerdeConfig()
        key = self._get_name(annotation)
        if key in self.__DES_CACHE:
            return self.__DES_CACHE[key]
        deserializer: Optional[DeserializerT] = None
        for check, des in self.__USER_DESS:
            if check(annotation.resolved):
                deserializer = des
                break
        if not deserializer:
            deserializer = self._build_des(annotation, key, namespace)
        self.__DES_CACHE[key] = deserializer
        return deserializer


@slotted(dict=False, weakref=True)
@dataclasses.dataclass
class BuildContext:
    annotation: Annotation
    ns: Mapping[str, Any]
    anno_name: str
    func: gen.Block
    namespace: Optional[Type] = None


HandlerCheckT = Callable[[Type[ObjectT], Tuple[Any, ...]], TypeGuard[Type[ObjectT]]]
BuildHandlerT = Callable[[DesFactory, BuildContext], Union[NoReturn, Literal[False]]]
