from __future__ import annotations

import inspect
from operator import methodcaller
from typing import (
    TYPE_CHECKING,
    Type,
    Mapping,
    Tuple,
    Optional,
    Set,
    Dict,
    Any,
    Callable,
    Iterator,
    Union,
    Iterable,
)

from typic.checks import (
    ismappingtype,
    isiterabletype,
    isliteral,
    isnamedtuple,
    isiteratortype,
    isbuiltinsubtype,
    istypicklass,
)
from typic.compat import lru_cache
from typic.gen import Block, Keyword, ParameterKind
from typic.util import (
    cached_type_hints,
    cached_simple_attributes,
    safe_get_params,
    get_unique_name,
    get_defname,
    get_name,
)

if TYPE_CHECKING:
    from .common import Annotation, TranslatorT, SerdeProtocol
    from .resolver import Resolver


_itemscaller = methodcaller("items")
_valuescaller = methodcaller("values")


class TranslatorTypeError(TypeError):
    ...


class TranslatorValueError(ValueError):
    ...


class TranslatorFactory:
    """Translation protocol factory for higher-order objects.

    Notes
    -----
    For lower-order objects this will be functionally the same as a serializer.
    """

    KWD_KINDS = frozenset(
        {inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD}
    )
    POS_KINDS = frozenset(
        {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.VAR_POSITIONAL}
    )
    VAR_KINDS = frozenset(
        {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    )

    def __init__(self, resolver: Resolver):
        self.resolver = resolver

    def sig_is_undef(self, params: Mapping[str, inspect.Parameter]) -> bool:
        return (not params) or {x.kind for x in params.values()}.issubset(
            self.VAR_KINDS
        )

    def kw_only(self, params: Mapping[str, inspect.Parameter]) -> bool:
        return not any(x.kind in self.POS_KINDS for x in params.values())

    def pos_only(self, params: Mapping[str, inspect.Parameter]) -> bool:
        return not any(x.kind in self.KWD_KINDS for x in params.values())

    @staticmethod
    def required_fields(params: Mapping[str, inspect.Parameter]) -> Set[str]:
        return {x for x, y in params.items() if y.default is y.empty}

    @staticmethod
    def _fields_from_hints(
        kind: ParameterKind, hints: Mapping[str, Type], exclude: Set[str]
    ) -> Mapping[str, inspect.Parameter]:
        return {
            x: inspect.Parameter(x, kind, annotation=y)
            for x, y in hints.items()
            if x not in exclude
        }

    @staticmethod
    def _fields_from_attrs(
        kind: ParameterKind, attrs: Tuple[str, ...], exclude: Set[str]
    ):
        return {x: inspect.Parameter(x, kind) for x in attrs if x not in exclude}

    @lru_cache(maxsize=None)
    def get_fields(
        self, type: Type, as_source: bool = False, exclude: Iterable[str] = ()
    ) -> Optional[Mapping[str, inspect.Parameter]]:
        """Get the fields for the given type.

        Notes
        -----
        We want this to be the type's signature, we really do. But if for some reason we
        can't make that happen, we fallback to a few known, semi-reliable methods for
        making this happen.
        """
        # Try first with the signature of the target if this is the target type
        exclude = {*exclude}
        params = safe_get_params(type)
        undefined = self.sig_is_undef(params)
        if not as_source and not undefined:
            return params
        # Now we start building a fake signature
        k: ParameterKind = inspect.Parameter.POSITIONAL_OR_KEYWORD
        # **kwargs
        if self.kw_only(params):
            k = inspect.Parameter.KEYWORD_ONLY
        # *args
        elif self.pos_only(params):
            k = inspect.Parameter.POSITIONAL_ONLY
        # Fetch any type hints and try to use those.
        hints = cached_type_hints(type)
        if hints:
            return self._fields_from_hints(k, hints, exclude)
        # Fallback to the target object's defined attributes
        # This will basically work for ORM models, Pydantic models...
        # Anything that defines the instance using the class body.
        attrs = cached_simple_attributes(type)
        if attrs:
            return self._fields_from_attrs(k, attrs, exclude)
        # Can't be done.
        return None if undefined else {f: params[f] for f in params.keys() - exclude}

    @lru_cache(maxsize=None)
    def iterator(
        self,
        type: Type,
        values: bool = False,
        relaxed: bool = False,
        exclude: Tuple[str, ...] = (),
    ) -> IteratorT:
        """Get an iterator function for a given type, if possible."""
        mapping, iterable, builtin, namedtuple, typicklass = (
            ismappingtype(type),
            isiterabletype(type),
            isbuiltinsubtype(type),
            isnamedtuple(type),
            istypicklass(type),
        )
        if mapping:
            return _valuescaller if values else _itemscaller

        if (iterable, namedtuple, typicklass) == (True, False, False):
            return iter if values else enumerate

        if (builtin, iterable) == (True, False):
            raise TranslatorTypeError(
                f"Cannot get iterator for type {type.__name__!r}."
            ) from None

        fields = self.get_fields(type, as_source=True, exclude=exclude) or {}

        if not fields and not relaxed:
            raise TranslatorTypeError(
                f"Cannot get iterator for type {type.__name__!r}, "
                f"unable to determine fields."
            ) from None

        func_name = get_defname("iterator", (type, values))
        oname = "o"
        ctx: dict = {}
        with Block(ctx) as main:
            with main.f(func_name, Block.p(oname)) as func:
                if fields:
                    if values:
                        for f in fields:
                            func.l(f"{Keyword.YLD} {oname}.{f}")
                    else:
                        for f in fields:
                            func.l(f"{Keyword.YLD} {f!r}, {oname}.{f}")
                else:
                    func.l(f"{Keyword.YLD}")

        return main.compile(name=func_name, ns=ctx)

    @staticmethod
    def _get_name(source: Type, target: Type) -> str:
        return get_defname("translator", (source, target))

    @staticmethod
    def _iter_field_assigns(
        fields: Mapping[str, inspect.Parameter],
        oname: str,
        protos: Mapping[str, SerdeProtocol],
        ctx: Dict[str, Any],
    ):
        for f, p in fields.items():
            fset = f"{oname}.{f}"
            if f in protos:
                deser_name = f"{f}_deser"
                proto = protos[f]
                ctx[deser_name] = proto.transmute
                fset = f"{deser_name}({fset})"
            if p.kind != p.POSITIONAL_ONLY:
                fset = f"{f}={fset}"
            yield fset

    def _compile_iterable_translator(self, source: Type, target: Type) -> TranslatorT:
        func_name = self._get_name(source, target)
        target_name = get_name(target)
        oname = "o"
        ismapping = ismappingtype(target)
        iterator = self.iterator(source, not ismapping)
        ctx = {"iterator": iterator, target_name: target}
        with Block(ctx) as main:
            with main.f(func_name, Block.p(oname)) as func:
                retval = f"iterator({oname})"
                if not isiteratortype(target):
                    retval = f"{target_name}({retval})"
                func.l(f"{Keyword.RET} {retval}")
        return main.compile(name=func_name)

    @lru_cache(maxsize=None)
    def _compile_translator(
        self, source: Type, target: Type, exclude: Tuple[str, ...] = ()
    ) -> TranslatorT:
        if isliteral(target):
            raise TranslatorTypeError(
                f"Cannot translate to literal type: {target!r}. "
            ) from None
        if isliteral(source):
            raise TranslatorTypeError(
                f"Cannot translate from literal type: {source!r}. "
            ) from None
        # Get the target fields for translation.
        target_fields = self.get_fields(target)
        if target_fields is None:
            if isiterabletype(target):
                return self._compile_iterable_translator(source, target)
            raise TranslatorTypeError(
                f"Cannot translate to type {target!r}. "
                f"Unable to determine target fields."
            ) from None

        # Ensure that the target fields are a subset of the source fields.
        # We treat the target fields as the parameters for the target,
        # so this must be true.
        fields = self.get_fields(source, as_source=True, exclude=exclude) or {}
        fields_to_pass = {x: fields[x] for x in fields.keys() & target_fields.keys()}
        required = self.required_fields(target_fields)
        if not required.issubset(fields_to_pass.keys()):
            diff = (*(required - fields.keys()),)
            raise TranslatorValueError(
                f"{source!r} can't be translated to {target!r}. "
                f"Source is missing required fields: {diff}."
            ) from None
        protocols = self.resolver.protocols(target)

        # Build the translator.
        anno_name = get_unique_name(source)
        target_name = get_unique_name(target)
        func_name = self._get_name(source, target)
        oname = "o"
        ctx: Dict[str, Any] = {target_name: target, anno_name: source}
        with Block(ctx) as main:
            with main.f(func_name, Block.p(oname)) as func:
                args = ", ".join(
                    self._iter_field_assigns(fields_to_pass, oname, protocols, ctx)
                )
                func.l(f"{Keyword.RET} {target_name}({args})")
        trans = main.compile(name=func_name, ns=ctx)
        return trans

    def factory(
        self, annotation: "Annotation", target: Type, exclude: Tuple[str, ...] = ()
    ) -> TranslatorT:
        """Generate a translator for :py:class:`typic.Annotation` -> ``type``."""
        exclude = (*(exclude or annotation.serde.flags.exclude),)
        return self._compile_translator(annotation.resolved, target, exclude=exclude)


IteratorT = Union[Callable[[Any], Iterator[Any]], Callable[[Any], Tuple[str, Any]]]
