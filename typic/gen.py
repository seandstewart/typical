#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import enum
import inspect
import linecache
import pathlib
import uuid
from typing import List, Union, Type, Tuple, Optional

import typic

_empty = inspect.Parameter.empty
ParameterKind = inspect._ParameterKind


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


@dataclasses.dataclass(frozen=True)
class Line:
    INDENT = "    "
    code: str
    level: int

    def render(self) -> str:
        if self.code.strip():
            return f"{self.INDENT * self.level}{self.code}\n"
        return self.code


@dataclasses.dataclass
class Block:
    namespace: dict = dataclasses.field(default_factory=dict)
    body: List[Union[Line, "Block"]] = dataclasses.field(default_factory=list)
    level: int = 0
    name: Optional[str] = None

    def line(self, line: str, *, level: int = None, **context):
        if level is None:
            level = self.level
        self.namespace.update(context)
        self.body.append(Line(line, level))

    l = line  # noqa: E741

    def block(
        self, *lines: str, level: int = None, name: str = None, **context
    ) -> "Block":
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
    ) -> "Block":
        sig = inspect.Signature(parameters=params or None, return_annotation=returns)
        defn = f"{Keyword.DEF} {name}"
        if coro:
            defn = f"{Keyword.ASN} {defn}"
        funcsig = f"{defn}{str(sig)}:"
        lines = ["\n", funcsig]
        if decorator:
            lines = ["\n", f"{Keyword.DEC}{decorator}", funcsig]
        return self.b(*lines, name=name, **context)

    f = func

    def cls(
        self, name: str, *, base: str = None, decorator: str = None, **context
    ) -> "Block":  # pragma: nocover
        decl = f"{Keyword.CLS} {name}"
        if base:
            decl = f"{decl}({base})"
        decl = f"{decl}:"
        lines = ["\n", decl]
        if decorator:
            lines = ["\n", f"{Keyword.DEC}{decorator}", decl]
        return self.b(*lines, name=name, **context)

    c = cls

    def __enter__(self) -> "Block":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def _generate_unique_filename(func_name):
        """Create a "filename" suitable for a function being generated.

        Notes
        -----
        Taken aproximately from `attrs`.

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

    def render(self) -> str:
        block = "".join(x.render() for x in self.body)
        return f"{block}" if block else ""

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
