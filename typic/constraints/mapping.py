#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import dataclasses
import uuid
from typing import (
    Type,
    ClassVar,
    Mapping,
    Dict,
    Any,
    Union,
    FrozenSet,
    Pattern,
    Callable,
    Optional,
    Tuple,
    Collection,
    List,
    Hashable,
    TYPE_CHECKING,
)

from typic import gen
from typic.types.frozendict import FrozenDict
from .common import (
    BaseConstraints,
    ContextT,
    ChecksT,
    VT,
    InstanceCheck,
)
from .error import ConstraintSyntaxError


if TYPE_CHECKING:  # pragma: nocover
    from typic.constraints.factory import ConstraintsT  # noqa: F401

KeyDependency = Union[Tuple[str], "MappingConstraints"]
"""A 'key dependency' defines constraints which are applied *only* if a key is present.

This can be either a tuple of dependent keys, or an additional MappingConstraints, which
is treated as a sub-schema to the parent MappingConstraints.
"""


def validate_pattern_constraints(
    constraints: Dict[Pattern, "ConstraintsT"], key: str, val: VT
) -> VT:
    for pattern, const in constraints.items():
        if pattern.match(key):
            val = const.validate(val)
    return val


MappedItemConstraints = Dict[Type, BaseConstraints]
ItemValidator = Union[
    Callable[[BaseConstraints, VT], VT], Callable[[MappedItemConstraints, VT], VT]
]


