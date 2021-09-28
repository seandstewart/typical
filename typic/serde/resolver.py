from __future__ import annotations

import dataclasses
import functools
import inspect
import warnings
from enum import Enum
from operator import attrgetter, methodcaller
from typing import (
    Mapping,
    Any,
    Type,
    Optional,
    ClassVar,
    Tuple,
    cast,
    Union,
    TypeVar,
    Iterator,
    Dict,
    Iterable,
)

from typic import checks, constraints as constr, util, strict as st
from typic.common import (
    EMPTY,
    ORIG_SETTER_NAME,
    SERDE_FLAGS_ATTR,
    TYPIC_ANNOS_NAME,
    ObjectT,
    Case,
    ReadOnly,
)
from typic.compat import lru_cache
from typic.ext import json
from typic.strict import StrictModeT
from .binder import Binder
from .common import (
    SerializerT,
    SerdeFlags,
    SerdeConfig,
    Annotation,
    SerdeProtocol,
    SerdeProtocolsT,
    DelayedSerdeProtocol,
    ForwardDelayedAnnotation,
    DelayedAnnotation,
    DeserializerT,
    EncoderT,
    DecoderT,
    TranslatorT,
    PrimitiveT,
    FieldIteratorT,
)
from .des import DesFactory
from .ser import SerFactory
from .translator import TranslatorFactory

_T = TypeVar("_T")


