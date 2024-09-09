# flake8: noqa
from __future__ import annotations

import json

from typing import Any, TYPE_CHECKING, AnyStr, Callable, Union

__all__ = ("dumps", "loads", "get_tojson")

if TYPE_CHECKING:
    from typic.serde.common import SerializerT

    dumps: Callable[..., Union[str, bytes]]
    loads: Callable[..., Any]

    def get_tojson(
        o: Any, *, ensure_ascii: bool = False, indent: int | None = None, **kwargs
    ) -> str | bytes: ...

else:

    try:
        import orjson

    except (ImportError, ModuleNotFoundError):
        orjson = None

    try:
        import ujson
    except (ImportError, ModuleNotFoundError):
        ujson = None

    if orjson:

        def get_tojson(serializer: SerializerT):
            def tojson(
                o: Any,
                *,
                ensure_ascii: bool = False,
                indent: int = None,
                __prim=serializer,
                __dumps=orjson.dumps,
                **kwargs,
            ) -> bytes:
                if indent:
                    option = kwargs.pop("option", None)
                    opt = orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE
                    kwargs["option"] = (opt | option) if option else opt
                return __dumps(__prim(o), **kwargs)

            tojson.__module__ = serializer.__module__
            tojson.__doc__ = orjson.dumps.__doc__

            return tojson

        dumps, loads = orjson.dumps, orjson.loads

    elif ujson:

        def get_tojson(serializer: SerializerT):
            def tojson(
                o: Any,
                *,
                ensure_ascii: bool = False,
                indent: int = None,
                __prim=serializer,
                __dumps=ujson.dumps,
                **kwargs,
            ) -> AnyStr:
                if indent is not None:
                    kwargs["indent"] = indent
                return __dumps(
                    __prim(o),
                    ensure_ascii=ensure_ascii,
                    **kwargs,
                )

            tojson.__module__ = get_tojson.__module__
            tojson.__doc__ = ujson.dumps.__doc__

            return tojson

        dumps, loads = ujson.dumps, ujson.loads

    else:

        def get_tojson(serializer: SerializerT):
            def tojson(
                o: Any,
                *,
                ensure_ascii: bool = False,
                indent: int = None,
                __prim=serializer,
                __dumps=json.dumps,
                **kwargs,
            ) -> AnyStr:
                return __dumps(
                    __prim(o),
                    indent=indent,
                    ensure_ascii=ensure_ascii,
                    **kwargs,
                )

            tojson.__module__ = get_tojson.__module__
            tojson.__doc__ = json.dumps.__doc__

            return tojson

        dumps, loads = json.dumps, json.loads
