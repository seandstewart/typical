# Using Typical

Typical has three primary means of interaction - the *Functional API*, the *Protocol
API*, and the *Object API*

## The Functional API

The *Functional API* largely mirrors the
[Object API](#the-object-api). It allows you to define your types and
pass them into set of high-level methods for largely the same effect
as binding directly to a class with `@typic.klass`.

!!! important

    One of the benefits to the Object API is that the protocols
    for  serialization, deserialization, and validation are generated 
    at compile-time of the module and cached for later use. The 
    Functional API has no compile-time optimization, so the protocols 
    for your custom types will not be generated and cached until the 
    first call. 
    
    There are, however, other runtime benefits to the Functional API 
    which we'll discuss below.
    
    !!! note ""
        
        We provide a path for optimizing this initial performance hit
        by manually binding a protocol via `typic.protocol(...)`. See
        [SerDes](serdes.md) for more.

### Defining Your Data

Anything goes!

No, really, for the most part, any custom type definition is valid for
the Functional API. The Functional API also knows to look out for
types defined with the Object API, no additional cost is incurred for
interacting with an object via either API, minus the cost of a few
additional function calls.

Let's look at the models we defined in the Object API, but this time,
only use the Functional API for interaction.

!!! note

    While we're using dataclasses to define our data, we could also
    use vanilla classes, `TypedDict`, or `NamedTuple`. All we need for 
    proper introspection is valid type annotations.


```python
from __future__ import annotations

import enum
import dataclasses
from typing import Iterable, Optional


class Instrument(str, enum.Enum):
    """The only instruments a band really needs, duh."""
    
    GUIT = "guitar"
    BASS = "bass"
    PIAN = "piano"
    DRUM = "drums"


@dataclasses.dataclass
class Member:
    """A member in the band, man."""

    name: str
    instrument: Instrument
    id: Optional[int] = None


@dataclasses.dataclass
class Band:
    """It's the band, man."""

    name: str
    members: Iterable[Member]
    id: Optional[int] = None


@dataclasses.dataclass
class Song:
    """A sick tune - platinum fer sure."""

    name: str
    lyrics: str
    band: Band
    id: Optional[int] = None
```

!!! info ""

    The important thing to take away here is that there's *virtually
    no difference in LOC or declaration* from the standard lib and the
    `@typic.klass` declaration. This is a cornerstone of Typical's
    design: Work with *with* standard libary, not against
    (or parallel) to it.

### Interacting With Your Data

#### `typic.schema(...)`

> A function which returns a JSON Schema definition of your class.
>
> If the class was not bound using the [Object API](#the-object-api)
> or by calling `typic.protocol()`, the schema will be generated at
> first call and then cached for later use.
>
> ??? example "Rendering a Schema"
>
>     ```python
>     print(typic.schema(Member).tojson(indent=2))
>     #> {
>     #>   "type": "object",
>     #>   "title": "Member",
>     #>   "description": "A member in the band, man.",
>     #>   "properties": {
>     #>     "id": {
>     #>       "type": "integer"
>     #>     },
>     #>     "instrument": {
>     #>       "type": "string",
>     #>       "enum": [
>     #>         "guitar",
>     #>         "bass",
>     #>         "piano",
>     #>         "drums"
>     #>       ]
>     #>     },
>     #>     "name": {
>     #>       "type": "string"
>     #>     }
>     #>   },
>     #>   "additionalProperties": false,
>     #>   "required": [
>     #>     "instrument",
>     #>     "name"
>     #>   ],
>     #>   "definitions": {
>     #>
>     #>   }
>     #> }
>     ```

#### `typic.transmute(...)`

> Convert incoming data into an type or Annotation.
>
> Incoming data may be:
>
> - Arbitrary classes (e.g., an ORM Model or other class)
> - JSON strings/bytes
> - Python literals
>
> The type may be any valid type annotation, standard Python type, or
> custom user-defined class.
>
> ??? example "Transmute Data to Member"
>
>     ```python
>     typic.transmute(Member, '{"name":"Ben","instrument":"piano"}')
>     #> Member(name='Ben', instrument=<Instrument.PIAN: 'piano'>, id=None)
>     ```

#### `typic.translate(...)`

> Convert an instance of any arbitrary class to another arbitrary class.
>
> !!! note
>
>     This function is considerably less powerful than 
>     [transmute](#typictransmute). At a functional level, you're
>     encouraged to make use of that method rather than this. To 
>     understand *why* this function exists, take a look at its
>     definition in the [Object API](#translate).
>
> ??? example "Translate Member"
>
>     ```python
>     class MemberORM:
>         def __init__(self, name, instrument, id=None):
>             self.name = name
>             self.instrument = instrument
>             self.id = id
> 
>         def __repr__(self):
>             return f"<Member id={self.id} name={self.name} instrument={self.instrument}"
>     
>     
>     m = typic.transmute(Member, '{"name":"Robert","instrument":"guitar"}')
>     typic.translate(m, MemberORM)
>     #> <Member id=None name=Robert instrument=guitar
>     ```


#### `typic.validate(...)`

> Validate some data against your an annotation or model.
>
> ??? example "Member Data Validation"
>
>     ```python
>
>     typic.validate(Member, {"name": "Paul", "instrument": "anything"})
>     #> Traceback (most recent call last):
>     #> 	...
>     #> typic.constraints.error.ConstraintValueError: Member.instrument: value <'anything'> fails constraints: (type=instrument, values=('guitar', 'bass', 'piano', 'drums', 'vocals'), nullable=False)
>     ```
>
> !!! fail "Gotcha"
>
>     Validators don't do any type conversion, so passing raw JSON into
>     the `typic.validate()` will fail. See [Validation](validation.md)

#### `typic.primitive(...)`

> Convert any instance into its "primitive" equivalent.
>
> This method effectively *downgrades* your model into a
> JSON-serializable dict.
>
> ??? example "Member to Primitive"
>
>     ```python
>     m = typic.transmute(Member, '{"name":"Darren","instrument":"drums"}')
>     print(typic.primitive(m))
>     #> {"name": "Darren", "instrument":"drums", "id": None}
>     ```

#### `typic.tojson(...)`

> Serialize your model instance to JSON
>
> This method will pass on any keyword arguments to the  downstream
> serializer.
>
> !!! note ""
>
>     If [ujson](https://pypi.org/project/ujson/) is installed,
>     this method will default to that library.
>
> ??? example "Member to JSON"
>
>     ```python
>     m = typic.transmute(Member, '{"name":"Darren","instrument":"drums"}')
>     print(typic.tojson(m, indent=2))
>     #> {
>     #>   "name": "Darren",
>     #>   "instrument": "drums",
>     #>   "id": null
>     #> }
>     ```
>
> !!! tip
>
>     It's possible to customize your serialized representation. See
>     [SerDes](serdes.md).

#### `typic.decode(...)`

> Decode on-the-wire data into your Model.
>
> This is useful if you plan to use a wire-format such as Avro, protocol buffers, etc.
>
> To use custom decoders, pass in a callable which takes the input as its first
> argument. All other keyword-arguments are passed on to the decoder function.
>
> ??? example "Decode Binary Data to Member"
>
>     ```python
>     
>     def decode(o: bytes, *, encoding: str = None):
>         # Pretend we're using something other than a basic .decode()...
>         return o.decode(encoding=encoding)
>     
>     input = '{"name":"Ben","instrument":"piano","id":1}'.encode("utf-8-sig")
>     typic.decode(Member, input, decoder=decode, encoding="utf-8-sig")
>     #> Member(name='Ben', instrument=<Instrument.PIAN: 'piano'>, id=1)
>     ```

#### `typic.encode(...)`

> Encode your Model to a custom wire-format.
>
> This is useful if you plan to use a wire-format such as Avro, protocol buffers, etc.
>
> To use custom encoders, pass in a callable which takes the primitive representation of
> your Model as the first argument. All other keyword-arguments are passed on to the
> encoder function.
>
> ??? example "Encode a Member to Binary Data"
>
>     ```python
>     import ujson
>     
>     def encode(o: Any, *, encoding: str = None) -> bytes:
>         # Pretend we're using something other than a basic dumps().encode()...
>         return ujson.dumps(o).encode(encoding=encoding)
>     
>     m = Member(name="Ben", instrument=Instrument.PIAN, id=1)
>     typic.encode(m, encoder=encode)
>     #> b'{"name":"Ben","instrument":"piano","id":1}'
>     ```

#### `typic.iterate(...)`

> !!! info ""
>
>     New in version 2.4
>
> If compatible, iterate over your data. If the object is a mapping or class, you have
> the option to iterate over (field, value) pairs, or simply over the values themselves.
>
> ??? example "Iterate a Member instance's data"
>
>     ```python
>     
>     m = Member(name="Ben", instrument=Instrument.PIAN, id=1)
>     
>     print([*typic.iterate(m)])
>     #> [('name', 'Ben'), ('instrument', <Instrument.PIAN: 'piano'>), ('id', 1)]
>     
>     print(dict(typic.iterate(m)))
>     #> {'name': 'Ben', 'instrument': <Instrument.PIAN: 'piano'>, 'id': 1}
>     
>     print([*typic.iterate(m, values=True)])
>     #> ['Ben', <Instrument.PIAN: 'piano'>, 1]
>     ```


## The Protocol API

As promised, Typical provides a path for optimizing your interactions with the
Functional API. This is done by calling the `typic.protocol` method. This method is a
public alias for our type resolver's main entry-point. This means that the protocol
provided by this method is guaranteed to work exactly as the methods on a class bound by
the Object API. Additionally, all high-level functional calls are guaranteed to have the
same result as calls to the bound protocol.

### Using Protocols

Binding a protocol gives us the best of both the Object and Functional
APIs. We get the benefit of the Object API's optimistic caching and
brevity alongside the flexibility of the Functional API for
interacting with virtually any type or class directly.

#### `typic.protocol(...)`

> Get a Serialization/Deserialization Protocol for the given type or
> annotation.
>
> ??? example "Bind a Protocol to Member"
>
>     ```python
>     protocol = typic.protocol(Member)
>     protocol.transmute(b'{"name":"Ben","instrument":"piano"}')
>     #> Member(name='Ben', instrument=<Instrument.PIAN: 'piano'>, id=None)
>     ```
>
> ??? example "Bind a Protocol to an Annotation"
>
>     ```python
>     from typing import Mapping
>     
>     MemberMappingT = Mapping[str, Member]
>     protocol = typic.protocol(MemberMappingT)
>     
>     mapping = protocol.transmute(b'{"vocalist":{"name":"Janis","instrument":"vocals"}}')
>     
>     print(mapping)
>     #> {'vocalist': Member(name='Janis', instrument=<Instrument.VOCL: 'vocals'>, id=None)}
>     
>     protocol.tojson(mapping)
>     #> '{"vocalist":{"name":"Janis","instrument":"vocals","id":null}}'
>     
>     protocol.validate({"vocalist": {"name": "Al", "instrument": "xylophone"}})
>     #> Traceback (most recent call last):
>     #>   ...
>     #> typic.constraints.error.ConstraintValueError: Member.instrument: value <'xylophone'> fails constraints: (type=instrument, values=('guitar', 'bass', 'piano', 'drums', 'vocals'), nullable=False)
>     ```
>

As shown in the example above, we can get a protocol for a class and
use that protocol to transmute inputs into the bound type.

We can also run validation, get a JSON schema, translate instances of
our class to another arbitrary class, get primitive representations of
instances, and dump instances to JSON.


## The Object API

As touched on in [Basics](index.md), you can interact with the Object
API in two ways: `@typic.al` and `@typic.klass`. What's the
difference? Very little.

`@typic.al` will wrap any class, but works best when combined with
[dataclasses](https://docs.python.org/3/library/dataclasses.html).
This is because of the declarative nature of defining fields and input
which dataclasses provide. To whit...

`@typic.klass` is a short-hand for the `@typic.al/@dataclass`
combination, which also provides a *slightly* more powerful API. For
brevity (the soul of wit), we'll be using `@typic.klass` for the
examples in this section.

### Defining your Objects

!!! tip

    If you're unfamiliar with dataclasses, it's best to take some time
    now and review the official 
    [documentation](https://docs.python.org/3/library/dataclasses.html) 
    and [PEP 557](https://www.python.org/dev/peps/pep-0557/).

As you've seen previously, defining your data is as simple as
following the now-familiar pattern across many libraries:

```python
from __future__ import annotations

import enum
import typic
from typing import Iterable, Optional


class Instrument(str, enum.Enum):
    """The only instruments a band really needs, duh."""
    
    GUIT = "guitar"
    BASS = "bass"
    PIAN = "piano"
    DRUM = "drums"
    VOCL = "vocals"


@typic.klass
class Member:
    """A member in the band, man."""

    name: str
    instrument: Instrument
    id: Optional[int] = None


@typic.klass
class Band:
    """It's the band, man."""

    name: str
    members: Iterable[Member]
    id: Optional[int] = None


@typic.klass
class Song:
    """A sick tune - platinum fer sure."""

    name: str
    lyrics: str
    band: Band
    id: Optional[int] = None
```

The `@typic.klass` decorator is built on top of the
`@dataclass.dataclass` decorator, so any parameter which the
`@dataclass.dataclass` decorator
[accepts](https://docs.python.org/3/library/dataclasses.html#dataclasses.dataclass)
is also accepted by `@typic.klass`, plus a few more:

`strict: bool = False`
> This enables "strict" validation of inputs. See
> [validation](validation.md).

`jsonschema: bool = True`
> Generate a JSON Schema definition for your object.

`serde: SerdeFlags = None`
> Customize the serialization & deserialization of your object. See [SerDes](serdes.md).

`slots: bool = True`
> Automatically generate a class with slots for the attributes defined by your
> annotations.

### Interacting With Your Objects

As we've already demonstrated, Typical will guarantee the  data
passed into your models is parsed and transformed into the data you
defined.

First, let's define the API. Below are the methods which Typical
will bind to your object when it is wrapped with `@typic.al` or
`@typic.klass`.


#### `.schema()`

> A classmethod which returns a JSON Schema definition of your class.
>
> This schema is computed and cached at compile-time so runtime calls
> incur no additional compute time.
>
> ??? example "Rendering a Schema"
>
>     ```python
>     print(Member.schema().tojson(indent=2))
>     #> {
>     #>   "type": "object",
>     #>   "title": "Member",
>     #>   "description": "A member in the band, man.",
>     #>   "properties": {
>     #>     "id": {
>     #>       "type": "integer"
>     #>     },
>     #>     "instrument": {
>     #>       "type": "string",
>     #>       "enum": [
>     #>         "guitar",
>     #>         "bass",
>     #>         "piano",
>     #>         "drums"
>     #>       ]
>     #>     },
>     #>     "name": {
>     #>       "type": "string"
>     #>     }
>     #>   },
>     #>   "additionalProperties": false,
>     #>   "required": [
>     #>     "instrument",
>     #>     "name"
>     #>   ],
>     #>   "definitions": {
>     #>
>     #>   }
>     #> }
>     ```

#### `.transmute(...)`

> Convert incoming data into your Model.
>
> This supports:
>
> - Arbitrary classes (e.g., an ORM Model or other class)
> - JSON strings/bytes
> - Python literals
>
> ??? example "Transmute Data to Member"
>
>     ```python
>     Member.transmute('{"name":"Ben","instrument":"piano"}')
>     #> Member(name='Ben', instrument=<Instrument.PIAN: 'piano'>, id=None)
>     ```

#### `.translate(...)`

> Convert an instance of your model to another arbitrary class.
>
> ??? example "Translate Member"
>
>     ```python
>     class MemberORM:
>         def __init__(self, name, instrument, id=None):
>             self.name = name
>             self.instrument = instrument
>             self.id = id
> 
>         def __repr__(self):
>             return f"<Member id={self.id} name={self.name} instrument={self.instrument}"
>     
>     
>     m = Member.transmute('{"name":"Robert","instrument":"guitar"}')
>     m.translate(MemberORM)
>     #> <Member id=None name=Robert instrument=guitar
>     ```
>
> !!! note ""
>
>     It's possible to translate *to* another class, then transmute *back*. e.g.:  
> 
>     ``` python
>     m = Member.transmute('{"name":"Robert","instrument":"guitar"}')
>     orm = m.translate(MemberORM)
>     ... ## (do stuff with orm, save it, etc.)
>     Member.transmute(orm)
>     #> Member(name='Robert', instrument=<Instrument.GUIT: 'guitar'>, id=1)
>     ```

#### `.validate(...)`

> Validate some data against your model.
>
> ??? example "Member Data Validation"
>
>     ```python
> 
>     Member.validate({"name": "Paul", "instrument": "anything"})
>     #> Traceback (most recent call last):
>     #> 	...
>     #> typic.constraints.error.ConstraintValueError: Member.instrument: value <'anything'> fails constraints: (type=instrument, values=('guitar', 'bass', 'piano', 'drums', 'vocals'), nullable=False)
>     ```
>
> !!! fail "Gotcha"
>
>     Validators don't do any type resolution, so passing raw JSON into 
>     the `.validate()` method will fail. See [Validation](validation.md)

#### `.primitive()`

> Convert your model instance into its "primitive" equivalent.
>
> This method effectively *downgrades* your model into a
> JSON-serializable dict.
>
> ??? example "Member to Primitive"
>
>     ```python
>     m = Member.transmute('{"name":"Darren","instrument":"drums"}')
>     print(m.primitive())
>     #> {"name": "Darren", "instrument":"drums", "id": None}
>     ```

#### `.tojson(...)`

> Serialize your model instance to JSON
>
> This method will pass on any keyword arguments to the  downstream
> serializer.
>
> !!! note ""
>
>     If [ujson](https://pypi.org/project/ujson/) is installed,
>     this method will default to that library.
>
> ??? example "Member to JSON"
>
>     ```python
>     m = Member.transmute('{"name":"Darren","instrument":"drums"}')
>     print(m.tojson(indent=2))
>     #> {
>     #>   "name": "Darren",
>     #>   "instrument": "drums",
>     #>   "id": null
>     #> }
>     ```
>
> !!! tip
>
>     It's possible to customize your serialized representation. See
>     [SerDes](serdes.md).

#### `.decode(...)`

> Decode on-the-wire data into your Model.
>
> This is useful if you plan to use a wire-format such as Avro, protocol buffers, etc.
>
> To use custom decoders, pass in a callable which takes the input as its first
> argument. All other keyword-arguments are passed on to the decoder function.
>
> ??? example "Decode Binary Data to Member"
>
>     ```python
>     
>     def decode(o: bytes, *, encoding: str = None):
>         # Pretend we're using something other than a basic .decode()...
>         return o.decode(encoding=encoding)
>     
>     @typic.klass(serde=typic.flags(decoder=decode)
>     class Member:
>         name: str
>         instrument: Instrument
>         id: int = None
>     
>     input = '{"name":"Ben","instrument":"piano","id":1}'.encode("utf-8-sig")
>     Member.decode(input, encoding="utf-8-sig")
>     #> Member(name='Ben', instrument=<Instrument.PIAN: 'piano'>, id=1)
>     ```

#### `.encode(...)`

> Encode your Model to a custom wire-format.
>
> This is useful if you plan to use a wire-format such as Avro, protocol buffers, etc.
>
> To use custom encoders, pass in a callable which takes the Model instance as its first
> argument. All other keyword-arguments are passed on to the encoder function.
>
> ??? example "Encode a Member to Binary Data"
>
>     ```python
>     
>     def encode(o: bytes, *, encoding: str = None):
>         # Pretend we're using something other than a basic .encode()...
>         return o.encode(encoding=encoding)
>     
>     @typic.klass(serde=typic.flags(encoder=encode)
>     class Member:
>         name: str
>         instrument: Instrument
>         id: int = None
>     
>     m = Member(name="Ben", instrument="piano", id=1)
>     m.encode()
>     #> b'{"name":"Ben","instrument":"piano","id":1}'
>     ```

#### `.iterate(...)`

> !!! info ""
>
>     New in version 2.4
>
> If compatible, iterate over your model instance's data. This will default to yielding
> (field, value) pairs. You can retrieve just values by passing `values=True`.
>
> The default behavior is also attached as the `__iter__()` magic method for your
> instance.
>
> ??? example "Iterate a Member instance's data"
>
>     ```python
>     
>     m = Member(name="Ben", instrument=Instrument.PIAN, id=1)
>     
>     print([*m.iterate()])
>     #> [('name', 'Ben'), ('instrument', <Instrument.PIAN: 'piano'>), ('id', 1)]
>     
>     print(dict(m.iterate()))
>     #> {'name': 'Ben', 'instrument': <Instrument.PIAN: 'piano'>, 'id': 1}
>     
>     print(dict(m))
>     #> {'name': 'Ben', 'instrument': <Instrument.PIAN: 'piano'>, 'id': 1}
>     
>     print([*m.iterate(values=True)])
>     #> ['Ben', <Instrument.PIAN: 'piano'>, 1]
>     ```


## Which API Should I Use?
The Functional API is the least intrusive way to introduce Typical into your code-base.
It also has the benefit of greater flexibility w.r.t. which types can actually be
supported out-of-the-box.

The Protocol API provides a slight runtime performance boost and the benefit of
explicitly defining, customizing, and using your protocols, but also retains all the
flexibility of the Functional API. In practice, this is probably the best choice for
most situations.

Finally, if you prefer the pattern of containing ser/des logic within the model
definition itself, the Object API is there to fill that void.


## Wrap Up and Next Steps

We've seen the supported high-level APIs and been given a variety of
avenues with which to interact with types in your Python application.
In the next few pages we'll dive deeper on interacting with native
Python types, annotations from the `typing` library, and some extended
types provided by this library. We'll also take a look at how we can
customize the shape of our data on on serialization (such as converting
field names to camelCase, etc.).
