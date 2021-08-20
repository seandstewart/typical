# Working with Types

Typical is *Python's Typing Toolkit*. Below we'll walk you through what that means.

## Postponed Annotations

Typical natively supports type annotations defined with forward references for all
interfaces. This support is automatic and requires no additional configuration:

```python
from __future__ import annotations

import typic


@typic.klass
class A:
    b: B


@typic.klass
class B:
    c: int


print(A.transmute({"b": {"c": "1"}}))
#> A(b=B(c=1))
```

!!! warning "Gotcha!"

    The type you reference *must* be available within the global namespace of the 
    enclosing object. Otherwise, the reference will be treated as an anonymous type
    and not be proactively transmuted.


### Self-referencing (Recursive) Types

As a side-effect of our support for postponed annotations, Typical also supports
self-referential (recursive) types:

```python
from __future__ import annotations

import typic
import dataclasses
from typing import Optional


@dataclasses.dataclass
class Node:
    pos: int
    child: Optional[Node] = None


n = typic.transmute(Node, {"pos": 0, "child": {"pos": 1}})
print(n)
#> Node(pos=0, child=Node(pos=1, child=None))

print(typic.tojson(n))
#> {"pos":0,"child":{"pos":1,"child":null}}
```


### Circular Dependencies

As another side-effect of postponed annotation support, Typical also handles types which
have circular dependencies upon each other:

```python
from __future__ import annotations

import typic
from typing import Optional


@typic.klass
class A:
    b: Optional[B] = None


@typic.klass
class B:
    a: Optional[A] = None


a = A.transmute({"b": {"a": {}}})
print(a)
#> A(b=B(a=A(b=None)))

print(a.tojson())
#> {"b":{"a":{"b":null}}}
```