class Resolver:
    """A type serializer/deserializer resolver."""

    STRICT = st.STRICT_MODE
    _DICT_FACTORY_METHODS = frozenset(
        {("asdict", methodcaller("asdict")), ("to_dict", methodcaller("to_dict"))}
    )
    _DYNAMIC = SerFactory._DYNAMIC
    OPTIONALS = (None, ...)
    LITERALS = (int, bytes, str, bool, Enum, type(None))

    def __init__(self):
        self.des = DesFactory(self)
        self.ser = SerFactory(self)
        self.binder = Binder(self)
        self.translator = TranslatorFactory(self)
        self.bind = self.binder.bind
        self.__cache = {}
        self.__stack = set()
        for typ in checks.STDLIB_TYPES:
            self.resolve(typ)
            self.resolve(Optional[typ])
            self.resolve(typ, is_optional=True)
            try:
                self.translator.iterator(typ)
                self.translator.iterator(typ, values=True)
            except TypeError:
                pass

    def transmute(self, annotation: Type[ObjectT], value: Any) -> ObjectT:
        """Convert a given value `into` the target annotation.

        Checks for:
            - :class:`datetime.date`
            - :class:`datetime.datetime`
            - builtin types
            - extended type annotations as described in the ``typing`` module.
            - User-defined classes (limited)

        Parameters
        ----------
        annotation :
            The provided annotation for determining the coercion
        value :
            The value to be transmuted
        """
        resolved: SerdeProtocol = self.resolve(annotation)
        transmuted: ObjectT = resolved.transmute(value)

        return transmuted

    def translate(self, value: ObjectT, target: Type[_T]) -> _T:
        """Translate an instance `from` its type `to` a target type.

        Notes
        -----
        This provides a functional interface for translating one custom class
        instance to another custom class. This should not be confused with
        :py:func:`typic.transmute`, which is generally a more powerful functional
        interface for conversion between types, but this is provided as for
        api-completeness with the object-api.

        Parameters
        ----------
        value
            The higher-order class instance to translate.
        target
            The higher-order class to translate into.
        """
        t = value.__class__
        resolved: SerdeProtocol = self.resolve(t)
        return resolved.translate(value, target)

    def validate(
        self, annotation: Type[ObjectT], value: Any, *, transmute: bool = False
    ) -> Union[ObjectT, Any]:
        """Validate an input against the type-constraints for the given annotation.

        Parameters
        ----------
        annotation
            The type or annotation to validate against
        value
            The value to check
        transmute: (kw-only)
            Whether to transmute the value to the annotation after validation
        """
        resolved: SerdeProtocol = self.resolve(annotation)
        value = resolved.validate(value)
        if transmute:
            return resolved.transmute(value)
        return value

    def iterate(
        self, obj, *, values: bool = False, exclude: Iterable[str] = ()
    ) -> Iterator[Union[Tuple[str, Any], Any]]:
        """Iterate over the fields of an object.

        Parameters
        ----------
        obj
            The object to iterate over
        values
            Whether to only yield values of an object's fields. (defaults False)
        exclude
            Proactively ignore any fields on the object
        """
        t = obj.__class__
        # Extract the type of the enum value if this is an Enum.
        # Enums classes are iterable and will generate the wrong kind of iterator.
        if checks.isenumtype(t):
            obj = obj.value
            t = obj.__class__
        iterator = self.translator.iterator(t, values=values, exclude=(*exclude,))
        return iterator(obj)

    def coerce_value(
        self, value: Any, annotation: Type[ObjectT]
    ) -> ObjectT:  # pragma: nocover
        warnings.warn(
            "'typic.coerce' has been deprecated and will be removed in a future "
            "version. Use 'typic.transmute' instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return self.transmute(annotation, value)

    def known(self, t: Type) -> bool:
        return hasattr(t, ORIG_SETTER_NAME) or hasattr(t, "__delayed__")

    def delayed(self, t: Type) -> bool:
        return getattr(t, "__delayed__", False)

    def primitive(
        self,
        obj: ObjectT,
        *,
        lazy: bool = False,
        name: util.ReprT = None,
        flags: SerdeFlags = None,
    ) -> PrimitiveT:
        """A method for converting an object to its primitive equivalent.

        Useful for encoding data to JSON.

        Examples
        --------
        >>> import typic
        >>> import datetime
        >>> import uuid
        >>> import ipaddress
        >>> import re
        >>> import dataclasses
        >>> typic.primitive("foo")
        'foo'
        >>> typic.primitive(("foo",))  # containers are converted to lists/dicts
        ['foo']
        >>> typic.primitive(datetime.datetime(1970, 1, 1))
        '1970-01-01T00:00:00'
        >>> typic.primitive(b"foo")
        'foo'
        >>> typic.primitive(ipaddress.IPv4Address("0.0.0.0"))
        '0.0.0.0'
        >>> typic.primitive(re.compile("[0-9]"))
        '[0-9]'
        >>> typic.primitive(uuid.UUID(int=0))
        '00000000-0000-0000-0000-000000000000'
        >>> @dataclasses.dataclass
        ... class Foo:
        ...     bar: str = 'bar'
        ...
        >>> typic.primitive(Foo())
        {'bar': 'bar'}
        """
        t = obj.__class__
        if checks.isenumtype(t):
            obj = obj.value  # type: ignore
            t = obj.__class__
        proto: SerdeProtocol = self.resolve(t, flags=flags)
        return proto.primitive(obj, lazy=lazy, name=name)  # type: ignore

    def tojson(
        self, obj: ObjectT, *, indent: int = 0, ensure_ascii: bool = False, **kwargs
    ) -> str:
        """A method for dumping any object to a valid JSON string.

        Notes
        -----
        If `ujson` is installed, we will default to that library for the final
        encoding, which can result in massive performance gains over the standard `json`
        library.

        Examples
        --------
        >>> import typic
        >>> import datetime
        >>> import uuid
        >>> import ipaddress
        >>> import re
        >>> import dataclasses
        >>> import enum
        >>> typic.tojson("foo")
        b'"foo"'
        >>> typic.tojson(("foo",))
        b'["foo"]'
        >>> typic.tojson(datetime.datetime(1970, 1, 1))
        b'"1970-01-01T00:00:00"'
        >>> typic.tojson(b"foo")
        b'"foo"'
        >>> typic.tojson(ipaddress.IPv4Address("0.0.0.0"))
        b'"0.0.0.0"'
        >>> typic.tojson(uuid.UUID(int=0))
        b'"00000000-0000-0000-0000-000000000000"'
        """
        t = obj.__class__
        if checks.isenumtype(t):
            obj = obj.value  # type: ignore
            t = obj.__class__
        proto: SerdeProtocol = self.resolve(t)
        return proto.tojson(obj, indent=indent, ensure_ascii=ensure_ascii, **kwargs)

    def decode(
        self, annotation: Type[ObjectT], value: Any, decoder: DecoderT[bytes], **kwargs
    ) -> ObjectT:
        proto: SerdeProtocol = self.resolve(annotation)
        return proto.transmute(decoder(value, **kwargs))  # type: ignore

    def encode(self, obj: Any, encoder: EncoderT[PrimitiveT], **kwargs) -> bytes:
        t = obj.__class__
        if checks.isenumtype(t):
            obj = obj.value
            t = obj.__class__
        proto: SerdeProtocol = self.resolve(t)
        return encoder(proto.primitive(obj), **kwargs)  # type: ignore

    @lru_cache(maxsize=None)
    def _get_configuration(self, origin: Type, flags: SerdeFlags) -> SerdeConfig:
        if hasattr(origin, SERDE_FLAGS_ATTR):
            flags = getattr(origin, SERDE_FLAGS_ATTR)
        # Get all the annotated fields
        params = util.safe_get_params(origin)
        # This is probably a builtin and has no signature
        fields: Dict[str, Annotation] = {}
        hints = util.cached_type_hints(origin)
        for name, t in hints.items():
            fields[name] = self.annotation(
                t,
                flags=dataclasses.replace(flags, fields={}),
                default=getattr(origin, name, EMPTY),
                namespace=origin,
            )

        # Filter out any annotations which aren't part of the object's signature.
        if flags.signature_only:
            fields = {x: fields[x] for x in fields.keys() & params.keys()}
        # Create a field-to-field mapping
        fields_out = {x: x for x in fields}
        # Make sure to include any fields explicitly listed
        include = flags.fields
        if include:
            if isinstance(include, Mapping):
                fields_out.update(include)
            else:
                fields_out.update({x: x for x in include})
        # Transform the output fields to the correct case.
        if flags.case:
            case = Case(flags.case)
            fields_out = {x: case.transformer(y) for x, y in fields_out.items()}
        omit = flags.omit
        # Omit fields with explicitly omitted types & flag values to omit at dump
        value_omissions: Tuple[Any, ...] = ()
        if omit:
            type_omissions = {
                o for o in omit if checks._type_check(o) or o is NotImplemented
            }
            type_name_omissions = {util.get_name(o) for o in type_omissions}
            value_omissions = (*(o for o in omit if o not in type_omissions),)
            fields_out_final = {}
            anno: Union[Annotation, DelayedAnnotation, ForwardDelayedAnnotation]
            for name, out in fields_out.items():
                anno = fields[name]
                default = anno.parameter.default if anno.parameter else EMPTY
                if isinstance(anno, ForwardDelayedAnnotation):
                    if (
                        not {util.get_name(anno.ref), util.get_name(default)}
                        & type_name_omissions
                    ):
                        fields_out_final[name] = out
                elif not {anno.origin, default} & type_omissions:
                    fields_out_final[name] = out
            fields_out = fields_out_final

        fields_in = {y: x for x, y in fields_out.items()}
        if params:
            fields_in = {x: y for x, y in fields_in.items() if y in params}
        exclude = flags.exclude
        if exclude:
            fields_out = {x: y for x, y in fields_out.items() if x not in exclude}
        fields_getters = {x: attrgetter(x) for x in fields}
        return SerdeConfig(
            flags=flags,
            fields=fields,
            fields_out=fields_out,
            fields_in=fields_in,
            fields_getters=fields_getters,
            omit_values=value_omissions,
            encoder=flags.encoder,
            decoder=flags.decoder,
        )

    def annotation(
        self,
        annotation: Type[ObjectT],
        name: str = None,
        parameter: Optional[inspect.Parameter] = None,
        is_optional: bool = None,
        is_strict: StrictModeT = None,
        flags: "SerdeFlags" = None,
        default: Any = EMPTY,
        namespace: Type = None,
    ) -> Annotation[Type[ObjectT]]:
        """Get a :py:class:`Annotation` for this type.

        Unlike a :py:class:`ResolvedAnnotation`, this does not provide access to a
        serializer/deserializer/validator protocol.
        """
        flags = cast(
            "SerdeFlags", getattr(annotation, SERDE_FLAGS_ATTR, flags or SerdeFlags())
        )
        if parameter is None:
            parameter = inspect.Parameter(
                name or "_",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=annotation,
                default=default if checks.ishashable(default) else ...,
            )
        # Check for the super-type
        non_super = util.resolve_supertype(annotation)
        # Note, this may be a generic, like Union.
        orig = util.origin(annotation)
        use = non_super
        # Get the unfiltered args
        args = getattr(non_super, "__args__", None)
        # Set whether this is optional/strict
        is_optional = (
            is_optional
            or checks.isoptionaltype(non_super)
            or parameter.default in self.OPTIONALS
        )
        is_strict = is_strict or checks.isstrict(non_super) or self.STRICT
        is_static = util.origin(use) not in self._DYNAMIC
        is_literal = checks.isliteral(use)
        # Determine whether we should use the first arg of the annotation
        while checks.should_unwrap(use) and args:
            is_optional = is_optional or checks.isoptionaltype(use)
            is_strict = is_strict or checks.isstrict(use)
            if is_optional and len(args) > 2:
                # We can't resolve this annotation.
                is_static = False
                use = Union[args[:-1]]
                break
            # Note that we don't re-assign `orig`.
            # This is intentional.
            # Special forms are needed for building the downstream validator.
            # Callers should be aware of this and perhaps use `util.origin` elsewhere.
            non_super = util.resolve_supertype(args[0])
            use = non_super
            args = util.get_args(use)
            is_static = util.origin(use) not in self._DYNAMIC
            is_literal = is_literal or checks.isliteral(use)

        # Only allow legal parameters at runtime, this has implementation implications.
        if is_literal:
            args = util.get_args(use)
            if any(not isinstance(a, self.LITERALS) for a in args):
                raise TypeError(
                    f"PEP 586: Unsupported parameters for 'Literal' type: {args}. "
                    "See https://www.python.org/dev/peps/pep-0586/"
                    "#legal-parameters-for-literal-at-type-check-time "
                    "for more information."
                )
        # The type definition doesn't exist yet.
        if checks.isforwardref(use):
            module = self.__module__
            # Ideally we have a namespace from a parent class/function to the field
            if namespace:
                module = namespace.__module__

            fda = ForwardDelayedAnnotation(
                ref=use,
                resolver=self,
                _name=name,
                parameter=parameter,
                is_optional=is_optional,
                is_strict=is_strict,
                flags=flags,
                default=default,
                module=module,
                frame=inspect.currentframe(),
            )
            return cast(Annotation, fda)
        # The type definition is recursive or within a recursive loop.
        elif use is namespace or use in self.__stack:
            # If detected via stack, we can remove it now.
            # Otherwise we'll cause another recursive loop.
            if use in self.__stack:
                self.__stack.remove(use)
            da = DelayedAnnotation(
                type=use,
                resolver=self,
                _name=name,
                parameter=parameter,
                is_optional=is_optional,
                is_strict=is_strict,
                flags=flags,
                default=default,
            )
            return cast(Annotation, da)
        # Otherwise, add this type to the stack to prevent a recursive loop from elsewhere.
        if not checks.isstdlibtype(use):
            self.__stack.add(use)
        serde = (
            self._get_configuration(util.origin(use), flags)
            if is_static and not is_literal
            else SerdeConfig(flags)
        )

        anno: Annotation = Annotation(
            resolved=use,
            origin=orig,
            un_resolved=annotation,
            parameter=parameter,
            optional=is_optional,
            strict=is_strict,
            static=is_static,
            serde=serde,
        )
        anno.translator = cast(
            TranslatorT, functools.partial(self.translator.factory, anno)
        )
        return anno

    @staticmethod
    def _finalize_deserializer(
        annotation: Annotation[Type[ObjectT]],
        deserializer: DeserializerT[ObjectT],
        constraints: constr.ConstraintsProtocolT[ObjectT],
    ) -> Tuple[DeserializerT[ObjectT], constr.ValidateT[ObjectT]]:
        # Set the default returns.
        validator = constraints.validate
        rdeserializer = deserializer
        # If we're in "strict" mode, we want to default to only validation.
        if annotation.strict or checks.isabstract(annotation.resolved_origin):
            rdeserializer = cast(DeserializerT[ObjectT], validator)

        # If we have type constraints, we'll bail out early.
        # If we have literal constraints, we must validate as a part of coercion.
        if isinstance(constraints, (constr.TypeConstraints, constr.LiteralConstraints)):
            if isinstance(constraints, constr.LiteralConstraints):
                d = deserializer

                def des(val: Any, *, __d=d, __v=validator) -> ObjectT:
                    return __v(__d(val))

                rdeserializer = cast(DeserializerT[ObjectT], des)

            return rdeserializer, validator
        # Finally, if we're in "strict" mode, but the constraint needs validation prior
        #   to coercion, we should inject the validator within the deserializer.
        if annotation.strict and constraints.coerce:
            d = deserializer

            def des(val: Any, *, __d=d, __v=validator) -> ObjectT:
                return __d(__v(val))

            rdeserializer = cast(DeserializerT[ObjectT], des)

        return rdeserializer, validator

    def _resolve_from_annotation(
        self,
        anno: Annotation[Type[ObjectT]],
        *,
        namespace: Type = None,
    ) -> SerdeProtocol[ObjectT]:
        if anno in self.__cache:
            return self.__cache[anno]
        if isinstance(anno, (DelayedAnnotation, ForwardDelayedAnnotation)):
            return DelayedSerdeProtocol(anno)

        # Build the deserializer
        constraints = constr.get_constraints(
            anno.resolved, nullable=anno.optional, cls=namespace
        )
        deserializer = self.des.factory(anno, namespace=namespace)
        deserializer, validator = self._finalize_deserializer(
            annotation=anno, deserializer=deserializer, constraints=constraints
        )
        # Build the serializer
        serializer = self.ser.factory(anno)
        # Put it all together
        proto = self._build_protocol(
            annotation=anno,
            constraints=constraints,
            deserializer=deserializer,
            validator=validator,
            serializer=serializer,
        )
        self.__cache[anno] = proto
        return proto

    def _build_protocol(
        self,
        *,
        annotation: Annotation[Type[ObjectT]],
        constraints: constr.ConstraintsProtocolT[ObjectT],
        deserializer: DeserializerT[ObjectT],
        validator: constr.ValidateT[ObjectT],
        serializer: SerializerT[ObjectT],
    ) -> SerdeProtocol[ObjectT]:
        tojson = json.get_tojson(serializer)
        tojson.__qualname__ = f"{SerdeProtocol.__name__}.{tojson.__name__}"
        tojson.__module__ = SerdeProtocol.__module__

        # Set the encoder/decoder protocols.
        # Default to JSON for wire-format
        encode: EncoderT = cast(EncoderT, tojson)
        if annotation.serde.encoder:

            def encode(  # type: ignore
                val: ObjectT,
                *,
                __prim=serializer,
                __encode=annotation.serde.encoder,
                **kwargs,
            ) -> bytes:
                return __encode(__prim(val), **kwargs)

            encode.__qualname__ = f"{SerdeProtocol.__name__}.{encode.__name__}"
            encode.__module__ = self.__class__.__module__

        # Default to JSON for wire-format
        decode: DecoderT = cast(DecoderT, deserializer)
        if annotation.serde.decoder:

            def decode(  # type: ignore
                val: bytes,
                *,
                __trans=deserializer,
                __decode=annotation.serde.decoder,
                **kwargs,
            ) -> ObjectT:
                return __trans(__decode(val, **kwargs))

            decode.__qualname__ = f"{SerdeProtocol.__name__}.{decode.__name__}"
            decode.__module__ = SerdeProtocol.__module__

        # Create the translator
        def translate(
            value: ObjectT, target: Type[_T], *, __factory=annotation.translator
        ) -> _T:
            trans = __factory(target)
            return trans(value)

        translate.__qualname__ = f"{SerdeProtocol.__name__}.{translate.__name__}"
        translate.__module__ = SerdeProtocol.__module__

        # Create the iterator, if possible.
        try:
            iterator = self._iterator_from_annotation(annotation)
            iterator.__qualname__ = f"{SerdeProtocol.__name__}.{iterator.__name__}"
            iterator.__module__ = SerdeProtocol.__module__
        # Default to lazy iteration, if not.
        except TypeError:
            iterator = cast(FieldIteratorT, self.iterate)

        return SerdeProtocol(
            annotation=annotation,
            constraints=constraints,
            deserialize=deserializer,
            decode=decode,
            serialize=serializer,
            encode=encode,
            validate=validator,
            translate=cast(TranslatorT, translate),
            tojson=cast(EncoderT, tojson),
            iterate=iterator,
        )

    def _iterator_from_annotation(
        self, annotation: Annotation[Type[ObjectT]]
    ) -> FieldIteratorT[ObjectT]:
        exclude = (*(annotation.serde.flags.exclude or ()),)
        fiterator = self.translator.iterator(
            annotation.resolved_origin, relaxed=True, exclude=exclude
        )
        viterator = self.translator.iterator(
            annotation.resolved_origin,
            values=True,
            relaxed=True,
            exclude=exclude,
        )

        def iterator(
            o: ObjectT, *, values: bool = False, __fields=fiterator, __values=viterator
        ) -> Iterator[Union[Tuple[str, Any], Any]]:
            if values:
                return __values(o)
            return __fields(o)

        return cast(FieldIteratorT, iterator)

    @lru_cache(maxsize=None)
    def resolve(
        self,
        annotation: Type[ObjectT],
        *,
        flags: SerdeFlags = None,
        name: str = None,
        parameter: Optional[inspect.Parameter] = None,
        is_optional: bool = None,
        is_strict: bool = None,
        namespace: Type = None,
    ) -> SerdeProtocol[ObjectT]:
        """Get a :py:class:`SerdeProtocol` from a given annotation or type.

        Parameters
        ----------
        annotation
            The class or callable object you wish to extract resolved annotations from.

        Other Parameters
        ----------------
        flags : (optional)
            An instance of :py:class:`SerdeFlags`
        name : (optional)
            An name, such as an attribute or parameter name.
        parameter: (optional)
            The parameter associated to this annotation, if any.
        is_optional: (optional)
            Whether to allow null values.
        is_strict: (optional)
            Whether to apply strict validation to any input for this annotation.

        Examples
        --------
        >>> import typic
        >>>
        >>> @typic.klass
        ... class Foo:
        ...     bar: str
        ...
        >>> protocol = typic.protocol(Foo)

        See Also
        --------
        :py:class:`SerdeProtocol`
        """
        # Extract the meta-data.
        anno = self.annotation(
            annotation=annotation,
            name=name,
            parameter=parameter,
            is_optional=is_optional,
            is_strict=is_strict,
            flags=flags,
            namespace=namespace,
        )
        resolved = self._resolve_from_annotation(anno, namespace=namespace)
        self.__stack.clear()
        return resolved

    @lru_cache(maxsize=None)
    def protocols(self, obj, *, strict: bool = False) -> SerdeProtocolsT:
        """Get a mapping of param/attr name -> :py:class:`SerdeProtocol`

        Parameters
        ----------
        obj
            The class or callable object you wish to extract resolved annotations from.
        strict
            Whether to validate instead of coerce.

        Examples
        --------
        >>> import typic
        >>>
        >>> @typic.klass
        ... class Foo:
        ...     bar: str
        ...
        >>> protocols = typic.protocols(Foo)

        See Also
        --------
        :py:class:`SerdeProtocol`
        """

        if not callable(obj):
            obj = obj.__class__

        hints = util.cached_type_hints(obj)
        params = util.safe_get_params(obj)
        fields: Mapping[str, dataclasses.Field] = {}
        if dataclasses.is_dataclass(obj):
            fields = {f.name: f for f in dataclasses.fields(obj)}
        ann = {}
        for name in params.keys() | hints.keys():
            param = params.get(name)
            hint = hints.get(name)
            field = fields.get(name)
            annotation = hint or param.annotation  # type: ignore
            annotation = util.resolve_supertype(annotation)
            param = param or inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=EMPTY,
                annotation=hint or annotation,
            )
            if repr(param.default) == "<factory>":
                param = param.replace(default=EMPTY)
            if checks.isclassvartype(annotation):
                val = getattr(obj, name)
                if annotation is ClassVar:
                    annotation = annotation[type(val)]
                default = val
                param = param.replace(default=default)
            if (
                field
                and field.default is not dataclasses.MISSING
                and param.default is EMPTY
            ):
                if field.init is False and util.origin(annotation) is not ReadOnly:
                    annotation = ReadOnly[annotation]  # type: ignore
                param = param.replace(default=field.default)

            if not checks.ishashable(param.default):
                param = param.replace(default=...)

            resolved = self.resolve(
                annotation, name=name, parameter=param, is_strict=strict, namespace=obj
            )
            ann[name] = resolved
        try:
            setattr(obj, TYPIC_ANNOS_NAME, ann)
        # We wrapped a bound method, or
        # are wrapping a static-/classmethod
        # after they were wrapped with @static/class
        except (AttributeError, TypeError):
            pass

        return ann


resolver = Resolver()
