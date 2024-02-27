# flake8: noqa
from __future__ import annotations

from typing import TYPE_CHECKING, Any, AnyStr, Callable, Union

if TYPE_CHECKING:
    from typical.core.interfaces import SerializerT


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
            sort_keys = kwargs.pop("sort_keys", None)
            option = kwargs.pop("option", None)
            if indent:
                opt = orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE
                option = (opt | option) if option else opt
            if sort_keys:
                opt = orjson.OPT_SORT_KEYS
                option = (opt | option) if option else opt
            if option is not None:
                kwargs["option"] = option

            return __dumps(__prim(o), **kwargs)

        tojson.__module__ = serializer.__module__
        tojson.__doc__ = orjson.dumps.__doc__

        return tojson

    dumps, loads = orjson.dumps, orjson.loads


except (ImportError, ModuleNotFoundError) as e:
    orjson = None

    try:
        import ujson

        def get_tojson(serializer: SerializerT):
            def tojson(
                o: Any,
                *,
                ensure_ascii: bool = False,
                indent: int = 0,
                __prim=serializer,
                __dumps=ujson.dumps,
                **kwargs,
            ) -> str:
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

    except (ImportError, ModuleNotFoundError) as e:  # pragma: nobranch
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
            ) -> str:
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
