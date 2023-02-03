from __future__ import annotations

from unittest import mock

from typical.core.constraints.core import error, types


def test_constraint_value_error_dump():
    # Given
    child = error.ConstraintValueError(
        "Child failed!",
        constraints=mock.MagicMock(spec=types.AbstractConstraints).return_value,
        path="child",
    )
    given_error = error.ConstraintValueError(
        "Failed!",
        constraints=mock.MagicMock(spec=types.AbstractConstraints).return_value,
        path="root",
        **{"root.child": child},
    )
    expected_report = [
        {
            "location": "root",
            "error_class": error.ConstraintValueError.__name__,
            "detail": "Failed!",
        },
        {
            "location": "root.child",
            "error_class": error.ConstraintValueError.__name__,
            "detail": "Child failed!",
        },
    ]
    # When
    report = given_error.dump()
    # Then
    assert report == expected_report
