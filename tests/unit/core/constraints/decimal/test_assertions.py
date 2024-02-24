from __future__ import annotations

import decimal
from unittest import mock

import pytest

from typical.constraints import error
from typical.constraints.core.assertions import NoOpAssertion
from typical.constraints.decimal import assertions


@pytest.mark.suite(
    max_digits_valid=dict(
        given_max_digits=2,
        given_max_decimals=None,
        given_value=2,
        expected_is_valid=True,
    ),
    max_digits_invalid=dict(
        given_max_digits=2,
        given_max_decimals=None,
        given_value=200,
        expected_is_valid=False,
    ),
    max_decimals_valid=dict(
        given_max_digits=None,
        given_max_decimals=2,
        given_value=decimal.Decimal("2.01"),
        expected_is_valid=True,
    ),
    max_decimals_invalid=dict(
        given_max_digits=None,
        given_max_decimals=2,
        given_value=decimal.Decimal("2.001"),
        expected_is_valid=False,
    ),
    max_digits_max_decimals_valid=dict(
        given_max_digits=3,
        given_max_decimals=2,
        given_value=decimal.Decimal("2.01"),
        expected_is_valid=True,
    ),
    max_digits_max_decimals_digits_invalid=dict(
        given_max_digits=3,
        given_max_decimals=2,
        given_value=decimal.Decimal("20.01"),
        expected_is_valid=False,
    ),
    max_digits_max_decimals_decimals_invalid=dict(
        given_max_digits=3,
        given_max_decimals=2,
        given_value=decimal.Decimal("0.001"),
        expected_is_valid=False,
    ),
    max_digits_max_decimals_both_invalid=dict(
        given_max_digits=3,
        given_max_decimals=2,
        given_value=decimal.Decimal("100.001"),
        expected_is_valid=False,
    ),
)
def test_inclusive_assertions(
    given_max_digits,
    given_max_decimals,
    given_value,
    expected_is_valid,
):
    # Given
    has_max_digits = given_max_digits is not None
    has_max_decimals = given_max_decimals is not None
    given_min = 0
    given_inclusive_min = True
    assertion_cls, num_assertion_cls = assertions.get_assertion_cls(
        has_min=True,
        has_max=False,
        has_mul=False,
        inclusive_max=False,
        inclusive_min=given_inclusive_min,
        has_max_digits=has_max_digits,
        has_max_decimals=has_max_decimals,
    )
    num_assertion = num_assertion_cls(
        min=given_min,
        max=None,
        mul=None,
    )
    assertion = assertion_cls(
        number_assertions=num_assertion,
        max_digits=given_max_digits,
        max_decimal_places=given_max_decimals,
    )
    # When
    is_valid = assertion(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    max_decimals_assertion=dict(
        has_min=True,
        has_max=True,
        has_mul=True,
        inclusive_min=True,
        inclusive_max=True,
        has_max_digits=False,
        has_max_decimals=True,
        expected_cls=(assertions.MaxDecimalsAssertion, mock.ANY),
    ),
    max_digits_assertion=dict(
        has_min=True,
        has_max=True,
        has_mul=True,
        inclusive_min=True,
        inclusive_max=True,
        has_max_digits=True,
        has_max_decimals=False,
        expected_cls=(assertions.MaxDigitsAssertion, mock.ANY),
    ),
    max_digits_and_decimals_assertion=dict(
        has_min=True,
        has_max=True,
        has_mul=True,
        inclusive_min=True,
        inclusive_max=True,
        has_max_digits=True,
        has_max_decimals=True,
        expected_cls=(assertions.MaxDigitsAndDecimalsAssertion, mock.ANY),
    ),
    num_no_assertion=dict(
        has_min=False,
        has_max=False,
        has_mul=False,
        inclusive_min=False,
        inclusive_max=False,
        has_max_digits=True,
        has_max_decimals=True,
        expected_cls=(assertions.MaxDigitsAndDecimalsAssertion, NoOpAssertion),
    ),
    dec_no_assertion=dict(
        has_min=True,
        has_max=True,
        has_mul=True,
        inclusive_min=True,
        inclusive_max=True,
        has_max_digits=False,
        has_max_decimals=False,
        expected_cls=None,
    ),
)
def test_get_assertion_cls(
    has_min,
    has_max,
    has_mul,
    inclusive_min,
    inclusive_max,
    has_max_digits,
    has_max_decimals,
    expected_cls,
):
    # When
    assertion_cls = assertions.get_assertion_cls(
        has_min=has_min,
        has_max=has_max,
        has_mul=has_mul,
        inclusive_min=inclusive_min,
        inclusive_max=inclusive_max,
        has_max_digits=has_max_digits,
        has_max_decimals=has_max_decimals,
    )
    # Then
    assert assertion_cls == expected_cls


def test_assertion_invalid_syntax():
    # Given
    given_min = 0
    given_max_digits = 1
    given_max_decimals = 2
    assertion_cls, num_assertion_cls = assertions.get_assertion_cls(
        has_min=True,
        has_max=False,
        has_mul=False,
        inclusive_max=False,
        inclusive_min=True,
        has_max_digits=True,
        has_max_decimals=True,
    )
    num_assertion = num_assertion_cls(
        min=given_min,
        max=None,
        mul=None,
    )
    with pytest.raises(error.ConstraintSyntaxError):
        assertion_cls(
            number_assertions=num_assertion,
            max_digits=given_max_digits,
            max_decimal_places=given_max_decimals,
        )
