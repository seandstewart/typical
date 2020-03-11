import functools
import inspect
from typing import TYPE_CHECKING, Type, Mapping, Tuple, Optional

from typic.gen import Block, Keyword
from typic.util import (
    cached_type_hints,
    cached_simple_attributes,
    hexhash,
    safe_get_params,
    get_name,
)

if TYPE_CHECKING:
    from .common import Annotation, TranslatorT


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

    def sig_is_undef(self, params: Mapping[str, inspect.Parameter]) -> bool:
        return (not params) or {x.kind for x in params.values()}.issubset(
            self.VAR_KINDS
        )

    def kw_only(self, params: Mapping[str, inspect.Parameter]) -> bool:
        return not any(x.kind in self.POS_KINDS for x in params.values())

    def pos_only(self, params: Mapping[str, inspect.Parameter]) -> bool:
        return not any(x.kind in self.KWD_KINDS for x in params.values())

    @staticmethod
    def _fields_from_hints(
        kind: inspect._ParameterKind, hints: Mapping[str, Type],
    ) -> Mapping[str, inspect.Parameter]:
        return {x: inspect.Parameter(x, kind, annotation=y) for x, y in hints.items()}

    @staticmethod
    def _fields_from_attrs(kind: inspect._ParameterKind, attrs: Tuple[str, ...]):
        return {x: inspect.Parameter(x, kind) for x in attrs}

    @functools.lru_cache(maxsize=None)
    def get_fields(self, target: Type) -> Optional[Mapping[str, inspect.Parameter]]:
        """Get the fields for the given type.

        Notes
        -----
        We want this to be the type's signature, we really do. But if for some reason we
        can't make that happen, we fallback to a few known, semi-reliable methods for
        making this happen.
        """
        # Try first with the signature of the target
        params = safe_get_params(target)
        if not self.sig_is_undef(params):
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
        hints = cached_type_hints(target)
        if hints:
            return self._fields_from_hints(k, hints)
        # Fallback to the target object's defined attributes
        # This will basically work for ORM models, Pydantic models...
        # Anything that defines the instance using the class body.
        attrs = cached_simple_attributes(target)
        if attrs:
            return self._fields_from_attrs(k, attrs)
        # Can't be done.
        return None

    @staticmethod
    def _get_name(source: Type, target: Type) -> str:
        return f"translator_{hexhash(source, target)}"

    @functools.lru_cache(maxsize=None)
    def _compile_translator(self, source: Type, target: Type) -> "TranslatorT":
        # Get the target fields for translation.
        target_fields = self.get_fields(target)
        if target_fields is None:
            raise TranslatorTypeError(
                f"Cannot translate to type {target!r}. "
                f"Unable to determine target fields."
            )

        # Ensure that the target fields are a subset of the source fields.
        # We treat the target fields as the parameters for the target,
        # so this must be true.
        fields = {*(self.get_fields(source) or {})}
        if not fields.issuperset(target_fields.keys()):
            diff = (*(target_fields.keys() - fields),)
            raise TranslatorValueError(
                f"{source!r} can't be translated to {target!r}. "
                f"Source is missing fields: {diff}."
            )
        # Build the translator.
        anno_name = get_name(source)
        target_name = get_name(target)
        func_name = self._get_name(source, target)
        oname = "o"
        ctx = {target_name: target, anno_name: source}
        with Block(ctx) as main:
            with main.f(func_name, Block.p(oname)) as func:
                args = ", ".join(
                    (
                        f"{oname}.{f}"
                        if p.kind == p.POSITIONAL_ONLY
                        else f"{f}={oname}.{f}"
                        for f, p in target_fields.items()
                    )
                )
                func.l(f"{Keyword.RET} {target_name}({args})")
        trans = main.compile(name=func_name, ns=ctx)
        return trans

    def factory(self, annotation: "Annotation", target: Type) -> "TranslatorT":
        """Generate a translator for :py:class:`typic.Annotation` -> ``type``."""
        return self._compile_translator(annotation.resolved, target)


translator = TranslatorFactory()
