from typing import Optional, Callable, List, Union
from typing_extensions import Final

from mypy.semanal import SemanticAnalyzer
from mypy.semanal_shared import set_callable_name
from mypy.typeops import TypingType

from mypy.nodes import (
    MDEF,
    Argument,
    SymbolTableNode,
    Var,
    TypeVarExpr,
    Decorator,
    NameExpr,
    PassStmt,
    Block,
    FuncDef,
    FuncBase,
    SymbolNode,
    ARG_POS,
    ARG_NAMED_OPT,
)
from mypy.plugin import ClassDefContext, Plugin, MethodContext
from mypy.plugins.common import _get_decorator_bool_argument
from mypy.types import (
    Type,
    TypeVarDef,
    TypeVarType,
    AnyType,
    TypeOfAny,
    CallableType,
    TypeType,
)
from mypy.plugins.dataclasses import DataclassTransformer
from mypy.typevars import fill_typevars
from mypy.util import get_unique_redefinition_name

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
}  # type: Final

SELF_TVAR_NAME = "_TT"


def typic_method_callback(ctx: MethodContext) -> Type:
    return ctx.default_return_type


def plugin(version: str) -> "TypingType[Plugin]":
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

    @staticmethod
    def _get_tvar_name(name: str, info) -> str:
        return f"{info.fullname}.{name}"

    def _get_tvar_self_name(self) -> str:
        return self._get_tvar_name(SELF_TVAR_NAME, self._ctx.cls.info)

    def _add_tvar_expr(self, name: str, ctx):
        info = ctx.cls.info
        obj_type = ctx.api.named_type("__builtins__.object")
        self_tvar_expr = TypeVarExpr(
            name, self._get_tvar_name(name, info), [], obj_type
        )
        info.names[name] = SymbolTableNode(MDEF, self_tvar_expr)

    def _add_self_tvar_expr(self, ctx):
        self._add_tvar_expr(SELF_TVAR_NAME, ctx)

    def _get_tvar_def(self, name: str, ctx):
        obj_type = ctx.api.named_type("__builtins__.object")
        return TypeVarDef(
            SELF_TVAR_NAME, self._get_tvar_name(name, ctx.cls.info), -1, [], obj_type
        )

    def add_schema_method(self):
        ctx = self._ctx
        api: SemanticAnalyzer = ctx.api
        return_type_info: SymbolTableNode = api.lookup_fully_qualified(
            "typic.SchemaReturnT"
        )
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        arg_type = api.named_type("__builtins__.bool")
        arg = Argument(Var("primitive", arg_type), arg_type, None, ARG_NAMED_OPT)
        add_method(
            ctx,
            "schema",
            args=[arg],
            return_type=return_type_info.node.target,
            self_type=TypeVarType(self_tvar_def),
            tvar_def=self_tvar_def,
            is_classmethod=True,
        )

    def add_primitive_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        bool_type = ctx.api.named_type("__builtins__.bool")
        arg = Argument(Var("lazy", bool_type), bool_type, None, ARG_NAMED_OPT)
        add_method(
            ctx,
            "primitive",
            args=[arg],
            return_type=AnyType(TypeOfAny.unannotated),
            self_type=TypeVarType(self_tvar_def),
            tvar_def=self_tvar_def,
        )

    def add_json_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        bool_type = ctx.api.named_type("__builtins__.bool")
        int_type = ctx.api.named_type("__builtins__.int")
        str_type = ctx.api.named_type("__builtins__.str")
        indent = Argument(Var("indent", int_type), int_type, None, ARG_NAMED_OPT)
        ensure = Argument(
            Var("ensure_ascii", bool_type), bool_type, None, ARG_NAMED_OPT
        )
        add_method(
            ctx,
            "tojson",
            args=[indent, ensure],
            return_type=str_type,
            self_type=TypeVarType(self_tvar_def),
            tvar_def=self_tvar_def,
        )

    def add_validate_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        arg_type = AnyType(TypeOfAny.explicit)
        arg = Argument(Var("obj", arg_type), arg_type, None, ARG_POS)
        add_method(
            ctx,
            "validate",
            args=[arg],
            return_type=TypeVarType(self_tvar_def),
            tvar_def=self_tvar_def,
            is_staticmethod=True,
        )

    def add_transmute_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        arg_type = AnyType(TypeOfAny.explicit)
        arg = Argument(Var("obj", arg_type), arg_type, None, ARG_POS)
        add_method(
            ctx,
            "transmute",
            args=[arg],
            return_type=TypeVarType(self_tvar_def),
            tvar_def=self_tvar_def,
            is_staticmethod=True,
        )

    def add_translate_method(self):
        ctx = self._ctx
        self_tvar_def = self._get_tvar_def(SELF_TVAR_NAME, ctx)
        r_type = AnyType(TypeOfAny.explicit)
        arg_type = TypeType(r_type)
        arg = Argument(Var("target", arg_type), arg_type, None, ARG_POS)
        add_method(
            ctx,
            "translate",
            args=[arg],
            return_type=r_type,
            self_type=TypeVarType(self_tvar_def),
            tvar_def=self_tvar_def,
        )


