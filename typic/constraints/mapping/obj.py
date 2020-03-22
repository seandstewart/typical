#!/usr/bin/env python
import dataclasses
from typing import (
    Type,
    ClassVar,
    Mapping,
    Dict,
    Any,
    FrozenSet,
    Pattern,
    Optional,
    Hashable,
    TYPE_CHECKING,
)

from typic import util
from ..common import (
    BaseConstraints,
    InstanceCheck,
)
from .builder import _build_validator, KeyDependencyT, _set_return


if TYPE_CHECKING:  # pragma: nocover
    from typic.constraints.factory import ConstraintsT  # noqa: F401


@dataclasses.dataclass(frozen=True, repr=False)
class MappingConstraints(BaseConstraints):
    type: ClassVar = Mapping
    min_items: Optional[int] = None
    """The minimum number of items which must be present in this mapping."""
    max_items: Optional[int] = None
    """The maximum number of items which may be present in this mapping."""
    required_keys: FrozenSet[str] = dataclasses.field(default_factory=frozenset)
    """A frozenset of keys which must be present in the mapping."""
    key_pattern: Optional[Pattern] = None
    """A regex pattern for which all keys must match."""
    items: Optional[Mapping[Hashable, "ConstraintsT"]] = None
    """A mapping of constraints associated to specific keys."""
    patterns: Optional[Mapping[Pattern, "ConstraintsT"]] = None
    """A mapping of constraints associated to any key which match the regex pattern."""
    values: Optional["ConstraintsT"] = None
    """Whether values not defined as required are allowed.

    May be a boolean, or more constraints which are applied to all additional values.
    """
    keys: Optional["ConstraintsT"] = None
    """Constraints to apply to any additional keys not explicitly defined."""
    key_dependencies: Optional[Mapping[str, KeyDependencyT]] = None
    """A mapping of keys and their dependent restrictions if they are present."""
    total: Optional[bool] = False
    """Whether to consider this schema as the 'total' representation.

    - If a mapping is ``total=True``, no additional keys/values are allowed and cannot be
      defined.
    - Conversely, if a mapping is ``total=False``, ``required_keys`` cannot not be
      defined.
    """
    X = "x"
    Y = "y"
    RETX = "retx"
    RETY = "rety"
    RETVAL = "retval"

    builder = _build_validator
    _returner = _set_return

    def for_schema(self, *, with_type: bool = False) -> dict:
        schema: Dict[str, Any] = dict(
            minProperties=self.min_items,
            maxProperties=self.max_items,
            required=tuple(self.required_keys) or None,
            propertyNames=(
                {"pattern": self.key_pattern.pattern} if self.key_pattern else None
            ),
            patternProperties=(
                {x: y.for_schema() for x, y in self.patterns.items()}
                if self.patterns
                else None
            ),
            additionalProperties=(
                self.values.for_schema(with_type=True)
                if self.values
                else not self.total
            ),
            dependencies=(
                {
                    x: y.for_schema(with_type=True)
                    if isinstance(y, BaseConstraints)
                    else y
                    for x, y in self.key_dependencies.items()
                }
                if self.key_dependencies
                else None
            ),
        )
        if with_type:
            schema["type"] = "object"
        return {x: y for x, y in schema.items() if y is not None}


@dataclasses.dataclass(frozen=True, repr=False)
class DictConstraints(MappingConstraints):
    type: ClassVar[Type[dict]] = dict


@dataclasses.dataclass(frozen=True, repr=False)
class ObjectConstraints(MappingConstraints):
    type: Type = object  # type: ignore
    instancecheck: ClassVar[InstanceCheck] = InstanceCheck.IS
    total: bool = True
    coerce: bool = True


@dataclasses.dataclass(frozen=True, repr=False)
class TypedDictConstraints(ObjectConstraints):
    instancecheck: ClassVar[InstanceCheck] = InstanceCheck.NOT
    ttype: Type = dict

    @util.cached_property
    def type_name(self):
        return util.get_name(self.ttype)
