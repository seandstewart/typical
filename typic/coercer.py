#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import datetime
import inspect
import re
from collections import deque
from operator import attrgetter
from types import FunctionType, MethodType
from typing import (
    Mapping,
    Any,
    Union,
    Callable,
    Type,
    Dict,
    Collection,
    Deque,
    Optional,
    Tuple,
    Iterable,
    List,
    Pattern,
    Match,
    ClassVar,
    cast,
    TypeVar,
    Generic,
)

from pendulum import parse as dateparse

import typic.schema as s
from typic import checks, constraints as const, gen
from typic.strict import STRICT as _STRICT, StrictModeT
from typic.util import (
    safe_eval,
    resolve_supertype,
    get_args,
    origin as get_origin,
    cached_signature,
    cached_type_hints,
    cached_property,
    cachedmethod,
    hexhash,
)

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

ObjectT = TypeVar("ObjectT")


OriginT = TypeVar("OriginT")
"""A type alias for an instance of the type associated to a Coercer."""

CoercerT = Callable[[Any], OriginT]
"""A type alias for the expected signature of a type coercer.

Type coercers should take a value of any type and return a value of the target type.
"""
CoercerTypeCheckT = Callable[[Type[Any]], bool]
"""A type alias for the expected signature of a type-check for a coercer.

Type-checkers should return a boolean indicating whether the provided type is valid for
a given coercer.
"""
CoercerRegistryT = Deque[Tuple[CoercerTypeCheckT, CoercerT]]


class Strict(Generic[ObjectT]):
    """A type-hint indicating an object should be validated rather than coerced.

    Examples
    --------
    >>> import typic
    >>>
    >>> @typic.klass
    ... class Foo:
    ...     bar: typic.Strict[str]
    ...
    >>> Foo(1)
    Traceback (most recent call last):
        ...
    typic.constraints.error.ConstraintValueError: Given value <1> fails constraints: (type=str, nullable=False, coerce=False)
    """


StrictStrT = Strict[str]
"""Strings are by far the most common use-case for enforced strictness.

This is because pretty much any Python object can be cast to ``str``. It's encouraged to
make use of this annotation in lieu of a bare ``str`` as that can lead to unwanted states.

Examples
--------
>>> import typic
>>>
>>> @typic.klass
... class Foo:
...     bar: typic.StrictStrT
...
>>> Foo(1)
Traceback (most recent call last):
    ...
typic.constraints.error.ConstraintValueError: Given value <1> fails constraints: (type=str, nullable=False, coerce=False)
"""


@dataclasses.dataclass(unsafe_hash=True)
class ResolvedAnnotation:
    """An actionable run-time annotation.

    For the case of ``typical``, a "resolved annotation" is one in which we have located:
        - Whether there is a coercer function
        - Whether there is a default value
        - The kind of parameter (if this annotation refers to a parameter)
    """

    EMPTY = _empty

    annotation: Any
    """The type annotation used to build the coercer."""
    origin: Type
    """The "origin"-type of the annotation."""
    un_resolved: Any
    """The type annotation before resolving super-types."""
    coercer: CoercerT
    """The actual coercer for the annotation."""
    parameter: inspect.Parameter
    """The parameter this annotation refers to."""
    constraints: Optional[const.ConstraintsT]
    """Type restrictions, if any."""
    strict: StrictModeT = False
    """Whether to enforce the annotation, rather than coerce."""

    def __post_init__(self):
        self.validate = self.constraints.validate
        self.coerce = self.coercer
        if (
            isinstance(self.constraints, const.TypeConstraints)
            and self.constraints.coerce
        ):
            self.validate = self.coerce

        self._call = self.__caller

    @cached_property
    def __caller(self):
        __call = self.coerce
        if isinstance(self.constraints, const.TypeConstraints):
            if self.strict:
                __call = self.validate
        else:
            if self.strict and self.constraints and self.constraints.coerce:

                def __call(val: Any, *, __c=self.coerce, __v=self.validate) -> ObjectT:
                    return __c(__v(val))

            elif self.strict:
                __call = self.validate
        return __call

    def __call__(self, val: Any) -> ObjectT:
        return self._call(val)


