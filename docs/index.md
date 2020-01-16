![image](img/typical.png)

# Take Typing Further.

## What Is This?

Typical is a simple fast, and correct data-validation library using
Python 3 type annotations. It supports automatic, guaranteed
validation and coercion of incoming data by taking advantage of the
type-hinting syntax provided by
[PEP 484](https://www.python.org/dev/peps/pep-0484/) and the standard
[typing](https://docs.python.org/3/library/typing.html) module.

Unlike other popular libraries such as Pydantic, Marshmallow, or Django
Rest Framework, there is no new DSL to learn. `typical` does all of the
work for you and all you need to know how to use is builtin type-hint
syntax.

`typical` provides an entire suite of tools and functionality
over-and-above the standard data-validation run-time:

-   Extended types for everyday web-development.
-   Contrained type descriptions for builtin types.
-   JSON Schema generation for builtins, `typing` types, and your own
    custom types or classes.

## Getting Started

`typical` is a Python-only package
[hosted on PyPI](https://pypi.org/project/typical/).

```shell
pip install typical
```

The next few steps should bring you up and running in no time:

-   **Why** gives you a rundown of potential alternatives and why we
    think `typical` is superior.
-   **Overview** will show you a simple example of `typical` in action
    and introduce you to its philosophy.
-   **Usage** will give you a quick look at the high-level API, and a
    few useful advanced patterns as well.
-   **Extras** will give you a comprehensive tour of `typical`\'s
    features.
