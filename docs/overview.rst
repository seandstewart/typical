====================
``typical`` Overview
====================

``typical`` was built with a singular purpose: let your type annotations work for you
in a concise, understandable, and `dynamic` way. This goes beyond static type-checking
and into runtime type enforcement. There are many popular libraries doing this, but we
think ``typical``'s emphasis on simplicity and performance makes it the best one out
there.

Take a look at how we can make type-annotations `do the work for us`:

.. doctest::


    >>> import dataclasses
    >>> import datetime
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
    ...     created_on: datetime.datetime
    ...
    >>> external_data = {'type': 'white', 'name': 'Donald', 'created_on': '1970-01-01 00:00:00+00:00'}
    >>> donald = Duck(**external_data)
    >>> donald.type
    <DuckType.WHT: 'white'>
    >>> donald.created_on
    datetime.datetime(1970, 1, 1, 0, 0, tzinfo=tzutc())


``typical`` also makes it easier to translate your class back into `primitive` data for
sending over the wire. Adding to the snippet from above:


.. code-block:: pycon


    >>> donald.primitive()
    {'type': 'white', 'name': 'Donald', 'created_on': '1970-01-01T00:00:00+00:00'}


The output from ``donald.primitive()`` is JSON-serializable, **guaranteed**, no need to
figure it out for yourself.


Philosophy
==========

**Simplicity Counts.**
    - There's no new DSL to learn - ``typical`` works directly with the Python standard
      library's ``typing`` library. Annotate as you would for your static checker and
      let ``typical`` do the rest.
    - Forget defining custom ``validators`` or ``converters`` for simple things like
      parsing date-strings or converting from ``bytes`` to ``str`` - ``typical``'s got
      your back.

**Correctness is Key**
    - Python embraces the builtin type-system and work with it rather than against it.
    - There should be one -- and preferably only one -- way to do things. ``typical``
      follows a predictable waterfall when resolving your type annotation into an
      actionable deserializer for run-time that covers about 99% of cases.
    - In the instances where this isn't sufficient, ``typical`` provides a simple
      mechanism for providing your own deserializer(s).

**Performance Matters**
    - It's not good enough to be correct if your application slows to a crawl. There's
      no way to avoid the run-time cost of coercion, but ``typical`` works hard to ensure
      the impact is minimal enough to only be felt in extremely tight loops. For
      standard application run-times, you shouldn't notice ``typical`` at work at all.

