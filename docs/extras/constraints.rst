``typical`` Constraints
=======================
Constraints allow you to define "restricted" types for your data. This is similar to
what you may see when defining your fields in JSON schema. In fact, we can (and do) use
constraints to generate extended JSON schema type definitions.

Usage
-----
You can define your "constrained type" by using the ``typic.constrained`` decorator on
a sub-class of the builtin Python type you want to restrict. This can be quite useful
for restricting the type of data a callable is allowed to receive:

.. code-block:: pycon

    >>> import typic
    >>>
    >>> @typic.constrained(ge=0, le=1)
    ... class TinyInt(int):
    ...     """An integer type restrcted to only 0-1."""
    ...     ...
    ...
    >>> @typic.al
    >>> def switch(val: TinyInt) -> str:
    ...     if val == 1:
    ...         return "on!"
    ...     if val == 0:
    ...         return "off!"
    ...
    >>> switch(1)
    'on!'
    >>> switch(0)
    'off!'
    >>> switch(2)
    Traceback (most recent call last):
    ...
    typic.constraints.error.ConstraintValueError: Given value <2> fails constraints: (type=int, ge=0, le=1)


API
---

.. autodecorator:: typic.constrained
