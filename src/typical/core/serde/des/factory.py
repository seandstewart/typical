from __future__ import annotations

import inspect
import pathlib
import re
from collections import abc, deque
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Mapping,
    Match,
    Pattern,
    Type,
    cast,
)

from typical import checks, inspection
from typical.core.annotations import ObjectT
from typical.core.constants import empty
from typical.core.interfaces import (
    Annotation,
    DeserializerRegistryT,
    DeserializerT,
    DeserializerTypeCheckT,
    SerdeConfig,
)
from typical.core.serde.des import routines

if TYPE_CHECKING:  # pragma: nocover
    from typical.core.resolver import Resolver


__all__ = ("DesFactory", "HandlerCheckT")


class DesFactory:
    """A callable class for ``des``erialzing values.

    Checks for:

        - builtin types
        - :py:mod:`typing` type annotations
        - :py:mod:`datetime` types
        - :py:mod:`uuid`
        - :py:mod:`pathlib`
        - :py:class:`typing.TypedDict`
        - :py:class:`typing.NamedTuple`
        - :py:func:`collections.namedtuple`
        - User-defined classes

    Examples
    --------
    >>> from __future__ import annotations
    >>> import typical
    >>> typical.transmute(bytes, "foo")
    b'foo'
    >>> typical.transmute(dict, '{"foo": "bar"}')
    {'foo': 'bar'}
    >>> typical.transmute(dict[str, int], '{"foo": "1"}')
    {'foo': 1}
    """

    def __init__(self, resolver: Resolver):
        self.resolver = resolver

    def factory(
        self,
        annotation: Annotation[Type[ObjectT]],
        namespace: Type = None,
    ) -> DeserializerT[ObjectT]:
        annotation.serde = annotation.serde or SerdeConfig()
        key = self._get_name(annotation)
        if key in self.__DES_CACHE:
            return self.__DES_CACHE[key]
        deserializer: DeserializerT | None = None
        for check, des in self.__USER_DESS:
            if check(annotation.resolved):
                deserializer = des
                break
        if not deserializer:
            deserializer = self._build_des(annotation, namespace)
        self.__DES_CACHE[key] = deserializer
        return deserializer

    __DES_CACHE: Dict[str, DeserializerT] = {}
    __USER_DESS: DeserializerRegistryT = deque()

    def register(self, deserializer: DeserializerT, check: DeserializerTypeCheckT):
        """Register a user-defined coercer.

        In the rare case where typic can't figure out how to coerce your annotation
        correctly, a custom coercer may be registered alongside a check function which
        returns a simple boolean indicating whether this is the correct coercer for an
        annotation.
        """
        self.__USER_DESS.appendleft((check, deserializer))

    @staticmethod
    def _get_name(annotation: Annotation) -> str:
        return inspection.get_defname("deserializer", annotation)

    def _build_des(  # noqa: C901
        self,
        annotation: Annotation[Type[ObjectT]],
        namespace: Type = None,
    ) -> DeserializerT[ObjectT]:
        args = annotation.args
        # Get the "origin" of the annotation.
        # For natives and their typing.* equivs, this will be a builtin type.
        # For SpecialForms (Union, mainly) this will be the un-subscripted type.
        # For custom types or classes, this will be the same as the annotation.
        origin = annotation.resolved_origin
        aliased = annotation.serde.fields_in.keys() != {
            *annotation.serde.fields_in.values()
        }
        if checks.isliteral(origin):
            return routines.LiteralDeserializerRoutine(
                annotation, self.resolver, namespace
            )

        if origin in self.UNRESOLVABLE:
            return cast("DeserializerT", lambda val: val)
        # Move through our queue.
        for check, Routine in self._HANDLERS.items():
            # If this is a valid type for this handler,
            #   write the deserializer.
            if check(origin, args, aliased):
                return Routine(annotation, self.resolver, namespace)

        return routines.FieldsDeserializerRoutine(annotation, self.resolver, namespace)

    UNRESOLVABLE = frozenset(
        (
            Any,
            Match,
            re.Match,  # type: ignore
            type(None),
            empty,
            Callable,
            abc.Callable,
            inspect.Parameter.empty,
        )
    )

    # Order is IMPORTANT! This is a FIFO queue.
    _HANDLERS: Mapping[HandlerCheckT, type[routines.BaseDeserializerRoutine]] = {
        # Special handler for Unions...
        lambda origin, args, aliased: checks.isuniontype(
            origin
        ): routines.UnionDeserializerRoutine,
        # Non-intersecting types (order doesn't matter here.
        lambda origin, args, aliased: checks.isdatetimetype(
            origin
        ): routines.DateTimeDeserializerRoutine,
        lambda origin, args, aliased: checks.isdatetype(
            origin
        ): routines.DateDeserializerRoutine,
        lambda origin, args, aliased: checks.istimetype(
            origin
        ): routines.TimeDeserializerRoutine,
        lambda origin, args, aliased: checks.istimedeltatype(
            origin
        ): routines.TimeDeltaDeserializerRoutine,
        lambda origin, args, aliased: checks.isuuidtype(
            origin
        ): routines.UUIDDeserializerRoutine,
        lambda origin, args, aliased: origin
        in {Pattern, re.Pattern}: routines.PatternDeserializerRoutine,
        lambda origin, args, aliased: issubclass(
            origin, pathlib.Path
        ): routines.SimpleDeserializerRoutine,
        lambda origin, args, aliased: checks.isdecimaltype(
            origin
        ): routines.SimpleDeserializerRoutine,
        lambda origin, args, aliased: issubclass(
            origin, (str, bytes, bytearray)
        ): routines.TextDeserializerRoutine,
        # MUST come before subtype check.
        lambda origin, args, aliased: (
            not args and checks.isbuiltintype(origin)
        ): routines.SimpleDeserializerRoutine,
        # Psuedo-structured containers, should check before generics.
        lambda origin, args, aliased: checks.istypeddict(
            origin
        ): routines.FieldsDeserializerRoutine,
        lambda origin, args, aliased: checks.istypedtuple(
            origin
        ): routines.FieldsDeserializerRoutine,
        lambda origin, args, aliased: checks.isnamedtuple(
            origin
        ): routines.FieldsDeserializerRoutine,
        lambda origin, args, aliased: (
            not args and not aliased and checks.isbuiltinsubtype(origin)
        ): routines.SimpleDeserializerRoutine,
        lambda origin, args, aliased: (
            not args and not aliased and checks.iscollectiontype(origin)
        ): routines.SimpleDeserializerRoutine,
        # A mapping is a collection so must come before that check.
        lambda origin, args, aliased: checks.ismappingtype(
            origin
        ): routines.MappingDeserializerRoutine,
        # A tuple is a collection so must come before that check.
        lambda origin, args, aliased: (
            checks.istupletype(origin) and args[-1] is not ...
        ): routines.FixedTupleDeserializerRoutine,
        # Generic collection handler
        lambda origin, args, aliased: checks.iscollectiontype(
            origin
        ): routines.CollectionDeserializerRoutine,
    }


HandlerCheckT = Callable[[Any, Any, Any], bool]
