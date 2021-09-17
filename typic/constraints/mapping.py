from __future__ import annotations

import dataclasses
import uuid
from types import MappingProxyType
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

from typic import gen, util
from typic.types.frozendict import FrozenDict, freeze
from .common import (
    BaseConstraints,
    ContextT,
    AssertionsT,
    VT,
    InstanceCheck,
    ConstraintsProtocolT,
)
from .error import ConstraintSyntaxError

if TYPE_CHECKING:  # pragma: nocover
    from typic.constraints.factory import ConstraintsT  # noqa: F401


def validate_pattern_constraints(
    constraints: Dict[Pattern, ConstraintsT], key: str, val: VT
) -> VT:
    for pattern, const in constraints.items():
        if pattern.match(key):
            val = const.validate(val)
    return val


MappedItemConstraints = Dict[Type, BaseConstraints]
ItemValidator = Union[
    Callable[[BaseConstraints, VT], VT], Callable[[MappedItemConstraints, VT], VT]
]


@util.slotted(dict=False)
@dataclasses.dataclass
class ItemValidatorNames:
    item_validators_name: str
    vals_validator_name: str
    keys_validator_name: str
    patterns_validators_name: str


@util.slotted
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
    items: Optional[FrozenDict[Hashable, ConstraintsProtocolT]] = None
    """A mapping of constraints associated to specific keys."""
    patterns: Optional[FrozenDict[Pattern, ConstraintsProtocolT]] = None
    """A mapping of constraints associated to any key which match the regex pattern."""
    values: Optional[ConstraintsProtocolT] = None
    """Whether values not defined as required are allowed.

    May be a boolean, or more constraints which are applied to all additional values.
    """
    keys: Optional[ConstraintsProtocolT] = None
    """Constraints to apply to any additional keys not explicitly defined."""
    key_dependencies: Optional[FrozenDict[str, KeyDependencyT]] = None
    """A mapping of keys and their dependent restrictions if they are present."""
    total: Optional[bool] = False
    """Whether to consider this schema as the 'total' representation.

    - If a mapping is `total=True`, no additional keys/values are allowed and cannot be
      defined.
    - Conversely, if a mapping is `total=False`, `required_keys` cannot not be
      defined.
    """
    X = "x"
    Y = "y"
    RETX = "retx"
    RETY = "rety"
    RETVAL = "retval"

    def _set_item_validator_loop_line(
        self, loop: gen.Block, func_name: str
    ) -> ContextT:
        names = ItemValidatorNames(
            item_validators_name=f"{func_name}_items",
            vals_validator_name=f"{func_name}_vals",
            keys_validator_name=f"{func_name}_keys",
            patterns_validators_name=f"{func_name}_patterns",
        )
        ctx: Dict[str, Any] = {}
        x = self.X
        y = self.Y
        field = f"_lazy_repr({self.FNAME}, {self.X})"
        if self.values:
            y = f"{names.vals_validator_name}({y}, field={field})"
            ctx[names.vals_validator_name] = self.values.validate
        if self.keys:
            x = f"{names.keys_validator_name}({self.X})"
            ctx[names.keys_validator_name] = self.keys.validate
        if self.patterns:
            y = (
                "validate_pattern_constraints"
                f"({names.patterns_validators_name}, {self.X}, {y})"
            )
            ctx[names.patterns_validators_name] = self.patterns
            ctx["validate_pattern_constraints"] = validate_pattern_constraints
        if self.items:
            ctx.update(
                {
                    names.item_validators_name: MappingProxyType(
                        {x: y.validate for x, y in self.items.items()}  # type: ignore
                    )
                }
            )
            y = (
                f"{names.item_validators_name}[{self.X}]({y}, field={field}) "
                f"if {self.X} in {names.item_validators_name} else {self.Y}"
            )

        loop.l(f"{x}: {y}")
        return ctx

    def _set_item_validator_pattern_constraints(self, loop: gen.Block, func_name: str):
        # Item constraints based upon key-pattern
        pattern_constr_name = f"{func_name}_pattern_constraints"
        if self.patterns:
            loop.l(
                f"{self.RETY} = "
                f"validate_pattern_constraints"
                f"({pattern_constr_name}, {self.X}, {self.Y})",
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
                f"valid = bool({key_pattern_name}.match({self.X}))",
                level=None,
                **{key_pattern_name: self.key_pattern},
            )
            with loop.b("if not valid:") as b:
                b.l("break")

    def _build_item_validator(self, func: gen.Block) -> Optional[ContextT]:
        if any(
            (
                self.items,
                self.patterns,
                self.key_pattern,
                self.keys,
                self.values,
            )
        ):
            with func.b(f"{self.VALUE} = {{") as loop:
                item_context = self._set_item_validator_loop_line(loop, func.name)
                loop.l(f"for {self.X}, {self.Y} in {self.VALUE}.items()")
            func.l("}")
            if self.key_pattern:
                key_pattern_name = f"{func.name}_key_pattern"
                with func.b(
                    f"if any((not {key_pattern_name}.match({self.X}) "
                    f"for {self.X} in {self.VALUE})):"
                ) as b:
                    b.l(f"return False, {self.VALUE}")
                    item_context[key_pattern_name] = self.key_pattern
            return item_context
        return None

    def _get_key_dependencies(self, assertions: AssertionsT, context: ContextT):
        for key, dep in self.key_dependencies.items():  # type: ignore
            # If it's a collection, then we're just checking if another set of keys exist.
            if isinstance(dep, Collection) and not isinstance(
                dep, (Mapping, str, bytes)
            ):
                line = (
                    f"{{*{self.VALUE}.keys()}}.issuperset({set(dep)})"
                    f"if {key!r} in {self.VALUE} else True"
                )
            # If it's an instance of mapping constraints,
            # then we validate the entire value against that constraint.
            elif isinstance(dep, MappingConstraints):
                name = f"__{key}_constr_{uuid.uuid4().int}"
                line = (
                    f"{name}.validate({self.VALUE}, field=field) "
                    f"if {key!r} in {self.VALUE} else True"
                )
                context[name] = dep
            # Fail loud and make the user fix that shit.
            else:
                raise ConstraintSyntaxError(
                    f"Got an unsupported dependency in {self!r} for key {key!r}: {dep!r}"
                )

            assertions.append(line)

    def _get_assertions(self) -> AssertionsT:
        assertions: List[str] = []
        if self.min_items is not None:
            assertions.append(f"size >= {self.min_items}")
        if self.max_items is not None:
            assertions.append(f"size <= {self.max_items}")
        if self.required_keys:
            assertions.append("valkeys.issuperset(required)")
        defined_keys = (self.required_keys or set()) | (self.items or {}).keys()
        if defined_keys:
            assertions.append(
                f"valkeys.{'issubset' if self.total else 'issuperset'}(defined)"
            )
        return assertions

    def _build_assertions(self, func: gen.Block, assertions: AssertionsT):
        if assertions:
            if (self.max_items, self.min_items) != (None, None):
                func.l(f"size = len({self.VALUE})")
            BaseConstraints._build_assertions(self, func, assertions)

    def _check_syntax(self):
        if self.total and (self.keys or self.values):
            raise ConstraintSyntaxError(
                f"A mapping may not be considered 'total' and allow additional "
                f"keys/values: {self}"
            )

    def _build_validator(
        self, func: gen.Block, context: Dict[str, Any], assertions: AssertionsT
    ) -> ContextT:
        if self.key_dependencies:
            self._get_key_dependencies(assertions, context)
        _lazy_repr = (
            util.collectionrepr if issubclass(self.type, Mapping) else util.joinedrepr
        )
        context.update(Mapping=Mapping, _lazy_repr=_lazy_repr)
        if self.required_keys:
            context["required"] = self.required_keys
        defined_keys = (self.required_keys or set()) | (self.items or {}).keys()
        if defined_keys:
            context["defined"] = frozenset(defined_keys)
        if not issubclass(self.type, Mapping):
            with func.b(f"if not isinstance({self.VALUE}, Mapping):") as b:
                b.l(f"return False, {self.VALUE}")
        func.l(f"valkeys = {{*{self.VALUE}}}")
        context = BaseConstraints._build_validator(
            self, func=func, context=context, assertions=assertions
        )
        items_context = self._build_item_validator(func)
        if items_context:
            context.update(items_context)
        return context

    def for_schema(self, *, with_type: bool = False) -> dict:
        props = (
            freeze({x: y.for_schema() for x, y in self.items.items()})
            if self.items
            else None
        )
        schema: Dict[str, Any] = dict(
            title=self.name,
            minProperties=self.min_items,
            maxProperties=self.max_items,
            required=tuple(self.required_keys) or None,
            properties=props,
            propertyNames=(
                {"pattern": self.key_pattern.pattern} if self.key_pattern else None
            ),
        )
        if with_type:
            schema["type"] = "object"
        return {x: y for x, y in schema.items() if y is not None}


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class DictConstraints(MappingConstraints):
    type: ClassVar[Type[dict]] = dict


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class ObjectConstraints(MappingConstraints):
    type: Type = dataclasses.field(default=object)  # type: ignore
    instancecheck: ClassVar[InstanceCheck] = InstanceCheck.IS
    total: bool = True
    coerce: bool = True


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class TypedDictConstraints(ObjectConstraints):
    instancecheck: ClassVar[InstanceCheck] = InstanceCheck.NOT
    ttype: Type = dict

    __ignore_repr__ = frozenset(("ttype",)) | ObjectConstraints.__ignore_repr__

    @util.cached_property
    def type_name(self):
        return util.get_name(self.ttype)


KeyDependencyT = Union[Tuple[str], MappingConstraints]
"""A 'key dependency' defines constraints which are applied *only* if a key is present.

This can be either a tuple of dependent keys, or an additional MappingConstraints, which
is treated as a sub-schema to the parent MappingConstraints.
"""
