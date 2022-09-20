from __future__ import annotations

import decimal as stdlib_decimal
import functools
from typing import Any, Callable, Collection, Hashable, TypeVar, Union

from typic import checks, util
from typic.compat import Generic, Protocol
from typic.core import constants
from typic.core.constraints import (
    array,
    decimal,
    engine,
    mapping,
    number,
    structured,
    text,
)
from typic.core.constraints.core import types, validators
from typic.types import frozendict

VT = TypeVar("VT")

__all__ = ("ConstrainedType", "factory")


class ConstraintsFactory:
    def __init__(self):
        self.__stack = set()
        self._RESOLUTION_STACK = {
            checks.isenumtype: self._from_enum_type,
            checks.isliteral: self._from_literal_type,
            checks.isuniontype: self._from_union_type,
            checks.istexttype: self._from_text_type,
            lambda t: issubclass(t, bool): self._from_bool_type,
            checks.isnumbertype: self._from_number_type,
            checks.isstructuredtype: self._from_user_type,
            checks.ismappingtype: self._from_mapping_type,
            checks.iscollectiontype: self._from_array_type,
        }

    @functools.lru_cache(maxsize=None)
    def build(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        name: str = None,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
        **config,
    ) -> types.AbstractConstraintValidator:
        if hasattr(t, "__constraints__"):
            return t.__constraints__  # type: ignore[attr-defined]

        while checks.should_unwrap(t):
            _nullable = checks.isoptionaltype(t)
            args = util.get_args(t)
            if _nullable:
                args = args[:-1]
            nullable = nullable or _nullable
            t = args[0] if len(args) == 1 else Union[args]
        if t in (Any, ..., type(...)):
            return engine.ConstraintValidator(
                constraints=types.TypeConstraints(
                    type=t, nullable=nullable, default=default
                ),
                validator=validators.NoOpInstanceValidator(
                    type=t,
                    precheck=validators.NoOpPrecheck(
                        type=t, nullable=nullable, name=name, **config
                    ),
                ),
            )
        if t is cls or t in self.__stack:
            module = getattr(t, "__module__", None)
            if cls and cls is not ...:
                module = cls.__module__
            return types.DelayedConstraintValidator(
                ref=t,
                module=module,
                localns={},
                nullable=nullable,
                name=name,
                factory=self.build,
                **config,
            )
        if checks.isforwardref(t):
            if not cls or cls is ...:
                raise TypeError(
                    f"Cannot build constraints for {t} without an enclosing class."
                )
            return types.DelayedConstraintValidator(
                ref=t,
                module=cls.__module__,
                localns=(getattr(cls, "__dict__") or {}).copy(),
                nullable=nullable,
                name=name,
                factory=self.build,
                **config,
            )
        with _limit_cyclic(t, self.__stack):
            ot = util.origin(t)
            handler = self._from_strict_type
            for check, factory in self._RESOLUTION_STACK.items():
                if check(ot):
                    handler = factory  # type: ignore[assignment]
                    break
            cv = handler(t, nullable=nullable, cls=cls, **config)
        return cv

    _RESOLUTION_STACK: dict[_FactoryCheckT, _ConstraintFactoryT]

    def _from_strict_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
    ) -> engine.ConstraintValidator[VT]:
        constraints = types.TypeConstraints(type=t, nullable=nullable, default=default)
        validator_cls = (
            validators.NullableIsInstanceValidator
            if nullable
            else validators.IsInstanceValidator
        )
        validator = validator_cls(type=t, precheck=validators.NoOpPrecheck(type=t))
        return engine.ConstraintValidator(constraints=constraints, validator=validator)

    def _from_text_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
        **config,
    ) -> engine.ConstraintValidator[VT]:
        return_if_instance = not config
        constraints = types.TextConstraints(
            type=t, nullable=nullable, default=default, **config
        )
        validator = text.get_validator(
            constraints=constraints,
            return_if_instance=return_if_instance,
            nullable=nullable,
        )
        return engine.ConstraintValidator(constraints=constraints, validator=validator)

    def _from_bool_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
        **config,
    ) -> engine.ConstraintValidator[VT]:
        constraints = types.TypeConstraints(type=t, nullable=nullable, default=default)
        validator_cls = (
            validators.NullableIsInstanceValidator
            if nullable
            else validators.IsInstanceValidator
        )
        validator = validator_cls(
            type=t,
            precheck=validators.NoOpPrecheck(),
        )
        return engine.ConstraintValidator(constraints=constraints, validator=validator)

    def _from_number_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
        **config,
    ) -> engine.ConstraintValidator[VT]:
        is_decimal = issubclass(t, stdlib_decimal.Decimal)
        return_if_instance = not config
        constraints: types.NumberConstraints
        if is_decimal:
            constraints = types.DecimalConstraints(
                type=t, nullable=nullable, default=default, **config
            )
            validator = decimal.get_validator(
                constraints=constraints,
                return_if_instance=return_if_instance,
                nullable=nullable,
            )
        else:
            constraints = types.NumberConstraints(type=t, **config)
            validator = number.get_validator(
                constraints=constraints,
                return_if_instance=return_if_instance,
                nullable=nullable,
            )
        return engine.ConstraintValidator(constraints=constraints, validator=validator)

    def _from_array_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
        values: types.AbstractConstraintValidator = None,
        **config,
    ) -> types.AbstractConstraintValidator[VT]:
        args = util.get_args(t)
        if values is None and args and args[0] is not Any:
            vt = args[0]
            values = self.build(vt, nullable=checks.isoptionaltype(vt), cls=cls or t)
        origin = util.origin(t)
        unique = checks.issubclass(t, (set, frozenset))
        config.setdefault("unique", unique)
        constraints = types.ArrayConstraints(
            type=origin,
            values=values.constraints if values else None,
            nullable=nullable,
            default=default,
            **config,
        )
        validator = array.get_validator(
            constraints=constraints,
            return_if_instance=not config and values is None,
            nullable=nullable,
        )
        if values is None:
            return engine.ConstraintValidator(
                constraints=constraints, validator=validator
            )
        return engine.ArrayConstraintValidator(
            constraints=constraints, validator=validator, items=values, assertion=None
        )

    def _from_mapping_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        keys: types.AbstractConstraintValidator = None,
        values: types.AbstractConstraintValidator = None,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
        **config,
    ) -> types.AbstractConstraintValidator[VT]:
        args = util.get_args(t)
        if args:
            key_arg, value_arg = args
            if keys is None and key_arg is not Any:
                keys = self.build(key_arg, cls=cls)
            if values is None and value_arg is not Any:
                values = self.build(value_arg, cls=cls)
        origin = util.origin(t)
        constraints = types.MappingConstraints(
            type=origin,
            keys=keys.constraints if keys else None,
            values=values.constraints if values else None,
            nullable=nullable,
            default=default,
            **config,
        )
        return_if_instance = not config and (keys, values) == (None, None)
        validator = mapping.get_validator(
            constraints=constraints,
            return_if_instance=return_if_instance,
            nullable=nullable,
        )
        if (keys, values) == (None, None):
            return engine.ConstraintValidator(
                constraints=constraints, validator=validator
            )
        keys_cv: engine.FieldEntryValidator | None = (
            engine.FieldEntryValidator(keys) if keys else None
        )
        values_cv: engine.ValueEntryValidator | None = (
            engine.ValueEntryValidator(values) if values else None
        )
        items: engine.FieldEntryValidator | engine.ValueEntryValidator | engine.CompoundEntryValidator | None
        items = keys_cv or values_cv
        if keys_cv and values_cv:
            items = engine.CompoundEntryValidator(keys_cv, values_cv)
        return engine.MappingConstraintValidator(
            constraints=constraints,
            validator=validator,
            items=items,
            assertion=None,
        )

    def _from_union_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
    ) -> engine.AbstractMultiConstraintValidator[VT]:
        ut = util.flatten_union(t)  # type: ignore[arg-type]
        nullable = nullable or checks.isoptionaltype(ut)  # type: ignore[arg-type]
        args = util.get_args(ut)
        args_cvs = [self.build(a, cls=cls) for a in args]
        tag = util.get_tag_for_types(args)
        value_constraints = (*(cv.constraints for cv in args_cvs),)
        constraints = types.MultiConstraints(
            type=ut,
            nullable=nullable,
            default=default,
            constraints=value_constraints,
            tag=tag,
        )
        has_tag = tag is not None
        truth = (has_tag, nullable)
        factory = self._MULTI_CONSTRAINT_TRUTH_TABLE[truth]
        cv = factory(constraints=constraints, constraint_validators=(*args_cvs,))
        return cv

    _MULTI_CONSTRAINT_TRUTH_TABLE: dict[
        tuple[bool, bool], type[engine.AbstractMultiConstraintValidator]
    ]
    _MULTI_CONSTRAINT_TRUTH_TABLE = {
        (True, True): engine.TaggedNullableMultiConstraintValidator,
        (True, False): engine.TaggedMultiConstraintValidator,
        (False, True): engine.NullableMultiConstraintValidator,
        (False, False): engine.SimpleMultiConstraintValidator,
    }

    def _from_literal_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
    ) -> engine.ConstraintValidator[VT]:
        items = util.get_args(t)
        if items[-1] is None:
            nullable = True
            items = items[:-1]

        v_cls = (
            validators.NullableOneOfValidator if nullable else validators.OneOfValidator
        )
        validator = v_cls(*items, type=t)
        constraints = types.EnumerationConstraints(
            type=t, nullable=nullable, default=default, items=items
        )
        cv: engine.ConstraintValidator[VT] = engine.ConstraintValidator(
            constraints=constraints,
            validator=validator,
        )
        return cv

    def _from_enum_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
    ) -> engine.ConstraintValidator[VT]:
        items = (*(v.value for v in t), *t)  # type: ignore[misc,attr-defined]
        v_cls = (
            validators.NullableOneOfValidator if nullable else validators.OneOfValidator
        )
        validator = v_cls(*items, type=t)
        constraints = types.EnumerationConstraints(
            type=t, nullable=nullable, default=default, items=items
        )
        cv: engine.ConstraintValidator[VT] = engine.ConstraintValidator(
            constraints=constraints,
            validator=validator,
        )
        return cv

    def _from_user_type(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
    ):
        isnamedtuple = checks.isnamedtuple(t)
        fields: dict[str, types.AbstractConstraints]
        constraints: types.AbstractConstraints
        if checks.istupletype(t) and not isnamedtuple:
            hints = util.cached_type_hints(t)
            cvs = (*(self.build(h, cls=cls) for h in hints),)
            fields = frozendict.freeze(dict(enumerate(cv.constraints for cv in cvs)))
            assertion_cls = structured.get_assertion_cls(
                has_fields=False, is_tuple=True
            )
            assertion = assertion_cls(fields=fields, size=len(cvs))
            constraints = types.ArrayConstraints(
                type=Collection, nullable=nullable, default=default
            )
            validator = array.get_validator(
                constraints=constraints,
                return_if_instance=False,
                nullable=nullable,
            )
            cv = engine.StructuredTupleConstraintValidator(
                constraints=constraints,
                validator=validator,
                assertion=assertion,
                items=cvs,
            )
            return cv

        sig = util.cached_signature(t)
        hints = util.cached_type_hints(t)
        params = {**sig.parameters}
        items: dict[str, types.AbstractConstraintValidator] = {}
        fields = {}
        required: list[str] = []
        istypeddict = checks.istypeddict(t)
        for name, param in params.items():
            annotation = param.annotation
            if (
                annotation is param.empty
                or checks.isforwardref(annotation)
                or annotation.__class__ is str
            ) and name in hints:
                annotation = hints[name]
                params[name] = param.replace(annotation=annotation)
            pnullable = param.default in (None, Ellipsis) or checks.isoptionaltype(
                annotation
            )
            default = constants.EMPTY if param.default is param.empty else param.default
            if (
                param.kind not in {param.VAR_POSITIONAL, param.VAR_KEYWORD}
                and default is constants.EMPTY
            ):
                required.append(name)
            if annotation in (Any, Ellipsis, param.empty, constants.EMPTY):
                continue
            cv = self.build(
                annotation,
                nullable=pnullable,
                name=name,
                default=default,
                cls=t,  # type: ignore[arg-type]
            )
            items[name] = cv
            fields[name] = cv.constraints

        assertion_cls = structured.get_assertion_cls(
            has_fields=True, is_tuple=isnamedtuple
        )
        assertion = assertion_cls(fields=frozenset(required), size=len(required))
        constraints = types.StructuredObjectConstraints(
            type=t,
            fields=frozendict.freeze(fields),
            required=tuple(required),
        )
        validator = structured.get_validator(
            constraints=constraints,
            return_if_instance=not istypeddict,
            nullable=nullable,
            has_fields=bool(required),
            is_tuple=isnamedtuple,
        )
        cv = engine.StructuredObjectConstraintValidator(
            constraints=constraints,
            validator=validator,
            assertion=assertion,
            items=items,
        )
        return cv


