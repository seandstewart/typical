from __future__ import annotations

import abc
import collections.abc
import dataclasses
import enum
import reprlib
import sys
import warnings
from inspect import Signature
from typing import (  # type: ignore
    Callable,
    Any,
    ClassVar,
    Type,
    Tuple,
    List,
    Dict,
    TypeVar,
    Union,
    TYPE_CHECKING,
    Iterable,
    Iterator,
    Set,
    Optional,
    Mapping,
    _GenericAlias,  # type: ignore
)

from typic import gen, util, checks
from typic.compat import ForwardRef, evaluate_forwardref, Protocol
from .error import ConstraintValueError

if TYPE_CHECKING:  # pragma: nocover
    from typic.constraints.factory import ConstraintsT  # noqa: F401


__all__ = (
    "BaseConstraints",
    "EnumConstraints",
    "LiteralConstraints",
    "MultiConstraints",
    "TypeConstraints",
    "ValidatorT",
    "ValidateT",
    "ConstraintsProtocolT",
    "VT",
)

VT = TypeVar("VT")
"""A generic type-var for values passed to a validator."""
AssertionsT = List[str]
ContextT = Dict[str, Any]
_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)


class ValidatorT(Protocol[_T_co]):
    """The expected signature of a value validator."""

    def __call__(
        self, value: Any, *, field: str = None, **kwargs
    ) -> Tuple[bool, _T_co]:
        ...


class ValidateT(Protocol[_T_co]):
    """The signature of the public validate callable for a Constraint."""

    def __call__(self, value: Any, *, field: str = None) -> _T_co:
        ...


class ConstraintsProtocolT(Protocol[_T]):
    """The guaranteed protocol for a Constraints instance."""

    type: Type
    nullable: bool
    coerce: bool
    name: Optional[str]
    validator: ValidatorT[_T]
    validate: ValidateT[_T]

    def for_schema(self, *, with_type: bool = False) -> Dict[str, Any]:
        ...


class _AbstractConstraints(abc.ABC):
    type: ClassVar[Type[Any]]
    VALUE = "value"
    VALTNAME = "valtname"
    FIELD = "field"
    FNAME = "fieldname"
    NULLABLES = (None, Ellipsis)

    __slots__ = ("__dict__",)
    __ignore_repr__ = frozenset(("type",))

    def __init_subclass__(cls, **kwargs):
        cls.__ignore_repr__ = _AbstractConstraints.__ignore_repr__ | cls.__ignore_repr__

    @util.cached_property
    @reprlib.recursive_repr()
    def __str(self) -> str:
        fields = [f"type={self.type_qualname}"]
        for f in dataclasses.fields(self):
            if f.name in self.__ignore_repr__:
                continue

            val = getattr(self, f.name)
            if (val or val in {False, 0}) and f.repr:
                fields.append(f"{f.name}={val!r}")
        return f"({', '.join(fields)})"

    def __str__(self) -> str:
        return self.__str

    def __repr__(self):
        return self.__str

    def define(self, block: gen.Block, name: str) -> gen.Function:
        f: gen.Function = block.f(
            name,
            block.param(self.VALUE, annotation="VT"),
            block.param(
                "field",
                annotation=str,
                kind=gen.ParameterKind.KEYWORD_ONLY,  # type: ignore
                default=None,
            ),
        )
        return f

    @util.cached_property
    def type_name(self) -> str:
        return util.get_name(self.type)

    @util.cached_property
    def type_qualname(self) -> str:
        return util.get_qualname(self.type)

    def _get_validator_name(self) -> str:
        return util.get_defname("validator", self)

    @util.cached_property
    @abc.abstractmethod
    def validator(self) -> ValidatorT:  # pragma: nocover
        ...

    def validate(self, value: VT, *, field: str = None) -> VT:
        """Validate that an incoming value meets the given constraints.

        Notes
        -----
        Some constraints may mutate the incoming value to conform, so the value is always
        returned.

        Raises
        ------
        :py:class:`ConstraintValueError`
            An error inheriting from :py:class:`ValueError` indicating the input is not
            valid.
        :py:class:`ConstraintSyntaxError`
            An error inheriting from :py:class:`SyntaxError` indicating the constraint
            configuration is invalid.
        """
        try:
            valid, value = self.validator(value, field=field)
        except AttributeError:
            valid, value = False, value

        if not valid:
            field = f"{field}:" if field is not None else "Given"
            raise ConstraintValueError(
                f"{field} value <{value!r}> fails constraints: {self}"
            ) from None
        return value

    @abc.abstractmethod
    def for_schema(
        self, *, with_type: bool = False
    ) -> Dict[str, Any]:  # pragma: nocover
        ...


