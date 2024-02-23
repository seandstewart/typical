from __future__ import annotations

import collections
import operator
from typing import Iterator, Protocol, Deque, Iterable, TypeVar

__all__ = ("bfs", "dfs", "iter2darray", "GraphProtocol")


def dfs(graph: _GraphT, *, reverse: bool = True) -> Iterator[_GraphT]:
    """Traverse the type graph via DFS, optionally reverse the flow."""
    return _traverse_reverse(graph) if reverse else _traverse_forward(graph)


def _traverse_forward(graph: _GraphT) -> Iterator[_GraphT]:
    root = graph
    while root.parent:
        root = root.parent

    stack = collections.deque([root])
    seen = set()
    while stack:
        leaf = stack.popleft()
        yield leaf
        seen.add(leaf)
        stack.extend((n for n in leaf.nodes if n not in seen))


def _traverse_reverse(graph: _GraphT) -> Iterator[_GraphT]:
    yield from reversed([*_traverse_forward(graph)])


def iter2darray(
    array: Deque[Deque[_T]],
    *,
    from_root: bool = False,
    from_left: bool = False,
) -> Iterable[_T]:
    """Iterate through a 2-dimensional array.

    By default, we iterate from the bottom-right to the top-left (LIFO[LIFO[...]]).

    Args:
        array: A 2-dimensional array utilizing :py:class:`collections.deque`.
        from_root: If True, iterate though the first dimension as a stack (FIFO).
        from_left: If True, iterate through the second dimension as a stack (FIFO).
    """
    one_pop = array.popleft if from_root else array.pop
    two_pop = (
        operator.methodcaller("popleft") if from_left else operator.methodcaller("pop")
    )

    while array:
        level = one_pop()
        while level:
            yield two_pop(level)


bfs = iter2darray


class GraphProtocol(Protocol):
    cyclic: bool
    nodes: list[GraphProtocol]
    parent: GraphProtocol | None
    pretty_name: str

    def __hash__(self) -> int:
        ...


_T = TypeVar("_T")
_GraphT = TypeVar("_GraphT", bound=GraphProtocol)
