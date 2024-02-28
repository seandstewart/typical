from __future__ import annotations

import re

import pytest

from typical.constraints.mapping import assertions


@pytest.mark.suite(
    item_range_pattern_valid=dict(
        given_min_items=1,
        given_max_items=3,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blah": 3},
        expected_is_valid=True,
    ),
    item_range_pattern_invalid_key=dict(
        given_min_items=1,
        given_max_items=3,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blar": 3},
        expected_is_valid=False,
    ),
    item_range_pattern_invalid_max_items=dict(
        given_min_items=1,
        given_max_items=3,
        given_key_pattern=re.compile(r"^(foo|bar|blah|fooey)$"),
        given_value={"foo": 1, "bar": 2, "blah": 3, "fooey": 4},
        expected_is_valid=False,
    ),
    item_range_pattern_invalid_min_items=dict(
        given_min_items=2,
        given_max_items=3,
        given_key_pattern=re.compile(r"^(foo|bar|blah|fooey)$"),
        given_value={"foo": 1},
        expected_is_valid=False,
    ),
    max_items_pattern_valid=dict(
        given_min_items=None,
        given_max_items=3,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blah": 3},
        expected_is_valid=True,
    ),
    max_items_pattern_invalid_key=dict(
        given_min_items=None,
        given_max_items=3,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blar": 3},
        expected_is_valid=False,
    ),
    max_items_pattern_invalid_max_items=dict(
        given_min_items=None,
        given_max_items=3,
        given_key_pattern=re.compile(r"^(foo|bar|blah|fooey)$"),
        given_value={"foo": 1, "bar": 2, "blah": 3, "fooey": 4},
        expected_is_valid=False,
    ),
    min_items_pattern_valid=dict(
        given_min_items=1,
        given_max_items=None,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blah": 3},
        expected_is_valid=True,
    ),
    min_items_pattern_invalid_key=dict(
        given_min_items=1,
        given_max_items=None,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blar": 3},
        expected_is_valid=False,
    ),
    min_items_pattern_invalid_min_items=dict(
        given_min_items=2,
        given_max_items=None,
        given_key_pattern=re.compile(r"^(foo|bar|blah|fooey)$"),
        given_value={"foo": 1},
        expected_is_valid=False,
    ),
    pattern_valid=dict(
        given_min_items=None,
        given_max_items=None,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blah": 3},
        expected_is_valid=True,
    ),
    pattern_invalid_key=dict(
        given_min_items=None,
        given_max_items=None,
        given_key_pattern=re.compile(r"^(foo|bar|blah)$"),
        given_value={"foo": 1, "bar": 2, "blar": 3},
        expected_is_valid=False,
    ),
    item_range_valid=dict(
        given_min_items=1,
        given_max_items=3,
        given_key_pattern=None,
        given_value={"foo": 1, "bar": 2, "blah": 3},
        expected_is_valid=True,
    ),
    item_range_invalid_max_items=dict(
        given_min_items=1,
        given_max_items=3,
        given_key_pattern=None,
        given_value={"foo": 1, "bar": 2, "blah": 3, "fooey": 4},
        expected_is_valid=False,
    ),
    item_range_invalid_min_items=dict(
        given_min_items=2,
        given_max_items=3,
        given_key_pattern=None,
        given_value={"foo": 1},
        expected_is_valid=False,
    ),
    min_items_valid=dict(
        given_min_items=1,
        given_max_items=None,
        given_key_pattern=None,
        given_value={"foo": 1, "bar": 2, "blah": 3},
        expected_is_valid=True,
    ),
    min_items_invalid_min_items=dict(
        given_min_items=2,
        given_max_items=None,
        given_key_pattern=None,
        given_value={"foo": 1},
        expected_is_valid=False,
    ),
    max_items_valid=dict(
        given_min_items=None,
        given_max_items=3,
        given_key_pattern=None,
        given_value={"foo": 1, "bar": 2, "blah": 3},
        expected_is_valid=True,
    ),
    max_items_invalid_max_items=dict(
        given_min_items=None,
        given_max_items=3,
        given_key_pattern=None,
        given_value={"foo": 1, "bar": 2, "blah": 3, "fooey": 4},
        expected_is_valid=False,
    ),
)
def test_assertions(
    given_min_items,
    given_max_items,
    given_key_pattern,
    given_value,
    expected_is_valid,
):
    # Given
    has_min = given_min_items is not None
    has_max = given_max_items is not None
    has_key_pattern = given_key_pattern is not None
    assertion_cls = assertions.get_assertion_cls(
        has_min=has_min, has_max=has_max, has_key_pattern=has_key_pattern
    )
    assertion = assertion_cls(
        min_items=given_min_items,
        max_items=given_max_items,
        key_pattern=given_key_pattern,
    )
    # When
    is_valid = assertion(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    min_and_max=dict(
        has_min=True,
        has_max=True,
        has_pattern=False,
        expected_cls=assertions.ItemRangeAssertion,
    ),
    only_min=dict(
        has_min=True,
        has_max=False,
        has_pattern=False,
        expected_cls=assertions.MinItemsAssertion,
    ),
    only_max=dict(
        has_min=False,
        has_max=True,
        has_pattern=False,
        expected_cls=assertions.MaxItemsAssertion,
    ),
    no_min_no_max_no_pattern=dict(
        has_min=False,
        has_max=False,
        has_pattern=False,
        expected_cls=None,
    ),
    min_and_max_and_pattern=dict(
        has_min=True,
        has_max=True,
        has_pattern=True,
        expected_cls=assertions.ItemRangePatternAssertion,
    ),
    min_and_pattern=dict(
        has_min=True,
        has_max=False,
        has_pattern=True,
        expected_cls=assertions.MinItemsPatternAssertion,
    ),
    max_and_pattern=dict(
        has_min=False,
        has_max=True,
        has_pattern=True,
        expected_cls=assertions.MaxItemsPatternAssertion,
    ),
    only_pattern=dict(
        has_min=False,
        has_max=False,
        has_pattern=True,
        expected_cls=assertions.PatternAssertion,
    ),
)
def test_get_assertion_cls(has_min, has_max, has_pattern, expected_cls):
    # When
    assertion_cls = assertions.get_assertion_cls(
        has_min=has_min, has_max=has_max, has_key_pattern=has_pattern
    )
    # Then
    assert assertion_cls is expected_cls
