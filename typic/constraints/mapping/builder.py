from typing import (
    Dict,
    Pattern,
    Union,
    Tuple,
    Type,
    Callable,
    TYPE_CHECKING,
    Any,
    Optional,
    Collection,
    Mapping,
    List,
)

from typic import gen, util
from typic.constraints.common import (
    BaseConstraints,
    VT,
    ChecksT,
    ContextT,
    ConstraintSyntaxError,
)

if TYPE_CHECKING:
    from .obj import MappingConstraints  # noqa: F401
    from ..factory import ConstraintsT  # noqa: F401


def validate_pattern_constraints(
    constraints: Dict[Pattern, "ConstraintsT"], key: str, val: VT
) -> VT:
    for pattern, const in constraints.items():
        if pattern.match(key):
            val = const.validate(val)
    return val


KeyDependencyT = Union[Tuple[str], "MappingConstraints"]
"""A 'key dependency' defines constraints which are applied *only* if a key is present.

This can be either a tuple of dependent keys, or an additional MappingConstraints, which
is treated as a sub-schema to the parent MappingConstraints.
"""

MappedItemConstraintsT = Dict[Type, BaseConstraints]
ItemValidatorT = Union[
    Callable[[BaseConstraints, VT], VT], Callable[[MappedItemConstraintsT, VT], VT]
]


class ItemValidatorNames:
    def __init__(
        self,
        item_validators_name: str,
        vals_validator_name: str,
        keys_validator_name: str,
    ):
        self.item_validators_name = item_validators_name
        self.vals_validator_name = vals_validator_name
        self.keys_validator_name = keys_validator_name

    def __repr__(self):
        return (
            f"{type(self).__name__}("
            f"item_validators_name={self.item_validators_name}, "
            f"vals_validator_name={self.vals_validator_name}, "
            f"keys_validator_name={self.keys_validator_name})"
        )


def _set_item_validator_items_loop_line(
    constr: "MappingConstraints", loop: gen.Block, names: ItemValidatorNames
):
    ctx: Dict[str, Any] = {
        names.item_validators_name: {
            x: y.validate for x, y in constr.items.items()  # type: ignore
        }
    }
    with loop.b(f"if {constr.X} in {names.item_validators_name}:", **ctx) as b:
        field = f"'.'.join(({constr.VALTNAME}, {constr.X}))"
        b.l(
            f"{constr.RETY} = "
            f"{names.item_validators_name}[{constr.X}]({constr.Y}, field={field})"
        )
    if any((constr.keys, constr.values)):
        with loop.b("else:") as b:
            if constr.keys and constr.values:
                _set_item_validator_keys_values_line(constr, b, names)
            elif constr.keys:
                _set_item_validator_keys_line(constr, b, names)
            elif constr.values:
                _set_item_validator_values_line(constr, b, names)


def _set_item_validator_keys_values_line(
    constr: "MappingConstraints", loop: gen.Block, names: ItemValidatorNames
):
    field = f"'.'.join(({constr.VALTNAME}, {constr.X}))"
    line = (
        f"{constr.RETX}, {constr.RETY} = "
        f"{names.keys_validator_name}({constr.X}), "
        f"{names.vals_validator_name}({constr.Y}, field={field})"
    )
    ctx = {
        names.keys_validator_name: constr.keys.validate,  # type: ignore
        names.vals_validator_name: constr.values.validate,  # type: ignore
    }
    loop.l(line, **ctx)  # type: ignore


def _set_item_validator_keys_line(
    constr: "MappingConstraints", loop: gen.Block, names: ItemValidatorNames
):
    line = f"{constr.RETX} = {names.keys_validator_name}({constr.X})"
    ctx = {
        names.keys_validator_name: constr.keys.validate,  # type: ignore
    }
    loop.l(line, **ctx)  # type: ignore


def _set_item_validator_values_line(
    constr: "MappingConstraints", loop: gen.Block, names: ItemValidatorNames
):
    field = f"'.'.join(({constr.VALTNAME}, {constr.X}))"
    line = f"{constr.RETY} = {names.vals_validator_name}({constr.Y}, field={field})"
    ctx = {
        names.vals_validator_name: constr.values.validate,  # type: ignore
    }
    loop.l(line, **ctx)  # type: ignore


def _set_item_validator_loop_line(
    constr: "MappingConstraints", loop: gen.Block, func_name: str
):
    names = ItemValidatorNames(
        item_validators_name=f"{func_name}_items_validators",
        vals_validator_name=f"{func_name}_vals_validator",
        keys_validator_name=f"{func_name}_keys_validator",
    )
    if constr.items:
        _set_item_validator_items_loop_line(constr, loop, names)
    elif constr.keys and constr.values:
        _set_item_validator_keys_values_line(constr, loop, names)
    elif constr.keys:
        _set_item_validator_keys_line(constr, loop, names)
    elif constr.values:
        _set_item_validator_values_line(constr, loop, names)


