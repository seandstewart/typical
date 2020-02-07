import pytest

from typic.constraints.common import TypeConstraints
from typic.constraints.error import ConstraintValueError
from typic.strict import STRICT


def test_no_validation_if_not_strict():
    tc = TypeConstraints(str)
    valid, value = tc.validator(1)
    assert valid


def test_validation_if_strict():
    STRICT.strict_mode()
    tc = TypeConstraints(str)
    with pytest.raises(ConstraintValueError):
        tc.validate(1)
    STRICT._unstrict_mode()


def test_allow_nullable_in_strict():
    STRICT.strict_mode()
    tc = TypeConstraints(str, nullable=True)
    valid, value = tc.validator(None)
    assert valid
    STRICT._unstrict_mode()


def test_validation_if_strict_and_nullable():
    STRICT.strict_mode()
    tc = TypeConstraints(str, nullable=True)
    with pytest.raises(ConstraintValueError):
        tc.validate(1)
    STRICT._unstrict_mode()
