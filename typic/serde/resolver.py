import dataclasses
import functools
import inspect
import warnings
from collections.abc import Callable
from operator import attrgetter, methodcaller
from typing import (
    Mapping,
    Any,
    Type,
    Optional,
    ClassVar,
    Tuple,
    Iterable,
    cast,
    Union,
    TypeVar,
    Iterator,
)

from typic import checks, constraints as const, util, strict as st
from typic.common import (
    EMPTY,
    ORIG_SETTER_NAME,
    SERDE_ATTR,
    SERDE_FLAGS_ATTR,
    TYPIC_ANNOS_NAME,
    ObjectT,
    Case,
    ReadOnly,
)
from typic.strict import StrictModeT
from .binder import Binder
from .common import (
    SerializerT,
    SerdeFlags,
    SerdeConfig,
    Annotation,
    SerdeProtocol,
    SerdeProtocolsT,
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

    def __init__(self):
        self.des = DesFactory(self)
        self.ser = SerFactory(self)
        self.binder = Binder(self)
        self.translator = TranslatorFactory(self)
        self.bind = self.binder.bind
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
        transmuted: ObjectT = resolved.transmute(value)  # type: ignore

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
        resolved: SerdeProtocol = self.resolve(type(value))
        return resolved.translate(value, target)  # type: ignore

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
            return resolved.transmute(value)  # type: ignore
        return value

    def iterate(
        self, obj, *, values: bool = False
    ) -> Iterator[Union[Tuple[str, Any], Any]]:
        """Iterate over the fields of an object.

        Parameters
        ----------
        obj
            The object to iterate over
        values
            Whether to only yield values of an object's fields. (defaults False)
        """
        t = obj.__class__
        # Extract the type of the enum value if this is an Enum.
        # Enums classes are iterable and will generate the wrong kind of iterator.
        if checks.isenumtype(t):
            obj = obj.value
            t = obj.__class__
        iterator = self.translator.iterator(t, values=values)
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

    @functools.lru_cache(maxsize=None)
    def _get_serializer_proto(self, t: Type) -> SerdeProtocol:
        tname = util.get_name(t)
        if hasattr(t, SERDE_ATTR):
            return getattr(t, SERDE_ATTR)
        for attr, caller in self._DICT_FACTORY_METHODS:
            if hasattr(t, attr):

                def serializer(
                    val,
                    lazy: bool = False,
                    name: util.ReprT = None,
                    *,
                    __prim=self.primitive,
                    __call=caller,
                    __tname=tname,
                    __repr=util.joinedrepr,
                ):
                    name = name or __tname
                    return {
                        __prim(x): __prim(y, lazy=lazy, name=__repr(name, x))
                        for x, y in __call(val).items()
                    }

                return SerdeProtocol(
                    self.annotation(t),
                    deserializer=None,
                    serializer=serializer,
                    constraints=None,
                    validator=None,
                )

        if checks.ismappingtype(t):
            t = Mapping[Any, Any]
        elif checks.iscollectiontype(t) and not issubclass(t, (str, bytes, bytearray)):
            t = Iterable[Any]
        settings = getattr(t, SERDE_FLAGS_ATTR, None)
        serde: SerdeProtocol = self.resolve(t, flags=settings, _des=False)
        return serde

    def primitive(self, obj: Any, lazy: bool = False, name: util.ReprT = None) -> Any:
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
        >>> typic.primitive(datetime.datetime(1970, 1, 1))  # note that we assume UTC
        '1970-01-01T00:00:00+00:00'
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
            obj = obj.value
            t = obj.__class__
        proto: SerdeProtocol = self._get_serializer_proto(t)
        return proto.primitive(obj, lazy=lazy, name=name)  # type: ignore

    def tojson(
        self, obj: Any, *, indent: int = 0, ensure_ascii: bool = False, **kwargs
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
        '"foo"'
        >>> typic.tojson(("foo",))
        '["foo"]'
        >>> typic.tojson(datetime.datetime(1970, 1, 1))  # note that we assume UTC
        '"1970-01-01T00:00:00+00:00"'
        >>> typic.tojson(b"foo")
        '"foo"'
        >>> typic.tojson(ipaddress.IPv4Address("0.0.0.0"))
        '"0.0.0.0"'
        >>> typic.tojson(re.compile("[0-9]"))
        '"[0-9]"'
        >>> typic.tojson(uuid.UUID(int=0))
        '"00000000-0000-0000-0000-000000000000"'
        >>> @dataclasses.dataclass
        ... class Foo:
        ...     bar: str = 'bar'
        ...
        >>> typic.tojson(Foo())
        '{"bar":"bar"}'
        >>> class Enum(enum.Enum):
        ...     FOO = "foo"
        ...
        >>> typic.tojson(Enum.FOO)
        '"foo"'
        """
        t = obj.__class__
        if checks.isenumtype(t):
            obj = obj.value
            t = obj.__class__
        proto: SerdeProtocol = self._get_serializer_proto(t)
        return proto.tojson(obj, indent=indent, ensure_ascii=ensure_ascii, **kwargs)

    @functools.lru_cache(maxsize=None)
    def _get_configuration(self, origin: Type, flags: "SerdeFlags") -> "SerdeConfig":
        if hasattr(origin, SERDE_FLAGS_ATTR):
            flags = getattr(origin, SERDE_FLAGS_ATTR)
        # Get all the annotated fields
        params = util.safe_get_params(origin)
        # This is probably a builtin and has no signature
        fields: Mapping[str, Annotation] = {
            x: self.annotation(
                y,
                flags=dataclasses.replace(flags, fields={}),
                default=getattr(origin, x, EMPTY),
            )
            for x, y in util.cached_type_hints(origin).items()
        }
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
            value_omissions = (*(o for o in omit if o not in type_omissions),)
            fields_out = {
                x: y
                for x, y in fields_out.items()
                if not {fields[x].origin, fields[x].parameter.default} & type_omissions
            }
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
    ) -> Annotation:
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
                default=default,
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
        # Determine whether we should use the first arg of the annotation
        while checks.should_unwrap(use) and args:
            is_optional = is_optional or checks.isoptionaltype(use)
            is_strict = is_strict or checks.isstrict(use)
            if is_optional and len(args) > 2:
                # We can't resolve this annotation.
                is_static = False
                break
            # Note that we don't re-assign `orig`.
            # This is intentional.
            # Special forms are needed for building the downstream validator.
            # Callers should be aware of this and perhaps use `util.origin` elsewhere.
            non_super = util.resolve_supertype(args[0])
            use = non_super
            args = util.get_args(use)
            is_static = util.origin(use) not in self._DYNAMIC

        serde = (
            self._get_configuration(util.origin(use), flags)
            if is_static
            else SerdeConfig(flags)
        )

        anno = Annotation(
            resolved=use,
            origin=orig,
            un_resolved=annotation,
            parameter=parameter,
            optional=is_optional,
            strict=is_strict,
            static=is_static,
            serde=serde,
        )
        anno.translator = functools.partial(self.translator.factory, anno)  # type: ignore
        return anno

    @functools.lru_cache(maxsize=None)
    def _resolve_from_annotation(
        self, anno: Annotation, _des: bool = True, _ser: bool = True,
    ) -> SerdeProtocol:
        # FIXME: Simulate legacy behavior. Should add runtime analysis soon (#95)
        if anno.origin is Callable:
            _des, _ser = False, False
        # Build the deserializer
        deserializer, validator, constraints = None, None, None
        if _des:
            constraints = const.get_constraints(anno.resolved, nullable=anno.optional)
            deserializer, validator = self.des.factory(anno, constraints)
        # Build the serializer
        serializer: Optional[SerializerT] = self.ser.factory(anno) if _ser else None
        # Put it all together
        return SerdeProtocol(
            annotation=anno,
            deserializer=deserializer,
            serializer=serializer,
            constraints=constraints,
            validator=validator,
        )

    @functools.lru_cache(maxsize=None)
    def resolve(
        self,
        annotation: Type[ObjectT],
        *,
        flags: SerdeFlags = None,
        name: str = None,
        parameter: Optional[inspect.Parameter] = None,
        is_optional: bool = None,
        is_strict: bool = None,
        _des: bool = True,
        _ser: bool = True,
    ) -> SerdeProtocol:
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
        )
        resolved = self._resolve_from_annotation(anno, _des, _ser)
        return resolved

    @functools.lru_cache(maxsize=None)
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

        if not any(
            (inspect.ismethod(obj), inspect.isfunction(obj), inspect.isclass(obj))
        ):
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
            if annotation is ClassVar:
                val = getattr(obj, name)
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
            resolved: SerdeProtocol = self.resolve(
                annotation, parameter=param, name=name, is_strict=strict
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
