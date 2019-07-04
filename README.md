Typical: Take Typing Further. :duck: 
=====================================
[![image](https://img.shields.io/pypi/v/typical.svg)](https://pypi.org/project/typical/)
[![image](https://img.shields.io/pypi/l/typical.svg)](https://pypi.org/project/typical/)
[![image](https://img.shields.io/pypi/pyversions/typical.svg)](https://pypi.org/project/typical/)
[![image](https://img.shields.io/github/languages/code-size/seandstewart/typical.svg?style=flat)](https://github.com/seandstewart/typical)
[![image](https://img.shields.io/travis/seandstewart/typical.svg)](https://travis-ci.org/seandstewart/typical)
[![codecov](https://codecov.io/gh/seandstewart/typical/branch/master/graph/badge.svg)](https://codecov.io/gh/seandstewart/typical)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

Take Typing Further with Typical. Make your annotations work for you.

## Quickstart

**Typical** is exceptionally light-weight (<50KB) and has only one
dependency -
[python-dateutil](https://dateutil.readthedocs.io/en/stable/), which
it uses to parse date-strings into datetime objects.

In order to install, simply `pip3 install typical` and annotate to your
heart's content! :duck: 


## Motivations

In the world of web-services development, type-safety becomes necessary
for the sanity of your code and your fellow developers. This is not to
say that static-typing is the solution - When it comes to the external
entrypoints to your code, not even a compiler is going to help you. 

With Python3, type annotations were introduced. With Python3.7, the
library was completely re-written for performance and ease-of-use. Type
annotations are here to stay and I couldn't be happier about it. 

However, there is one place where annotations fall down. There is no
provided path for ensuring the type-safety of your methods, functions,
and classes. This means if you're receiving data from an external
source, (such as with a web service) you still need to do this work
yourself.

Until now.


## Automatic, Guaranteed Duck-Typing

Behold, the power of *Typical*:

```python
>>> import typic
>>>
>>> @typic.al
>>> def multi(a: int, b: int):
...    return a * b
...
>>> multi('2', '3')
6
```

Take it further...

```python
>>> import dataclasses
>>> import enum
>>> import typic
>>>
>>> class DuckType(str, enum.Enum):
...     MAL = 'mallard'
...     BLK = 'black'
...     WHT = 'white'
... 
>>> @typic.al
... @dataclasses.dataclass
... class Duck:
...     type: DuckType
...     name: str
...
>>> donald = Duck('white', 'Donald')
>>> donald.type
<DuckType.WHT: 'white'>
```

This is all fine and dandy, but can we go... further? :thinking: 

```python
>>> class DuckRegistry:
...     """A Registry for all the ducks"""
...     
...     @typic.al
...     def __init__(self, *duck: Duck):
...         self._reg = {x.name: x for x in duck}
... 
...     @typic.al
...     def add(self, duck: Duck):
...         self._reg[duck.name] = duck
... 
...     @typic.al
...     def find(self, name: str):
...         """Try to find a duck by its name. Otherwise, try with type."""
...         if name not in self._reg:
...             matches = [x for x in self._reg.values() if x.type == name]
...             if matches:
...                 return matches[-1] if len(matches) == 1 else matches
...         return self._reg[name]
... 
>>> registry = DuckRegistry({'type': 'black', 'name': 'Daffy'})
>>> registry.find('Daffy')
Duck(type=<DuckType.BLK: 'black'>, name='Daffy')
>>> registry.add({'type': 'white', 'name': 'Donald'})
>>> registry.find('Donald')
Duck(type=<DuckType.WHT: 'white'>, name='Donald')

>>> registry.add({'type': 'goose', 'name': 'Maynard'})
Traceback (most recent call last):
 ...
ValueError: 'goose' is not a valid DuckType
```

### What Just Happended Here?

When we wrap a callable with `@typic.al`, the wrapper reads the
signature of the callable and automatically coerces the incoming data to
the type which is annotated. This includes varargs (`*args` and
`**kwargs`). This means that you no longer need to do the work of
converting incoming data yourself. You just need to signal what you
expect the data to be with an annotation and **Typical** will do the
rest.

The `ValueError` we see in the last operation is what we  can expect when
attempting to supply an invalid value for the Enum class we used above.
Rather than have to write code to cast this data and handle stuff that's
invalid, you can rest easy in the guarantee that the data you expect is
the data you'll get.

### What's Supported?

As of this version, **Typical** can parse the following inputs into
valid Python types and classes:
* JSON
* YAML (if [PyYAML](https://pyyaml.org/wiki/PyYAMLDocumentation) is 
  installed)
* Python code (via
  [ast.literal_eval](https://docs.python.org/3/library/ast.html#ast.literal_eval))
* Date-strings and Unix Timestamps (via
  [python-dateutil](https://dateutil.readthedocs.io/en/stable/))
* Custom `NewType` declarations.


### Limitations

#### Forward Refs
A "forward reference" is a reference to a type which has either not yet
been defined, or is not available within the module which the annotation
lives. This is noted by encapsulating the annotation in quotes, e.g.:
`foo: 'str' = 'bar'`. Beware of using such syntax in combination with
Typical. Typical makes use of `typing.get_type_hints`, which scans the
namespace(s) available to the given object to resolve annotations. If
the annotation is unavailable, a `NameError` will be raised. This
behavior is considered valid. If you wish to make use of Typical for
type-coercion, make sure the annotated type is in the namespace of the
object you're wrapping and avoid Forward References if at all possible.

#### Special Forms
There is a subset of type annotations which are 'suscriptable' - meaning
you can specify what other types this annotation may resolve to. In a
few of those cases, the intended type for the incoming data is too
ambiguous to resolve. The following annotations are special forms which
cannot be supported:
* Union
* Any

Because these signal an unclear resolution, Typical will ignore this
flavor of annotation, leaving it to the developer to determine the
appropriate action.


## Updates

_New in version 1.1.0:_ `typing.Optional` and `typing.ClassVar` are now
supported.

_New in version 1.2.0:_ Values set to annotated attributes are
automagically resolved.

_New in version 1.3.0:_ 
1. Custom coercers may now be registered, e.g.:
    ```python
    import typic
    
    class MyCustomClass:
    
        def __init__(self, value):
            self.value = value
    
        @classmethod
        def factory(cls, value):
            return cls(value)
    
    
    def custom_class_coercer(value, annotation: MyCustomClass):
        return annotation.factory(value)
    
    
    def ismycustomclass(obj) -> bool:
        return obj is MyCustomClass
        
    
    typic.register(custom_class_coercer, ismycustomclass)
    ```

2. Squashed a few bugs:
   -  Nested calls of `Coercer.coerce_value` didn't account for values
      that didn't need coercion. This sometimes broke evaluation, and
      definitely resulted in sub-optimal type resolution performance.
   -  In the final attempt to coerce a custom class, calling
      `typic.evals.safe_eval` could reveal that a value is null. In this
      case, we should respect whether the annotation was optional.
   -  Sometimes people are using a version of PyYAML that's older than
      5.1. We should support that.

_New in version 1.3.1_:
1. Improved caching strategy and resolution times.

_New in version 1.3.2:_ 
1. Resolution time is better than ever.
2. Custom Unions are now supported via registering custom coercers with
   `typic.register`, as a result of raising the priority of
   user-registered coercers.
   
_New in version 1.4.0:_
1. A new wrapper has been added to simplify dataclass usage:

    ```python
    import typic
    
    @typic.klass
    class Foo:
        bar: str
    
    ```
    is equivalent to 
    ```python
    import dataclasses
    import typic
    
    @typic.al
    @dataclasses.dataclass
    class Foo:
        bar: str
    
    ```
    All standard dataclass syntax is supported with
    `typic.klass`
   
_New in version 1.4.1:_
1. Fixed a nasty bug in wrapped classes that resulted in
   infinite recursion.
   
_New in version 1.5.0:_
1. Frozen dataclasses are now supported.

_New in version 1.9.0:_
1. Introducing `typic.bind`:
   - An optimized version of `inspect.Signature.bind` which will also coerce inputs given.
2. `typic.al` is now up to ~30% faster on wrapped callables.

## Documentation

Full documentation coming soon!

Happy Typing :duck:


## How to Contribute
1.  Check for open issues or open a fresh issue to start a discussion
    around a feature idea or a bug. 
2.  Create a branch on Github for your issue or fork
    [the repository](https://github.com/seandstewart/que) on GitHub to
    start making your changes to the **master** branch.
3.  Write a test which shows that the bug was fixed or that the feature
    works as expected.
4.  Send a pull request and bug the maintainer until it gets merged and
    published. :)
