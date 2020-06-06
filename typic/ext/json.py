from typing import Callable, Any, AnyStr

dumps: Callable[..., AnyStr]
loads: Callable[..., Any]
NATIVE_JSON = False


try:
    import ujson

    dumps = ujson.dumps  # type: ignore
    loads = ujson.loads

except (ImportError, ModuleNotFoundError):  # pragma: nocover
    NATIVE_JSON = True
    import json

    dumps = json.dumps  # type: ignore
    loads = json.loads


def using_stdlib() -> bool:
    return NATIVE_JSON
