from __future__ import annotations

import pytest

from typical.constraints.structured import assertions


@pytest.mark.suite(
    valid_fields_dict=dict(
        given_fields=frozenset(("foo", "bar")),
        given_value=dict(foo=1, bar=1),
        expected_is_valid=True,
    ),
    valid_extra_fields_dict=dict(
        given_fields=frozenset(("foo", "bar")),
        given_value=dict(foo=1, bar=1, extra=3),
        expected_is_valid=True,
    ),
    invalid_fields_dict=dict(
        given_fields=frozenset(("foo", "bar")),
        given_value=dict(foo=1),
        expected_is_valid=False,
    ),
    valid_fields_collection=dict(
        given_fields=frozenset(("foo", "bar")),
        given_value=[("foo", 1), ("bar", 2)],
        expected_is_valid=True,
    ),
    invalid_fields_collection=dict(
        given_fields=frozenset(("foo", "bar")),
        given_value=[("foo", 1)],
        expected_is_valid=False,
    ),
    invalid_collection_shape=dict(
        given_fields=frozenset(("foo", "bar")),
        given_value=[("foo", 1, 3)],
        expected_is_valid=False,
    ),
    invalid_type=dict(
        given_fields=frozenset(("foo", "bar")),
        given_value=1,
        expected_is_valid=False,
    ),
)
@pytest.mark.suite(
    tuple=dict(is_tuple=True),
    object=dict(is_tuple=False),
)
def test_structured_fields_assertion(
    given_fields,
    given_value,
    expected_is_valid,
    is_tuple,
):
    # Given
    assertion_cls = assertions.get_assertion_cls(
        has_fields=True,
        is_tuple=is_tuple,
    )
    assertion = assertion_cls(fields=given_fields, size=len(given_fields))
    # When
    is_valid = assertion(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    valid_collection=dict(
        given_size=3,
        given_value=(1, 2, 3),
        expected_is_valid=True,
    ),
    valid_collection_extra=dict(
        given_size=3,
        given_value=(1, 2, 3, 4),
        expected_is_valid=True,
    ),
    invalid_collection=dict(
        given_size=3,
        given_value=(1, 2),
        expected_is_valid=False,
    ),
    invalid_type=dict(
        given_size=3,
        given_value=1,
        expected_is_valid=False,
    ),
)
def test_structured_tuple_assertion(given_size, given_value, expected_is_valid):
    # Given
    assertion_cls = assertions.get_assertion_cls(
        has_fields=False,
        is_tuple=True,
    )
    assertion = assertion_cls(fields=frozenset(()), size=given_size)
    # When
    is_valid = assertion(given_value)
    # Then
    assert is_valid == expected_is_valid


@pytest.mark.suite(
    fields_assertion=dict(
        given_has_fields=True,
        given_is_tuple=False,
        expected_assertion_cls=assertions.StructuredFieldsObjectAssertion,
    ),
    tuple_assertion=dict(
        given_has_fields=False,
        given_is_tuple=True,
        expected_assertion_cls=assertions.StructuredTupleAssertion,
    ),
    tuple_fields_assertion=dict(
        given_has_fields=True,
        given_is_tuple=True,
        expected_assertion_cls=assertions.StructuredFieldsTupleAssertion,
    ),
    no_assertion=dict(
        given_has_fields=False,
        given_is_tuple=False,
        expected_assertion_cls=None,
    ),
)
def test_get_assertion_cls(given_has_fields, given_is_tuple, expected_assertion_cls):
    # When
    assertion_cls = assertions.get_assertion_cls(
        has_fields=given_has_fields,
        is_tuple=given_is_tuple,
    )
    # Then
    assert assertion_cls is expected_assertion_cls
