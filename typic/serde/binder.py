import dataclasses
import inspect
from collections import deque
from typing import (
    Dict,
    Deque,
    Any,
    Tuple,
    TYPE_CHECKING,
    List,
    Optional,
    Union,
    Type,
    Callable,
    Mapping,
    Iterable,
)

from typic import util
from ..common import (
    EMPTY,
    POSITIONAL_ONLY,
    RETURN_KEY,
    TOO_MANY_POS,
    VAR_POSITIONAL,
    VAR_KEYWORD,
    KWD_KINDS,
)

if TYPE_CHECKING:  # pragma: nocover
    from .resolver import Resolver  # noqa: F401
    from .common import SerdeProtocol, SerdeProtocolsT  # noqa: F401


@dataclasses.dataclass(frozen=True)
class BoundArguments:
    obj: Union[Type, Callable]
    """The object we "bound" the input to."""
    annotations: "SerdeProtocolsT"
    """A mapping of the resolved annotations."""
    parameters: Mapping[str, inspect.Parameter]
    """A mapping of the parameters."""
    arguments: Dict[str, Any]
    """A mapping of the input to parameter name."""
    returns: Optional["SerdeProtocol"]
    """The resolved return type, if any."""
    _argnames: Tuple[str, ...]
    _kwdargnames: Tuple[str, ...]

    @util.cached_property
    def args(self) -> Tuple[Any, ...]:
        """A tuple of the args passed to the callable."""
        args: List = list()
        argsappend = args.append
        argsextend = args.extend
        paramsget = self.parameters.__getitem__
        argumentsget = self.arguments.__getitem__
        for name in self._argnames:
            kind = paramsget(name).kind
            arg = argumentsget(name)
            if kind == VAR_POSITIONAL:
                argsextend(arg)
            else:
                argsappend(arg)
        return tuple(args)

    @util.cached_property
    def kwargs(self) -> Dict[str, Any]:
        """A mapping of the key-word arguments passed to the callable."""
        kwargs: Dict = {}
        kwargsupdate = kwargs.update
        kwargsset = kwargs.__setitem__
        paramsget = self.parameters.__getitem__
        argumentsget = self.arguments.__getitem__
        for name in self._kwdargnames:
            kind = paramsget(name).kind
            arg = argumentsget(name)
            if kind == VAR_KEYWORD:
                kwargsupdate(arg)
            else:
                kwargsset(name, arg)
        return kwargs

    def eval(self) -> Any:
        """Evaluate the callable against the input provided.

        Examples
        --------
        >>> import typic
        >>>
        >>> def foo(bar: int) -> int:
        ...     return bar ** bar
        ...
        >>> bound = typic.bind(foo, "2")
        >>> bound.eval()
        4
        """
        return self.obj(*self.args, **self.kwargs)


