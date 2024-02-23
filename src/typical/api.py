from __future__ import annotations as a

from typical import constraints, serde
from typical.core.annotations import ReadOnly, WriteOnly
from typical.constraints import ConstrainedType, constrained
from typical.core.interfaces import Annotation, SerdeFlags, SerdeProtocol
from typical.resolver import resolver
from typical.serde.binder import BoundArguments
from typical.serde.ser import SerializationValueError
from typical.core.strict import Strict, StrictStrT, is_strict_mode, strict_mode
from typical.core.strings import Case
from typical.env import EnvironmentTypeError, EnvironmentValueError

__all__ = (
    "Annotation",
    "bind",
    "BoundArguments",
    "Case",
    "constrained",
    "ConstrainedType",
    "constraints",
    "decode",
    "encode",
    "EnvironmentTypeError",
    "EnvironmentValueError",
    "flags",
    "is_strict_mode",
    "iterate",
    "tojson",
    "primitive",
    "protocol",
    "protocols",
    "ReadOnly",
    "register",
    "resolver",
    "serde",
    "SerdeFlags",
    "SerdeProtocol",
    "SerializationValueError",
    "Strict",
    "strict_mode",
    "StrictStrT",
    "transmute",
    "translate",
    "validate",
    "WriteOnly",
)


transmute = resolver.transmute
translate = resolver.translate
validate = resolver.validate
bind = resolver.bind
register = resolver.des.register
primitive = resolver.primitive
protocols = resolver.protocols
protocol = resolver.resolve
tojson = resolver.tojson
iterate = resolver.iterate
flags = SerdeFlags
encode = resolver.encode
decode = resolver.decode
