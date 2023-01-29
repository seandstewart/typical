from __future__ import annotations

import collections
from typing import Iterator, Protocol

__all__ = ("traverse", "GraphProtocol")


def traverse(graph: GraphProtocol, *, reverse: bool = True) -> Iterator[GraphProtocol]:
    """Traverse the type graph via DFS, optionally reverse the flow."""
    return _traverse_reverse(graph) if reverse else _traverse_forward(graph)


def _traverse_forward(graph: GraphProtocol) -> Iterator[GraphProtocol]:
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


def _traverse_reverse(graph: GraphProtocol) -> Iterator[GraphProtocol]:
    yield from reversed([*_traverse_forward(graph)])


class GraphProtocol(Protocol):
    cyclic: bool
    nodes: list[GraphProtocol]
    parent: GraphProtocol | None
    pretty_name: str

    def __hash__(self) -> int:
        ...