def _set_item_validator_pattern_constraints(
    constr: "MappingConstraints", loop: gen.Block, func_name: str
):
    # Item constraints based upon key-pattern
    pattern_constr_name = f"{func_name}_pattern_constraints"
    if constr.patterns:
        loop.l(
            f"{constr.RETY} = "
            f"validate_pattern_constraints"
            f"({pattern_constr_name}, {constr.X}, {constr.Y})",
            level=None,
            **{
                "validate_pattern_constraints": validate_pattern_constraints,
                pattern_constr_name: constr.patterns,
            },
        )
    # Required key pattern
    if constr.key_pattern:
        key_pattern_name = f"{func_name}_key_pattern"
        loop.l(
            f"valid = bool({key_pattern_name}.match({constr.X}))",
            level=None,
            **{key_pattern_name: constr.key_pattern},
        )
        with loop.b("if not valid:") as b:
            b.l("break")


def _create_item_validator(
    constr: "MappingConstraints", func_name: str, ns: dict = None
) -> Tuple[Optional[Callable], Optional[str]]:
    if any(
        (constr.items, constr.patterns, constr.key_pattern, constr.keys, constr.values,)
    ):
        if ns is None:
            ns = {}
        name = f"{func_name}_item_validator"
        with gen.Block(ns) as main:
            with main.f(
                name, main.param(constr.VAL), main.param("addtl", annotation=set),
            ) as f:
                f.l(f"{constr.VALTNAME} = {constr.type_name!r}")
                f.l(f"{constr.RETVAL}, valid = {{}}, True")
                with f.b(
                    f"for {constr.X}, {constr.Y} in {constr.VAL}.items():"
                ) as loop:
                    loop.l(f"{constr.RETX}, {constr.RETY} = {constr.X}, {constr.Y}")
                    # Basic item constraints.
                    _set_item_validator_loop_line(constr, loop, name)
                    # Key pattern and Item constraints based on pattern.
                    _set_item_validator_pattern_constraints(constr, loop, name)
                    loop.l(f"{constr.RETVAL}[{constr.RETX}] = {constr.RETY}")
                # Return the result of the validation
                f.l(f"return valid, {constr.RETVAL}")
        return main.compile(name=name), name
    return None, None


def _build_key_dependencies(
    constr: "MappingConstraints", checks: ChecksT, context: ContextT
):
    for key, dep in constr.key_dependencies.items():  # type: ignore
        # If it's a collection, then we're just checking if another set of keys exist.
        if isinstance(dep, Collection) and not isinstance(dep, (Mapping, str, bytes)):
            line = (
                f"{{*{constr.VAL}.keys()}}.issuperset({set(dep)})"
                f"if {key!r} in val else True"
            )
        # If it's an instance of mapping constraints,
        # then we validate the entire value against that constraint.
        elif isinstance(dep, type(constr)):
            name = f"__{key}_constr_{util.hexhash(dep)}"
            line = (
                f"{name}.validate({constr.VAL}) "
                f"if {key!r} in {constr.VAL} else True"
            )
            context[name] = dep
        # Fail loud and make the user fix that shit.
        else:
            raise ConstraintSyntaxError(
                f"Got an unsupported dependency in {constr!r} for key {key!r}: {dep!r}"
            )

        checks.append(line)


def _build_validator(
    constr: "MappingConstraints", func: gen.Block
) -> Tuple[ChecksT, ContextT]:
    if constr.total and (constr.keys or constr.values):
        raise ConstraintSyntaxError(
            f"A mapping may not be considered 'total' and allow additional "
            f"keys/values: {constr}"
        )
    defined_keys = (constr.required_keys or set()) | (constr.items or {}).keys()
    if defined_keys:
        func.l(f"addtl = {constr.VAL}.keys() - {defined_keys}")
    else:
        func.l(f"addtl = {constr.VAL}.keys()")
    if {constr.max_items, constr.min_items} != {None, None}:
        func.l(f"size = len({constr.VAL})")

    context: Dict[str, Any] = {"Mapping": Mapping}
    checks: List[str] = []
    if constr.min_items is not None:
        checks.append(f"size >= {constr.min_items}")
    if constr.max_items is not None:
        checks.append(f"size <= {constr.max_items}")
    if constr.required_keys:
        checks.append(f"{{*val.keys()}}.issuperset({constr.required_keys})")
    if constr.total:
        checks.append("not addtl")
    if constr.key_dependencies:
        _build_key_dependencies(constr, checks, context)
    check = " and ".join(checks) or "True"
    func.l(f"valid = {check}")
    item_validator, item_validator_name = _create_item_validator(
        constr, func.name, context  # type: ignore
    )
    if item_validator:
        with func.b("if valid:") as b:
            b.l(  # type: ignore
                f"valid, {constr.VAL} = {item_validator_name}({constr.VAL}, addtl)",
                level=None,
                **{item_validator_name: item_validator},
            )
    return [], context


def _set_return(
    constr: "BaseConstraints", func: gen.Block, checks: ChecksT, context: ContextT
):
    func.l(f"return valid, {constr.VAL}", **context)
