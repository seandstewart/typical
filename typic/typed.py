#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import collections.abc
import copy
import datetime
import functools
import inspect
from collections import deque
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
)

import dateutil.parser

from typic import checks
from typic.eval import safe_eval

__all__ = (
    "resolve_annotations",
    "coerce",
    "coerce_parameters",
    "typed",
    "typed_class",
    "typed_callable",
)


@functools.lru_cache(typed=True)
def _should_resolve(param: inspect.Parameter) -> bool:
    return param.annotation is not param.empty and isinstance(
        param.annotation, (str, ForwardRef)
    )


@functools.lru_cache(typed=True)
def cached_signature(obj: Callable) -> inspect.Signature:
    return inspect.signature(obj)


@functools.lru_cache(typed=True)
def cached_type_hints(obj: Callable) -> dict:
    return get_type_hints(obj)


def resolve_annotations(
    cls_or_callable: Union[Type[object], Callable], sig: inspect.Signature
):
    """Resolve all type-hints in the signature for the class or callable.

    Parameters
    ----------
    cls_or_callable
        A class or callable object.
    sig
        The signature of the object.

    Returns
    -------
    A new signature with all annotations resolved, unless a NameError is raised.
    """
    parameters = dict(sig.parameters)
    to_resolve = {x: y for x, y in parameters.items() if _should_resolve(y)}
    if to_resolve:  # nocover
        hints = get_type_hints(cls_or_callable)
        resolved = {x: y.replace(annotation=hints[x]) for x, y in to_resolve.items()}
        parameters.update(resolved)
        return sig.replace(parameters=parameters.values())
    return sig


class _Coercer(NamedTuple):
    check: Callable
    coerce: Callable
    ident: str = None
    check_origin: bool = True

    @property
    @functools.lru_cache(1)
    def key(self):
        return self.ident or self.coerce.__qualname__

    @property
    @functools.lru_cache(1)
    def parameters(self):
        return cached_signature(self.coerce).parameters


