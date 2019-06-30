#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Sized, Union

__all__ = ("SecretMixin", "SecretStr", "SecretBytes")


class SecretMixin:
    """A mixin for making a sized object 'secret' (hiding the value(s)).

    See Also
    --------
    :py:class:`SecretStr`
    :py:class:`SecretBytes`
    """

    _P: Union[str, bytes]

    def __init__(self, value: Sized, *args, **kwargs):
        super().__init__()
        self.__repr = str(self._P * len(value))
        self.__secret = value

    def __repr__(self) -> str:
        return self.__repr

    def __str__(self) -> str:
        return self.__repr

    @property
    def secret(self) -> Sized:
        return self.__secret


class SecretStr(SecretMixin, str):
    """A string that hides the true value in its repr.

    The hidden value may be accessed via :py:attr:`SecretStr.secret`

    Examples
    --------
    >>> import typic
    >>> mysecret = typic.SecretStr("The Ring is in Frodo's pocket.")
    >>> print(mysecret)
    ******************************
    >>> print(mysecret.secret)
    The Ring is in Frodo's pocket.
    >>> f"{mysecret}"
    '******************************'
    >>> import json
    >>> json.dumps([mysecret])
    '["The Ring is in Frodo\\'s pocket."]'

    Notes
    -----
    This object inherits directly from :py:class:`str` and, so is natively JSON-serializable.
    There is no need to add logic to extract the secret value.

    See Also
    --------
    :py:class:`SecretMixin`
    """

    _P: str = "*"

    def __init__(self, value="", encoding=None, errors="strict"):
        super().__init__(value, encoding=encoding, errors=errors)


class SecretBytes(SecretMixin, bytes):
    """A bytes object that hides the true value in its repr.

    The hidden value may be accessed via :py:attr:`SecretBytes.secret`

    Notes
    -----
    :py:class:`bytes` is not natively JSON serializable, so a user would need to register
    a default handler for that type. However, once done, no additional work needs to be done
    to make this type serializable.

    See Also
    --------
    :py:class:`SecretMixin`
    :py:class:`SecretStr`
    """

    _P: bytes = b"*"

    def __init__(self, value=b"", encoding=None, errors="strict"):
        super().__init__(value, encoding=encoding, errors=errors)