!!! note "About those \_\_future__ imports"

    [PEP 563](https://www.python.org/dev/peps/pep-0563) introduced a new methodology for
    the analysis of annotations at runtime which treats all annotations as strings 
    until the runtime types are explicitly fetched. This greatly simplifies the 
    development overhead for type resolution and also removes the need for wrapping
    annotations referencing potentially undefined or recursive types in quotes `""`. 
    
    *You're __highly encouraged__ to adopt this import in your Python3.7-8 code. Starting 
    with __Python 3.9__, it is the default behavior.*


## The Standard Library

Typical is built upon the standard `typing` library. Virtually any valid static type may
be reflected and managed by Typical. Just follow the rules defined by
[PEP 484](https://www.python.org/dev/peps/pep-0484/) and you're good to go!

!!! important "Primitive Unions"

    `Union` types will not be proactively transmuted to a type within 
     union's definition. This is because the resolution of a Union
     is inherently unclear. In such cases, you may define a
     [custom converter]() for handling your union-type.
    
    The major exception to this rule is `Optional`/`Union[..., None]`. 
    This is a defined use-case for union-types which as a clear 
    resolution.

!!! important "Tagged Unions"

    Tagged Unions, i.e., Polymorphic or Discriminated Types, are now supported as an
    experimental feature. See our docs on [Experimental Features](experimental.md) for 
    more.

Beyond classes, standard types, and the annotation syntax provided by the `typing`
library, Typical also natively supports extended types defined in the following standard
modules & bases:

- [datetime](https://docs.python.org/3.9/library/datetime.html)

    !!! note ""

        By nature of how we convert string literals to date objects, we
        also natively support date objects provided by
        [pendulum](https://pendulum.eustace.io).

- [decimal](https://docs.python.org/3/library/decimal.html)
- [ipaddress](https://docs.python.org/3/library/ipaddress.html)
- [defaultdict](https://docs.python.org/3/library/collections.html#collections.defaultdict)
- [typing.NamedTuple](https://docs.python.org/3/library/typing.html#typing.NamedTuple)
- [typing.TypedDict](https://docs.python.org/3/library/typing.html#typing.TypedDict)
- [typing.NewType](https://docs.python.org/3/library/typing.html#typing.NewType)
- [typing.DefaultDict](https://docs.python.org/3/library/typing.html?highlight=defaultdict#typing.DefaultDict)

    !!! note ""

        We will use the subscripted value type to attempt to determine a factory
        for your defaultdict. If one can't be determined, or the value type
        requires additional parameters upon initialization, the default value
        will be `None`.

Additionally, we maintain mapping of typing/collection
ABCs to actionable runtime type:

| ABC                    | Builtin |
|:-----------------------|:--------|
| typing.Mapping         | dict    |
| typing.MutableMapping  | dict    |
| typing.Collection      | list    |
| typing.Iterable        | list    |
| typing.Sequence        | list    |
| typing.MutableSequence | list    |
| typing.AbstractSet     | set     |
| typing.MutableSet      | set     |
| typing.Hashable        | str     |

## Literal Types

!!! info ""

    New in version 2.1

typical supports validation of Literal types, as described in
[PEP 586](https://www.python.org/dev/peps/pep-0586/).

Literals are a bit like Unions and Enums had a love child, meaning that they may be
subscripted with a series of inputs that are considered "valid". Unlike Unions and like
Enums, Literals declare specific primitive values (i.e., builtins). Valid annotations
include:

```python
from typic.compat import Literal

Literal[1]
Literal[1, None]
Literal[1, "foo", b'bar']
...
```

An interesting side-effect of their similarity is that a Literal of the form
`Literal[..., None]` is equivalent to `Optional[Literal[...]]`

For an exhaustive explanation, see the PEP linked above.

For typical, this means we can resolve a deserializer with behavior similar to Enums and
Unions.

```python
import typic
from typic.compat import Literal

Literally1 = Literal[1]

print(typic.transmute(Literally1, b"1"))
#> 1

LessThan4 = Literal[0, 1, 2, 3]
print(typic.transmute(LessThan4, b"1"))
#> 1
```

Literals provide a means of runtime validation as well:

```python
typic.transmute(LessThan4, 5)
#> Traceback (most recent call last):
#>   ...
#> typic.constraints.error.ConstraintValueError: Given value <5> fails constraints: (type=Literal, values=(0, 1, 2, 3), nullable=False)
```

If the Literal has values of multiple types, we treat it as a Union type and cannot
proactively deserialize the input, but we can still validate against the constraint:

```python
SuperImportantValues = Literal[1, "foo"]

typic.transmute(SuperImportantValues, b"foo")
#> Traceback (most recent call last):
#>   ...
#> typic.constraints.error.ConstraintValueError: Given value <b'foo'> fails constraints: (type=Literal, values=(1, 'foo'), nullable=False)
```


## Unions (Polymorphic Types)

!!! warning ""

    :dragon: Here be dragons :dragon: 

### Tagged Unions

!!! info ""

    New in version 2.1


typical supports Tagged Unions, as described in
[Mypy's documentation](https://mypy.readthedocs.io/en/stable/literal_types.html#tagged-unions).

In a strongly-typed container, such as a TypedDict or NamedTuple, or a more standard
class, this means if a field is annotated with a constant value, it can be considered a
"tag" or "discriminator" when analyzed within a Union.

typical currently supports annotating your tag using ClassVars or Literals.

Expanding on our example from the [API Docs](api.md):

```python
from __future__ import annotations

import enum
import dataclasses
from typing import ClassVar, Iterable, Optional, Union

import typic


class Instrument(str, enum.Enum):
    """The only instruments a band really needs, duh."""
    
    GUIT = "guitar"
    BASS = "bass"
    PIAN = "piano"
    DRUM = "drums"


@dataclasses.dataclass
class BaseMember:
    """A member in the band, man."""

    instrument: ClassVar[Instrument]
    name: str
    id: Optional[int] = None
    
    @property
    def _catch_phrase(self) -> str:
        return "played"

    def play(self) -> str:
        return f"{self.name} {self._catch_phrase} the {self.instrument.value}!"


class Drummer(BaseMember):
    """It all about those sick beats."""
    instrument = Instrument.DRUM


class BassPlayer(BaseMember):
    """Slappin out that rhythm."""
    instrument = Instrument.BASS
    
    @property
    def _catch_phrase(self) -> str:
        return "slapped"


class GuitarPlayer(BaseMember):
    """Shred it."""
    instrument = Instrument.GUIT


class PianoPlayer(BaseMember):
    """Let's face it, I'm the true genius."""
    instrument = Instrument.PIAN


BandMemberT = Union[Drummer, BassPlayer, GuitarPlayer, PianoPlayer]



@dataclasses.dataclass
class Band:
    """It's the band, man."""

    name: str
    members: Iterable[BandMemberT]
    id: Optional[int] = None


@dataclasses.dataclass
class Song:
    """A sick tune - platinum fer sure."""

    name: str
    lyrics: str
    band: Band
    id: Optional[int] = None

```

Now that we're able to use polymorphism for our Band member types, we can take advantage
of those sick OOP patterns we all love, such as defining a base interface and
overloading methods on child classes. And with typical, you get your deserialization for
free!

```python
member_proto = typic.protocol(BandMemberT)

member = member_proto.transmute({"instrument": "bass", "name": "Robert"})
print(member.play())
#> Robert slapped the bass!
```

???+ warning "Gotcha!"

    When combining postponed annotations with polymorphic types, you're *highly 
    encouraged* to add `from __future__ import annotations` to the top of your module. 
    
    If you don't like that pattern, then you should wrap the **entire annotation** in 
    quotes, rather than the single recursive or circular type in the Union.

    **Preferred**:
    ```python
    from __future__ import annotations
    
    from typing import Union
    
    import typic
    from typic.compat import Literal
    
    @typic.klass
    class ABlah:
        key: Literal[3]
        field: Union[AFoo, ABar, ABlah, None]
    
    
    @typic.klass
    class AFoo:
        key: Literal[1]
        field: str
    
    
    @typic.klass
    class ABar:
        key: Literal[2]
        field: bytes
    ```

    **OK**:
    ```python    
    from typing import Union
    
    import typic
    from typic.compat import Literal
    
    @typic.klass
    class ABlah:
        key: Literal[3]
        field: "Union[AFoo, ABar, ABlah, None]"
    
    
    @typic.klass
    class AFoo:
        key: Literal[1]
        field: str
    
    
    @typic.klass
    class ABar:
        key: Literal[2]
        field: bytes
    ```

    **WRONG**:
    ```python    
    from typing import Union
    
    import typic
    from typic.compat import Literal
    
    @typic.klass
    class ABlah:
        key: Literal[3]
        field: Union[AFoo, ABar, "ABlah", None]
    
    
    @typic.klass
    class AFoo:
        key: Literal[1]
        field: str
    
    
    @typic.klass
    class ABar:
        key: Literal[2]
        field: bytes
    ```

### Generic Unions

While you're *highly encouraged* to make use of [Tagged Unions](#tagged-unions) for your
polymorphic types, typical can generate a deserilization protocol for generic unions as
well. This is intended for use when it's simply not possible to define a discriminator
for your union.

!!! info ""

    New in version 2.6

!!! warning ""

    Tagged Union deserialization is O(1) where N is the number of target types. Generic
    Unions are 0(N). Keep this in mind when defining your types - you may be better-served
    by re-working your data model.

When defining your Generic Union, you're encouraged to order your types from *most*
specific to *least*. As a part of the implementation, we treat the possible types as
FIFO queue, taking a type from the top of the stack and attempting deserialization. If
all attempt at deserialization fail, we raise a `ValueError`.

??? example "Working with Generic Unions"

    **Wrong:**
    
    ```python
    from __future__ import annotations
    
    from typing import Union
    
    import typic
    
    
    # `str` should never be first! Everything can be a string...
    proto = typic.protocol(Union[str, int])
    print(type(proto.transmute("1")))
    #> <class 'str'>
    
    ```
    
    **Right:**
    
    ```python
    from __future__ import annotations
    
    from typing import Union
    
    import typic
    
    proto = typic.protocol(Union[int, str])
    print(type(proto.transmute("1")))
    #> <class 'int'>
    ```

!!! error "Gotcha!"

    In static typing, `Union[str, int]` and `Union[int, str]` are identical. For Python,
    this means they have the same hash value, which in turn breaks typical's caching 
    mechanism. *Tread carefully when defining your types and always ensure you define 
    your union from* most *to* least *strict.*


## Constraining Builtin Types
Typical provides a path for defining "constrained" types based upon
Python builtins. This gives you a means to express limited types in a
declarative manner. There is some overlap between constrained types
and JSON Schema - this is intentional. However, Typical's
constraints are built with Python types in mind, so there are small,
but important differences between the two implementations.

!!! note

    It should be noted that Typical's constraint syntax is the means 
    by which we generate JSON Schema definitions.

The public interface for constraining types is the `@typic.constrained` decorator.
Specific keywords are defined by the type which is being constrained.

### The Constraints API

It all starts with a single decorator:

#### `@typic.constrained(...)`

> Create a "constrained" subclass of a Python builtin type.
>
> !!! fail "Prohibited"
>
>     Attempting to constrain a type not explicitly listed below will 
>     result in a `TypeError`.
>
> ??? example "An ID Class"
>
>     ```python
>     import typic
>     
>     @typic.constrained(ge=1)
>     class ID(int):
>         """An integer which must be >= 1"""
>     
>     ID(1)
>     #> 1
>     
>     ID(0)
>     #> Traceback (most recent call last):
>     #>  ...
>     #> typic.constraints.error.ConstraintValueError: Given value <0> fails constraints: (type=int, nullable=False, coerce=False, ge=1)
>     ```




#### Numbers

The following builtin types are currently supported by the numeric
constraints system:

- `int`
- `float`
- `decimal.Decimal`

Number constraints all have share these parameters:

`gt: Optional[Number] = None`
> The value inputs must be greater-than.

`ge: Optional[Number] = None`
> The value inputs must be greater-than-or-equal-to.

`lt: Optional[Number] = None`
> The value inputs must be less-than.

`le: Optional[Number] = None`
> The value inputs must be less-than-or-equal-to.

`mul: Optional[Number] = None`
> The value inputs must be a multiple-of.

Additionally, you may define the following constraints for subclasses
of `Decimal`:

`max_digits: Optional[int] = None`
> The maximum allowed digits for the input.

`decimal_places: Optional[int] = None`
> The maximum allowed decimal places for the input.

!!! fail "Gotcha"

    Numbers may *not* define conflicting constraints (e.g., `>` & `>=`).
    Rather than deal with this silently, we will raise a 
    [ConstraintSyntaxError](#errors).


#### Text

The following builtins are currently supported by the textual
constraints system:

- `str`
- `bytes`

Text constraints all share the following parameters:

`strip_whitespace: Optional[bool] = None`
> Whether to strip any whitespace from the input.
>
> !!! warning "Callers Beware"
>
>     This will result in mutation of the provided input.

`min_length: Optional[int] = None`
> The minimun length this input text must be.

`max_length: Optional[int] = None`
> The maximum length this input text may be.

`curtail_length: Optional[int] = None`
> Whether to cut off characters after the defined length.
>
> !!! warning "Callers Beware"
>
>     This will result in mutation of the provided input.

`regex: Optional[Pattern[Text]] = None`
> A regex pattern which the input must match.


#### Arrays

The following builtins are currently supported but the array
constraints system:

- `list`
- `tuple`
- `set`
- `frozenset`

Array constraints share the following parameters:

`min_items: Optional[int] = None`
> The minimum number of items which must be present in the array.

`max_items: Optional[int] = None`
> The maximum number of items which may be present in the array.

`unique: Optional[bool] = None`
> Whether this array should only have unique items.
>
> !!! warning "Callers Beware"
>
>     This will result in mutation of the provided input.

`values: Optional["ConstraintsT"] = None`
> The constraints for which the items in the array must adhere.
>
> This can be a single type-constraint, or a tuple of multiple
> constraints.

!!! note

    `set` & `frozenset` constraints default `unique=True`. This makes
    sense, as they are unique by nature.

#### Mappings

The mapping constraint system currently only supports `dict`.

`min_items: Optional[int] = None`
> The minimum number of items which must be present in this mapping.

`max_items: Optional[int] = None`
> The maximum number of items which may be present in this mapping.

`required_keys: FrozenSet[str] = dataclasses.field(default_factory=frozenset)`
> A frozenset of keys which must be present in the mapping.

`key_pattern: Optional[Pattern] = None`
> A regex pattern for which all keys must match.

`items: Optional[FrozenDict[Hashable, "ConstraintsT"]] = None`
> A mapping of constraints associated to specific keys.

`patterns: Optional[FrozenDict[Pattern, "ConstraintsT"]] = None`
> A mapping of constraints associated to any key which match the regex
> pattern.

`values: Optional["ConstraintsT"] = None`
> Whether values not defined as required are allowed
>
> May be a boolean, or more constraints which are applied to all
> additional values.

`keys: Optional["ConstraintsT"] = None`
> Constraints to apply to any additional keys not explicitly defined.

`key_dependencies: Optional[FrozenDict[str, KeyDependency]] = None`
> A mapping of keys and their dependent restrictions if they are
> present.
>
> A 'key dependency' defines constraints which are applied *only* if a
> key is present.
>
> This can be either a tuple of dependent keys, or an additional
> mapping constraints, which is treated as a sub-schema to the parent
> constraints.

`total: Optional[bool] = False`
> Whether to consider this schema as the 'total' representation
>
> !!! fail "Beware"
>
>     If a mapping is `total=True`, no additional keys/values are
>     allowed and cannot be defined.
>     
>     Conversely, if a mapping is `total=False`, `required_keys` cannot
>     not be defined.
>

!!! tip ""

    The Constraints system is based largely upon JSON Schema, and 
    those familiar with the specification have likely already noted 
    the many similarities.
    
    This system has been customized for the Python-specific 
    type topology, so there are some subtle, but important, 
    differences between the two.
    
    In the case of mapping constraints, you're encouraged to
    familiarize yourself with the
    [JSON Schema: Object](https://json-schema.org/understanding-json-schema/reference/object.html)
    documentation, as the more advanced (and unwieldy) pieces such as 
    key-dependencies are derived from there.
    
    *In general, if your mapping constraints get too complex, you're 
    encouraged to make use of legitimate classes or `TypedDict`.*


#### Errors

The Constraints API has defined the following errors:

`ConstraintValueError(ValueError)`
> A generic error indicating a value violates a constraint.
>
> The error message will provide the value provided and the
> constraints which were violated.

`ConstraintSyntaxError(SyntaxError)`
> A generic error indicating an improperly defined constraint.
>
> This will be raised at compile-time, not as a surprise during
> run-time.

## Extended Types

Typical also ships with a library of extended types to make your
daily work a breeze:

## Networking

All networking types are subclasses of `str`, so are natively
JSON-serializable. They provide an `info` attribute which itself
provides accessors to useful information regarding the specific type.

All network addresses are immutable and no attributes may be set or
removed.

### `.info` Property

Unless otherwise specified, the `info` attribute will contain an
instance of `NetAddrInfo` with the following attributes, propertes,
and methods:

`scheme: str`
> The net-address scheme, e.g., `http`, `tcp`, `ssh`, etc.

`auth: str`
> The user auth info.

`password: SecretStr`
> The user's password.

`host: str`
> The host for this address, e.g. `0.0.0.0`, `foobar.net`.

`port: int`
> The port for this net-address

`path: str`
> The URI path.

`qs: str`
> The query-string, unparsed, e.g. `?id=1&name=foo`

`params: str`
> The url parameters, unparsed, e.g. `id=2;foo=bar`

`fragment: str`
> The uri fragment, e.g. `#some-page-anchor`

`base: str`
> The 'base' of the URL, including scheme, auth, and host.

`relative: str`
> The 'relative' portion of the URL: path, params, query, and fragment.

`address: str`
> The fully-qualified network address.
>
> If this instance was generated from a string, it will match.

`address_encoded: str`
> The fully-qualified network address, encoded.

`query: Mapping[str, List[str]]:`
> The query-string, parsed into a mapping of key -> \[values, ...].

`parameters: Mapping[str, List[str]]:`
> The params, parsed into a mapping of key -> \[values, ...].

`is_default_port: bool`
> Whether address is using the default port assigned to the given scheme.

`is_relative: bool`
> Whether address is 'relative' (i.e., whether a scheme is provided).

`is_absolute: bool`
> The opposite of `is_relative`.

`is_private: bool`
> Whether or not the URL is using a 'private' host, i.e., 'localhost'.

`is_internal: bool`
> Whether the host provided is an 'internal' host.
>
> This may or may not be private, hence the distinction.

### `NetworkAddress(str)`
> This is the base class for all Networking types. It's fully
> functional and may be used on its own if desired, but the inheritors
> defined below provide their own advanced features and are much more
> useful at runtime.
>
> ??? example "Working with a NetworkAddress"
>
>     ```python
>     
>     import typic
>     
>     net_addr = typic.NetworkAddress("http://foo.bar/bazz;foo=bar?buzz=1#loc")
>     print(net_addr)
>     #> 'http://foo.bar/bazz;foo=bar?buzz=1#loc'
>     
>     print(net_addr.info.is_absolute)
>     #> True
>     
>     print(net_addr.info.host)
>     #> 'foo.bar'
>     
>     print(net_addr.info.scheme)
>     #> 'http'
>     
>     print(net_addr.info.address_encoded)
>     #> 'http%3A//foo.bar/bazz%3Bfoo%3Dbar%3Fbuzz%3D1%23loc'
>     
>     print(net_addr.info.query)
>     #> mappingproxy({'buzz': ['1']})
>     
>     print(net_addr.info.parameters)
>     #> mappingproxy({'foo': ['bar']})
>     
>     print(net_addr.info.fragment)
>     #> 'loc'
>     
>     domain = typic.NetworkAddress("foo.bar")
>     print(domain)
>     #> 'foo.bar'
>     
>     print(domain.info.is_relative)
>     #> True
>     
>     print(domain.info.host)
>     #> 'foo.bar'
>     
>     print(net_addr)
>     #> 'http://foo.bar/bazz;foo=bar?buzz=1#loc'
>     
>     print(typic.tojson([net_addr]))
>     #> '["http://foo.bar/bazz;foo=bar?buzz=1#loc"]'
>     ```

### `URL(NetworkAddress)`
> A URL is a Network Address which may be "joined" with additional
> paths, similar to the implementation in
> [pathlib](https://docs.python.org/3/library/pathlib.html)
>
> ??? example "Working with URLs"
>
>     ```python
>     import typic
>     
>     url = typic.URL("http://foo.bar/bazz")
>     print(url)
>     #> 'http://foo.bar/bazz'
>     
>     more = url / 'foo' / 'bar'
>     print(more)
>     #> 'http://foo.bar/bazz/foo/bar'
>     
>     print(typic.URL(url.info.base) / 'other')
>     #> 'http://foo.bar/other'
>     ```

### `AbsoluteURL(URL)`
> An *AbsoluteURL* is a URL which *must* have a `scheme` and `host`.
>
> ??? example "Working with AbsoluteURLs"
>
>     ```python
>     import typic
>     
>     pep484 = typic.AbsoluteURL("https://www.python.org/dev/peps/pep-0484/")
>     print(pep484)
>     #> https://www.python.org/dev/peps/pep-0484/
>     
>     typic.AbsoluteURL("/dev/peps/pep-0484/")
>     #> Traceback (most recent call last):
>     #>   ...
>     #> typic.types.url.AbsoluteURLValueError: <'/foo'> is not an absolute URL.
>     ```

### `RelativeURL(URL)`
> A *RelativeURL* is a URL which *must not* have a `scheme` and
> `host`.
>
> ??? example "Working with RelativeURLs"
>
>     ```python
>     import typic
>     
>     pep484 = typic.RelativeURL("/dev/peps/pep-0484/")
>     print(pep484)
>     #> /dev/peps/pep-0484/
>     
>     typic.RelativeURL("https://www.python.org/dev/peps/pep-0484/")
>     #> Traceback (most recent call last):
>     #>   ...
>     #> typic.types.url.RelativeURLValueError: <'https://www.python.org/dev/peps/pep-0484/'> is not a relative URL.
>     ```


### `HostName(URL)`
> A *HostName* is a URL which *must only* have a `host`.
>
> ??? example "Working with RelativeURLs"
>
>     ```python
>     import typic
>     
>     python = typic.HostName("www.python.org")
>     print(python)
>     #> www.python.org
>     
>     typic.HostName("https://www.python.org/dev/peps/pep-0484/")
>     #> Traceback (most recent call last):
>     #>   ...
>     #> typic.types.url.HostNameValueError: <'https://www.python.org/dev/peps/pep-0484/'> is not a hostname.
>     ```

!!! note

    The following network address types have their own `info` 
    implementations and validation.

### `DSN(NetworkAddress)`
> A D(ata)S(ource)N(ame) string. This is essentially a URL, but the
> api is already well-defined with different attributes than a
> standard URL.
>
> ??? example "Working with DSNs"
>
>     ```python
>     
>     import typic
>     dsn = typic.DSN("postgresql://user:secret@localhost:5432/mydb")
>     print(dsn)
>     #> 'postgresql://user:secret@localhost:5432/mydb'
>     print(dsn.info.host)
>     #> 'localhost'
>     print(dsn.info.is_private)
>     #> True
>     print(dsn.info.is_default_port)
>     #> True
>     print(dsn.info.username)
>     #> 'user'
>     print(dsn.info.password)   # This has been converted to a secret :)
>     #> ******
>     print(dsn.info.name)
>     #> '/mydb'
>     print(dsn.info.driver)
>     #> 'postgresql'
>     print(typic.tojson([dsn]))
>     #> '["postgresql://user:secret@localhost:5432/mydb"]'
>     ```

### `Email(NetworkAddress)`
> We all know what an Email is!
>
> ??? example "Working with Emails"
>
>     ```python
>     import typic
>     
>     email = typic.Email("Foo Bar <foo.bar@foobar.net>")
>     print(email)
>     #> Foo Bar <foo.bar@foobar.net>
>     print(email.info.host)
>     #> foobar.net
>     email.info.is_named
>     #> True
>     typic.tojson([email])
>     #> '["Foo Bar <foo.bar@foobar.net>"]'
>     ```

## Paths
Typical provides two subclasses of
[`pathlib.Path`](https://docs.python.org/3/library/pathlib.html):

1. `FilePath`
    - A Path object which must point to a file.
2. `DirectoryPath`
    - A Path object which must point ot a directory.

!!! important ""

    Due to the implementation of Paths, these subclasses require that 
    a path exists in order for the validation to be successful.

## Miscellaneous

### FrozenDict
> A hashable, immutable dictionary. This inherits directly from
> Python's `dict` builtin and is natively JSON serializable.
>
> ??? example "Working with FrozenDict"
>
>     ```python
> 
>     import typic
>     
>     fdict = typic.FrozenDict({"foo": ["bar"]})
>     typic.ishashable(fdict)
>     #> True
>     
>     fdict["foo"]
>     #> ('bar',)
>     
>     new = fdict.mutate({"bazz": "buzz"}, bazz="blah")
>     print(new)
>     #> {'foo': ('bar',), 'bazz': 'blah'}
>     
>     fdict.update(foo=["car"])
>     #> Traceback (most recent call last):
>     #> ...
>     #> TypeError: attempting to mutate immutable type 'FrozenDict'
>     
>     del fdict["foo"]
>     #> Traceback (most recent call last):
>     #> ...
>     #> TypeError: attempting to mutate immutable type 'FrozenDict'
>     
>     fdict.pop("foo")
>     #> Traceback (most recent call last):
>     #> ...
>     #> TypeError: attempting to mutate immutable type 'FrozenDict'
>     
>     fdict.clear()
>     #> Traceback (most recent call last):
>     #> ...
>     #> TypeError: attempting to mutate immutable type 'FrozenDict'
>     ```

### SecretStr & SecretBytes
> A subclass of `str` (or `bytes`, respectively) which masks its value
> on repr. Secrets can be accessed with the `.value` attribute.
>
> ??? example "Working with Secrets"
>
>     ```python
>     import typic
>     
>     mysecret = typic.SecretStr("The Ring is in Frodo's pocket.")
>     print(mysecret)
>     #> ******************************
>     
>     print(mysecret.secret)
>     #> The Ring is in Frodo's pocket.
>     
>     print(f"{mysecret}")
>     #> '******************************'
>     
>     typic.tojson([mysecret])
>     #> '["The Ring is in Frodo\\'s pocket."]'
>     ```
