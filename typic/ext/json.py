# flake8: noqa
from __future__ import annotations

from typing import Any, TYPE_CHECKING, AnyStr, Callable, Union

if TYPE_CHECKING:
    from typic.serde.common import SerializerT


__all__ = ("dumps", "loads", "get_tojson")


dumps: Callable[..., Union[str, bytes]]
loads: Callable[..., Any]


try:
    import orjson

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


except (ImportError, ModuleNotFoundError):
    orjson = None

    try:
        import ujson

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
                return __dumps(
                    __prim(o),
                    indent=indent,
                    ensure_ascii=ensure_ascii,
                    **kwargs,
                )

            tojson.__module__ = get_tojson.__module__
            tojson.__doc__ = ujson.dumps.__doc__

            return tojson

        dumps, loads = ujson.dumps, ujson.loads

    except (ImportError, ModuleNotFoundError):  # pragma: nobranch
        import json

        ujson = None

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
