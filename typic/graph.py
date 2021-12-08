from __future__ import annotations

import dataclasses
import collections
import reprlib
from typing import Type, Sequence, Iterator

from .compat import lru_cache
from .util import slotted, get_type_hints, origin as get_origin, get_args, get_qualname
from .checks import isstdlibtype


@slotted(dict=False, weakref=True)
@dataclasses.dataclass(unsafe_hash=True)
class TypeGraph:
    """A graph representation of a"""

    type: Type
    origin: Type
    cyclic: bool = False
    nodes: list[TypeGraph] = dataclasses.field(
        default_factory=list, hash=False, compare=False
    )
    parent: TypeGraph | None = None
    var: str | None = dataclasses.field(default=None, hash=False, compare=False)
    _type_name: str = dataclasses.field(
        repr=False, init=False, hash=False, compare=False
    )
    _origin_name: str = dataclasses.field(
        repr=False, init=False, hash=False, compare=False
    )

    def __post_init__(self):
        self._type_name = get_qualname(self.type)
        self._origin_name = get_qualname(self.origin)

    @property
    def pretty_name(self) -> str:
        pre = ""
        if self.var:
            pre = f"{self.var}: "
        tname = self._type_name
        if self._origin_name != tname:
            tname = f"{tname} ({self._origin_name})"
        return pre + tname

    @reprlib.recursive_repr()
    def __repr__(self) -> str:
        cyclic = self.cyclic
        nodes = f"({', '.join(repr(n) for n in self.nodes)},)"
        return (
            f"<{self.__class__.__name__} "
            f"type={self._type_name}, "
            f"origin={self._origin_name}, {cyclic=}, "
            f"parent={self.parent}, "
            f"nodes={nodes}>"
        )


def _node(t: type, *, var: str = None) -> TypeGraph:
    origin = get_origin(t)
    return TypeGraph(t, origin, var=var)


def _level(node: TypeGraph) -> Sequence[tuple[str | None, type]]:
    args = get_args(node.type)
    members = get_type_hints(node.type)
    return [*((None, t) for t in args), *(members.items())]  # type: ignore


@lru_cache(maxsize=None)
def get(t: Type) -> TypeGraph:
    """Get a directed graph of the type(s) this annotation represents."""
    graph = _node(t)
    visited = {graph.type: graph}
    stack = collections.deque([graph])
    while stack:
        parent = stack.popleft()
        for var, type in _level(parent):
            seen = visited.get(type)
            if seen:
                cyclic = not isstdlibtype(type)
                node = dataclasses.replace(seen, cyclic=cyclic, parent=parent, var=var)
                parent.nodes.append(node)
                continue

            node = _node(type, var=var)
            parent.nodes.append(node)
            node.parent = parent
            stack.append(node)
            visited[node.type] = node

    return graph


def traverse(graph: TypeGraph, *, reverse: bool = True) -> Iterator[TypeGraph]:
    """Traverse the type graph via DFS, optionally reverse the flow."""
    return _traverse_reverse(graph) if reverse else _traverse_forward(graph)


def draw(graph: TypeGraph, *, json: bool = False, depth: int = 1):
    """Pretty-print the type-tree for easy inspection and debugging."""
    print(graph.pretty_name)
    total = len(graph.nodes)
    for i, child in enumerate(graph.nodes, 1):
        tree_bar = "└" if i == total else "├"
        print(f"{tree_bar}── {child.pretty_name}")
        _display_tree(child, set())


def dfs(
    graph: TypeGraph,
    *,
    level: int = 0,
    last: bool = True,
    visited: dict[TypeGraph, int] = None,
    depth: int = 1,
) -> Iterator[tuple[TypeGraph, int, bool]]:
    """Traverse the graph using DFS, preserving some diagnostic metadata."""
    visited = collections.defaultdict(int) if visited is None else visited
    if graph.cyclic and visited[graph] >= depth:
        return
    visited[graph] += 1
    yield graph, level, last
    lastix = len(graph.nodes)
    nlevel = level + 1
    for i, child in enumerate(graph.nodes, start=1):
        yield from dfs(child, level=nlevel, last=i == lastix, visited=visited)


def _display_tree(
    graph: TypeGraph,
    visited: set[TypeGraph],
    previous_tree_bar: str = "├",
    level: int = 1,
) -> None:
    previous_tree_bar = previous_tree_bar.replace("├", "│")

    tree_bar = previous_tree_bar + "  ├"
    total = len(graph.nodes)
    for i, dependency in enumerate(graph.nodes, 1):
        current_tree = visited
        if i == total:
            tree_bar = previous_tree_bar + "  └"

        circular_warn = ""
        if dependency.cyclic and dependency in current_tree:
            circular_warn = "(circular dependency aborted here)"

        info = f"{tree_bar}── {dependency.pretty_name} {circular_warn}"
        print(info)
        if dependency.cyclic and dependency in current_tree:
            return

        tree_bar = tree_bar.replace("└", " ")
        current_tree.add(dependency)

        _display_tree(dependency, current_tree, tree_bar, level + 1)


def _traverse_forward(graph: TypeGraph) -> Iterator[TypeGraph]:
    stack = collections.deque([graph])
    seen = set()
    while stack:
        leaf = stack.popleft()
        yield leaf
        seen.add(leaf)
        stack.extend((n for n in leaf.nodes if n not in seen))


def _traverse_reverse(graph: TypeGraph) -> Iterator[TypeGraph]:
    yield from reversed([*_traverse_forward(graph)])