class Binder:
    def __init__(self, resolver: "Resolver"):
        self.resolver = resolver

    def _bind_posargs(
        self,
        arguments: Dict[str, Any],
        params: Deque[inspect.Parameter],
        annos: "SerdeProtocolsT",
        args: Deque[Any],
        kwargs: Dict[str, Any],
    ) -> Tuple[str, ...]:
        # Bind any positional arguments

        # bytecode hack to localize access
        # only noticeable with really large datasets
        # but it's best to be prepared.
        posargs: List[str] = []
        posargsadd = posargs.append
        argspop = args.popleft
        paramspop = params.popleft
        annosget = annos.get
        argumentsset = arguments.__setitem__
        while args and params:
            val = argspop()
            param: inspect.Parameter = paramspop()
            name = param.name
            anno: Optional["SerdeProtocol"] = annosget(name)
            kind = param.kind
            # We've got varargs, so push all supplied args to that param.
            if kind == VAR_POSITIONAL:
                value = (val, *args)
                args = deque()
                if anno:
                    value = anno(value)
                argumentsset(name, value)
                posargsadd(name)
                break

            # We're not supposed to have kwdargs....
            if kind in KWD_KINDS:
                raise TypeError(TOO_MANY_POS) from None

            # Passed in by ref and assignment... no good.
            if name in kwargs:
                raise TypeError(f"multiple values for argument '{name}'") from None

            # We're g2g
            value = anno(val) if anno else val
            argumentsset(name, value)
            posargsadd(name)

        if args:
            raise TypeError(TOO_MANY_POS) from None

        return tuple(posargs)

    def _bind_kwdargs(
        self,
        arguments: Dict[str, Any],
        params: Deque[inspect.Parameter],
        annos: Dict[str, "SerdeProtocol"],
        kwargs: Dict[str, Any],
        partial: bool = False,
    ) -> Tuple[str, ...]:
        # Bind any key-word arguments
        kwdargs: List[str] = list()
        kwdargsadd = kwdargs.append
        kwargs_anno = None
        kwdargs_param = None
        kwargspop = kwargs.pop
        annosget = annos.get
        argumentsset = arguments.__setitem__
        for param in params:
            kind = param.kind
            name = param.name
            anno = annosget(name)
            # Move on, but don't forget
            if kind == VAR_KEYWORD:
                kwargs_anno = anno
                kwdargs_param = param
                continue
            # We don't care about these
            if kind == VAR_POSITIONAL:
                continue
            # try to bind the parameter
            if name in kwargs:
                val = kwargspop(name)
                if kind == POSITIONAL_ONLY:
                    raise TypeError(
                        f"{name!r} parameter is positional only,"
                        "but was passed as a keyword."
                    )
                value = anno(val) if anno else val
                argumentsset(name, value)
                kwdargsadd(name)
            elif not partial and param.default is EMPTY:
                raise TypeError(f"missing required argument: {name!r}")

        # We didn't clear out all the kwdargs. Check to see if we came across a **kwargs
        if kwargs:
            if kwdargs_param is not None:
                # Process our '**kwargs'-like parameter
                name = kwdargs_param.name
                value = kwargs_anno.transmute(kwargs) if kwargs_anno else kwargs  # type: ignore
                argumentsset(name, value)
                kwdargsadd(name)
            else:
                raise TypeError(
                    f"'got an unexpected keyword argument {next(iter(kwargs))!r}'"
                )

        return tuple(kwdargs)

    def _bind_input(
        self,
        obj: Union[Type, Callable],
        annos: "SerdeProtocolsT",
        params: Mapping[str, inspect.Parameter],
        args: Iterable[Any],
        kwargs: Dict[str, Any],
        *,
        partial: bool = False,
    ) -> BoundArguments:
        """Bind annotations and parameters to received input.

        Taken approximately from :py:meth:`inspect.Signature.bind`, with a few changes.

        About 10% faster, on average, and coerces values with their annotation if possible.

        Parameters
        ----------
        annos
            A mapping of :py:class:`ResolvedAnnotation` to param name.
        params
            A mapping of :py:class:`inspect.Parameter` to param name.
        args
            The positional args to bind to their param and annotation, if possible.
        kwargs
            The keyword args to bind to their param and annotation, if possible.

        Other Parameters
        ----------------
        partial
            Bind a partial input.

        Raises
        ------
        TypeError
            If we can't match up the received input to the signature
        """
        arguments: Dict[str, Any] = dict()
        returns = annos.pop(RETURN_KEY, None)
        args = deque(args)
        parameters = deque(params.values())
        # Bind any positional arguments.
        posargs = self._bind_posargs(arguments, parameters, annos, args, kwargs)
        # Bind any keyword arguments.
        kwdargs = self._bind_kwdargs(arguments, parameters, annos, kwargs, partial)
        return BoundArguments(obj, annos, params, arguments, returns, posargs, kwdargs)

    def bind(
        self,
        obj: Union[Type, Callable],
        *args: Any,
        partial: bool = False,
        coerce: bool = True,
        strict: bool = False,
        **kwargs: Mapping[str, Any],
    ) -> BoundArguments:
        """Bind a received input to a callable or object's signature.

        If we can locate an annotation for any args or kwargs, we'll automatically
        coerce as well.

        This implementation is similar to :py:meth:`inspect.Signature.bind`,
        but is ~10-20% faster.
        We also use a cached the signature to avoid the expense of that call if possible.

        Parameters
        ----------
        obj
            The object you wish to bind your input to.
        *args
            The given positional args.
        partial
            Whether to bind a partial input.
        coerce
            Whether to coerce the input to the annotation provided.
        strict
            Whether to validate the input against the annotation provided.
        **kwargs
            The given keyword args.

        Returns
        -------
        :py:class:`BoundArguments`
            The bound and coerced arguments.

        Raises
        ------
        TypeError
            If we can't match up the received input to the signature

        Examples
        --------
        >>> import typic
        >>>
        >>> def add(a: int, b: int, *, c: int = None) -> int:
        ...     return a + b + (c or 0)
        ...
        >>> bound = typic.bind(add, "1", "2", c=3.0)
        >>> bound.arguments
        {'a': 1, 'b': 2, 'c': 3}
        >>> bound.args
        (1, 2)
        >>> bound.kwargs
        {'c': 3}
        >>> bound.eval()
        6
        >>> typic.bind(add, 1, 3.0, strict=True)
        Traceback (most recent call last):
            ...
        typic.constraints.error.ConstraintValueError: Given value <3.0> fails constraints: (type=int, nullable=False, coerce=False)
        """
        return self._bind_input(
            obj=obj,
            annos=self.resolver.protocols(obj, strict=strict)
            if (coerce or strict)
            else {},
            params=util.cached_signature(obj).parameters,
            args=args,
            kwargs=kwargs,
            partial=partial,
        )
