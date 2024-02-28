from __future__ import annotations

import pytest

from typical.constraints.array import assertions


@pytest.mark.suite(
    item_range_valid=dict(
        assertion=assertions.ItemRangeAssertion(min_items=1, max_items=3),
        value=[1, 2],
        expected_is_valid=True,
    ),
    item_range_invalid=dict(
        assertion=assertions.ItemRangeAssertion(min_items=1, max_items=3),
        value=[1, 2, 3, 4],
        expected_is_valid=False,
    ),
    min_items_valid=dict(
        assertion=assertions.MinItemsAssertion(
            min_items=1,
        ),
        value=[1],
        expected_is_valid=True,
    ),
    min_items_invalid=dict(
        assertion=assertions.MinItemsAssertion(
            min_items=1,
        ),
        value=[],
        expected_is_valid=False,
    ),
    max_items_valid=dict(
        assertion=assertions.MaxItemsAssertion(
            max_items=1,
        ),
        value=[1],
        expected_is_valid=True,
    ),
    max_items_invalid=dict(
        assertion=assertions.MaxItemsAssertion(
            max_items=1,
        ),
        value=[1, 2],
        expected_is_valid=False,
    ),
)
def test_assertions(assertion, value, expected_is_valid):
    # When
    is_valid = assertion(value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    min_and_max=dict(
        has_min=True, has_max=True, expected_cls=assertions.ItemRangeAssertion
    ),
    only_min=dict(
        has_min=True,
        has_max=False,
        expected_cls=assertions.MinItemsAssertion,
    ),
    only_max=dict(
        has_min=False,
        has_max=True,
        expected_cls=assertions.MaxItemsAssertion,
    ),
    no_min_no_max=dict(
        has_min=False,
        has_max=False,
        expected_cls=None,
    ),
)
def test_get_assertion_cls(has_min, has_max, expected_cls):
    # When
    assertion_cls = assertions.get_assertion_cls(has_min=has_min, has_max=has_max)
    # Then
    assert assertion_cls is expected_cls
