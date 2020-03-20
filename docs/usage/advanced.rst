``typical`` Advanced Usage
==========================
As you've seen, ``typical`` is a veritable Swiss Army knife for managing type
annotations at run-time. Below are some additional supported uses that you may find
yourself needing from time-to-time.

Helpers
-------
``typical`` also provides a variety of high-level helpers that make interacting with
types a breeze:

.. autofunction:: typic.transmute
    :noindex:

.. autofunction:: typic.primitive
    :noindex:

.. autofunction:: typic.bind
    :noindex:

.. autofunction:: typic.schema
    :noindex:

.. autofunction:: typic.schemas
    :noindex:

.. autofunction:: typic.protocol
    :noindex:


.. autofunction:: typic.protocols
    :noindex:


.. autofunction:: typic.validate
    :noindex:


.. autofunction:: typic.tojson
    :noindex:


Classes
-------
There are a few high-level classes that may be interacted with.

.. autoclass:: typic.Annotation
    :members:
    :noindex:

.. autoclass:: typic.SerdeProtocol
    :members:
    :noindex:

.. autoclass:: typic.BoundArguments
    :members:
    :noindex:



Delayed Protocol Resolution
---------------------------
Sometimes you define a class that depends upon another class or type which isn't defined
quite yet. This can cause issues resolving your annotation for coercion. In those
cases, we provide a simple ``delay`` parameter and a ``typic.resolve()`` function.


.. autofunction:: typic.resolve


.. code-block:: python

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


.. note::

    If you don't manually call :py:func:`typic.resolve`, your annotations for your
    delayed object will be resolved the first time your class or function is called.
    This is an expensive operation so you're encourage to call
    :py:func:`typic.resolve` ahead of time.



Custom Type Deserializers
-------------------------
Typic does everything it can to figure out how to initialize your custom classes
without much input from you. If you feel the need to control the initialization of your
``typic.al`` class, you can do so in one of two ways:

1. Define a ``from_dict`` factory method on your class:

.. code-block:: python

    import typic


    @typic.klass
    class Foo:
        bar: str

        @classmethod
        def from_dict(cls, data: dict) -> "Foo":
            ... # do stuff with the data
            return Foo(**data)


.. note::

    ``typical`` assumes that if your incoming data is in the format of a JSON blob or a
    dict, it can map directly to your model's fields so the above example is
    functionally unnecessary unless you're mutating said data in some way.


2. Register a custom type deserializer for your class:


.. code-block:: python

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
    def foo_deserializer(val: dict):
        type = val.pop("type", None)
        if type:
            cls = FooType.select(type)
            return cls(**val)
        raise ValueError(f"Can't determine FooType from {val}")


    # register your deserializer with a function to detect if an annotation is valid
    typic.register(foo_deserializer, isfootype)
    # resolve your annotations
    typic.resolve()



Customizing your Ser/Des Protocol
---------------------------------
``typical`` provides a path for you to customize *how* your data is transmuted into
your custom classes, and how it is dumped back to its primitive form. It all starts
with this class:

.. autoclass:: typic.SerdeFlags
    :members:
    :noindex:


The simplest method for customizing your protocol is via :py:func:`typic.klass`:

.. doctest::

    >>> import typic
    >>>
    >>> @typic.klass
    >>> class Foo:
    ...    bar: str = typic.field(name="Bar")
    ...    exc: str = typic.field(exclude=True)
    ...
    >>> foo = Foo("bar", "exc")
    >>> foo.primitive()
    {'Bar': 'bar'}
    >>> foo.tojson()
    '{"Bar":"bar"}'


For more power, you can manually assign the ``__serde_flags__`` attribute on any class:

.. doctest::

    >>> class Foo:
    ...     __serde_flags__ = typic.SerdeFlags(fields=("bar", "prop"))
    ...     prop: int
    ...     bar: str = ""
    ...
    ...     @property
    ...     def prop(self) -> int:
    ...         return 0
    ...
    >>> proto = typic.protocol(Foo)
    >>> proto.primitive(Foo())
    {'prop': 0, 'bar': ''}


Manual Ser/Des
--------------
If, for some reason, you don't like all the magic and you want to have manual control
over when and how you coerce your types, ``typical`` still has your back with its
high-level API. Instead of wrapping your functions or classes, you can call
:py:func:`typic.transmute` & :py:func:`typic.primitive` when and where you want.


.. code-block:: python

    # foo.py
    import dataclasses

    import typic


    @dataclasses.dataclass
    class Foo:
        bar: str


    def some_function_which_expects_foo(data: Foo) -> Foo:
        ... # do stuff with foo
        return foo



Voila! Let's pop into an interpreter to see this in action:


.. doctest::

    >>> import typic
    >>>
    >>> from .foo import some_function_without_magic, Foo
    >>>
    >>> data = "bar"
    >>> some_function_without_magic(typic.transmute(Foo, data))
    Foo(bar='bar')
    >>> some_function_without_magic(typic.transmute(Foo, '{"bar": 1}'))
    Foo(bar='1')
    >>> typic.primitive(Foo(bar="bar"))
    {'bar': 'bar'}


.. note::

    While this interaction is valid, it's encouraged to follow the decorator pattern
    where-ever possible. Otherwise, you will take a warm-up hit in performance while
    ``typical`` works to figure out how to coerce your stuff the first time anything
    like this is called.


You can also retrieve a ser/des protocol for nearly any type, including your own:

.. doctest::

    >>> import typic
    >>> str_proto: typic.SerdeProtocol = typic.protocol(str, is_strict=True)
    >>> str_proto.transmute(1)
    Traceback (most recent call last):
      ...
    typic.constraints.error.ConstraintValueError: Given value <1> fails constraints: (type=str, nullable=False, coerce=False)


.. doctest::

    >>> import typic
    >>> import dataclasses
    >>> @dataclasses.dataclass
    ... class Foo:
    ...     bar: str
    ...
    >>> foo_proto: typic.SerdeProtocol = typic.protocol(Foo)
    >>> foo_proto.transmute({"bar": "foo"})
    Foo(bar='foo')
    >>> foo_proto.transmute("foo")
    Foo(bar='foo')
    >>> foo_proto.primitive(Foo("foo"))
    {'bar': 'foo'}
    >>> foo_proto.tojson(Foo("foo"))
    '{"bar":"foo"}'
