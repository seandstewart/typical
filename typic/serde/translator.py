import functools
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
)

from typic.checks import iscollectiontype, ismappingtype
from typic.gen import Block, Keyword
from typic.util import (
    cached_type_hints,
    cached_simple_attributes,
    safe_get_params,
    get_unique_name,
    get_defname,
)

if TYPE_CHECKING:
    from .common import Annotation, TranslatorT, SerdeProtocol, FieldIteratorT
    from .resolver import Resolver


_itemscaller = methodcaller("items")
_valuescaller = methodcaller("values")
_iter = iter


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

    def __init__(self, resolver: "Resolver"):
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
        kind: inspect._ParameterKind, hints: Mapping[str, Type],
    ) -> Mapping[str, inspect.Parameter]:
        return {x: inspect.Parameter(x, kind, annotation=y) for x, y in hints.items()}

    @staticmethod
    def _fields_from_attrs(kind: inspect._ParameterKind, attrs: Tuple[str, ...]):
        return {x: inspect.Parameter(x, kind) for x in attrs}

    @functools.lru_cache(maxsize=None)
    def get_fields(
        self, type: Type, as_source: bool = False
    ) -> Optional[Mapping[str, inspect.Parameter]]:
        """Get the fields for the given type.

        Notes
        -----
        We want this to be the type's signature, we really do. But if for some reason we
        can't make that happen, we fallback to a few known, semi-reliable methods for
        making this happen.
        """
        # Try first with the signature of the target if this is the target type
        params = safe_get_params(type)
        undefined = self.sig_is_undef(params)
        if not as_source and not undefined:
            return params
        # Now we start building a fake signature
        k = inspect.Parameter.POSITIONAL_OR_KEYWORD
        # **kwargs
        if self.kw_only(params):
            k = inspect.Parameter.KEYWORD_ONLY
        # *args
        elif self.pos_only(params):
            k = inspect.Parameter.POSITIONAL_ONLY
        # Fetch any type hints and try to use those.
        hints = cached_type_hints(type)
        if hints:
            return self._fields_from_hints(k, hints)
        # Fallback to the target object's defined attributes
        # This will basically work for ORM models, Pydantic models...
        # Anything that defines the instance using the class body.
        attrs = cached_simple_attributes(type)
        if attrs:
            return self._fields_from_attrs(k, attrs)
        # Can't be done.
        return None if undefined else params

    @functools.lru_cache(maxsize=None)
    def iterator(self, type: Type, values: bool = False) -> "FieldIteratorT":
        """Get an iterator function for a given type, if possible."""

        if ismappingtype(type):
            iter = _valuescaller if values else _itemscaller
            return iter

        if iscollectiontype(type):
            return _iter

        fields = self.get_fields(type, as_source=True) or {}

        if fields:
            func_name = get_defname("iterator", (type, values))
            oname = "o"
            ctx: dict = {}
            with Block(ctx) as main:
                with main.f(func_name, Block.p(oname)) as func:
                    if values:
                        for f in fields:
                            func.l(f"{Keyword.YLD} {oname}.{f}")
                    else:
                        for f in fields:
                            func.l(f"{Keyword.YLD} {f!r}, {oname}.{f}")

            return main.compile(name=func_name, ns=ctx)

        raise TranslatorTypeError(
            f"Cannot get iterator for type {type!r}, unable to determine fields."
        ) from None

    @staticmethod
    def _get_name(source: Type, target: Type) -> str:
        return get_defname("translator", (source, target))

    @staticmethod
    def _iter_field_assigns(
        fields: Mapping[str, inspect.Parameter],
        oname: str,
        protos: Mapping[str, "SerdeProtocol"],
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

    @functools.lru_cache(maxsize=None)
    def _compile_translator(self, source: Type, target: Type) -> "TranslatorT":
        # Get the target fields for translation.
        target_fields = self.get_fields(target)
        if target_fields is None:
            raise TranslatorTypeError(
                f"Cannot translate to type {target!r}. "
                f"Unable to determine target fields."
            ) from None

        # Ensure that the target fields are a subset of the source fields.
        # We treat the target fields as the parameters for the target,
        # so this must be true.
        fields = self.get_fields(source, as_source=True) or {}
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

    def factory(self, annotation: "Annotation", target: Type) -> "TranslatorT":
        """Generate a translator for :py:class:`typic.Annotation` -> ``type``."""
        return self._compile_translator(annotation.resolved, target)
