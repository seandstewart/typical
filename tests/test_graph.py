from __future__ import annotations

import dataclasses

import pytest

from typical import graph


@dataclasses.dataclass(frozen=True)
class Graph:
    pretty_name: str
    cyclic: bool = False
    nodes: list[Graph] = dataclasses.field(
        default_factory=list, hash=False, compare=False
    )
    parent: Graph | None = None


@pytest.mark.suite(
    one_member=dict(
        tree=Graph("one"),
        expected=["one"],
    ),
    nested_parent=dict(
        tree=Graph("one", parent=Graph("parent", nodes=[Graph("one")])),
        expected=["parent", "one"],
    ),
    recursive_tree=dict(
        tree=Graph("one", nodes=[Graph("one")]),
        expected=["one"],
    ),
    cyclic_tree=dict(
        tree=Graph("one", nodes=[Graph("two", nodes=[Graph("one")])]),
        expected=["one", "two"],
    ),
)
@pytest.mark.suite(
    reverse_true=dict(reverse=True),
    reverse_false=dict(reverse=False),
)
def test_traverse(
    tree: graph.GraphProtocol, reverse: bool, expected: list[graph.GraphProtocol]
):
    # Given
    if reverse:
        expected = [*reversed(expected)]
    # When
    traversed = [g.pretty_name for g in graph.traverse(tree, reverse=reverse)]
    # Then
    assert traversed == expected
