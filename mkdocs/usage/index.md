# The Basics

`typical` is built around a powerful, high-level functional API whose
purpose is to make working with annotations at runtime a breeze for
any developer.

## Installation

Installation is as simple as `pip install -U typical`.

For an easy speedup at runtime, you can add `ujson` to the
installation with `typical[json]`. This results in a 30-50%
improvement when serializing your data with `.tojson()`.


## `@typic.al()`

The simplest way to get going with `typical` is the `@typic.al`
decorator. This is the core entrypoint for all the magic
:crystal_ball:.

### Wrapping Callables

```python
import enum

import typic


class Decision(enum.IntEnum):
    YES = 1
    NO = 0
    MAYBE = -1
    

class Explanation(str, enum.Enum):
    YES = "Of course!"
    NO = "That's just the way it is."
    MAYBE = "¯\_(ツ)_/¯"
    

DECISION_MAP = dict(zip(Decision, Explanation))


@typic.al
def explain(decision: Decision) -> str:
    return DECISION_MAP[decision]
  

print(repr(explain(1.0)))
#> <Explanation.YES: 'Of course!'>

```

In the above example, `typical` has taken care of your runtime
type-validation automatically. It also follows the classical Python
logic of duck-typing: `float -> int -> Decision`. But it will handle
more cases than that:

```python
print(repr(explain(b"-1")))
#> <Explanation.MAYBE: '¯\\_(ツ)_/¯'>
```

`typical` knows to look for common cases such as json and string/byte
literals and handles them gracefully.

That means you don't have to remember to handle every single edge case
yourself. Just write your pure function and let `typical` handle the
rest. **This is incredibly useful for code which lives on the edges of
your application** - such as a handler for an external caller or an
ingestor from a data-source.

#### Errors

But what about errors? `typical` is built to provide transparency in
the event that a value cannot be transmuted into the expected
annotation. Taking the above example, if we pass a value not defined
by our `Decsion` enum:

```python
explain(2)
#> ValueError: 2 is not a valid Decision
```

So instead of a random, non-descriptive `KeyError`, you get a clear,
predictable `ValueError` which can be easily passed on to the external
caller for handling.

### Wrapping Classes

`typical` works with classes too -

```python
import typic


@typic.al
class Foo:
    bar: str
        
    def __init__(self, bar: str):
        self.bar = bar

print(repr(Foo(b"bar").bar))
#> 'bar'
```

But if you're wrapping your class, you may as well go all the way with
that sexy dataclass-style...

```python
import typic


@typic.klass
class Foo:
    bar: str


```

This is a dataclass under the hood, so anything you do with
dataclasses you can do with your `@typic.klass`, and much, much more.