def typic_klass_maker_callback(ctx: ClassDefContext) -> None:
    transformer = TypicTransformer(ctx)
    transformer.transform()


def add_method(
    ctx: ClassDefContext,
    name: str,
    args: List[Argument],
    return_type: Type,
    self_type: Optional[Type] = None,
    tvar_def: Optional[TypeVarDef] = None,
    is_classmethod: bool = False,
    is_new: bool = False,
    is_staticmethod: bool = False,
) -> None:
    """
    Adds a new method to a class.
    This can be dropped if/when https://github.com/python/mypy/issues/7301 is merged
    """
    info = ctx.cls.info

    # First remove any previously generated methods with the same name
    # to avoid clashes and problems in the semantic analyzer.
    if name in info.names:
        sym = info.names[name]
        if sym.plugin_generated and isinstance(sym.node, FuncDef):
            ctx.cls.defs.body.remove(sym.node)

    self_type = self_type or fill_typevars(info)
    if is_classmethod or is_new:
        first = [
            Argument(Var("_cls"), TypeType.make_normalized(self_type), None, ARG_POS)
        ]
    elif is_staticmethod:
        first = []
    else:
        self_type = self_type or fill_typevars(info)
        first = [Argument(Var("self"), self_type, None, ARG_POS)]
    args = first + args
    arg_types, arg_names, arg_kinds = [], [], []
    for arg in args:
        assert arg.type_annotation, "All arguments must be fully typed."
        arg_types.append(arg.type_annotation)
        arg_names.append(get_name(arg.variable))
        arg_kinds.append(arg.kind)

    function_type = ctx.api.named_type("__builtins__.function")
    signature = CallableType(
        arg_types, arg_kinds, arg_names, return_type, function_type
    )
    if tvar_def:
        signature.variables = [tvar_def]

    func = FuncDef(name, args, Block([PassStmt()]))
    func.info = info
    func.type = set_callable_name(signature, func)
    func.is_class = is_classmethod
    func.is_static = is_staticmethod
    func._fullname = get_fullname(info) + "." + name
    func.line = info.line

    # NOTE: we would like the plugin generated node to dominate, but we still
    # need to keep any existing definitions so they get semantically analyzed.
    if name in info.names:
        # Get a nice unique name instead.
        r_name = get_unique_redefinition_name(name, info.names)
        info.names[r_name] = info.names[name]

    if is_classmethod or is_staticmethod:
        func.is_decorated = True
        v = Var(name, func.type)
        v.info = info
        v._fullname = func._fullname
        if is_classmethod:
            v.is_classmethod = True
            dec = Decorator(func, [NameExpr("classmethod")], v)
        else:
            v.is_staticmethod = True
            dec = Decorator(func, [NameExpr("staticmethod")], v)

        dec.line = info.line
        sym = SymbolTableNode(MDEF, dec)
    else:
        sym = SymbolTableNode(MDEF, func)
    sym.plugin_generated = True

    info.names[name] = sym
    info.defn.defs.body.append(func)


def get_fullname(x: Union[FuncBase, SymbolNode]) -> str:
    """
    Used for compatibility with mypy 0.740; can be dropped once support for 0.740 is dropped.
    """
    fn = x.fullname
    if callable(fn):  # pragma: no cover
        return fn()
    return fn


def get_name(x: Union[FuncBase, SymbolNode]) -> str:
    """
    Used for compatibility with mypy 0.740; can be dropped once support for 0.740 is dropped.
    """
    fn = x.name
    if callable(fn):  # pragma: no cover
        return fn()
    return fn
