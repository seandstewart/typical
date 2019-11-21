#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json

import pytest

from typic.types import SecretStr, SecretBytes


@pytest.mark.parametrize(
    argnames=("value", "rep"), argvalues=[("foo", "***"), (b"foo", "b'***'")]
)
def test_secrets(value, rep):
    secret = SecretStr(value) if isinstance(value, str) else SecretBytes(value)
    assert value == secret
    assert rep == repr(secret)
    assert rep == str(secret)
    assert value == secret.secret
    if isinstance(value, str):
        assert json.dumps(value) == json.dumps(secret)
