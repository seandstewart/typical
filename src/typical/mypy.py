from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional
from typing import Type as TypingType

from mypy.nodes import (
    ARG_NAMED_OPT,
    ARG_POS,
    MDEF,
    Argument,
    SymbolTableNode,
    TypeVarExpr,
    Var,
)
from mypy.plugin import ClassDefContext, MethodContext, Plugin
from mypy.plugins.common import _get_decorator_bool_argument, add_method_to_class
from mypy.plugins.dataclasses import DataclassTransformer
from mypy.semanal import SemanticAnalyzer
from mypy.types import AnyType, Type, TypeOfAny, TypeType, TypeVarType

if TYPE_CHECKING:
    from typing_extensions import Final  # noqa: F401

typic_class_maker_decorators = {
    "klass",
    "settings",
    "typic.klass",
    "typic.klass.klass",
    "typic.settings",
    "typic.api.settings",
}  # type: Final

typic_class_maker = "typic.api.wrap_cls"

typic_methods = {
    "primitive",
    "transmute",
    "validate",
    "schema",
    "tojson",
    "__iter__",
    "iterate",
    "translate",
}  # type: Final

SELF_TVAR_NAME = "_TT"


def typic_method_callback(ctx: MethodContext) -> Type:
    return ctx.default_return_type


def plugin(version: str) -> TypingType[Plugin]:
    """
    `version` is the mypy version string
    We might want to use this to print a warning if the mypy version being used is
    newer, or especially older, than we expect (or need).
    """
    return TypicPlugin


class TypicPlugin(Plugin):
    def get_method_hook(
        self, fullname: str
    ) -> Optional[Callable[[MethodContext], Type]]:
        if any(fullname.endswith(x) for x in typic_methods):
            return typic_method_callback
        return None

    def get_class_decorator_hook(
        self, fullname: str
    ) -> Optional[Callable[[ClassDefContext], None]]:
        if fullname in typic_class_maker_decorators:
            return typic_klass_maker_callback
        return None


class TypicTransformer:
    """A transformer for allowing MyPy to recognize typical klasses."""

    def __init__(self, ctx: ClassDefContext):
        self._ctx = ctx
        self.dclass = DataclassTransformer(self._ctx)

    def transform(self) -> None:
        self.dclass.transform()
        self._add_self_tvar_expr(self._ctx)
        jsonschema = _get_decorator_bool_argument(self._ctx, "jsonschema", True)
        if jsonschema:
            self.add_schema_method()
        self.add_primitive_method()
        self.add_transmute_method()
        self.add_validate_method()
        self.add_json_method()
        self.add_translate_method()
        self.add_iterate_method()
        self.add_iter_method()

    @staticmethod
    def _get_tvar_name(name: str, info) -> str:
        return f"{info.fullname}.{name}"

    def _get_tvar_self_name(self) -> str:
        return self._get_tvar_name(SELF_TVAR_NAME, self._ctx.cls.info)

    def _add_tvar_expr(self, name: str, ctx):
        info = ctx.cls.info
        obj_type = ctx.api.named_type("builtins.object")
        self_tvar_expr = TypeVarExpr(
            name, self._get_tvar_name(name, info), [], obj_type
        )
        info.names[name] = SymbolTableNode(MDEF, self_tvar_expr)

    def _add_self_tvar_expr(self, ctx):
        self._add_tvar_expr(SELF_TVAR_NAME, ctx)

    def _get_tvar_def(self, name: str, ctx):
        obj_type = ctx.api.named_type("builtins.object")
        return TypeVarType(
            SELF_TVAR_NAME, self._get_tvar_name(name, ctx.cls.info), -1, [], obj_type
        )

    def add_schema_method(self):
        ctx = self._ctx
        api: SemanticAnalyzer = ctx.api
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        bool_type = api.named_type("builtins.bool")
        str_type = api.named_type("builtins.str")
        primarg = Argument(Var("primitive", bool_type), bool_type, None, ARG_NAMED_OPT)
        fmtarg = Argument(Var("format", str_type), str_type, None, ARG_NAMED_OPT)
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="schema",
            args=[primarg, fmtarg],
            return_type=AnyType(TypeOfAny.unannotated),
            self_type=self_tvar_def,
            tvar_def=self_tvar_def,
            is_classmethod=True,
        )

    def add_primitive_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        bool_type = ctx.api.named_type("builtins.bool")
        arg = Argument(Var("lazy", bool_type), bool_type, None, ARG_NAMED_OPT)
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="primitive",
            args=[arg],
            return_type=AnyType(TypeOfAny.unannotated),
            self_type=self_tvar_def,
            tvar_def=self_tvar_def,
        )

    def add_json_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        bool_type = ctx.api.named_type("builtins.bool")
        int_type = ctx.api.named_type("builtins.int")
        str_type = ctx.api.named_type("builtins.str")
        indent = Argument(Var("indent", int_type), int_type, None, ARG_NAMED_OPT)
        ensure = Argument(
            Var("ensure_ascii", bool_type), bool_type, None, ARG_NAMED_OPT
        )
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="tojson",
            args=[indent, ensure],
            return_type=str_type,
            self_type=self_tvar_def,
            tvar_def=self_tvar_def,
        )

    def add_validate_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        arg_type = AnyType(TypeOfAny.explicit)
        arg = Argument(Var("obj", arg_type), arg_type, None, ARG_POS)
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="validate",
            args=[arg],
            return_type=self_tvar_def,
            self_type=TypeType(self_tvar_def),
            tvar_def=self_tvar_def,
            is_classmethod=True,
        )

    def add_transmute_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        arg_type = AnyType(TypeOfAny.explicit)
        arg = Argument(Var("obj", arg_type), arg_type, None, ARG_POS)
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="transmute",
            args=[arg],
            return_type=self_tvar_def,
            self_type=TypeType(self_tvar_def),
            tvar_def=self_tvar_def,
            is_classmethod=True,
        )

    def add_translate_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        r_type = AnyType(TypeOfAny.explicit)
        arg_type = TypeType(r_type)
        arg = Argument(Var("target", arg_type), arg_type, None, ARG_POS)
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="translate",
            args=[arg],
            return_type=r_type,
            self_type=self_tvar_def,
            tvar_def=self_tvar_def,
        )

    def add_iterate_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        r_type = AnyType(TypeOfAny.explicit)
        bool_type = ctx.api.named_type("builtins.bool")
        arg = Argument(Var("values", bool_type), bool_type, None, ARG_NAMED_OPT)
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="iterate",
            args=[arg],
            return_type=r_type,
            self_type=self_tvar_def,
            tvar_def=self_tvar_def,
        )

    def add_iter_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        r_type = AnyType(TypeOfAny.explicit)
        bool_type = ctx.api.named_type("builtins.bool")
        arg = Argument(Var("values", bool_type), bool_type, None, ARG_NAMED_OPT)
        add_method_to_class(
            api=ctx.api,
            cls=ctx.cls,
            name="__iter__",
            args=[arg],
            return_type=r_type,
            self_type=self_tvar_def,
            tvar_def=self_tvar_def,
        )


def typic_klass_maker_callback(ctx: ClassDefContext) -> None:
    transformer = TypicTransformer(ctx)
    transformer.transform()
