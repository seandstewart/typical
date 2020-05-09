import pytest

from typic.constraints.common import TypeConstraints
from typic.constraints.error import ConstraintValueError
from typic.strict import STRICT_MODE


def test_validation_if_not_strict():
    tc = TypeConstraints(str)
    with pytest.raises(ConstraintValueError):
        tc.validate(1)


def test_validation_if_strict():
    STRICT_MODE.strict_mode()
    tc = TypeConstraints(str)
    with pytest.raises(ConstraintValueError):
        tc.validate(1)
    STRICT_MODE._unstrict_mode()


def test_allow_nullable_in_strict():
    STRICT_MODE.strict_mode()
    tc = TypeConstraints(str, nullable=True)
    valid, value = tc.validator(None)
    assert valid
    STRICT_MODE._unstrict_mode()


def test_validation_if_strict_and_nullable():
    STRICT_MODE.strict_mode()
    tc = TypeConstraints(str, nullable=True)
    with pytest.raises(ConstraintValueError):
        tc.validate(1)
    STRICT_MODE._unstrict_mode()
