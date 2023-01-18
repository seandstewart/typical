from __future__ import annotations

from typical.core import constraints
from typical.magic.schema import abc, jsonschema

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
            raise SchemaFormatUnknownError(
                f"Unknown schema format {format!r}. "
                f"Available formats are: {(*self.builders,)}."
            )
        return self.builders[format].build(c=c)

    def all(self, *, format: str = "jsonschema"):
        if format not in self.builders:
            raise SchemaFormatUnknownError(
                f"Unknown schema format {format!r}. "
                f"Available formats are: {(*self.builders,)}."
            )
        return self.builders[format].all()

    def attach(self, c: constraints.AbstractConstraints):
        for builder in self.builders.values():
            builder.attach(c)

    def register(
        self, name: str, builder: abc.AbstractSchemaBuilder, *, force: bool = False
    ):
        if name in self.builders and force is False:
            current = self.builders[name]
            raise SchemaFormatConflictError(
                f"{name!r} is already registered "
                f"with {current.__class__.__qualname__}. "
                "If you wish to override the current builder, "
                "pass `force=True` on registration."
            )
        self.builders[name] = builder


class SchemaFormatError(Exception):
    ...


class SchemaFormatConflictError(SchemaFormatError, LookupError):
    ...


class SchemaFormatUnknownError(SchemaFormatError, LookupError):
    ...
