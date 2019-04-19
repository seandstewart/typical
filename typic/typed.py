#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import copy
import datetime
import enum
import functools
import inspect
import collections.abc
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
    Optional,
    ClassVar,
)

import dateutil.parser

from typic.eval import safe_eval


__all__ = (
    "BUILTIN_TYPES",
    "isbuiltintype",
    "isclassvar",
    "isoptional",
    "resolve_annotations",
    "coerce",
    "coerce_parameters",
    "typed",
    "typed_class",
    "typed_callable",
    "resolve_supertype",
)

# Python stdlib and Python documentation have no "definitive list" of builtin-**types**, despite the fact that they are
# well-known. The closest we have is https://docs.python.org/3.7/library/functions.html, which clumps the
# builtin-types with builtin-functions. Despite clumping these types with functions in the documentation, these types
# eval as False when compared to types.BuiltinFunctionType, which is meant to be an alias for the builtin-functions
# listed in the documentation.
#
# All this to say, here we are with a manually-defined set of builtin-types. This probably won't break anytime soon,
# but we shall see...
BUILTIN_TYPES = frozenset(
    (int, bool, float, str, bytes, bytearray, list, set, frozenset, tuple, dict)
)


def resolve_supertype(annotation: Any) -> Any:
    """Resolve NewTypes, recursively."""
    if hasattr(annotation, "__supertype__"):
        return resolve_supertype(annotation.__supertype__)
    return annotation


@functools.lru_cache(typed=True)
def isbuiltintype(obj: Any) -> bool:
    """Check whether the provided object is a builtin-type"""
    return (
        resolve_supertype(obj) in BUILTIN_TYPES
        or resolve_supertype(type(obj)) in BUILTIN_TYPES
    )


@functools.lru_cache(typed=True)
def isoptional(obj: Any) -> bool:
    """Test whether an annotation is Optional"""
    args = getattr(obj, "__args__", ())
    return (
        len(args) == 2
        and args[-1]
        is type(None)  # noqa: E721 - we don't know what args[-1] is, so this is safer
        and getattr(obj, "__origin__", obj) in {Optional, Union}
    )


@functools.lru_cache(typed=True)
def isclassvar(obj: Any) -> bool:
    """Test whether an annotation is a ClassVar annotation."""
    return getattr(obj, "__origin__", obj) is ClassVar


