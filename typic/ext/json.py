import functools
from typing import Callable, Any, AnyStr

dumps: Callable[..., AnyStr]
loads: Callable[..., Any]


try:
    import ujson

    dumps = ujson.dumps  # type: ignore
    loads = ujson.loads

except ImportError:  # pragma: nocover
    import json
    from typic.serde.resolver import resolver

    dumps = functools.partial(json.dumps, default=resolver.primitive)  # type: ignore
    loads = json.loads
