from __future__ import annotations

from typing import Union, Generic, TypeVar


class _Strict:
    __STRICT: bool = False

    def __bool__(self) -> bool:
        return self.__STRICT

    def __str__(self):  # pragma: nocover
        return str(self.__STRICT)

    def __repr__(self):  # pragma: nocover
        return f"<strict-mode={self.__STRICT}>"

    def __hash__(self):
        return hash(self.__STRICT)

    def is_strict_mode(self) -> bool:
        return self.__STRICT

    def strict_mode(self) -> bool:
        """Turn on global ``strict`` mode.

        All resolved annotations will validate their inputs against the generated
        constraints. In some cases, coercion may still be used as the method for
        validation. Additionally, post-validation coercion will occur for
        user-defined classes if needed.

        Notes
        -----
        Global state is messy, but this is provided for convenience. Care must be taken
        when manipulating global state in this way. If you intend to turn on global
        ``strict`` mode, it should be done once, at the start of the application
        runtime, before all annotations have been resolved.

        You cannot toggle ``strict`` mode off once it is enabled during the runtime
        of an application. This is intentional, to limit the potential for hazy or
        unclear state.

        If you find yourself in a situation where you need ``strict`` mode for some
        cases, but not others, you're encouraged to flag ``strict=True`` on the
        decorated class/callable, or even make use of the
        :py:class:`~typic.api.Strict` annotation to flag ``strict`` mode on
        individual fields.
        """
        self.__STRICT = True
        return self.__STRICT

    def _unstrict_mode(self) -> bool:
        self.__STRICT = False
        return self.__STRICT


_T = TypeVar("_T")


class Strict(Generic[_T]):
    pass


StrictStrT = Strict[str]
StrictModeT = Union[bool, _Strict]
STRICT_MODE = _Strict()
is_strict_mode = STRICT_MODE.is_strict_mode
strict_mode = STRICT_MODE.strict_mode
