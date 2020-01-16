# typical Strict Mode

## Strict Mode

`strict` mode turns `typical` into a run-time *enforcer*, not just coercer. What
does this mean? Simply put, if the input does not meet the constraints of the provided
type, an error will be raised. There are three different levels of `strict` mode
enforcement:

1. *Global* 
2. *Namespaced* 
3. *Annotation*

`Global` is the easiest to turn on, but has its drawbacks:

::: typic.api.strict_mode

`Namespaced` enforces on a per-class/per-callable basis:


    >>> import typic
    >>>
    >>> @typic.al(strict=True)
    ... def add(*num: int) -> int:
    ...     return sum(num)
    ...
    >>> add(1, "2")
    Traceback (most recent call last):
        ...
    typic.constraints.error.ConstraintValueError: Given value <'2'> fails constraints: (type=int, nullable=False, coerce=False)



`Annotation` is enforced at the type-hint level. This is the 
recommended method for strict-mode enforcement:

    >>> import typic
    >>>
    >>> @typic.klass
    ... class Foo:
    ...     bar: typic.StrictStrT  # convenience alias for most common need.
    ...     blah: int  # will be coerced if possible.
    ...
    >>> Foo("bar", "2")
    Foo(bar='bar', blah=2)
    >>> Foo(None, 2)
    Traceback (most recent call last):
        ...
    typic.constraints.error.ConstraintValueError: Given value <None> fails constraints: (type=str, nullable=False, coerce=False)


There are cases where the returned value is still coerced, so if you
are listening for the result of a call to `typic.coerce` while
enforcing strict-mode, you should be sure to track the updated value.

## On Validation & Coercion

**Validation** is a bloated term in Python typing. There are many
camps which define validation as different things - static type
checking, runtime type checking, runtime type coercion...

Unlike other popular libraries, `typical` makes an extremely clear
delineation between type *coercion* and type *validation*.

We approach type-enforcement via *coercion-first*. While you may get
validation as a side-effect of coercion, the line between the two
operations is not blurred. In order to operate with
*validation-first*, you must change the mode of operation. This is not
the case in other popular libraries.

These are the paths to "validation" which `typical` will follow:

### Validate-by-Coerce

The given value is inherently validated by the action of coercion.
This is `typical`'s default mode and for many built-in higher-level
types this behavior does not change in strict-mode:

    >>> import ipaddress
    >>> import typic
    >>>
    >>> typic.coerce("", ipaddress.IPv4Address)
    Traceback (most recent call last):
        ...
    ipaddress.AddressValueError: Address cannot be empty
    >>> typic.coerce("", typic.Strict[ipaddress.IPv4Address])
    Traceback (most recent call last):
        ...
    ipaddress.AddressValueError: Address cannot be empty
    >>> typic.coerce("", typic.URL)
    Traceback (most recent call last):
        ...
    typic.types.url.NetworkAddressValueError: '' is not a valid network address.

    >>> typic.coerce("", typic.Strict[typic.URL])
    Traceback (most recent call last):
        ...
    typic.types.url.NetworkAddressValueError: '' is not a valid network address.


### Coerce-then-Validate 

The given value will be coerced and then validated against any
additional constraints. This can be activated for primitive types by
defining constrained subclasses:



    >>> import typic
    >>> @typic.constrained(gt=0)
    ... class PositiveInt(int): ...
    ...
    >>> typic.coerce("1", PositiveInt)
    1
    >>> typic.coerce("-1", PositiveInt)
    Traceback (most recent call last):
        ...
    typic.constraints.error.ConstraintValueError: Given value <-1> fails constraints: (type=int, nullable=False, coerce=False, gt=0)


### Validate-Only

The given value *must* meet the type-constraints provided. This can be
done by signaling to `typical` to use "strict-mode" when resolving an
annotation for coercion.

In strict-mode, `validation-only` is used for primitive types.



    >>> import typic
    >>> typic.coerce("1", typic.Strict[int])
    Traceback (most recent call last):
        ...
    typic.constraints.error.ConstraintValueError: Given value <'1'> fails constraints: (type=int, nullable=False, coerce=False)



### Validate-then-Coerce

The given value *must* meet the type-constraints provided - after
which we coerce the value. This can be done by signaling to `typical`
to use "strict-mode" when resolving an annotation for coercion.

In strict-mode, `validate-then-coerce` is used for user-defined types.



    >>> import dataclasses
    >>> import typic
    >>>
    >>> @dataclasses.dataclass
    ... class Foo:
    ...     bar: str
    ...
    >>> typic.coerce({"bar": "bar"}, typic.Strict[Foo])
    Foo(bar='bar')
    >>> typic.coerce({"bar": 1}, typic.Strict[Foo])
    Traceback (most recent call last):
        ...
    typic.constraints.error.ConstraintValueError: Given value <1> fails constraints: (type=str, nullable=False, coerce=False)


## What "Mode" Should I Use?

`typical` provides users with a path for easy, safe coercion of types
at runtime.

The best use-case for "strict-mode" is when you find yourself using
`str` as your annotation. This is because any object in Python can be
a string, so you could end up in a weird place if you're blindly
casting all of your inputs to `str`.

To this, `typical` provides a `StrictStrT` annotation for public
consumption that will enforce strict type-checking for string fields.


