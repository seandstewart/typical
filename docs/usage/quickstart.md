# typical Quickstart

`typical` defines a high-level API that is simple, functional, and
powerful.

The core functionality of `typical` is provided by the `@typic.al`
decorator:

::: typic.al

For example:

    >>> import typic
    >>>
    >>> @typic.al
    ... def foo(bar: str) -> str:
    ...     return f"{bar!r} is type {type(bar)!r}"
    ...
    >>> foo(b"bar")
    "'bar' is type <class 'str'>"
    >>>
    >>> import dataclasses
    >>>
    >>> @typic.al
    ... @dataclasses.dataclass
    ... class Foo:
    ...     bar: str
    ...
    >>> Foo(b"bar")
    Foo(bar='bar')


Since the `typic.al`/`dataclasses.dataclass` combination is so common,
`typic` actually provides a shortcut:

::: typic.klass

This should be enough to get you going with `typical` - the emphasis
of this library is usability and simplicity. You shouldn't *need* to
interact with the rest of the high-level API.

However, that option is always available to you...
