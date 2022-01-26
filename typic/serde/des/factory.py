from __future__ import annotations

import dataclasses
import inspect
import pathlib
import re
from collections import deque, abc
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
    TYPE_CHECKING,
    Optional,
    cast,
)

from typic import checks, gen
from typic.strict import STRICT_MODE
from typic.util import slotted, get_defname
from typic.common import ObjectT
from typic.compat import TypeGuard
from typic.serde.common import (
    DeserializerT,
    DeserializerRegistryT,
    SerdeConfig,
    Annotation,
)
from typic.serde.des import routines

if TYPE_CHECKING:  # pragma: nocover
    from typic.serde.resolver import Resolver

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
    >>> typic.transmute(dict, '{"foo": "bar"}')
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

    @staticmethod
    def _get_name(annotation: Annotation) -> str:
        return get_defname("deserializer", annotation)

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
            ).deserializer()

        if origin in self.UNRESOLVABLE:
            return cast("DeserializerT", lambda val: val)
        # Move through our queue.
        for check, Routine in self._HANDLERS.items():
            # If this is a valid type for this handler,
            #   write the deserializer.
            if check(origin, args, aliased):
                return Routine(annotation, self.resolver, namespace).deserializer()

        return routines.FieldsDeserializerRoutine(
            annotation, self.resolver, namespace
        ).deserializer()

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
            deserializer = self._build_des(annotation, namespace)
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


HandlerCheckT = Callable[
    [Type[ObjectT], Tuple[Any, ...], bool], TypeGuard[Type[ObjectT]]
]