class Coercer:
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
        self.registry = self.Registry(self)
        self.register = self.registry.register

    class Registry:
        __registry: Deque[_Coercer] = deque()
        __user_registry: Deque[_Coercer] = deque()

        def __init__(self, cls: "Coercer"):
            self.cls = cls
            self._register_builtin_coercers()

        def register(self, coercer: Callable, check: Callable, ident: str = None):
            _coercer = _Coercer(check=check, coerce=coercer, ident=ident)
            type(self).__user_registry.appendleft(_coercer)

        def _register_builtin_coercers(self):
            """Build the deque of builtin coercers.

            Order here is important!
            """
            type(self).__registry.extend(
                [
                    # Check if the annotaion is a date-type
                    _Coercer(checks.isdatetype, self.cls._coerce_datetime),
                    # Check if the annotation maps directly to a builtin-type
                    # We use the raw annotation here, not the origin, since we account for
                    # subscripted generics later.
                    _Coercer(
                        checks.isbuiltintype,
                        self.cls._coerce_builtin,
                        check_origin=False,
                    ),
                    # Check for a class with a ``from_dict()`` factory
                    _Coercer(checks.isfromdictclass, self.cls._coerce_from_dict),
                    # Enums are iterable and evaluate as a Collection,
                    # so we need to short-circuit the next set of checks
                    _Coercer(checks.isenumtype, self.cls._coerce_enum),
                    # Check for a subscripted generic of the ``Mapping`` type
                    _Coercer(checks.ismappingtype, self.cls._coerce_mapping),
                    # Check for a subscripted generic of the ``Collection`` type
                    # This *must* come after the check for a ``Mapping`` type
                    _Coercer(checks.iscollectiontype, self.cls._coerce_collection),
                    # Finally, try a generic class coercion.
                    _Coercer(inspect.isclass, self.cls._coerce_class),
                ]
            )

        @functools.lru_cache(None, typed=True)
        def check(self, origin: Type, annotation: Any) -> Optional[_Coercer]:
            """Locate the """
            for coercer in type(self).__user_registry + type(self).__registry:
                if coercer.check(origin if coercer.check_origin else annotation):
                    return coercer

        def coerce(self, value: Any, origin: Type, annotation: Any) -> Any:
            coercer = self.check(origin, annotation)
            if coercer:
                kwargs = {"value": value}
                if "origin" in coercer.parameters:
                    kwargs["origin"] = origin
                if "annotation" in coercer.parameters:
                    kwargs["annotation"] = annotation
                return coercer.coerce(**kwargs)
            return value

    @classmethod
    def _check_generics(cls, hint: Any):
        return cls.GENERIC_TYPE_MAP.get(hint, hint)

    @classmethod
    def get_origin(cls, annotation: Any) -> Any:
        """Get origins for subclasses of typing._SpecialForm, recursive"""
        # Resolve custom NewTypes, recursively.
        actual = checks.resolve_supertype(annotation)
        # Extract the origin of the annotation, recursively.
        actual = getattr(actual, "__origin__", actual)
        if checks.isoptionaltype(annotation) or checks.isclassvartype(annotation):
            return cls.get_origin(annotation.__args__[0])

        # provide defaults for generics
        if not checks.isbuiltintype(actual):
            actual = cls._check_generics(actual)

        return actual

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

        coerced = annotation(value)
        return coerced

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
        arg = annotation.__args__[0] if annotation.__args__ else None
        if arg and not isinstance(arg, TypeVar):
            return self._coerce_builtin(
                [
                    self.coerce_value(x, arg)
                    for x in self._coerce_builtin(value, origin)
                ],
                origin,
            )
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
        args = tuple(
            self.get_origin(x)
            for x in annotation.__args__
            if not isinstance(x, TypeVar)
        )
        if args:
            key_type, value_type = args
            value = self._coerce_builtin(
                {
                    self.coerce_value(x, key_type): self.coerce_value(y, value_type)
                    for x, y in self._coerce_builtin(value, origin).items()
                },
                origin,
            )
            return value

        return self._coerce_builtin(value, origin)

    def _coerce_from_dict(self, origin: Type, value: Dict) -> Any:
        if isinstance(value, origin):
            return value
        if isinstance(value, (str, bytes)):
            processed, value = safe_eval(value)
        bound = self.coerce_parameters(inspect.signature(origin).bind(**value))
        return origin.from_dict(dict(bound.arguments))

    def _coerce_class(self, value: Any, origin: Type, annotation: Any) -> Any:
        processed, value = (
            safe_eval(value) if isinstance(value, str) else (False, value)
        )
        coerced = value
        if isinstance(value, (Mapping, dict)):
            bound = self.coerce_parameters(inspect.signature(origin).bind(**value))
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
        # Otherwise, start over with the origin if this is an Optional or ClassVar.
        elif optional or checks.isclassvartype(annotation):
            return self.coerce_value(value, origin)

        coerced = self.registry.coerce(value, origin, annotation)

        return coerced

    __call__ = coerce_value  # alias for easy access to most common operation.

    @classmethod
    def should_coerce(cls, parameter: inspect.Parameter, value: Any) -> bool:
        """Check whether we need to coerce the given value to the parameter's annotation.

            1. Ignore values provided by defaults, even if the type doesn't match the annotation.
                - Handles values which default to ``None``, for instance.
            2. Only check parameters which have an annotation.

        Parameters
        ----------
        parameter
            The parameter in question, provided by :func:`inspect.signature`
        value
            The value to check for coercion.
        """
        origin = cls.get_origin(parameter.annotation)
        is_default = (
            parameter.default is not parameter.empty and value == parameter.default
        )
        has_annotation = parameter.annotation is not parameter.empty
        special = (
            isinstance(origin, (str, ForwardRef))
            or origin in cls.UNRESOLVABLE
            or type(origin) in cls.UNRESOLVABLE
        )
        args = getattr(parameter.annotation, "__args__", None)
        return (
            not is_default
            and has_annotation
            and not special
            and (not isinstance(value, origin) or args)
        )

    def coerce_parameter(self, param: inspect.Parameter, value: Any) -> Any:
        """Coerce the value of a parameter to its appropriate type."""
        if param.kind == param.VAR_POSITIONAL:
            coerced_value = tuple(self.coerce_value(x, param.annotation) for x in value)
        elif param.kind == param.VAR_KEYWORD:
            coerced_value = {
                x: self.coerce_value(y, param.annotation) for x, y in value.items()
            }
        else:
            coerced_value = self.coerce_value(value, param.annotation)
        return coerced_value

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
        to_coerce = {
            x: y
            for x, y in bound.arguments.items()
            if self.should_coerce(bound.signature.parameters[x], y)
        }
        # return a new copy to prevent any unforeseen side-effects
        coerced = copy.copy(bound)
        for name, value in to_coerce.items():
            param: inspect.Parameter = bound.signature.parameters[name]
            coerced_value = self.coerce_parameter(param, value)
            coerced.arguments[name] = coerced_value

        return coerced

    @staticmethod
    def bind_wrapper(wrapper: Callable, func: Callable):
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

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            sig = resolve_annotations(func, inspect.signature(func))
            bound = self.coerce_parameters(sig.bind(*args, **kwargs))
            return func(*bound.args, **bound.kwargs)

        self.bind_wrapper(wrapper, func)

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

        def wrapper(cls_):
            cls_.__init__ = self.wrap(cls_.__init__)
            cls_.__setattr__ = __setattr_coerced__
            return cls_

        wrapped = wrapper(klass)
        wrapped.__signature__ = cached_signature(klass)
        return wrapped


def __setattr_coerced__(self, name, value):
    # we use caching here because we're making the relatively safe bet
    # that the annotation won't change after the class is initialized.
    sig = cached_signature(type(self))
    hints = cached_type_hints(type(self))
    # We do this to support when a parametrized attribute can default to None,
    # but isn't marked as Optional.
    if name in sig.parameters:
        param = sig.parameters[name]
        value = (
            coerce.coerce_parameter(param, value)
            if coerce.should_coerce(param, value)
            else value
        )
    # Otherwise use the type-hint at face-value.
    elif name in hints:
        value = coerce(value, hints[name])
    super(type(self), self).__setattr__(name, value)


coerce = Coercer()
coerce_parameters = coerce.coerce_parameters
typed_callable = coerce.wrap
typed_class = coerce.wrap_cls


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
