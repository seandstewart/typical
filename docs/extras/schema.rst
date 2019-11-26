``typical`` JSON Schema
=======================
``typical`` provides a high-level API for fetching the JSON schema of an object:

.. autofunction:: typic.schema


Additionally, classes wrapped with :py:func:`typic.al` or :py:func:`typic.klass` have
are given a ``schema()`` classmethod for quick introspection.

.. doctest::

    >>> import json
    >>> import typic
    >>>
    >>> @typic.klass
    ... class Foo:
    ...     """A Foo that bars!"""
    ...     bar: str
    ...
    >>> @typic.klass
    ... class Buzz:
    ...     """A Buzz with Foo."""
    ...     foo: Foo
    ...
    >>> print(json.dumps(Buzz.schema(primitive=True), indent=2))
    {
      "type": "object",
      "title": "Buzz",
      "description": "A Buzz with Foo.",
      "properties": {
        "foo": {
          "$ref": "#/definitions/Foo"
        }
      },
      "additionalProperties": false,
      "required": [
        "foo"
      ],
      "definitions": {
        "Foo": {
          "type": "object",
          "title": "Foo",
          "description": "A Foo that bars!",
          "properties": {
            "bar": {
              "type": "string"
            }
          },
          "additionalProperties": false,
          "required": [
            "bar"
          ]
        }
      }
    }


In the case where you need all the definitions for your models, ``typical``'s got your
back. Any model wrapped with :py:func:`typic.al` or :py:func:`typic.klass` is
automatically registered at runtime and can be accessed by a single call:

.. autofunction:: typic.schemas

For a look into the low-level API, see the schema documentation in ``Low Level API``.