_sentinel = object()
_FactoryCheckT = Callable[[type], bool]


class _ConstraintFactoryT(Protocol[VT]):
    def __call__(
        self,
        t: type[VT],
        *,
        nullable: bool = False,
        cls: type | None | ... = ...,  # type: ignore[misc]
        default: Hashable | Callable[[], VT] | constants._Empty = constants.EMPTY,
        **config,
    ) -> types.AbstractConstraintValidator[VT]:
        ...


class _limit_cyclic:
    __slots__ = ("t", "stack")

    def __init__(self, t, stack: set):
        self.t = t
        self.stack = stack

    def __enter__(self):
        self.stack.add(self.t)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stack.clear()


class ConstrainedType(Generic[VT]):
    __constraints__: types.AbstractConstraintValidator[VT]
    __parent__: type[VT]
    __args__: tuple[()] | tuple[type] | tuple[type, type]

    def __init_subclass__(
        cls: type[VT],
        keys: type | tuple[type, ...] = None,
        values: type | tuple[type, ...] = None,
        **constraints,
    ):
        cls.__resolve_constraints(keys=keys, values=values, **constraints)  # type: ignore[attr-defined]
        cls.__set_constructor()  # type: ignore[attr-defined]

    @classmethod
    def __resolve_constraints(
        cls: type[VT],
        keys: type | tuple[type, ...] = None,
        values: type | tuple[type, ...] = None,
        **constraints,
    ):
        args = []
        if keys and checks.ismappingtype(cls):
            kcv = cls.__handle_sub_constraints(keys)  # type: ignore[attr-defined]
            args.append(kcv.constraints.type)
            constraints["keys"] = kcv
        if values and checks.iscollectiontype(cls):
            vcv = cls.__handle_sub_constraints(values)  # type: ignore[attr-defined]
            args.append(vcv.constraints.type)
            constraints["values"] = vcv
        cv = factory.build(t=cls, **constraints)  # type: ignore[arg-type]
        cls.__constraints__ = cv  # type: ignore[attr-defined]
        cls.__args__ = (*args,)  # type: ignore[attr-defined]
        cls.__parent__ = cv.constraints.type  # type: ignore[attr-defined,union-attr]

    @classmethod
    def __set_constructor(cls: type[VT]):
        if issubclass(cls, (str, bytes, int, float)):
            wrapper = cls.__get_new_wrapper()  # type: ignore[attr-defined]
            cls.__new__ = wrapper(cls.__new__)  # type: ignore[assignment]
            return
        wrapper = cls.__get_init_wrapper()  # type: ignore[attr-defined]
        cls.__init__ = wrapper(cls.__init__)  # type: ignore[assignment]

    @classmethod
    def __get_new_wrapper(cls: type[VT]):
        __validate = cls.__constraints__.validate  # type: ignore[attr-defined]

        def new(_new):
            @functools.wraps(_new)
            def __constrained_new(*args, __validate=__validate, **kwargs) -> VT:
                result = _new(*args, **kwargs)
                return __validate(result)

            return __constrained_new

        return new

    @classmethod
    def __get_init_wrapper(cls: type[VT]):
        __validate = cls.__constraints__.validate  # type: ignore[attr-defined]

        def init(_init):
            @functools.wraps(_init)
            def __constrained_init(self: VT, *args, __validate=__validate, **kwargs):
                _init(self, *args, **kwargs)
                __validate(self)

            return __constrained_init

        return init

    @staticmethod
    def __handle_sub_constraints(
        sub: type | tuple[type, ...] = None
    ) -> types.AbstractConstraintValidator:
        if isinstance(sub, tuple):
            return factory.build(Union[sub])
        return factory.build(sub)


factory = ConstraintsFactory()
