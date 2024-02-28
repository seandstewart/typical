from __future__ import annotations

import pytest

from typical.constraints.text import prechecks


@pytest.mark.suite(
    curtail_and_strip=dict(
        given_max_length=2,
        given_should_curtail_length=True,
        given_should_strip_whitespace=True,
        given_value="fo0 ",
        expected_output="fo",
    ),
    strip=dict(
        given_max_length=2,
        given_should_curtail_length=False,
        given_should_strip_whitespace=True,
        given_value="fo0 ",
        expected_output="fo0",
    ),
    curtail=dict(
        given_max_length=2,
        given_should_curtail_length=True,
        given_should_strip_whitespace=False,
        given_value="fo0 ",
        expected_output="fo",
    ),
)
def test_prechecks(
    given_max_length,
    given_should_curtail_length,
    given_should_strip_whitespace,
    given_value,
    expected_output,
):
    # Given
    precheck_cls = prechecks.get_precheck_cls(
        should_curtail_length=given_should_curtail_length,
        should_strip_whitespace=given_should_strip_whitespace,
    )
    precheck = precheck_cls(max_length=given_max_length)
    # When
    output = precheck(given_value)
    # Then
    assert output == expected_output