Annotations = Dict[str, ResolvedAnnotation]
"""A mapping of attr/param name to :py:class:`ResolvedAnnotation`."""


@dataclasses.dataclass(frozen=True)
class BoundArguments:
    obj: Union[Type, Callable]
    """The object we "bound" the input to."""
    annotations: Annotations
    """A mapping of the resolved annotations."""
    parameters: Mapping[str, inspect.Parameter]
    """A mapping of the parameters."""
    arguments: Dict[str, Any]
    """A mapping of the input to parameter name."""
    returns: Optional[ResolvedAnnotation]
    """The resolved return type, if any."""
    _argnames: Tuple[str, ...]
    _kwdargnames: Tuple[str, ...]

    @cached_property
    def args(self) -> Tuple[Any, ...]:
        """A tuple of the args passed to the callable."""
        args: List = list()
        argsappend = args.append
        argsextend = args.extend
        paramsget = self.parameters.__getitem__
        argumentsget = self.arguments.__getitem__
        for name in self._argnames:
            kind = paramsget(name).kind
            arg = argumentsget(name)
            if kind == _VAR_POSITIONAL:
                argsextend(arg)
            else:
                argsappend(arg)
        return tuple(args)

    @cached_property
    def kwargs(self) -> Dict[str, Any]:
        """A mapping of the key-word arguments passed to the callable."""
        kwargs: Dict = {}
        kwargsupdate = kwargs.update
        kwargsset = kwargs.__setitem__
        paramsget = self.parameters.__getitem__
        argumentsget = self.arguments.__getitem__
        for name in self._kwdargnames:
            kind = paramsget(name).kind
            arg = argumentsget(name)
            if kind == _VAR_KEYWORD:
                kwargsupdate(arg)
            else:
                kwargsset(name, arg)
        return kwargs

    def eval(self) -> Any:
        """Evaluate the callable against the input provided.

        Examples
        --------
        >>> import typic
        >>>
        >>> def foo(bar: int) -> int:
        ...     return bar ** bar
        ...
        >>> bound = typic.bind(foo, "2")
        >>> bound.eval()
        4
        """
        return self.obj(*self.args, **self.kwargs)


