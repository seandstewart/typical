from __future__ import annotations

from unittest import mock

import pytest

from typical.constraints.core import validators


class UserClass: ...


@pytest.mark.suite(
    null_value=dict(
        given_type=object,
        given_value=None,
        expected_is_valid=True,
        expected_assertion_called=False,
    ),
    not_null_instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
        expected_assertion_called=False,
    ),
    not_null_not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=True,
        expected_assertion_called=True,
    ),
)
def test_nullable_instance_assertion_validator(
    given_type,
    given_value,
    expected_is_valid,
    expected_assertion_called,
):
    # Given
    assertion = mock.MagicMock(return_value=expected_is_valid)
    validator = validators.NullableIsInstanceAssertionsValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
        assertion=assertion,
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid
    assert assertion.called == expected_assertion_called


@pytest.mark.suite(
    null_value=dict(
        given_type=object,
        given_value=None,
        expected_is_valid=True,
        expected_assertion_called=False,
    ),
    not_null_instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
        expected_assertion_called=True,
    ),
    not_null_not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=False,
        expected_assertion_called=False,
    ),
)
def test_nullable_not_instance_assertion_validator(
    given_type,
    given_value,
    expected_is_valid,
    expected_assertion_called,
):
    # Given
    assertion = mock.MagicMock(return_value=expected_is_valid)
    validator = validators.NullableNotInstanceAssertionsValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
        assertion=assertion,
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid
    assert assertion.called == expected_assertion_called


@pytest.mark.suite(
    instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
        expected_assertion_called=False,
    ),
    not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=True,
        expected_assertion_called=True,
    ),
)
def test_instance_assertion_validator(
    given_type,
    given_value,
    expected_is_valid,
    expected_assertion_called,
):
    # Given
    assertion = mock.MagicMock(return_value=expected_is_valid)
    validator = validators.NullableIsInstanceAssertionsValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
        assertion=assertion,
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid
    assert assertion.called == expected_assertion_called


@pytest.mark.suite(
    null_value=dict(
        given_type=object,
        given_value=None,
        expected_is_valid=True,
    ),
    not_null_instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
    ),
    not_null_not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=False,
    ),
)
def test_nullable_instance_validator(
    given_type,
    given_value,
    expected_is_valid,
):
    # Given
    validator = validators.NullableIsInstanceValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
        expected_assertion_called=True,
    ),
    not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=False,
        expected_assertion_called=False,
    ),
)
def test_not_instance_assertion_validator(
    given_type,
    given_value,
    expected_is_valid,
    expected_assertion_called,
):
    # Given
    assertion = mock.MagicMock(return_value=expected_is_valid)
    validator = validators.NotInstanceAssertionsValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
        assertion=assertion,
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid
    assert assertion.called == expected_assertion_called


@pytest.mark.suite(
    null_value=dict(
        given_type=object,
        given_value=None,
        expected_is_valid=True,
    ),
    not_null_instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
    ),
    not_null_not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=False,
    ),
)
def test_nullable_not_instance_validator(
    given_type,
    given_value,
    expected_is_valid,
):
    # Given
    validator = validators.NullableNotInstanceValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
    ),
    not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=False,
    ),
)
def test_instance_validator(
    given_type,
    given_value,
    expected_is_valid,
):
    # Given
    validator = validators.IsInstanceValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    instance=dict(
        given_type=object,
        given_value=1,
        expected_is_valid=True,
    ),
    not_instance=dict(
        given_type=UserClass,
        given_value={},
        expected_is_valid=False,
    ),
)
def test_not_instance_validator(
    given_type,
    given_value,
    expected_is_valid,
):
    # Given
    validator = validators.NotInstanceValidator(
        type=given_type,
        precheck=validators.NoOpPrecheck(),
    )
    # When
    is_valid, validated = validator(given_value)
    # Then
    assert is_valid == expected_is_valid


def test_no_op_validator():
    # Given
    validator = validators.NoOpInstanceValidator(
        type=object, precheck=validators.NoOpPrecheck()
    )
    # When
    is_valid, validated = validator(1)
    # Then
    assert is_valid