class InstanceCheck(enum.IntEnum):
    """Flags for instance check methods.

    See Also
    --------
    :py:class:`~typic.constraints.mapping.MappingConstraints`
    """

    IS = 0
    """Allows for short-circuiting validation if `isinstance(value, <type>) is True`.

    Otherwise, perform additional checks to see if we can treat this as valid.
    """
    NOT = 1
    """Allows for short-circuiting validation if `isinstance(value, <type>) is False`.

    Otherwise, we must perform additional checks.
    """


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)  # type: ignore
class BaseConstraints(_AbstractConstraints):
    """A base constraints object. Shouldn't be used directly.

    Notes
    -----
    Inheritors of :py:class:`Constraints` should conform to JSON Schema type-constraints.

    See Also
    --------
    :py:class:`~typic.types.constraints.TextConstraints`
    :py:class:`~typic.types.constraints.NumberConstraints`
    :py:class:`~typic.types.constraints.ArrayConstraints`
    :py:class:`~typic.types.constraints.MappingConstraints`
    """

    type: ClassVar[Type[Any]]
    """The target type for this constraint."""
    instancecheck: ClassVar[InstanceCheck] = InstanceCheck.NOT
    """The method to use when short-circuting with instance checks."""
    nullable: bool = False
    """Whether to allow null values."""
    coerce: bool = False
    """Whether additional coercion should be done after validation.

    Even in `strict` mode, we may still want to coerce after validation.
    """
    name: Optional[str] = None

    __ignore_repr__ = frozenset(("coerce", "name", "instancecheck"))

    def __post_init__(self):
        self.validator

    def _build_validator(
        self, func: gen.Block, context: ContextT, assertions: AssertionsT
    ) -> ContextT:
        if assertions:
            self._build_assertions(func=func, assertions=assertions)
        return context

    def _build_assertions(self, func: gen.Block, assertions: AssertionsT):
        check = " and ".join(assertions)
        with func.b(f"if not ({check}):") as b:
            b.l(f"return False, {self.VALUE}")

    def _check_syntax(self):
        return

    def _get_assertions(self) -> AssertionsT:
        raise NotImplementedError

    def _compile_validator(self) -> ValidatorT:
        func_name = self._get_validator_name()
        origin = util.origin(self.type)
        type_name = self.type_name
        self._check_syntax()
        assertions = self._get_assertions()
        context: ContextT = {type_name: self.type}
        with gen.Block() as main:
            with self.define(main, func_name) as f:
                # This is a signal that -*-anything can happen...-*-
                if origin in {Any, Signature.empty}:
                    f.l(f"return True, {self.VALUE}")
                    return main.compile(name=func_name)
                f.l(f"{self.VALTNAME} = {type_name!r}")
                f.l(f"{self.FNAME} = {self.VALTNAME} if field is None else field")
                # Short-circuit validation if the value isn't the correct type.
                if self.instancecheck == InstanceCheck.IS:
                    line = f"if isinstance({self.VALUE}, {type_name}):"
                    if self.nullable:
                        line = (
                            f"if {self.VALUE} in {self.NULLABLES} "
                            f"or isinstance({self.VALUE}, {type_name}):"
                        )
                    with f.b(line, **context) as b:  # type: ignore
                        b.l(f"return True, {self.VALUE}")
                else:
                    if self.nullable:
                        with f.b(f"if {self.VALUE} in {self.NULLABLES}:") as b:
                            b.l(f"return True, {self.VALUE}")
                    line = f"if not isinstance({self.VALUE}, {type_name}):"
                    with f.b(line, **context) as b:  # type: ignore
                        b.l(f"return False, {self.VALUE}")
                context = self._build_validator(
                    f, context=context, assertions=assertions
                )
                f.namespace.update(context)
                f.localize_context(*context)
                f.l(f"return True, {self.VALUE}")
        return main.compile(name=func_name)

    @util.cached_property
    def validator(self) -> ValidatorT:
        """Accessor for the generated validator.

        Validators are generated code based upon the constraint syntax provided.
        The resulting code is about as optimized as you can get in Python, since
        the constraint values are localized to the validator and only the checks
        that the validator performs are the checks that were set. There is no
        computation time wasted on deciding whether or not to perform a validation.
        """
        validator = self._compile_validator()
        return validator


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class MultiConstraints(_AbstractConstraints):
    """A container for multiple constraints for a single field."""

    constraints: Tuple[ConstraintsProtocolT, ...]
    coerce: bool = False
    name: Optional[str] = None
    tag: Optional[util.TaggedUnion] = None

    @util.cached_property
    def nullable(self) -> bool:
        return any(x.nullable for x in self.constraints)

    @util.cached_property
    def __str(self) -> str:  # type: ignore
        constraints = f"({', '.join((str(c) for c in self.constraints))})"
        return f"(constraints={constraints}, nullable={self.nullable})"

    def __str__(self) -> str:
        return self.__str

    def __repr__(self):
        return self.__str

    def __type(self) -> Iterator[Type]:
        to_flatten: Set[Union[Type, Iterable[Type]]]
        to_flatten = {x.type for x in self.constraints}
        while to_flatten:
            t: Union[Type, Iterable[Type]] = to_flatten.pop()
            if isinstance(t, Iterable):
                to_flatten.update(t)
                continue
            yield t

    @util.cached_property
    def type(self) -> Tuple[Type, ...]:  # type: ignore
        return (*self.__type(),)

    @util.cached_property
    def type_name(self) -> str:
        return f"({', '.join(util.get_name(t) for t in self.type)})"

    @util.cached_property
    def type_qualname(self) -> str:
        return f"({', '.join(util.get_qualname(t) for t in self.type)})"

    @util.cached_property
    def validator(self) -> ValidatorT:
        """Accessor for the generated multi-validator.

        Validators are keyed by the origin-type of :py:class:`BaseConstraints` inheritors.

        If a value does not match any origin-type, as reported by :py:func:`typic.origin`,
        then we will report the value as invalid.
        """
        func_name = self._get_validator_name()
        vmap = util.TypeMap({c.type: c for c in self.constraints})
        ns = {"tag": self.tag and self.tag.tag, "empty": util.empty}
        with gen.Block(ns) as main:
            with self.define(main, func_name) as f:
                if not vmap:
                    f.l(f"return True, {self.VALUE}")
                else:
                    f.l(f"{self.VALTNAME} = {self.VALUE}.__class__")
                    if self.nullable:
                        with f.b(f"if {self.VALUE} is None:") as b:
                            b.l(f"return True, {self.VALUE}")
                    if self.tag:
                        validators = {
                            value: vmap[t] for value, t in self.tag.types_by_values
                        }
                        f.namespace.update(vmap=validators)
                        with f.b(
                            f"if issubclass({self.VALTNAME}, Mapping):",
                            Mapping=collections.abc.Mapping,
                        ) as b:
                            b.l(f"tag_value = {self.VALUE}.get(tag, empty)")
                        with f.b("else:") as b:
                            b.l(f"tag_value = getattr({self.VALUE}, tag, empty)")
                        f.l(
                            f"valid, {self.VALUE} = "
                            f"(True, vmap[tag_value].validate({self.VALUE}, field=field)) "
                            f"if tag_value in vmap else (False, {self.VALUE})"
                        )
                    else:
                        vmap = util.TypeMap(
                            {util.origin(t): v for t, v in vmap.items()}
                        )
                        f.namespace.update(vmap=vmap)
                        f.l(f"v = vmap.get_by_parent({self.VALTNAME}, None)")
                        f.l(
                            f"valid, {self.VALUE} = (True, v.validate(value, field=field)) "
                            f"if v else (False, value)"
                        )
                    f.l(f"return valid, {self.VALUE}")
        validator = main.compile(name=func_name)
        return validator  # type: ignore

    def for_schema(self, *, with_type: bool = False) -> dict:
        scheme: dict = {
            "anyOf": [x.for_schema(with_type=True) for x in self.constraints],
        }
        if self.name:
            scheme["name"] = self.name
        return scheme


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class TypeConstraints(_AbstractConstraints):
    """A container for simple types. Validation is limited to instance checks.

    Examples
    --------
    >>> import typic
    >>> tc = typic.get_constraints(typic.AbsoluteURL)
    >>> tc.validate("http://foo.bar")
    Traceback (most recent call last):
        ...
    typic.constraints.error.ConstraintValueError: Given value <'http://foo.bar'> fails constraints: (type=AbsoluteURL, nullable=False)
    >>> tc = typic.get_constraints(typic.AbsoluteURL, nullable=True)
    >>> tc.validate(None)

    >>>
    """

    type: Type[Any]  # type: ignore
    """The type to check for."""
    nullable: bool = False
    """Whether this constraint can allow null values."""
    name: Optional[str] = None

    def __post_init__(self):
        self.validator

    @util.cached_property
    def validator(self) -> ValidatorT:
        ns = dict(__t=self.type, VT=VT)
        func_name = self._get_validator_name()
        with gen.Block(ns) as main:
            with self.define(main, func_name) as f:
                # Standard instancecheck is default.
                check = "isinstance(value, __t)"
                retval = "value"
                # Have to allow nulls if its nullable.
                if self.nullable:
                    check = "(value is None or isinstance(value, __t))"
                elif self.type is Any:
                    check = "True"
                f.l(f"{gen.Keyword.RET} {check}, {retval}")

        validator: ValidatorT = main.compile(name=func_name, ns=ns)
        return validator

    def for_schema(self, *, with_type: bool = False) -> Dict[str, Any]:
        if self.name:
            return {"title": self.name}
        return {}


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class EnumConstraints(_AbstractConstraints):
    type: Type[enum.Enum]  # type: ignore
    """The enum to check for."""
    nullable: bool = False
    """Whether this constraint can allow null values."""
    coerce: bool = True
    name: Optional[str] = None

    def __post_init__(self):
        self.validator

    @util.cached_property
    def __str(self) -> str:
        values = (*(x.value for x in self.type),)
        return (
            f"(type={self.name or self.type.__name__}, "
            f"values={values}, "
            f"nullable={self.nullable})"
        )

    def __str__(self) -> str:
        return self.__str

    def __repr__(self):
        return self.__str

    @util.cached_property
    def validator(self) -> ValidatorT:
        ns = dict(__t=self.type, VT=VT, __values=(*self.type,))
        func_name = self._get_validator_name()
        with gen.Block(ns) as main:
            with self.define(main, func_name) as f:
                if self.nullable:
                    with f.b(f"if value in {self.NULLABLES}:") as b:
                        b.l(f"{gen.Keyword.RET} True, value")
                # This is O(N), but so is casting to the enum
                # And handling a ValueError is an order of magnitude heavier
                f.l(f"{gen.Keyword.RET} value in __values, value")

        validator: ValidatorT = main.compile(name=func_name, ns=ns)
        return validator

    def for_schema(self, *, with_type: bool = False) -> Dict[str, Any]:
        if self.name:
            return {"title": self.name}
        return {}


