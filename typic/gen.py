from __future__ import annotations
import dataclasses
import enum
import inspect
import linecache
import pathlib
import uuid
from typing import List, Union, Type, Tuple, Optional, TypeVar

import typic
from .util import slotted

_empty = inspect.Parameter.empty
ParameterKind = inspect._ParameterKind


class rawstr(str):
    def __repr__(self):
        return super().__repr__().strip("'\"")


class Keyword(str, enum.Enum):
    RET = "return"
    YLD = "yield"
    ASN = "async"
    AWT = "await"
    DEF = "def"
    CLS = "class"
    AST = "assert"
    IMP = "import"
    FRM = "from"
    DEC = "@"


@slotted(dict=False)
@dataclasses.dataclass(frozen=True)
class Line:
    INDENT = "    "
    code: str
    level: int

    def render(self) -> str:
        if self.code.strip():
            return f"{self.INDENT * self.level}{self.code}\n"
        return self.code


_BT = TypeVar("_BT")


@slotted(dict=False)
@dataclasses.dataclass
class Block:
    namespace: dict = dataclasses.field(default_factory=dict)
    body: List[Union[Line, Block]] = dataclasses.field(default_factory=list)
    level: int = 0
    name: str = ""

    def line(self, line: str, *, level: int = None, **context):
        if level is None:
            level = self.level
        self.namespace.update(context)
        self.body.append(Line(line, level))

    l = line  # noqa: E741

    def block(self, *lines: str, level: int = None, name: str = "", **context) -> Block:
        level = (self.level + 1) if level is None else level
        self.namespace.update(context)
        block = Block(self.namespace, level=level, name=name)
        for line in lines:
            self.l(line)
        self.body.append(block)
        return block

    b = block

    @staticmethod
    def param(  # type: ignore
        name: str,
        kind: ParameterKind = ParameterKind.POSITIONAL_OR_KEYWORD,  # type: ignore
        *,
        default=_empty,
        annotation=_empty,
    ) -> inspect.Parameter:
        return inspect.Parameter(
            name=name, kind=kind, default=default, annotation=annotation
        )

    p = param

    def func(
        self,
        name: str,
        *params: inspect.Parameter,
        decorator: str = None,
        returns: Type = _empty,
        coro: bool = False,
        **context,
    ) -> Function:
        self.namespace.update(context)
        func = Function(
            namespace=self.namespace,
            level=self.level + 1,
            name=name,
            parameters=[*params],
            returns=returns,
            coro=coro,
            decorator=decorator,
        )
        self.body.append(func)
        return func

    f = func

    def cls(
        self, name: str, *params, base: str = None, decorator: str = None, **context
    ) -> Class:  # pragma: nocover
        self.namespace.update(context)
        cls = Class(
            namespace=self.namespace,
            level=self.level + 1,
            name=name,
            parameters=[*params],
            base=base,
            decorator=decorator,
        )
        self.body.append(cls)
        return cls

    c = cls

    def __enter__(self: _BT) -> _BT:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def _generate_unique_filename(func_name):
        """Create a "filename" suitable for a function being generated.

        Notes
        -----
        Taken approximately from `attrs`.

        See Also
        --------
        https://github.com/python-attrs/attrs/blob/8c00f755f9d91c06fbdd9a20e24d2c4663e6339d/src/attr/_make.py#L1066
        """
        unique_id = uuid.uuid4()
        extra = ""
        count = 1

        while True:
            unique_filename = f"<typical generated {func_name}{extra}>"
            # To handle concurrency we essentially "reserve" our spot in
            # the linecache with a dummy line.  The caller can then
            # set this value correctly.
            cache_line = (1, None, (str(unique_id),), unique_filename)
            if linecache.cache.setdefault(unique_filename, cache_line) == cache_line:
                return unique_filename

            # Looks like this spot is taken. Try again.
            count += 1
            extra = f"-{count}"

    def _add_to_linecache(self, fname, code):
        linecache.cache[fname] = (
            len(self.body),
            None,
            code.splitlines(True),
            fname,
        )

    def _render_head(self) -> str:
        return ""

    def _render_body(self) -> str:
        block = "".join(str(x.render()) for x in self.body)
        return block or "..."

    def render(self) -> str:
        return self._render_head() + self._render_body()

    def compile(self, *, name: str, ns: dict = None):
        ns = {} if ns is None else ns
        fname = self._generate_unique_filename(func_name=name)
        self.namespace.update(ns)
        code = self.render()
        bytecode = compile(code, fname, "exec")
        eval(bytecode, self.namespace, self.namespace)
        target = self.namespace[name]
        target.__raw__ = code
        self._add_to_linecache(fname, code)
        return target


