# Validation, Parsing, and Deserialization
Typical's default mode is that of a *deserializer & serializer*. The
API also provides a means to manually validate inputs against your
defined type, but it should be noted that Typical approaches
validation as a means or side-effect of deserialization.

You can, however, change the default mode.

## Strict Mode

`strict` mode turns Typical into a run-time *enforcer*, not just
coercer. What does this mean? Simply put, if the input does not meet
the constraints of the provided type, an error will be raised. There
are three different levels of `strict` mode enforcement:

1. *Global*
2. *Namespaced*
3. *Annotated*

### Global Strict Mode
Global strict mode is the easiest to just turn on, but has its
drawbacks.

#### `typic.strict_mode()`
> Turn on global ``strict`` mode.
>
> All resolved annotations will validate their inputs against the generated
> constraints. In some cases, coercion may still be used as the method for
> validation. Additionally, post-validation coercion will occur for
> user-defined classes if needed.
>
> !!! warning
>
>     Global state is messy, but this is provided for convenience. Care must
>     be taken when manipulating global state in this way. If you intend to
>     turn on global ``strict`` mode, it should be done once, at the start
>     of the application runtime, before all annotations have been resolved.
>     
>     You cannot toggle ``strict`` mode off once it is enabled during the runtime
>     of an application. This is intentional, to limit the potential for hazy or
>     unclear state.
>     
>     If you find yourself in a situation where you need `strict` mode for some
>     cases, but not others, you're encouraged to flag `strict=True` on the
>     decorated class/callable, or even make use of the `typic.Strict` 
>     annotation to flag `strict` mode on individual fields.


### Namespaced Strict Mode

Namespaced enforces on a per-class/per-callable basis:


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

### Annotated Strict Mode

Annotated Strict Mode is enforced at the type-hint level.

??? example "Annotated Strict Mode"

    ```python
    import typic
    
    
    @typic.klass
    class Foo:
        bar: typic.StrictStrT  # convenience alias for most common need.
        blah: int  # will be coerced if possible.
    
    
    Foo(None, 2)
    #> Traceback (most recent call last):
    #>     ...
    #> typic.constraints.error.ConstraintValueError: Given value <None> fails constraints: (type=str, nullable=False, coerce=False)
    ```

!!! warning ""

    There are cases where the returned value is still coerced, so if you
    are listening for the result of a call to `typic.transmute` while
    enforcing strict-mode, you should be sure to track the updated value.

## On Validation & Deserialization

**Validation** is a bloated term in Python typing. There are many
camps which define validation as different things - static type
checking, runtime type checking, runtime type coercion...

Unlike other popular libraries, Typical makes an extremely clear
delineation between type *deserialization* and type *validation*.

We approach type-enforcement via *deserialization-first*. While you
may get validation as a side-effect of coercion, the line between the
two operations is not blurred. In order to operate with
*validation-first*, you must change the mode of operation. This is not
the case in other popular libraries.

These are the paths to "validation" which Typical will follow:

### Validate-by-Parse

The given value is inherently validated by the action of
conversion. This is Typical's default mode of operation:

```
>>> import ipaddress
>>> import typic
>>>
>>> typic.transmute(ipaddress.IPv4Address, "")
Traceback (most recent call last):
    ...
ipaddress.AddressValueError: Address cannot be empty
>>> typic.transmute(typic.URL, "")
Traceback (most recent call last):
    ...
typic.types.url.NetworkAddressValueError: '' is not a valid network address.
```


### Parse-then-Validate

The given value will be transmuted and then validated against any
additional constraints. This can be activated for primitive types by
defining constrained subclasses:



```python
>>> import typic
>>> @typic.constrained(gt=0)
... class PositiveInt(int): ...
...
>>> typic.transmute(PositiveInt, "1")
1
>>> typic.transmute(PositiveInt, "-1")
Traceback (most recent call last):
    ...
typic.constraints.error.ConstraintValueError: Given value <-1> fails constraints: (type=int, nullable=False, coerce=False, gt=0)
```


### Validate-Only

The given value *must* meet the type-constraints provided. This can be
done by signaling to Typical to use "strict-mode" when resolving an
annotation for coercion.

In strict-mode, `validation-only` is used for primitive
types and builtin higher-level types:



```python
>>> import datetime
>>> import ipaddress
>>> import typic
>>> typic.transmute(typic.Strict[int], "1")
Traceback (most recent call last):
    ...
typic.constraints.error.ConstraintValueError: Given value <'1'> fails constraints: (type=int, nullable=False, coerce=False)
>>> typic.transmute(typic.Strict[ipaddress.IPv4Address], "")
Traceback (most recent call last):
    ...
typic.constraints.error.ConstraintValueError: Given value <''> fails constraints: (type=IPv4Address, nullable=False)
>>> typic.transmute(typic.Strict[typic.URL], "")
Traceback (most recent call last):
    ...
typic.constraints.error.ConstraintValueError: Given value <''> fails constraints: (type=URL, nullable=False)
>>> typic.transmute(typic.Strict[datetime.date], "")
Traceback (most recent call last):
    ...
typic.constraints.error.ConstraintValueError: Given value <''> fails constraints: (type=date, nullable=False)
```




### Validate-then-Parse

The given value *must* meet the type-constraints provided - after
which we transmute the value. This can be done by signaling to
Typical to use "strict-mode" when resolving an annotation for
coercion.

In strict-mode, `validate-then-parse` is used for user-defined types.



```python
>>> import dataclasses
>>> import typic
>>>
>>> @dataclasses.dataclass
... class Foo:
...     bar: str
...
>>> typic.transmute(typic.Strict[Foo], {"bar": "bar"})
Foo(bar='bar')
>>> typic.transmute(typic.Strict[Foo], {"bar": 1})
Traceback (most recent call last):
    ...
typic.constraints.error.ConstraintValueError: Foo.bar: value <1> fails constraints: (type=str, nullable=False, coerce=False)
```


!!! tip ""

    All of the above examples use `typic.transmute(...)` and wrap the annotation in
    `typic.Strict[...]`, however, users may call `typic.validate(...)` directly to
    access Typical's runtime validation engine.


## What "Mode" Should I Use?

Typical provides users with a path for easy, safe conversion of
types at runtime.

The best use-case for "strict-mode" is when you find yourself using
`str` as your annotation. This is because any object in Python can be
a string, so you could end up in a weird place if you're blindly
casting all of your inputs to `str`.

To this, Typical provides a `StrictStrT` annotation for public
consumption that will enforce strict type-checking for string fields.


