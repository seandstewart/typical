from __future__ import annotations

import pytest

from typical.constraints.array import prechecks


@pytest.mark.suite(
    hashable_values=dict(
        cls=list,
        instance=[1, 2, 3, 2],
        expected_result=[1, 2, 3],
    ),
    unhashable_values=dict(
        cls=list, instance=[[], [1], [1]], expected_result=[[], [1]]
    ),
)
def test_unique_precheck(cls, instance, expected_result):
    # Given
    precheck = prechecks.UniquePrecheck(cls=cls)
    # When
    result = precheck(instance)
    # Then
    assert result == expected_result