class TypeCoercer:
    """A callable class for coercing values.

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
    >>> typic.coerce("foo", bytes)
    b'foo'
    >>> typic.coerce("{'foo': 'bar'}", dict)
    {'foo': 'bar'}
    """

    STRICT = _STRICT
    DEFAULT_BYTE_ENCODING = "utf-8"
    UNRESOLVABLE = frozenset(
        (
            Any,
            Union,
            Match,
            re.Match,  # type: ignore
            type(None),
            _empty,
        )
    )

    def __init__(self):
        self._resolved_cache = {}
        self._coercer_cache = {}
        self._schema_cache = {}
        self.schema_builder = s.SchemaBuilder()
        for typ in checks.BUILTIN_TYPES:
            self._build_coercer(typ)
        self._user_coercers: CoercerRegistryT = deque()

    def register(self, coercer: CoercerT, check: CoercerTypeCheckT):
        """Register a user-defined coercer.

        In the rare case where typic can't figure out how to coerce your annotation
        correctly, a custom coercer may be registered alongside a check function which
        returns a simple boolean indicating whether this is the correct coercer for an
        annotation.
        """
        self._user_coercers.appendleft((check, coercer))

    def seen(self, cls_or_callable: Union[Callable, Type]) -> bool:
        return cls_or_callable in self._resolved_cache or hasattr(
            cls_or_callable, _ORIG_SETTER_NAME
        )

    @staticmethod
    def _set_checks(func: gen.Block, optional: bool, default: Any = _empty):
        _checks = []
        _ctx = {}
        if optional:
            _checks.append("val is None")
        if default is not _empty:
            _checks.append("val == __default")
            _ctx["__default"] = default
        if _checks:
            check = " or ".join(_checks)
            func.l(f"if {check}:", **_ctx)
            with func.b() as b:
                b.l("return val")

    @staticmethod
    def _get_coercer_name(annotation, default, optional: bool = None) -> str:
        return f"coercer_{hexhash(annotation, default, optional=optional)}"

    @staticmethod
    def _build_date_coercer(func: gen.Block, origin: Type, anno_name: str):
        if origin is datetime.datetime:
            with func.b("if isinstance(val, datetime.date):") as b:
                b.l(
                    "val = datetime.datetime(val.year, val.month, val.day)",
                    datetime=datetime,
                )
        elif origin is datetime.date:
            with func.b("if isinstance(val, datetime.datetime):") as b:
                b.l("val = val.date()", datetime=datetime)
        with func.b("elif isinstance(val, (int, float)):") as b:
            b.l(f"val = {anno_name}.fromtimestamp(val)")
        with func.b("elif isinstance(val, (str, bytes)):") as b:
            b.l("val = dateparse(val)", dateparse=dateparse)

    @staticmethod
    def _build_builtin_coercer(func: gen.Block, origin: Type, anno_name: str):
        if issubclass(origin, Collection) and not issubclass(origin, (str, bytes)):
            with func.b("if isinstance(val, (str, bytes)):") as b:
                b.l("_, val = safe_eval(val)", safe_eval=safe_eval)
        if issubclass(origin, bytes):
            with func.b("if isinstance(val, str):") as b:
                b.l(f"val = {anno_name}(val, encoding='utf-8')")
        elif issubclass(origin, str):
            with func.b("if isinstance(val, bytes):") as b:
                b.l("val = val.decode('utf-8')")
        func.l(f"val = {anno_name}(val)")

    @staticmethod
    def _build_pattern_coercer(func: gen.Block, anno_name: str):
        with func.b(f"if not isinstance(val, {anno_name}):") as b:
            b.l("val = __re_compile(val)", __re_compile=re.compile)

    @staticmethod
    def _build_fromdict_coercer(func: gen.Block, anno_name: str):
        with func.b(f"if isinstance(val, {anno_name}):") as b:
            b.l("return val")
        with func.b("if isinstance(val, (str, bytes)):") as b:
            b.l("_, val = safe_eval(val)", safe_eval=safe_eval)
        func.l(f"val = {anno_name}.from_dict(val)")

    def _build_typeddict_coercer(
        self, func: gen.Block, anno_name: str, partial: bool = False
    ):
        with func.b("if isinstance(val, (str, bytes)):") as b:
            b.l("_, val = safe_eval(val)", safe_eval=safe_eval)
        func.l(
            f"val = __bind({anno_name}, partial={partial}, **val).eval()",
            __bind=self.bind,
        )

    def _build_typedtuple_coercer(self, func: gen.Block, anno_name: str):
        with func.b("if isinstance(val, (str, bytes)):") as b:
            b.l("_, val = safe_eval(val)", safe_eval=safe_eval)
        func.l(
            f"val = __bind({anno_name}, **val).eval()"
            f"if isinstance(val, Mapping) else "
            f"__bind({anno_name}, *val).eval()",
            __bind=self.bind,
            Mapping=Mapping,
        )

    def _build_mapping_coercer(
        self, func: gen.Block, args: Tuple[Type, Type], anno_name: str
    ):
        key_type, item_type = args
        key_coercer = self.resolve(key_type)
        item_coercer = self.resolve(item_type)
        kc_name = f"{anno_name}_key_coercer"
        it_name = f"{anno_name}_item_coercer"
        with func.b("if isinstance(val, (str, bytes)):") as b:
            b.l("_, val = safe_eval(val)", safe_eval=safe_eval)
        func.l(
            f"val = {anno_name}(({kc_name}(x), {it_name}(y)) "
            f"for x, y in {anno_name}(val).items())",
            level=None,
            **{kc_name: key_coercer, it_name: item_coercer},
        )

    def _build_collection_coercer(
        self, func: gen.Block, args: Tuple[Type, ...], anno_name: str
    ):
        item_type = args[0]
        item_coercer = self.resolve(item_type)
        it_name = f"{anno_name}_item_coercer"
        with func.b("if isinstance(val, (str, bytes)):") as b:
            b.l("_, val = safe_eval(val)", safe_eval=safe_eval)
        func.l(
            f"val = {anno_name}({it_name}(x) for x in {anno_name}(val))",
            level=None,
            **{it_name: item_coercer},
        )

    def _build_generic_coercer(self, func: gen.Block, origin: Type, anno_name: str):
        with func.b(f"if isinstance(val, {anno_name}):") as b:
            b.l("return val")
        with func.b("if isinstance(val, (str, bytes)):") as b:
            b.l("_, val = safe_eval(val)", safe_eval=safe_eval)
        params = {*cached_signature(origin).parameters}
        params_name = f"{anno_name}_params"
        with func.b("if isinstance(val, Mapping):", Mapping=Mapping) as b:
            b.l(
                f"val = {{x: val[x] for x in val.keys() & {params_name}}}",
                level=None,
                **{params_name: params},
            )
            if not self.seen(origin):
                b.l(f"bound = __bind({anno_name}, **val)", __bind=self.bind)
                b.l(f"val = {anno_name}(*bound.args, **bound.kwargs)")
            else:
                b.l(f"val = {anno_name}(**val)")
        with func.b("else:") as b:
            b.l(f"val = {anno_name}(val)")

    def _build_coercer(
        self, annotation, *, default: Any = _empty, is_optional: bool = None
    ) -> Callable:
        func_name = self._get_coercer_name(annotation, default, is_optional)
        if func_name in self._coercer_cache:
            return self._coercer_cache[func_name]
        # Resolve NewTypes into their annotation. Recursive.
        resolved = resolve_supertype(annotation)
        args = get_args(resolved)
        # Get the "origin" of the annotation.
        # For natives and their typing.* equivs, this will be a builtin type.
        # For SpecialForms (Union, mainly) this will be the un-subscripted type.
        # For custom types or classes, this will be the same as the annotation.
        origin = get_origin(resolved)
        optional = is_optional or False
        anno_name = f"{func_name}_anno"
        ns = {anno_name: origin}
        with gen.Block(ns) as main:
            with main.f(func_name, main.param("val")) as func:
                if origin not in self.UNRESOLVABLE:
                    self._set_checks(func, optional, default)
                    if checks.isdatetype(origin):
                        self._build_date_coercer(func, origin, anno_name)
                    elif origin in {Pattern, re.Pattern}:  # type: ignore
                        self._build_pattern_coercer(func, anno_name)
                    elif not args and checks.isbuiltintype(origin):
                        self._build_builtin_coercer(func, origin, anno_name)
                    elif checks.isfromdictclass(origin):
                        self._build_fromdict_coercer(func, anno_name)
                    elif checks.isenumtype(origin):
                        self._build_builtin_coercer(func, origin, anno_name)
                    elif checks.istypeddict(origin):
                        self._build_typeddict_coercer(
                            func, anno_name, not origin.__total__
                        )
                    elif checks.istypedtuple(origin) or checks.isnamedtuple(origin):
                        self._build_typedtuple_coercer(func, anno_name)
                    elif not args and checks.isbuiltinsubtype(origin):
                        self._build_builtin_coercer(func, origin, anno_name)
                    elif checks.ismappingtype(origin):
                        args = cast(Tuple[Type, Type], args)
                        self._build_mapping_coercer(func, args, anno_name)
                    elif checks.iscollectiontype(origin):
                        args = cast(Tuple[Type, ...], args)
                        self._build_collection_coercer(func, args, anno_name)
                    else:
                        self._build_generic_coercer(func, origin, anno_name)
                func.l("return val")
        coercer = main.compile(ns=self._coercer_cache, name=func_name)
        return coercer

    def get_coercer(
        self, annotation, *, default: Any = _empty, is_optional: bool = None
    ) -> CoercerT:
        key = self._get_coercer_name(annotation, default, is_optional)
        if key in self._coercer_cache:
            return self._coercer_cache[key]
        for check, coercer in self._user_coercers:
            if check(annotation):
                self._coercer_cache[key] = coercer
                return coercer

        return self._build_coercer(annotation, default=default, is_optional=is_optional)

    def coerce_value(self, value: Any, annotation: Type[ObjectT]) -> ObjectT:
        """Coerce the given value to the given annotation, if possible.

        Checks for:
            - :class:`datetime.date`
            - :class:`datetime.datetime`
            - builtin types
            - extended type annotations as described in the ``typing`` module.
            - User-defined classes (limited)

        Parameters
        ----------
        value :
            The value to be coerced
        annotation :
            The provided annotation for determining the coercion
        """
        resolved: ResolvedAnnotation = self.resolve(annotation)
        coerced: ObjectT = resolved(value)

        return coerced

    __call__ = coerce_value  # alias for easy access to most common operation.

    @cachedmethod
    def resolve(
        self,
        annotation: Type[ObjectT],
        *,
        name: str = None,
        parameter: Optional[inspect.Parameter] = None,
        is_optional: bool = None,
        is_strict: bool = None,
    ) -> ResolvedAnnotation:
        """Get a :py:class:`ResolvedAnnotation` from a type."""
        if parameter is None:
            parameter = inspect.Parameter(
                name or "_",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=annotation,
            )
        # Check for the super-type
        non_super = resolve_supertype(annotation)
        origin = get_origin(annotation)
        use = non_super
        # Get the unfiltered args
        args = getattr(non_super, "__args__", None)
        # Set whether this is optional/strict
        is_optional = is_optional or checks.isoptionaltype(non_super)
        is_strict = is_strict or checks.isstrict(non_super)
        # Determine whether we should use the first arg of the annotation
        while checks.should_unwrap(use) and args:
            is_optional = is_optional or checks.isoptionaltype(use)
            is_strict = is_strict or checks.isstrict(use)
            if is_optional and len(args) > 2:
                # We can't resolve this annotation.
                break
            non_super = resolve_supertype(args[0])
            use = non_super
            args = get_args(use)

        # Build the coercer
        coercer: CoercerT = self.get_coercer(
            use, default=parameter.default, is_optional=is_optional
        )
        # Handle *args and **kwargs
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            __coerce = coercer

            def coercer(__val):
                return (*(__coerce(x) for x in __val),)

        elif parameter.kind == inspect.Parameter.VAR_KEYWORD:
            __coerce = coercer

            def coercer(__val):
                return {x: __coerce(y) for x, y in __val.items()}

        resolved = ResolvedAnnotation(
            annotation=non_super,
            origin=origin,
            un_resolved=annotation,
            coercer=coercer,
            parameter=parameter,
            constraints=const.get_constraints(use, nullable=is_optional),
            strict=is_strict or self.STRICT,
        )
        return resolved

    @cachedmethod
    def annotations(self, obj, *, strict: bool = False) -> Annotations:
        """Get a mapping of param/attr name -> :py:class:`ResolvedAnnotation`

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
        >>> annotations = typic.annotations(Foo)

        See Also
        --------
        :py:class:`ResolvedAnnotation`
        """

        if not any(
            (inspect.ismethod(obj), inspect.isfunction(obj), inspect.isclass(obj))
        ):
            obj = type(obj)

        sig = cached_signature(obj)
        hints = cached_type_hints(obj)
        params: Mapping[str, inspect.Parameter] = sig.parameters
        fields: Mapping[str, dataclasses.Field] = {}
        if dataclasses.is_dataclass(obj):
            fields = {f.name: f for f in dataclasses.fields(obj)}
        ann = {}
        for name in params.keys() | hints.keys():
            param = params.get(name)
            hint = hints.get(name)
            field = fields.get(name)
            annotation = hint or param.annotation  # type: ignore
            annotation = resolve_supertype(annotation)
            param = param or inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=_empty,
                annotation=hint or annotation,
            )
            if repr(param.default) == "<factory>":
                param = param.replace(default=_empty)
            if annotation is ClassVar:
                val = getattr(obj, name)
                annotation = annotation[type(val)]
                default = val
                param = param.replace(default=default)
            if (
                field
                and field.default is not dataclasses.MISSING
                and param.default is _empty
            ):
                if field.init is False and get_origin(annotation) is not s.ReadOnly:
                    annotation = s.ReadOnly[annotation]  # type: ignore
                param = param.replace(default=field.default)
            resolved: ResolvedAnnotation = self.resolve(
                annotation, parameter=param, name=name, is_strict=strict
            )
            ann[name] = resolved
        try:
            setattr(obj, _TYPIC_ANNOS_NAME, ann)
        # We wrapped a bound method, or
        # are wrapping a static-/classmethod
        # after they were wrapped with @static/class
        except AttributeError:
            pass

        return ann

    def _bind_posargs(
        self,
        arguments: Dict[str, Any],
        params: Deque[inspect.Parameter],
        annos: Dict[str, ResolvedAnnotation],
        args: Deque[Any],
        kwargs: Dict[str, Any],
    ) -> Tuple[str, ...]:
        # Bind any positional arguments

        # bytecode hack to localize access
        # only noticeable with really large datasets
        # but it's best to be prepared.
        posargs: List[str] = list()
        posargsadd = posargs.append
        argspop = args.popleft
        paramspop = params.popleft
        annosget = annos.get
        argumentsset = arguments.__setitem__
        while args and params:
            val = argspop()
            param: inspect.Parameter = paramspop()
            name = param.name
            anno: Optional[ResolvedAnnotation] = annosget(name)
            kind = param.kind
            # We've got varargs, so push all supplied args to that param.
            if kind == _VAR_POSITIONAL:
                value = (val,) + tuple(args)
                args = deque()
                if anno:
                    value = anno(value)
                argumentsset(name, value)
                posargsadd(name)
                break

            # We're not supposed to have kwdargs....
            if kind in _KWD_KINDS:
                raise TypeError(_TOO_MANY_POS) from None

            # Passed in by ref and assignment... no good.
            if name in kwargs:
                raise TypeError(f"multiple values for argument '{name}'") from None

            # We're g2g
            value = anno(val) if anno else val
            argumentsset(name, value)
            posargsadd(name)

        if args:
            raise TypeError(_TOO_MANY_POS) from None

        return tuple(posargs)

    def _bind_kwdargs(
        self,
        arguments: Dict[str, Any],
        params: Deque[inspect.Parameter],
        annos: Dict[str, ResolvedAnnotation],
        kwargs: Dict[str, Any],
        partial: bool = False,
    ) -> Tuple[str, ...]:
        # Bind any key-word arguments
        kwdargs: List[str] = list()
        kwdargsadd = kwdargs.append
        kwargs_anno = None
        kwdargs_param = None
        kwargspop = kwargs.pop
        annosget = annos.get
        argumentsset = arguments.__setitem__
        for param in params:
            kind = param.kind
            name = param.name
            anno = annosget(name)
            # Move on, but don't forget
            if kind == _VAR_KEYWORD:
                kwargs_anno = anno
                kwdargs_param = param
                continue
            # We don't care about these
            if kind == _VAR_POSITIONAL:
                continue
            # try to bind the parameter
            if name in kwargs:
                val = kwargspop(name)
                if kind == _POSITIONAL_ONLY:
                    raise TypeError(
                        f"{name!r} parameter is positional only,"
                        "but was passed as a keyword."
                    )
                value = anno(val) if anno else val
                argumentsset(name, value)
                kwdargsadd(name)
            elif not partial and param.default is _empty:
                raise TypeError(f"missing required argument: {name!r}")

        # We didn't clear out all the kwdargs. Check to see if we came across a **kwargs
        if kwargs:
            if kwdargs_param is not None:
                # Process our '**kwargs'-like parameter
                name = kwdargs_param.name
                value = kwargs_anno.coerce(kwargs) if kwargs_anno else kwargs
                argumentsset(name, value)
                kwdargsadd(name)
            else:
                raise TypeError(
                    f"'got an unexpected keyword argument {next(iter(kwargs))!r}'"
                )

        return tuple(kwdargs)

    def _bind_input(
        self,
        obj: Union[Type, Callable],
        annos: Annotations,
        params: Mapping[str, inspect.Parameter],
        args: Iterable[Any],
        kwargs: Dict[str, Any],
        *,
        partial: bool = False,
    ) -> BoundArguments:
        """Bind annotations and parameters to received input.

        Taken approximately from :py:meth:`inspect.Signature.bind`, with a few changes.

        About 10% faster, on average, and coerces values with their annotation if possible.

        Parameters
        ----------
        annos
            A mapping of :py:class:`ResolvedAnnotation` to param name.
        params
            A mapping of :py:class:`inspect.Parameter` to param name.
        args
            The positional args to bind to their param and annotation, if possible.
        kwargs
            The keyword args to bind to their param and annotation, if possible.

        Other Parameters
        ----------------
        partial
            Bind a partial input.

        Raises
        ------
        TypeError
            If we can't match up the received input to the signature
        """
        arguments: Dict[str, Any] = dict()
        returns = annos.pop(_RETURN_KEY, None)
        args = deque(args)
        parameters = deque(params.values())
        # Bind any positional arguments.
        posargs = self._bind_posargs(arguments, parameters, annos, args, kwargs)
        # Bind any keyword arguments.
        kwdargs = self._bind_kwdargs(arguments, parameters, annos, kwargs, partial)
        return BoundArguments(obj, annos, params, arguments, returns, posargs, kwdargs)

    def bind(
        self,
        obj: Union[Type, Callable],
        *args: Any,
        partial: bool = False,
        coerce: bool = True,
        strict: bool = False,
        **kwargs: Mapping[str, Any],
    ) -> BoundArguments:
        """Bind a received input to a callable or object's signature.

        If we can locate an annotation for any args or kwargs, we'll automatically
        coerce as well.

        This implementation is similar to :py:meth:`inspect.Signature.bind`,
        but is ~10-20% faster.
        We also use a cached the signature to avoid the expense of that call if possible.

        Parameters
        ----------
        obj
            The object you wish to bind your input to.
        *args
            The given positional args.
        partial
            Whether to bind a partial input.
        coerce
            Whether to coerce the input to the annotation provided.
        strict
            Whether to validate the input against the annotation provided.
        **kwargs
            The given keyword args.

        Returns
        -------
        :py:class:`BoundArguments`
            The bound and coerced arguments.

        Raises
        ------
        TypeError
            If we can't match up the received input to the signature

        Examples
        --------
        >>> import typic
        >>>
        >>> def add(a: int, b: int, *, c: int = None) -> int:
        ...     return a + b + (c or 0)
        ...
        >>> bound = typic.bind(add, "1", "2", c=3.0)
        >>> bound.arguments
        {'a': 1, 'b': 2, 'c': 3}
        >>> bound.args
        (1, 2)
        >>> bound.kwargs
        {'c': 3}
        >>> bound.eval()
        6
        >>> typic.bind(add, 1, 3.0, strict=True)
        Traceback (most recent call last):
            ...
        typic.constraints.error.ConstraintValueError: Given value <3.0> fails constraints: (type=int, nullable=False, coerce=False)
        """
        return self._bind_input(
            obj=obj,
            annos=self.annotations(obj, strict=strict) if (coerce or strict) else {},
            params=cached_signature(obj).parameters,
            args=args,
            kwargs=kwargs,
            partial=partial,
        )

    def schema(
        self, obj: Type[ObjectT], *, primitive: bool = False
    ) -> "s.ObjectSchemaField":
        """Get a JSON schema for object for the given object.

        Parameters
        ----------
        obj
            The class for which you wish to generate a JSON schema
        primitive
            Whether to return an instance of :py:class:`typic.schema.ObjectSchemaField` or
            a "primitive" (dict object).

        Examples
        --------
        >>> import typic
        >>>
        >>> @typic.klass
        ... class Foo:
        ...     bar: str
        ...
        >>> typic.schema(Foo)
        ObjectSchemaField(title='Foo', description='Foo(bar: str)', properties={'bar': StrSchemaField()}, additionalProperties=False, required=('bar',))
        >>> typic.schema(Foo, primitive=True)
        {'type': 'object', 'title': 'Foo', 'description': 'Foo(bar: str)', 'properties': {'bar': {'type': 'string'}}, 'additionalProperties': False, 'required': ['bar'], 'definitions': {}}

        """
        if obj in {FunctionType, MethodType}:
            raise ValueError("Cannot build schema for function or method.")

        annotation = self.resolve(obj)

        schema = self.schema_builder.get_field(annotation)
        self._schema_cache[obj] = schema
        try:
            setattr(obj, _SCHEMA_NAME, schema)
        except (AttributeError, TypeError):
            pass
        return schema.asdict() if primitive else schema
