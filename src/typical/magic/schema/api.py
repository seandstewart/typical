from __future__ import annotations

from typical import api
from typical.core.annotations import ObjectT
from typical.magic.schema import builder

__all__ = ("attach", "schema", "schemas", "register_format")


def schema(
    annotation: type[ObjectT],
    *,
    primitive: bool = False,
    format: str = "jsonschema",
):
    cv = api.resolver.constraints(annotation)
    sch = factory.build(cv.constraints, format=format)
    if primitive:
        resolved = api.resolver.resolve(annotation=sch.__class__)
        prim = resolved.primitive(sch)
        return prim
    return sch


factory = builder.SchemaBuilder()
schemas = factory.all
attach = factory.attach
register_format = factory.register
