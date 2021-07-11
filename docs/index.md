# typical: Python's Typing Toolkit
[![image](https://img.shields.io/pypi/v/typical.svg)](https://pypi.org/project/typical/)
[![image](https://img.shields.io/pypi/l/typical.svg)](https://pypi.org/project/typical/)
[![image](https://img.shields.io/pypi/pyversions/typical.svg)](https://pypi.org/project/typical/)
[![image](https://img.shields.io/github/languages/code-size/seandstewart/typical.svg?style=flat)](https://github.com/seandstewart/typical)
[![Test & Lint](https://github.com/seandstewart/typical/workflows/Test%20&%20Lint/badge.svg)](https://github.com/seandstewart/typical/actions)
[![Coverage](https://codecov.io/gh/seandstewart/typical/branch/master/graph/badge.svg)](https://codecov.io/gh/seandstewart/typical)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Netlify Status](https://api.netlify.com/api/v1/badges/982a0ced-bb7f-4391-87e8-1957071d2f66/deploy-status)](https://app.netlify.com/sites/typical-python/deploys)

![How Typical](static/typical.png)

## Introduction

Typical is a library devoted to runtime analysis, inference,
validation, and enforcement of Python types,
[PEP 484](https://www.python.org/dev/peps/pep-0484/) Type Hints, and
custom user-defined data-types.

Typical is fully compliant with the following Python Typing PEPs:

- [PEP 484 -- Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [PEP 563 -- Postponed Evaluation of Annotations](https://www.python.org/dev/peps/pep-0563/)
- [PEP 585 -- Type Hinting Generics In Standard Collections](https://www.python.org/dev/peps/pep-0585/)
- [PEP 586 -- Literal Types](https://www.python.org/dev/peps/pep-0586/)
- [PEP 589 -- TypedDict: Type Hints for Dictionaries with a Fixed Set of Keys](https://www.python.org/dev/peps/pep-0589/)
- [PEP 604 -- Allow writing union types as X | Y](https://www.python.org/dev/peps/pep-0604/)

It provides a high-level Protocol API, Functional API, and Object API to suit most any
occasion.

## Getting Started

Installation is as simple as `pip install -U typical`.
## Help

The latest documentation is hosted at
[python-typical.org](https://python-typical.org/).

> Starting with version 2.0, All documentation is hand-crafted
> markdown & versioned documentation can be found at typical's
> [Git Repo](https://github.com/seandstewart/typical/tree/master/docs).
> (Versioned documentation is still in-the-works directly on our
> domain.)

## A Typical Use-Case

The decorator that started it all:

### `typic.al(...)`

```python
import typic


@typic.al
def hard_math(a: int, b: int, *c: int) -> int:
    return a + b + sum(c)

hard_math(1, "3")
#> 4


@typic.al(strict=True)
def strict_math(a: int, b: int, *c: int) -> int:
    return a + b + sum(c)

strict_math(1, 2, 3, "4")
#> Traceback (most recent call last):
#>  ...
#> typic.constraints.error.ConstraintValueError: Given value <'4'> fails constraints: (type=int, nullable=False, coerce=False)
  
```

Typical has both a high-level *Object API* and high-level
*Functional API*. In general, any method registered to one API is also
available to the other.

### The Protocol API

```python
import dataclasses
from typing import Iterable

import typic


@typic.constrained(ge=1)
class ID(int):
    ...


@typic.constrained(max_length=280)
class Tweet(str):
    ...


@dataclasses.dataclass # or typing.TypedDict or typing.NamedTuple or annotated class...
class Tweeter:
    id: ID
    tweets: Iterable[Tweet]


json = '{"id":1,"tweets":["I don\'t understand Twitter"]}'
protocol = typic.protocol(Tweeter)

t = protocol.transmute(json)
print(t)
#> Tweeter(id=1, tweets=["I don't understand Twitter"])

print(protocol.tojson(t))
#> '{"id":1,"tweets":["I don\'t understand Twitter"]}'

protocol.validate({"id": 0, "tweets": []})
#> Traceback (most recent call last):
#>  ...
#> typic.constraints.error.ConstraintValueError: Tweeter.id: value <0> fails constraints: (type=int, nullable=False, coerce=False, ge=1)
```

### The Functional API

```python
import dataclasses
from typing import Iterable

import typic


@typic.constrained(ge=1)
class ID(int):
    ...


@typic.constrained(max_length=280)
class Tweet(str):
    ...


@dataclasses.dataclass # or typing.TypedDict or typing.NamedTuple or annotated class...
class Tweeter:
    id: ID
    tweets: Iterable[Tweet]


json = '{"id":1,"tweets":["I don\'t understand Twitter"]}'

t = typic.transmute(Tweeter, json)
print(t)
#> Tweeter(id=1, tweets=["I don't understand Twitter"])

print(typic.tojson(t))
#> '{"id":1,"tweets":["I don\'t understand Twitter"]}'

typic.validate(Tweeter, {"id": 0, "tweets": []})
#> Traceback (most recent call last):
#>  ...
#> typic.constraints.error.ConstraintValueError: Tweeter.id: value <0> fails constraints: (type=int, nullable=False, coerce=False, ge=1)
```

### The Object API

```python
from typing import Iterable

import typic


@typic.constrained(ge=1)
class ID(int):
    ...


@typic.constrained(max_length=280)
class Tweet(str):
    ...


@typic.klass
class Tweeter:
    id: ID
    tweets: Iterable[Tweet]
    

json = '{"id":1,"tweets":["I don\'t understand Twitter"]}'
t = Tweeter.transmute(json)

print(t)
#> Tweeter(id=1, tweets=["I don't understand Twitter"])

print(t.tojson())
#> '{"id":1,"tweets":["I don\'t understand Twitter"]}'

Tweeter.validate({"id": 0, "tweets": []})
#> Traceback (most recent call last):
#>  ...
#> typic.constraints.error.ConstraintValueError: Given value <0> fails constraints: (type=int, nullable=False, coerce=False, ge=1)
```


## Changelog

See our
[Releases](https://github.com/seandstewart/typical/releases).