@util.slotted
@dataclasses.dataclass(frozen=True, repr=False)
class LiteralConstraints(_AbstractConstraints):
    type: _GenericAlias  # type: ignore  # real-type: Literal
    nullable: bool = False
    coerce: bool = False
    name: Optional[str] = None

    def __post_init__(self):
        self.validator

    @property
    def values(self):
        return util.get_args(self.type)

    @util.cached_property
    def __str(self) -> str:
        return f"(type=Literal, " f"values={self.values}, " f"nullable={self.nullable})"

    def __str__(self) -> str:
        return self.__str

    def __repr__(self):
        return self.__str

    @util.cached_property
    def validator(self) -> ValidatorT:
        ns = dict(__t=self.type, VT=VT, __values=frozenset(self.values))
        func_name = self._get_validator_name()
        with gen.Block(ns) as main:
            with self.define(main, func_name) as f:
                if self.nullable:
                    with f.b(f"if value in {self.NULLABLES}:") as b:
                        b.l(f"{gen.Keyword.RET} True, value")
                with f.b("try:") as b:
                    b.l(f"{gen.Keyword.RET} value in __values, value")
                with f.b("except TypeError:") as b:
                    b.l(f"{gen.Keyword.RET} False, value")

        validator: ValidatorT = main.compile(name=func_name, ns=ns)
        return validator

    def for_schema(self, *, with_type: bool = False) -> Dict[str, Any]:
        if self.name:
            return {"title": self.name}
        return {}


