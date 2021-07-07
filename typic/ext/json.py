from typing import Callable, Any, AnyStr

dumps: Callable[..., AnyStr]
loads: Callable[..., Any]


try:
    import ujson

    dumps = ujson.dumps  # type: ignore
    loads = ujson.loads

except (ImportError, ModuleNotFoundError):  # pragma: nocover
    import json

    dumps = json.dumps  # type: ignore
    loads = json.loads
