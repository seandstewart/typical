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
)

from typic import gen
from typic.types.frozendict import FrozenDict
from .common import BaseConstraints, Context, Checks, VT
from .error import ConstraintSyntaxError

KeyDependency = Union[Tuple[str], "MappingConstraints"]
"""A 'key dependency' defines constraints which are applied *only* if a key is present.

This can be either a tuple of dependent keys, or an additional MappingConstraints, which
is treated as a sub-schema to the parent MappingConstraints.
"""


def _validate_item(constraints: BaseConstraints, val: VT) -> VT:
    return constraints.validate(val)


def _validate_item_multi(constraints: Dict[Type, BaseConstraints], val: VT) -> VT:
    validator = constraints.get(type(val))
    return validator.validate(val) if validator else val


def validate_pattern_constraints(
    constraints: Dict[Pattern, BaseConstraints], key: str, val: VT
) -> VT:
    for pattern, const in constraints.items():
        if pattern.match(key):
            val = const.validate(val)
    return val


@dataclasses.dataclass(frozen=True, repr=False)
class MappingConstraints(BaseConstraints):
    type: ClassVar[Type[Mapping]]
    min_items: Optional[int] = None
    """The minimum number of items which must be present in this mapping."""
    max_items: Optional[int] = None
    """The maximum number of items which may be present in this mapping."""
    required_keys: FrozenSet[str] = dataclasses.field(default_factory=frozenset)
    """A frozenset of keys which must be present in the mapping."""
    key_pattern: Optional[Pattern] = None
    """A regex pattern for which all keys must match."""
    items: FrozenDict[str, BaseConstraints] = dataclasses.field(
        default_factory=FrozenDict
    )
    """A mapping of constraints associated to specific keys."""
    patterns: FrozenDict[Pattern, BaseConstraints] = dataclasses.field(
        default_factory=FrozenDict
    )
    """A mapping of constraints associated to any key which match the regex pattern."""
    additional_items: Optional[Union[bool, BaseConstraints]] = None
    """Whether items not defined as required are allowed.

    May be a boolean, or more constraints which are applied to all additional items.
    """
    key_dependencies: FrozenDict[str, KeyDependency] = dataclasses.field(
        default_factory=FrozenDict
    )
    """A mapping of keys and their dependent restrictions if they are present."""

    def _select_additional_validator(
        self,
    ) -> Tuple[
        Union[Dict[str, BaseConstraints], BaseConstraints, None, bool],
        Callable[[BaseConstraints, Any], Any],
    ]:
        addtl_constraints = self.additional_items
        addtl_validator = _validate_item
        if isinstance(self.additional_items, tuple):
            addtl_constraints = {x.type: x for x in self.additional_items}
            addtl_validator = _validate_item_multi
        return addtl_constraints, addtl_validator

    def _set_item_validator_loop_line(self, loop: gen.Block, func_name: str):
        ctx: Dict[str, Any] = {}
        line = ""
        item_constr_name = f"{func_name}_items_validator"
        addtl_constr_name = f"{func_name}_addtl_constr"
        addtl_validator_name = f"{func_name}_addtl_validator"
        if self.items and self.additional_items:
            addtl_constraints, addtl_validator = self._select_additional_validator()
            line = (
                f"val[x] = {item_constr_name}[x].validate(y) "
                f"if x in {item_constr_name} "
                f"else {addtl_validator_name}({addtl_constr_name}, y)"
            )
            ctx.update(
                **{
                    item_constr_name: self.items,
                    addtl_constr_name: addtl_constraints,
                    addtl_validator_name: addtl_validator,
                }
            )
        elif self.items:
            line = (
                f"val[x] = {item_constr_name}[x].validate(y) "
                f"if x in {item_constr_name} else y"
            )
            ctx.update(**{item_constr_name: self.items})
        elif self.additional_items:
            addtl_constraints, addtl_validator = self._select_additional_validator()
            line = f"val[x] = {addtl_validator_name}({addtl_constr_name}, y)"
            ctx.update(
                **{
                    addtl_constr_name: addtl_constraints,
                    addtl_validator_name: addtl_validator,
                }
            )
        loop.l(line, level=None, **ctx)

    def _set_item_validator_pattern_constraints(self, loop: gen.Block, func_name: str):
        # Item constraints based upon key-pattern
        pattern_constr_name = f"{func_name}_pattern_constraints"
        if self.patterns:
            loop.l(
                f"val[x] = validate_pattern_constraints({pattern_constr_name}, x, y)",
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
        if any(
            (
                self.items,
                isinstance(self.additional_items, (BaseConstraints, tuple)),
                self.patterns,
                self.key_pattern,
            )
        ):
            if ns is None:
                ns = {}
            name = f"{func_name}_item_validator"
            with gen.Block(ns) as main:
                with main.f(
                    name,
                    main.param("val", annotation=self.type),
                    main.param("addtl", annotation=set),
                ) as f:
                    f.l("valid = True")
                    with f.b("for x, y in val.items():") as loop:
                        # Basic item constraints.
                        self._set_item_validator_loop_line(loop, name)
                        # Key pattern and Item constraints based on pattern.
                        self._set_item_validator_pattern_constraints(loop, name)
                    # Return the result of the validation
                    f.l("return valid, val")
            return main.compile(name=name), name
        return None, None

    def _build_key_dependencies(self, checks: Checks, context: Context):
        for key, dep in self.key_dependencies.items():
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

    def _build_validator(self, func: gen.Block) -> Tuple[Checks, Context]:

        func.l(
            f"addtl = val.keys() - "
            f"{(self.required_keys or set()) | self.items.keys()}"
        )
        if {self.max_items, self.min_items} != {None, None}:
            func.l("size = len(val)")

        context: Dict[str, Any] = {}
        checks: List[str] = []
        if self.min_items is not None:
            checks.append(f"size >= {self.min_items}")
        if self.max_items is not None:
            checks.append(f"size <= {self.max_items}")
        if self.required_keys:
            checks.append(f"{{*val.keys()}}.issuperset({self.required_keys})")
        if self.additional_items is False:
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
    def _set_return(func: gen.Block, checks: Checks, context: Context):
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
                {x: y.for_schema() for x, y in self.patterns.items()} or None
            ),
            additionalProperties=(
                self.additional_items.for_schema(with_type=True)
                if isinstance(self.additional_items, BaseConstraints)
                else self.additional_items
            ),
            dependencies=(
                {
                    x: y.for_schema() if isinstance(y, BaseConstraints) else y
                    for x, y in self.key_dependencies.items()
                }
                or None
            ),
        )
        if with_type:
            schema["type"] = "object"
        return {x: y for x, y in schema.items() if y is not None}


@dataclasses.dataclass(frozen=True, repr=False)
class DictConstraints(MappingConstraints):
    type: ClassVar[Type[dict]] = dict
