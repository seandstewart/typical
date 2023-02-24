from __future__ import annotations

import re

import pytest

from typical.core.constraints.text import assertions


@pytest.mark.suite(
    range_and_pattern_valid=dict(
        given_min_length=2,
        given_max_length=4,
        given_regex=re.compile(r"^\d+$"),
        given_value="200",
        expected_is_valid=True,
    ),
    range_and_pattern_min_invalid=dict(
        given_min_length=2,
        given_max_length=4,
        given_regex=re.compile(r"^\d+$"),
        given_value="2",
        expected_is_valid=False,
    ),
    range_and_pattern_max_invalid=dict(
        given_min_length=2,
        given_max_length=4,
        given_regex=re.compile(r"^\d+$"),
        given_value="20000",
        expected_is_valid=False,
    ),
    range_and_pattern_pattern_invalid=dict(
        given_min_length=2,
        given_max_length=4,
        given_regex=re.compile(r"^\d+$"),
        given_value="2i",
        expected_is_valid=False,
    ),
    max_and_pattern_valid=dict(
        given_min_length=None,
        given_max_length=3,
        given_regex=re.compile(r"\d+"),
        given_value="20",
        expected_is_valid=True,
    ),
    max_and_pattern_max_invalid=dict(
        given_min_length=None,
        given_max_length=3,
        given_regex=re.compile(r"^\d+$"),
        given_value="2000",
        expected_is_valid=False,
    ),
    max_and_pattern_pattern_invalid=dict(
        given_min_length=None,
        given_max_length=3,
        given_regex=re.compile(r"^\d+$"),
        given_value="20i",
        expected_is_valid=False,
    ),
    min_and_pattern_valid=dict(
        given_min_length=2,
        given_max_length=None,
        given_regex=re.compile(r"^\d+$"),
        given_value="20",
        expected_is_valid=True,
    ),
    min_and_pattern_min_invalid=dict(
        given_min_length=2,
        given_max_length=None,
        given_regex=re.compile(r"^\d+$"),
        given_value="2",
        expected_is_valid=False,
    ),
    min_and_pattern_pattern_invalid=dict(
        given_min_length=2,
        given_max_length=None,
        given_regex=re.compile(r"^\d+$"),
        given_value="2i",
        expected_is_valid=False,
    ),
    range_valid=dict(
        given_min_length=2,
        given_max_length=4,
        given_regex=None,
        given_value="foo",
        expected_is_valid=True,
    ),
    range_min_invalid=dict(
        given_min_length=2,
        given_max_length=4,
        given_regex=None,
        given_value="f",
        expected_is_valid=False,
    ),
    range_max_invalid=dict(
        given_min_length=2,
        given_max_length=4,
        given_regex=None,
        given_value="foooo",
        expected_is_valid=False,
    ),
    min_valid=dict(
        given_min_length=2,
        given_max_length=None,
        given_regex=None,
        given_value="fo",
        expected_is_valid=True,
    ),
    min_invalid=dict(
        given_min_length=2,
        given_max_length=None,
        given_regex=None,
        given_value="f",
        expected_is_valid=False,
    ),
    max_valid=dict(
        given_min_length=None,
        given_max_length=2,
        given_regex=None,
        given_value="f0",
        expected_is_valid=True,
    ),
    max_invalid=dict(
        given_min_length=None,
        given_max_length=2,
        given_regex=None,
        given_value="f00",
        expected_is_valid=False,
    ),
)
def test_assertions(
    given_min_length,
    given_max_length,
    given_regex,
    given_value,
    expected_is_valid,
):
    # Given
    has_min = given_min_length is not None
    has_max = given_max_length is not None
    has_regex = given_regex is not None
    assertion_cls = assertions.get_assertion_cls(
        has_min=has_min, has_max=has_max, has_regex=has_regex
    )
    assertion = assertion_cls(
        min_length=given_min_length,
        max_length=given_max_length,
        regex=given_regex,
    )
    # When
    is_valid = assertion(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    min_and_max=dict(
        has_min=True,
        has_max=True,
        has_regex=False,
        expected_cls=assertions.RangeAssertion,
    ),
    only_min=dict(
        has_min=True,
        has_max=False,
        has_regex=False,
        expected_cls=assertions.MinAssertion,
    ),
    only_max=dict(
        has_min=False,
        has_max=True,
        has_regex=False,
        expected_cls=assertions.MaxAssertion,
    ),
    no_min_no_max_no_pattern=dict(
        has_min=False,
        has_max=False,
        has_regex=False,
        expected_cls=None,
    ),
    min_and_max_and_pattern=dict(
        has_min=True,
        has_max=True,
        has_regex=True,
        expected_cls=assertions.RangeAndPatternAssertion,
    ),
    min_and_pattern=dict(
        has_min=True,
        has_max=False,
        has_regex=True,
        expected_cls=assertions.MinAndPatternAssertion,
    ),
    max_and_pattern=dict(
        has_min=False,
        has_max=True,
        has_regex=True,
        expected_cls=assertions.MaxAndPatternAssertion,
    ),
    only_pattern=dict(
        has_min=False,
        has_max=False,
        has_regex=True,
        expected_cls=assertions.PatternAssertion,
    ),
)
def test_get_assertion_cls(has_min, has_max, has_regex, expected_cls):
    # When
    assertion_cls = assertions.get_assertion_cls(
        has_min=has_min, has_max=has_max, has_regex=has_regex
    )
    # Then
    assert assertion_cls is expected_cls
