from __future__ import annotations

from typic.core import constraints
from typic.core.schema import abc, jsonschema

__all__ = ("SchemaBuilder",)


class SchemaBuilder:
    __slots__ = ("builders",)

    def __init__(self):
        self.builders: dict[str, abc.AbstractSchemaBuilder] = {
            "jsonschema": jsonschema.JSONSchemaBuilder()
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(formats={(*self.builders,)})>"

    def build(self, c: constraints.AbstractConstraints, *, format: str = "jsonschema"):
        if format not in self.builders:
            raise ValueError(
                f"Unknown schema format {format!r}. "
                f"Available formats are: {(*self.builders,)}."
            )
        return self.builders[format].build(c=c)

    def all(self, *, format: str = "jsonschema"):
        if format not in self.builders:
            raise ValueError(
                f"Unknown schema format {format!r}. "
                f"Available formats are: {(*self.builders,)}."
            )
        return self.builders[format].all()

    def attach(self, c: constraints.AbstractConstraints):
        for builder in self.builders.values():
            builder.attach(c)

    def register(self, name: str, builder: abc.AbstractSchemaBuilder):
        self.builders[name] = builder