@functools.lru_cache(typed=True)
def _should_resolve(param: inspect.Parameter) -> bool:
    return param.annotation is not param.empty and isinstance(
        param.annotation, (str, ForwardRef)
    )


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

    @classmethod
    def _check_generics(cls, hint: Any):
        return cls.GENERIC_TYPE_MAP.get(hint, hint)

    @classmethod
    def get_origin(cls, annotation: Any) -> Any:
        """Get origins for subclasses of typing._SpecialForm, recursive"""
        actual = resolve_supertype(annotation)
        actual = getattr(actual, "__origin__", actual)
        if isoptional(annotation) or isclassvar(annotation):
            return cls.get_origin(annotation.__args__[0])

        # provide defaults for generics
        if not isbuiltintype(actual):
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

    @classmethod
    def _coerce_collection(
        cls, value: Any, origin: Type, annotation: Type[Collection[Any]]
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
            return cls._coerce_builtin(
                [cls.coerce_value(x, arg) for x in cls._coerce_builtin(value, origin)],
                origin,
            )
        return cls._coerce_builtin(value, origin)

    @classmethod
    def _coerce_mapping(
        cls, value: Any, origin: Type, annotation: Mapping[Any, Any]
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
            cls.get_origin(x) for x in annotation.__args__ if not isinstance(x, TypeVar)
        )
        if args:
            key_type, value_type = args
            value = cls._coerce_builtin(
                {
                    cls.coerce_value(x, key_type): cls.coerce_value(y, value_type)
                    for x, y in cls._coerce_builtin(value, origin).items()
                },
                origin,
            )
            return value

        return cls._coerce_builtin(value, origin)

    @classmethod
    def _coerce_from_dict(cls, klass: Type[object], value: Dict) -> Any:
        if isinstance(value, klass):
            return value
        if isinstance(value, (str, bytes)):
            processed, value = safe_eval(value)
        bound = cls.coerce_parameters(inspect.signature(klass).bind(**value))
        return klass.from_dict(dict(bound.arguments))

    @classmethod
    def coerce_value(cls, value: Any, annotation: Any) -> Any:
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
        annotation = resolve_supertype(annotation)
        origin = cls.get_origin(annotation)
        coerced = value
        if isoptional(annotation) and value is None:
            return
        elif isoptional(annotation) or isclassvar(annotation):
            return cls.coerce_value(value, origin)

        if annotation in {datetime.datetime, datetime.date}:
            coerced = cls._coerce_datetime(value, origin)
        elif isbuiltintype(annotation):
            coerced = cls._coerce_builtin(value, origin)
        elif inspect.isclass(origin):
            if hasattr(origin, "from_dict"):
                coerced = cls._coerce_from_dict(origin, value)
            elif issubclass(origin, enum.Enum):
                coerced = origin(value)
            elif issubclass(origin, (Mapping, dict)):
                coerced = cls._coerce_mapping(value, origin, annotation)
            elif issubclass(origin, (Collection, list)):
                coerced = cls._coerce_collection(value, origin, annotation)
            elif isinstance(value, (Mapping, dict)):
                bound = cls.coerce_parameters(inspect.signature(origin).bind(**value))
                coerced = origin(**bound.arguments)
            else:
                coerced = origin(value)

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

    @classmethod
    def coerce_parameters(cls, bound: inspect.BoundArguments) -> inspect.BoundArguments:
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
            if cls.should_coerce(bound.signature.parameters[x], y)
        }
        # return a new copy to prevent any unforeseen side-effects
        coerced = copy.copy(bound)
        for name, value in to_coerce.items():
            param: inspect.Parameter = bound.signature.parameters[name]
            if param.kind == param.VAR_POSITIONAL:
                coerced_value = tuple(
                    cls.coerce_value(x, param.annotation) for x in value
                )
            elif param.kind == param.VAR_KEYWORD:
                coerced_value = {
                    x: cls.coerce_value(y, param.annotation) for x, y in value.items()
                }
            else:
                coerced_value = cls.coerce_value(value, param.annotation)
            coerced.arguments[name] = coerced_value

        return coerced

    @classmethod
    def wrap(cls, func: Callable) -> Callable:
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
            bound = cls.coerce_parameters(sig.bind(*args, **kwargs))
            return func(*bound.args, **bound.kwargs)

        return wrapper

    @classmethod
    def wrap_cls(cls, klass: Type[object] = None):
        """Wrap a class to automatically enforce type-coercion on init.

        Notes
        -----
        While ``Coercer.wrap`` will work with classes alone, it changes the signature of the
        object to a function, there-by breaking inheritance. This follows a similar pattern to
        :func:`dataclasses.dataclasses`, which executes the function when wrapped, preserving the
        signature of the target class.

        Parameters
        ----------
        klass :
            The class you wish to patch with coercion.
        """

        def wrapper(cls_):
            cls_.__init__ = cls.wrap(cls_.__init__)
            return cls_

        return wrapper if klass is None else wrapper(klass)


coerce = Coercer()
coerce_parameters = coerce.coerce_parameters
typed_callable = coerce.wrap
typed_class = coerce.wrap_cls


def typed(
    cls_or_callable: Union[Callable, Type[object]]
) -> Union[Callable, Type[object]]:
    """A convenience function which automatically selects the correct wrapper.

    Parameters
    ----------
    cls_or_callable
        The target object.

    Returns
    -------
    The target object, appropriately wrapped.
    """
    if inspect.isclass(cls_or_callable):
        return typed_class(cls_or_callable)
    elif isinstance(cls_or_callable, Callable):
        return typed_callable(cls_or_callable)
    else:
        raise TypeError(
            f"{__name__} requires a callable or class. Provided: {type(cls_or_callable)}: {cls_or_callable}"
        )
