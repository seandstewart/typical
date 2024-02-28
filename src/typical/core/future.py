from __future__ import annotations

import ast
import collections
import functools

from typical import compat


@functools.lru_cache(maxsize=None)
def transform_annotation(annotation: str, *, union: str = "Union") -> str:
    """Transform a new-style UnionType (str | int) into an old-style :py:class:`typing.Union`.

    Args:
        annotation: The annotation to transform, as a string.
        union: The name of the Union type to subscript (defaults "Union").

    Notes:
        This is a raw string transformation that does not test for the *correctness*
        of your annotation. As such, if you attempt to evaluate the transformed string
        at runtime and there are errors in your declaration, they will result in an
        error in the transformed annotation as well.
    """
    parsed = ast.parse(annotation, mode="eval")
    transformed = TransformUnion().visit(parsed)
    unparsed = compat.unparse(transformed).strip()
    return unparsed


class TransformUnion(ast.NodeTransformer):
    def visit_BinOp(self, node: ast.BinOp):
        if not isinstance(node.op, ast.BitOr):
            return node

        args = collections.deque([node.right])
        left = node.left
        while isinstance(left, ast.BinOp):
            args.appendleft(left.right)
            left = left.left
        args.appendleft(left)

        union = ast.Subscript(
            value=ast.Name(id="Union", ctx=ast.Load()),
            slice=ast.Index(value=ast.Tuple(elts=[*args], ctx=ast.Load())),
            ctx=ast.Load(),
        )
        ast.copy_location(union, node)
        ast.fix_missing_locations(union)
        return union

    def visit_Name(self, node: ast.Name):
        if node.id not in _GENERICS:
            return node

        new = ast.Name(id=_GENERICS[node.id], ctx=ast.Load())
        ast.copy_location(new, node)
        return new


_GENERICS = {
    "dict": "typing.Dict",
    "list": "typing.List",
    "set": "typing.Set",
    "tuple": "typing.Tuple",
    "Pattern": "typing.Pattern",
}