@slotted(dict=False)
@dataclasses.dataclass
class Function(Block):
    parameters: List[inspect.Parameter] = dataclasses.field(default_factory=list)
    returns: Optional[Type] = None
    coro: bool = False
    decorator: Optional[str] = None

    def _render_head(self) -> str:
        defn = f"{Keyword.DEF} {self.name}"
        if self.coro:
            defn = f"{Keyword.ASN} {defn}"
        funcsig = f"{defn}{str(inspect.Signature(self.parameters))}:"
        lines = ["\n", funcsig, "\n"]
        if self.decorator:
            lines = ["\n", f"{Keyword.DEC}{self.decorator}", funcsig, "\n"]

        return "".join(lines)

    def localize_context(self, *context: str):
        """A byte-code hack to inject variables into the local namespace."""
        self.parameters.extend(
            (
                self.param(name=n, kind=ParameterKind.KEYWORD_ONLY, default=rawstr(n))
                for n in context
            )
        )

    def add_param(
        self,
        name: str,
        kind: ParameterKind = ParameterKind.POSITIONAL_OR_KEYWORD,  # type: ignore
        *,
        default=_empty,
        annotation=_empty,
    ):
        self.parameters.append(
            self.param(name=name, kind=kind, default=default, annotation=annotation)
        )


@slotted(dict=False)
@dataclasses.dataclass
class Class(Block):
    parameters: List[inspect.Parameter] = dataclasses.field(default_factory=list)
    decorator: Optional[str] = None
    base: Optional[str] = None

    def _render_head(self) -> str:
        decl = f"{Keyword.CLS} {self.name}"
        if self.base:
            decl = f"{decl}({self.base})"
        initfn = ""
        if self.parameters:
            sig = inspect.Signature(parameters=self.parameters)
            initfn = f"\n{Keyword.DEF} __init__{str(sig)}:"
        lines = ["\n", decl, "\n", initfn, "\n"]
        if self.decorator:
            lines = ["\n", f"{Keyword.DEC}{self.decorator}", *lines]
        return "".join(lines)


# This isn't used or tested. It's just here for API completion.
# Perhaps an optimization could be to allow users to pre-compile their protocols.
@dataclasses.dataclass
class Module:  # pragma: nocover
    namespace: dict = dataclasses.field(init=False, default_factory=dict)
    body: Block = dataclasses.field(init=False)

    def __post_init__(self):
        self.body = Block(self.namespace)

    @staticmethod
    def imports(namespace: dict) -> Tuple[Block, dict]:
        with Block() as imports:
            remains = {}
            for key, value in namespace.items():
                if inspect.ismodule(value):
                    imports.l(f"{Keyword.IMP} {value.__name__} as {key}", level=0)
                elif (
                    (inspect.isclass(value) or inspect.isfunction(value))
                    and not value.__module__ == "__main__"
                    and not typic.isbuiltintype(value)
                ):
                    imports.l(
                        f"{Keyword.FRM} {value.__module__} {Keyword.IMP} {value.__name__} as {key}",
                        level=0,
                    )
                else:
                    remains[key] = value
        return imports, remains

    @staticmethod
    def globals(namespace: dict) -> Tuple[Block, dict]:
        remains = {}
        with Block() as g:
            for key, value in namespace.items():
                if isinstance(value, tuple(typic.BUILTIN_TYPES)):
                    g.l(f"{key} = {value}", level=0)
                else:
                    # Can't set values for custom types/classes when writing a file
                    remains[key] = value
        return g, remains

    def render(self) -> Tuple[str, dict]:
        imports, remains = self.imports(self.namespace)
        globs, remains = self.globals(remains)
        return "".join((imports.render(), globs.render(), self.body.render())), remains

    def compile(self, ns: dict):
        code, namespace = self.render()
        ns.update(namespace)
        exec(code, ns, ns)

    def write(self, path: pathlib.Path):
        code, namespace = self.render()
        path.write_text(code)
        return code
