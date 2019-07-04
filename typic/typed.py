#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import collections.abc
import copy
import dataclasses
import datetime
import functools
import inspect
import warnings
from collections import deque
from operator import attrgetter
from typing import (
    ForwardRef,
    Mapping,
    Sequence,
    Any,
    Union,
    Callable,
    Type,
    TypeVar,
    Dict,
    Collection,
    get_type_hints,
    Hashable,
    NamedTuple,
    Deque,
    Optional,
    TYPE_CHECKING,
    Tuple,
    Iterable,
    MutableMapping,
)

import dateutil.parser

from typic import checks
from typic.eval import safe_eval

__all__ = (
    "annotations",
    "coerce",
    "coerce_parameters",
    "typed",
    "typed_class",
    "typed_callable",
    "bind",
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


@functools.lru_cache(maxsize=None)
def cached_signature(obj: Callable) -> inspect.Signature:
    return inspect.signature(obj)


@functools.lru_cache(maxsize=None)
def cached_type_hints(obj: Callable) -> dict:
    return get_type_hints(obj)


class Coercer(NamedTuple):
    check: Callable
    coerce: Callable
    ident: str = None
    check_origin: bool = True

    @property
    @functools.lru_cache(None)
    def parameters(self):
        return cached_signature(self.coerce).parameters


_Empty = inspect.Parameter.empty


class ResolvedAnnotation(NamedTuple):
    """A named tuple of resolved annotations.

    For the case of ``typical``, a "resolved annotation" is one in which we have located:
        - Whether there is a coercer function
        - Whether there is a default value
        - The kind of parameter (if this :py:class:`Annotation` refers to a parameter)
    """

    annotation: Any
    origin: Any
    un_resolved: Any
    coercer: Optional[Coercer]
    name: str = None
    default: Any = _Empty
    param_kind: Any = _Empty
    is_optional: bool = False

    @property
    @functools.lru_cache(None)
    def parameters(self) -> Mapping[str, Any]:
        return {x: y for x, y in self._asdict().items() if x in self.coercer.parameters}

    def coerce(self, value: Any) -> Any:
        if (
            type(value) is self.annotation
            or value == self.default
            or not self.coercer
            or self.is_optional
            and value is None
        ):
            return value

        if self.param_kind == inspect.Parameter.VAR_POSITIONAL:
            return coerce._coerce_args(value, self.annotation)
        if self.param_kind == inspect.Parameter.VAR_KEYWORD:
            return coerce._coerce_kwargs(value, self.annotation)
        return self.coercer.coerce(value=value, **self.parameters)


class CoercerRegistry:
    __registry: Deque[Coercer] = deque()
    __user_registry: Deque[Coercer] = deque()
    __annotation_registry: MutableMapping[Hashable, ResolvedAnnotation] = dict()

    def __init__(self, cls: "TypeCoercer"):
        self.cls = cls
        self._register_builtin_coercers()

    def register(
        self,
        coercer: Callable,
        check: Callable,
        ident: str = None,
        check_origin: bool = True,
    ):
        _coercer = Coercer(
            check=check, coerce=coercer, ident=ident, check_origin=check_origin
        )
        type(self).__user_registry.appendleft(_coercer)

    def _register_builtin_coercers(self):
        """Build the deque of builtin coercers.

        Order here is important!
        """
        type(self).__registry.extend(
            [
                # Check if the annotaion is a date-type
                Coercer(checks.isdatetype, self.cls._coerce_datetime),
                # Check if the annotation maps directly to a builtin-type
                # We use the raw annotation here, not the origin, since we account for
                # subscripted generics later.
                Coercer(
                    checks.isbuiltintype, self.cls._coerce_builtin, check_origin=False
                ),
                # Check for a class with a ``from_dict()`` factory
                Coercer(checks.isfromdictclass, self.cls._coerce_from_dict),
                # Enums are iterable and evaluate as a Collection,
                # so we need to short-circuit the next set of checks
                Coercer(checks.isenumtype, self.cls._coerce_enum),
                # Check for a subscripted generic of the ``Mapping`` type
                Coercer(checks.ismappingtype, self.cls._coerce_mapping),
                # Check for a subscripted generic of the ``Collection`` type
                # This *must* come after the check for a ``Mapping`` type
                Coercer(checks.iscollectiontype, self.cls._coerce_collection),
                # Finally, try a generic class coercion.
                Coercer(inspect.isclass, self.cls._coerce_class),
            ]
        )

    @staticmethod
    def _check(reg: Deque[Coercer], origin: Type, annotation: Any) -> Optional[Coercer]:
        for coercer in reg:
            if coercer.check(origin if coercer.check_origin else annotation):
                return coercer

    @functools.lru_cache(None)
    def check_user_registry(self, origin: Type, annotation: Any) -> Optional[Coercer]:
        """Locate a coercer from the user registry."""
        return self._check(
            reg=self.__user_registry, origin=origin, annotation=annotation
        )

    @staticmethod
    def key(annotation: Any, *, default: Any = _Empty, param_kind: Any = _Empty):
        """Get a key for the Annotation mapping.

        Hide what we're really doing, in case it needs to change.
        """
        return annotation, default, param_kind

    def check(
        self,
        origin: Type,
        annotation: Any,
        *,
        name: str = None,
        default: Any = _Empty,
        param_kind: inspect._ParameterKind = _Empty,
    ) -> ResolvedAnnotation:
        """Locate the coercer for this annotation from either registry."""
        key = self.key(annotation, default=default, param_kind=param_kind)
        if key not in self.__annotation_registry:
            use = annotation
            is_optional = checks.isoptionaltype(annotation)
            if is_optional or (
                checks.isclassvartype(annotation)
                and getattr(annotation, "__args__", ())
            ):
                use = annotation.__args__[0]

            coercer = self._check(
                reg=self.__user_registry + self.__registry,
                origin=origin,
                annotation=use,
            )
            anno = (
                ResolvedAnnotation(
                    annotation=use,
                    origin=origin,
                    un_resolved=annotation,
                    coercer=coercer,
                    name=name,
                    default=default,
                    param_kind=param_kind,
                    is_optional=is_optional,
                )
                if coercer
                else None
            )
            self.__annotation_registry[key] = anno

        return self.__annotation_registry[key]

    def coerce(self, value: Any, origin: Type, annotation: Any) -> Any:
        annotation = self.check(origin, annotation)
        if not annotation:
            return value
        return annotation.coerce(value=value)


Annotations = Dict[str, ResolvedAnnotation]


@dataclasses.dataclass(frozen=True)
class BoundArguments:
    annotations: Annotations
    parameters: Mapping[str, inspect.Parameter]
    arguments: Dict[str, Any]
    returns: Optional[ResolvedAnnotation]
    _argnames: Tuple[str]
    _kwdargnames: Tuple[str]

    @property
    def args(self) -> Tuple[Any]:
        args = list()
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

    @property
    def kwargs(self) -> Dict[str, Any]:
        kwargs = {}
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


class TypeCoercer:
    """A callable class for coercing values."""

    GENERIC_TYPE_MAP = {
        collections.abc.Sequence: list,
        Sequence: list,
        collections.abc.Collection: list,
        Collection: list,
        Mapping: dict,
        collections.abc.Mapping: dict,
        Hashable: str,
        collections.abc.Hashable: str,
    }
    DEFAULT_BYTE_ENCODING = "utf-8"
    UNRESOLVABLE = frozenset((Any, Union))

    def __init__(self):
        self.registry = CoercerRegistry(self)
        self.register = self.registry.register
        self._parameter_handlers = {
            inspect.Parameter.VAR_POSITIONAL: self._coerce_args,
            inspect.Parameter.VAR_KEYWORD: self._coerce_kwargs,
        }

    @classmethod
    def _check_generics(cls, hint: Any):
        return cls.GENERIC_TYPE_MAP.get(hint, hint)

    @classmethod
    @functools.lru_cache(maxsize=None)
    def get_origin(cls, annotation: Any) -> Any:
        """Get origins for subclasses of typing._SpecialForm, recursive"""
        # Resolve custom NewTypes, recursively.
        actual = checks.resolve_supertype(annotation)
        # Extract the origin of the annotation, recursively.
        actual = getattr(actual, "__origin__", actual)
        if checks.isoptionaltype(annotation) or checks.isclassvartype(annotation):
            return cls.get_origin(cls.get_args(annotation))

        # provide defaults for generics
        if not checks.isbuiltintype(actual):
            actual = cls._check_generics(actual)

        return actual

    @classmethod
    @functools.lru_cache(maxsize=None)
    def get_args(cls, annotation: Any) -> Tuple[Any, ...]:
        return tuple(
            x for x in getattr(annotation, "__args__", ()) if not isinstance(x, TypeVar)
        )

    @classmethod
    def _coerce_builtin(cls, value: Any, annotation: Type) -> Any:
        """If the declared type is a builtin, we should just try casting it. Allow errors to bubble up."""
        # Special case: truthy value that was previously coerced to str ('0', ...)
        # Special case: JSON/YAML for a dict or list field
        if annotation in (bool, dict, list, tuple, set, frozenset) and isinstance(
            value, (str, bytes)
        ):
            processed, value = safe_eval(value)
        if annotation in (bytearray, bytes) and not isinstance(
            value, (bytes, bytearray)
        ):
            value = str(value).encode(cls.DEFAULT_BYTE_ENCODING)

        return annotation(value)

    @staticmethod
    def _coerce_datetime(
        value: Any, annotation: Type[Union[datetime.date, datetime.datetime]]
    ) -> Union[datetime.datetime, datetime.date]:
        """Coerce date, datetime, and date-string objects.

        Parameters
        ----------
        value :
            The value which maps to this annotation
        annotation :
            The time-object annotation
        """
        if isinstance(value, datetime.date) and annotation == datetime.datetime:
            value = datetime.datetime(value.year, value.month, value.day)
        elif isinstance(value, datetime.datetime) and annotation == datetime.date:
            value = value.date()
        elif isinstance(value, (int, float)):
            value = annotation.fromtimestamp(value)
        else:
            value = dateutil.parser.parse(value)

        return value

    def _coerce_collection(
        self, value: Any, origin: Type, annotation: Type[Collection[Any]]
    ) -> Collection:
        """Coerce a Sequence or related sub-type.

        If the declared type is ``Sequence``, it will default to a list.

        Parameters
        ----------
        value :
            A value to be coerced.
        origin :
            The builtin origin of an ABC or type-hint from the ``typing`` module.
        annotation :
            The original annotation.
        """
        args = self.get_args(annotation)
        value = self._coerce_builtin(value, origin)
        if args:
            arg = args[0]
            return type(value)(self.coerce_value(x, arg) for x in value)
        return self._coerce_builtin(value, origin)

    def _coerce_mapping(
        self, value: Any, origin: Type, annotation: Mapping[Any, Any]
    ) -> Mapping:
        """Coerce a Mapping type (i.e. dict or similar).

        Default to a dict if ``Mapping`` is declared.

        Notes
        -----
        If we're able to locate

        Parameters
        ----------
        value :
            The value to be coerced.
        origin :
            The builtin origin of an ABC or type-hint from the ``typing`` module.
        annotation :
            The original annotation.
        """
        args = self.get_args(annotation)
        value = self._coerce_builtin(value, origin)
        if args:
            key_type, value_type = args
            return type(value)(
                (self.coerce_value(x, key_type), self.coerce_value(y, value_type))
                for x, y in value.items()
            )

        return value

    def _coerce_from_dict(self, origin: Type, value: Dict) -> Any:
        if isinstance(value, (str, bytes)):
            processed, value = safe_eval(value)
        bound = self.coerce_parameters(cached_signature(origin).bind(**value))
        return origin.from_dict(dict(bound.arguments))

    def _coerce_class(self, value: Any, origin: Type, annotation: Any) -> Any:
        processed, value = (
            safe_eval(value) if isinstance(value, str) else (False, value)
        )
        coerced = value
        if isinstance(value, (Mapping, dict)):
            bound = self.coerce_parameters(cached_signature(origin).bind(**value))
            coerced = origin(*bound.args, **bound.kwargs)
        elif value is not None and not checks.isoptionaltype(annotation):
            coerced = origin(value)

        return coerced

    @staticmethod
    def _coerce_enum(value: Any, annotation: Any) -> Any:
        return annotation(value)

    def coerce_value(self, value: Any, annotation: Any) -> Any:
        """Coerce the given value to the given annotation, if possible.

        Checks for:
            - :class:`datetime.date`
            - :class:`datetime.datetime`
            - builtin types
            - extended type annotations as described in the ``typing`` module.
            - Classes with a ``from_dict`` method

        Parameters
        ----------
        value :
            The value to be coerced
        annotation :
            The provided annotation for determining the coercion
        """
        # Resolve NewTypes into their annotation. Recursive.
        annotation = checks.resolve_supertype(annotation)
        # Get the "origin" of the annotation. This will be a builtin for native types.
        # For custom types or classes, this will be the same as the annotation.
        origin = self.get_origin(annotation)
        optional = checks.isoptionaltype(annotation)
        # Short-circuit checks if this is an optional type and the value is None
        # Or if the type of the value is the annotation.
        if type(value) is annotation or (optional and value is None):
            return value

        coerced = self.registry.coerce(value, origin, annotation)

        return coerced

    __call__ = coerce_value  # alias for easy access to most common operation.

    @functools.lru_cache(None)
    def coerceable(self, annotation: Any) -> bool:
        if annotation is _Empty:
            return False

        annotation = checks.resolve_supertype(annotation)
        origin = self.get_origin(annotation)
        if self.registry.check_user_registry(origin, annotation):
            return True

        has_annotation = annotation is not inspect.Parameter.empty
        if has_annotation:
            return not (
                isinstance(origin, (str, ForwardRef))
                or origin in self.UNRESOLVABLE
                or type(origin) in self.UNRESOLVABLE
            )
        return False

    def should_coerce(self, parameter: inspect.Parameter, value: Any) -> bool:
        """Check whether we need to coerce the given value to the parameter's annotation.

            1. Ignore values provided by defaults, even if the type doesn't match the annotation.
                - Handles values which default to ``None``, for instance.
            2. Only check parameters which have an annotation.

        Parameters
        ----------
        parameter
            The parameter in question, provided by :func:`cached_signature`
        value
            The value to check for coercion.
        """
        # No need to coerce defaults
        if value == parameter.default:
            return False

        annotation = checks.resolve_supertype(parameter.annotation)
        origin = self.get_origin(annotation)
        # If we can coerce the annotation,
        # and either the annotation has args,
        # or the value is not an instance of the origin
        return self.coerceable(annotation) and (
            getattr(annotation, "__args__", None) or not isinstance(value, origin)
        )

    def _coerce_args(self, value: Iterable[Any], annotation: Any) -> Tuple[Any]:
        return tuple(self.coerce_value(x, annotation) for x in value)

    def _coerce_kwargs(
        self, value: Mapping[str, Any], annotation: Any
    ) -> Mapping[str, Any]:
        return {x: self.coerce_value(y, annotation) for x, y in value.items()}

    def coerce_parameter(self, param: inspect.Parameter, value: Any) -> Any:
        """Coerce the value of a parameter to its appropriate type."""
        handler = self._parameter_handlers.get(param.kind, self.coerce_value)

        return handler(value=value, annotation=param.annotation)

    def coerce_parameters(
        self, bound: inspect.BoundArguments
    ) -> inspect.BoundArguments:
        """Coerce the paramertes in the bound arguments to their annotated types.

        Ignore defaults and un-resolvable Forward References.

        Parameters
        ----------
        bound
            The bound arguments, provided by :func:`inspect.Signature.bind`

        Returns
        -------
        The bound arguments, with their values coerced.
        """
        warnings.warn(
            (
                f"{self.coerce_parameters.__qualname__} has been deprecated "
                "and will be removed in version 2.0."
                f" Use {self.bind.__qualname__} instead."
            ),
            DeprecationWarning,
            stacklevel=3,
        )
        coerced = copy.copy(bound)
        params = bound.signature.parameters
        for name, value in bound.arguments.items():
            param: inspect.Parameter = params[name]
            if self.should_coerce(param, value):
                coerced_value = self.coerce_parameter(param, value)
                coerced.arguments[name] = coerced_value

        return coerced

    def resolve(
        self,
        annotation: Any,
        *,
        name: str = None,
        default: Any = _Empty,
        param_kind: inspect._ParameterKind = _Empty,
    ) -> Optional[ResolvedAnnotation]:
        if self.coerceable(annotation):
            origin = self.get_origin(annotation)
            resolved = self.registry.check(
                origin, annotation, default=default, param_kind=param_kind, name=name
            )
            return resolved

    def annotations(self, obj) -> Annotations:
        if hasattr(obj, _TYPIC_ANNOS_NAME):
            return _annosgetter(obj)

        hints = cached_type_hints(obj)
        sig = cached_signature(obj)
        params: Mapping[str, inspect.Parameter] = sig.parameters
        ann = {}
        for name in set(params) | set(hints):
            param = params.get(name)
            hint = hints.get(name)
            annotation = hint or param.annotation
            annotation = checks.resolve_supertype(annotation)
            default = param.default if param else _Empty
            kind = param.kind if param else _Empty
            resolved = self.resolve(
                annotation, default=default, param_kind=kind, name=name
            )
            if resolved:
                ann[name] = resolved
        setattr(obj, _TYPIC_ANNOS_NAME, ann)
        return ann

    @staticmethod
    def _bind_posargs(
        arguments: Dict[str, Any],
        params: Deque[inspect.Parameter],
        annos: Dict[str, ResolvedAnnotation],
        args: Deque[Any],
        kwargs: Dict[str, Any],
    ) -> Tuple[Any]:
        posargs = list()
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
                if anno:
                    value = anno.coerce(value)
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
            value = anno.coerce(val) if anno else val
            argumentsset(name, value)
            posargsadd(name)

        if args:
            raise TypeError(_TOO_MANY_POS) from None

        return tuple(posargs)

    @staticmethod
    def _bind_kwdargs(
        arguments: Dict[str, Any],
        params: Deque[inspect.Parameter],
        annos: Dict[str, ResolvedAnnotation],
        kwargs: Dict[str, Any],
        partial: bool = False,
    ) -> Tuple[str]:
        # Bind any key-word arguments
        kwdargs = list()
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

            try:
                val = kwargspop(name)
                if kind == _POSITIONAL_ONLY:
                    raise TypeError(
                        f"{name!r} parameter is positional only,"
                        "but was passed as a keyword."
                    )
                value = anno.coerce(val) if anno else val
                argumentsset(name, value)
                kwdargsadd(name)
            except KeyError:
                if not partial and param.default is _empty:
                    raise TypeError(f"missing required argument: {name!r}")
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
        arguments = dict()
        returns = annos.pop(_RETURN_KEY, None)
        args = deque(args)
        parameters = deque(params.values())
        # Bind any positional arguments.
        posargs = self._bind_posargs(arguments, parameters, annos, args, kwargs)
        # Bind any keyword arguments.
        kwdargs = self._bind_kwdargs(arguments, parameters, annos, kwargs, partial)
        return BoundArguments(annos, params, arguments, returns, posargs, kwdargs)

    def bind(
        self, obj: Type, *args: Any, partial: bool = False, **kwargs: Mapping[str, Any]
    ) -> BoundArguments:
        """Bind a received input to a callable or object's signature.

        If we can locate an annotation for any args or kwargs, we'll automatically coerce as well.

        This implementation is similar to :py:meth`inspect.Signature.bind`, but is ~10-20% faster.
        We also use a cached the signature to avoid the expense of that call if possible.

        Parameters
        ----------
        obj
            The object you wish to bind your input to.
        *args
            The given positional args.
        partial
            Whether to bind a partial input.
        **kwargs
            The given keyword args.

        Returns
        -------
        The bound and coerced arguments.

        Raises
        ------
        TypeError
            If we can't match up the received input to the signature
        """
        return self._bind_input(
            annos=self.annotations(obj),
            params=cached_signature(obj).parameters,
            args=args,
            kwargs=kwargs,
            partial=partial,
        )

    @staticmethod
    def _bind_wrapper(wrapper: Callable, func: Callable):  # pragma: nocover
        wrapper.__defaults__ = (wrapper.__defaults__ or ()) + (func.__defaults__ or ())
        wrapper.__kwdefaults__ = wrapper.__kwdefaults__ or {}.update(
            func.__kwdefaults__ or {}
        )
        wrapper.__signature__ = cached_signature(func)

    def wrap(self, func: Callable) -> Callable:
        """Wrap a callable to automatically enforce type-coercion.

        Parameters
        ----------
        func :
            The callable for which you wish to ensure type-safety

        See Also
        --------
        :py:func:`inspect.signature`
        :py:method:`inspect.Signature.bind`
        """
        self.annotations(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            bound = self.bind(func, *args, **kwargs)
            return func(*bound.args, **bound.kwargs)

        if TYPE_CHECKING:  # pragma: nocover
            self._bind_wrapper(wrapper, func)

        return wrapper

    def wrap_cls(self, klass: Type[object]):
        """Wrap a class to automatically enforce type-coercion on init.

        Notes
        -----
        While ``Coercer.wrap`` will work with classes alone, it changes the signature of the
        object to a function, there-by breaking inheritance. This follows a similar pattern to
        :func:`dataclasses.dataclasses`, which executes the function when wrapped, preserving the
        signature of the target class.

        Parameters
        ----------
        klass
            The class you wish to patch with coercion.
        """
        # Resolve the annotations. This will store them on the object as well
        self.annotations(klass)

        def wrapper(cls_):
            # Frozen dataclasses don't use the native setattr
            # So we wrap the init. This should be fine.
            if (
                hasattr(cls_, "__dataclass_params__")
                and cls_.__dataclass_params__.frozen
            ):
                cls_.__init__ = self.wrap(cls_.__init__)
            else:
                setattr(cls_, _ORIG_SETTER_NAME, _get_setter(cls_))
                cls_.__setattr__ = __setattr_coerced__
            return cls_

        wrapped = wrapper(klass)
        wrapped.__signature__ = cached_signature(klass)
        return wrapped


def __setattr_coerced__(self, name, value):
    ann = _annosgetter(self)
    value = ann[name].coerce(value) if name in ann else value
    _origsettergetter(self)(name, value)


def _get_setter(cls: Type, bases: Tuple[Type, ...] = None):
    bases = bases or cls.__bases__
    setter = cls.__setattr__
    if setter is __setattr_coerced__:
        for base in bases:
            name = (
                _ORIG_SETTER_NAME if hasattr(base, _ORIG_SETTER_NAME) else "__setattr__"
            )
            setter = getattr(base, name, None)
            if setter is not __setattr_coerced__:
                break
    return setter


coerce = TypeCoercer()
coerce_parameters = coerce.coerce_parameters
coerceable = coerce.coerceable
annotations = coerce.annotations
typed_callable = coerce.wrap
typed_class = coerce.wrap_cls
bind = coerce.bind


def typed(cls_or_callable: Union[Callable, Type[object]]):
    """A convenience function which automatically selects the correct wrapper.

    Parameters
    ----------
    cls_or_callable
        The target object.

    Returns
    -------
    The target object, appropriately wrapped.
    """
    _annotations_ = {"return": cls_or_callable}
    typed.__annotations__.update(_annotations_)
    if inspect.isclass(cls_or_callable):
        typed_class.__annotations__.update(_annotations_)
        return typed_class(cls_or_callable)
    elif isinstance(cls_or_callable, Callable):
        typed_callable.__annotations__.update(_annotations_)
        return typed_callable(cls_or_callable)
    else:
        raise TypeError(
            f"{__name__} requires a callable or class. Provided: {type(cls_or_callable)}: {cls_or_callable}"
        )
