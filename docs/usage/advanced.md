# typical Advanced Usage

As you've seen, `typical` is a veritable Swiss Army knife for managing type
annotations at run-time. Below are some additional supported uses that you may find
yourself needing from time-to-time.

## Helpers

`typical` also provides a variety of high-level helpers that make interacting with
types a breeze:

::: typic.coerce

::: typic.primitive

::: typic.bind

::: typic.schema

::: typic.schemas

::: typic.annotations

## Classes

There are a few high-level classes that may be interacted with.

::: typic.ResolvedAnnotation

::: typic.BoundArguments

## Delayed Annotation Resolution

Sometimes you define a class that depends upon another class or type which isn't defined
quite yet. This can cause issues resolving your annotation for coercion. In those
cases, we provide a simple `delay` parameter and a `typic.resolve()` function.


::: typic.resolve


    import datetime
    
    import typic
    
    
    @typic.klass(delay=True)
    class Parent:
        id: int
        child: "Child"
        created_on: datetime.datetime
    
    
    @typic.klass
    class Child:
        id: int
        created_on: datetime.datetime
    
    
    ... # more code/definitions

    # at the BOTTOM of your module:
    typic.resolve()


!!! warning  
    If you don't manually call `typic.resolve`, your annotations
    for your delayed object will be resolved the first time your class or
    function is called. This is an expensive operation so you're encourage
    to call `typic.resolve` ahead of time.



## Custom Type Coercers

Typic does everything it can to figure out how to initialize your custom classes
without much input from you. If you feel the need to control the initialization of your
`typic.al` class, you can do so in one of two ways:

1. Define a `from_dict` factory method on your class:

```
import typic


@typic.klass
class Foo:
    bar: str

    @classmethod
    def from_dict(cls, data: dict) -> "Foo":
        ... # do stuff with the data
        return Foo(**data)

```


!!! note  
    `typical` assumes that if your incoming data is in the format of a
    JSON blob or a dict, it can map directly to your model's fields so the
    above example is functionally unnecessary unless you're mutating said
    data in some way.


2. Register a custom type coercer for your class:

```
import enum

import typic


class FooType(str, enum.Enum):
    BAR = "bar"
    BAZ = "baz"
    BUZ = "buz"

    @classmethod
    def select(cls, type: "FooType"):
        type = FooType(type)
        if type == cls.BAR:
            return Bar
        if type == cls.BAZ:
            return Baz
        if type == cls.BUZ:
            return Buz


# delay annotation resolution
@typic.klass(delay=True)
class Bar:
    val: str


@typic.klass(delay=True)
class Baz:
    val: str


@typic.klass(delay=True)
class Buz:
    val: str


def isfootype(annotation) -> bool:
    return annotation in {Bar, Baz, Buz}


@typic.al
def foo_coercer(val: dict):
    type = val.pop("type", None)
    if type:
        cls = FooType.select(type)
        return cls(**val)
    raise ValueError(f"Can't determine FooType from {val}")


# register your coercer with a function to detect if an annotation is valid
typic.register(foo_coercer, isfootype)
# resolve your annotations
typic.resolve()
```

!!! important  
    When registering a custom coercer, you *must* delay annotation
    resolution until all custom types are defined for which the coercer is
    responsible.


## Manual Coercion

If, for some reason, you don't like all the magic and you want to have
manual control over when and how you coerce your types, `typical`
still has your back with its high-level API. Instead of wrapping your
functions or classes, you can call `typic.coerce` when and where you
want.

```
# foo.py
import dataclasses

import typic


@dataclasses.dataclass
class Foo:
    bar: str


def some_function_which_expects_foo(data: Foo) -> Foo:
    ... # do stuff with foo
    return foo
```


Voila! Let's pop into an interpreter to see this in action:

```
>>> import typic
>>>
>>> from .foo import some_function_without_magic, Foo
>>>
>>> data = "bar"
>>> some_function_without_magic(typic.coerce(data, Foo))
Foo(bar='bar')
>>> some_function_without_magic(typic.coerce('{"bar": 1}', Foo))
Foo(bar='1')
```


!!! note  
    While this interaction is valid, it's encouraged to follow
    the decorator pattern where-ever possible. Otherwise, you will 
    warm-up hit in performance while `typical` works to figure
    this is called.