@dataclasses.dataclass
class ItemValidatorNames:
    item_validators_name: str
    vals_validator_name: str
    keys_validator_name: str


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
    items: Optional[FrozenDict[Hashable, "ConstraintsT"]] = None
    """A mapping of constraints associated to specific keys."""
    patterns: Optional[FrozenDict[Pattern, "ConstraintsT"]] = None
    """A mapping of constraints associated to any key which match the regex pattern."""
    values: Optional["ConstraintsT"] = None
    """Whether values not defined as required are allowed.

    May be a boolean, or more constraints which are applied to all additional values.
    """
    keys: Optional["ConstraintsT"] = None
    """Constraints to apply to any additional keys not explicitly defined."""
    key_dependencies: Optional[FrozenDict[str, KeyDependency]] = None
    """A mapping of keys and their dependent restrictions if they are present."""
    total: Optional[bool] = False
    """Whether to consider this schema as the 'total' representation.

    - If a mapping is ``total=True``, no additional keys/values are allowed and cannot be
      defined.
    - Conversely, if a mapping is ``total=False``, ``required_keys`` cannot not be
      defined.
    """

    def _set_item_validator_items_loop_line(
        self, loop: gen.Block, names: ItemValidatorNames
    ):

        ctx: Dict[str, Any] = {
            names.item_validators_name: {
                x: y.validate for x, y in self.items.items()  # type: ignore
            }
        }
        with loop.b(f"if x in {names.item_validators_name}:", **ctx) as b:
            b.l(f"rety = {names.item_validators_name}[x](y)")
        if any((self.keys, self.values)):
            with loop.b("else:") as b:
                if self.keys and self.values:
                    self._set_item_validator_keys_values_line(b, names)
                elif self.keys:
                    self._set_item_validator_keys_line(b, names)
                elif self.values:
                    self._set_item_validator_values_line(b, names)

    def _set_item_validator_keys_values_line(
        self, loop: gen.Block, names: ItemValidatorNames
    ):
        line = (
            "retx, rety = "
            f"{names.keys_validator_name}(x), "
            f"{names.vals_validator_name}(y)"
        )
        ctx = {
            names.keys_validator_name: self.keys.validate,  # type: ignore
            names.vals_validator_name: self.values.validate,  # type: ignore
        }
        loop.l(line, **ctx)  # type: ignore

    def _set_item_validator_keys_line(self, loop: gen.Block, names: ItemValidatorNames):
        line = f"retx = {names.keys_validator_name}(x)"
        ctx = {
            names.keys_validator_name: self.keys.validate,  # type: ignore
        }
        loop.l(line, **ctx)  # type: ignore

    def _set_item_validator_values_line(
        self, loop: gen.Block, names: ItemValidatorNames
    ):
        line = f"rety = {names.vals_validator_name}(y)"
        ctx = {
            names.vals_validator_name: self.values.validate,  # type: ignore
        }
        loop.l(line, **ctx)  # type: ignore

    def _set_item_validator_loop_line(self, loop: gen.Block, func_name: str):
        names = ItemValidatorNames(
            item_validators_name=f"{func_name}_items_validators",
            vals_validator_name=f"{func_name}_vals_validator",
            keys_validator_name=f"{func_name}_keys_validator",
        )
        if self.items:
            self._set_item_validator_items_loop_line(loop, names)
        elif self.keys and self.values:
            self._set_item_validator_keys_values_line(loop, names)
        elif self.keys:
            self._set_item_validator_keys_line(loop, names)
        elif self.values:
            self._set_item_validator_values_line(loop, names)

    def _set_item_validator_pattern_constraints(self, loop: gen.Block, func_name: str):
        # Item constraints based upon key-pattern
        pattern_constr_name = f"{func_name}_pattern_constraints"
        if self.patterns:
            loop.l(
                f"rety = validate_pattern_constraints({pattern_constr_name}, x, y)",
                level=None,
                **{
                    "validate_pattern_constraints": validate_pattern_constraints,
                    pattern_constr_name: self.patterns,
                },
            )
        # Required key pattern
        if self.key_pattern:
            key_pattern_name = f"{func_name}_key_pattern"
            loop.l(
                f"valid = bool({key_pattern_name}.match(x))",
                level=None,
                **{key_pattern_name: self.key_pattern},
            )
            with loop.b("if not valid:") as b:
                b.l("break")

    def _create_item_validator(
        self, func_name: str, ns: dict = None
    ) -> Tuple[Optional[Callable], Optional[str]]:
        if any((self.items, self.patterns, self.key_pattern, self.keys, self.values,)):
            if ns is None:
                ns = {}
            name = f"{func_name}_item_validator"
            with gen.Block(ns) as main:
                with main.f(
                    name, main.param("val"), main.param("addtl", annotation=set),
                ) as f:
                    f.l("retval, valid = {}, True")
                    with f.b("for x, y in val.items():") as loop:
                        loop.l("retx, rety = x, y")
                        # Basic item constraints.
                        self._set_item_validator_loop_line(loop, name)
                        # Key pattern and Item constraints based on pattern.
                        self._set_item_validator_pattern_constraints(loop, name)
                        loop.l("retval[retx] = rety")
                    # Return the result of the validation
                    f.l("return valid, retval")
            return main.compile(name=name), name
        return None, None

    def _build_key_dependencies(self, checks: ChecksT, context: ContextT):
        for key, dep in self.key_dependencies.items():  # type: ignore
            # If it's a collection, then we're just checking if another set of keys exist.
            if isinstance(dep, Collection) and not isinstance(
                dep, (Mapping, str, bytes)
            ):
                line = (
                    f"{{*val.keys()}}.issuperset({set(dep)})"
                    f"if {key!r} in val else True"
                )
            # If it's an instance of mapping constraints,
            # then we validate the entire value against that constraint.
            elif isinstance(dep, MappingConstraints):
                name = f"__{key}_constr_{uuid.uuid4().int}"
                line = f"{name}.validate(val) if {key!r} in val else True"
                context[name] = dep
            # Fail loud and make the user fix that shit.
            else:
                raise ConstraintSyntaxError(
                    f"Got an unsupported dependency in {self!r} for key {key!r}: {dep!r}"
                )

            checks.append(line)

    def _build_validator(self, func: gen.Block) -> Tuple[ChecksT, ContextT]:

        if self.total and (self.keys or self.values):
            raise ConstraintSyntaxError(
                f"A mapping may not be considered 'total' and allow additional "
                f"keys/values: {self}"
            )
        defined_keys = (self.required_keys or set()) | (self.items or {}).keys()
        if defined_keys:
            func.l(f"addtl = val.keys() - {defined_keys}")
        else:
            func.l(f"addtl = val.keys()")
        if {self.max_items, self.min_items} != {None, None}:
            func.l("size = len(val)")

        context: Dict[str, Any] = {"Mapping": Mapping}
        checks: List[str] = []
        if self.min_items is not None:
            checks.append(f"size >= {self.min_items}")
        if self.max_items is not None:
            checks.append(f"size <= {self.max_items}")
        if self.required_keys:
            checks.append(f"{{*val.keys()}}.issuperset({self.required_keys})")
        if self.total:
            checks.append("not addtl")
        if self.key_dependencies:
            self._build_key_dependencies(checks, context)
        check = " and ".join(checks) or "True"
        func.l(f"valid = {check}")
        item_validator, item_validator_name = self._create_item_validator(
            func.name, context  # type: ignore
        )
        if item_validator:
            with func.b("if valid:") as b:
                b.l(  # type: ignore
                    f"valid, val = {item_validator_name}(val, addtl)",
                    level=None,
                    **{item_validator_name: item_validator},
                )
        return [], context

    @staticmethod
    def _set_return(func: gen.Block, checks: ChecksT, context: ContextT):
        func.l("return valid, val", **context)

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
    type: Type = dataclasses.field(default=object)  # type: ignore
    instancecheck: ClassVar[InstanceCheck] = InstanceCheck.IS
    total: bool = True
    coerce: bool = True