class DelayedConstraints:
    __slots__ = "t", "nullable", "name", "factory", "_constraints"

    def __init__(self, t: Type, nullable: bool, name: Optional[str], factory: Callable):
        self.t = t
        self.nullable = nullable
        self.name = name
        self.factory = factory
        self._constraints: Optional["_AbstractConstraints"] = None

    def _evaluate_contraints(self):
        type = self.t
        if checks.isoptionaltype(type):
            args = util.get_args(type)[:-1]
            type = args[0] if len(args) == 1 else Union[args]
            self.nullable = True
            self.t = type
        c = self.factory(type, nullable=self.nullable, name=self.name)
        return c

    @property
    def constraints(self) -> "_AbstractConstraints":
        if self._constraints is None:
            self._constraints = self._evaluate_contraints()
        return self._constraints

    def validate(self, value: VT, *, field: str = None):
        return self.constraints.validate(value, field=field)

    def __getattr__(self, item):
        return self.constraints.__getattribute__(item)


class ForwardDelayedConstraints:
    __slots__ = (
        "ref",
        "module",
        "localns",
        "nullable",
        "name",
        "factory",
        "_constraints",
    )

    def __init__(
        self,
        ref: ForwardRef,
        module: str,
        localns: Mapping,
        nullable: bool,
        name: Optional[str],
        factory: Callable,
    ):
        self.ref = ref
        self.module = module
        self.localns = localns
        self.nullable = nullable
        self.name = name
        self.factory = factory
        self._constraints: Optional["_AbstractConstraints"] = None

    def _evaluate_contraints(self):
        globalns = sys.modules[self.module].__dict__.copy()
        try:
            type = evaluate_forwardref(self.ref, globalns or {}, self.localns or {})
        except NameError as e:  # pragma: nocover
            warnings.warn(
                f"Counldn't resolve forward reference: {e}. "
                f"Make sure this type is available in {self.module}."
            )
            type = object  # make it a no-op
        if checks.isoptionaltype(type):
            args = util.get_args(type)[:-1]
            type = args[0] if len(args) == 1 else Union[args]
            self.nullable = True
        c = self.factory(type, nullable=self.nullable, name=self.name)
        return c

    @property
    def constraints(self) -> "_AbstractConstraints":
        if self._constraints is None:
            self._constraints = self._evaluate_contraints()
        return self._constraints

    def validate(self, value: VT, *, field: str = None):
        return self.constraints.validate(value, field=field)

    def __getattr__(self, item):
        return self.constraints.__getattribute__(item)
