# Working with Types

Typical is *Python's Typing Toolkit*. Below we'll walk you through what that means.

## Postponed Annotations

Typical natively supports type annotations defined with forward references for all
interfaces. This support is automatic and requires no additional configuration:

```python
import typic


@typic.klass
class A:
    b: "B"


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
import typic
import dataclasses
from typing import Optional


@dataclasses.dataclass
class Node:
    pos: int
    child: Optional["Node"] = None


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
import typic
from typing import Optional


@typic.klass
class A:
    b: Optional["B"] = None


@typic.klass
class B:
    a: Optional["A"] = None


a = A.transmute({"b": {"a": {}}})
print(a)
#> A(b=B(a=A(b=None)))

print(a.tojson())
#> {"b":{"a":{"b":null}}}
```


## The Standard Library

Typical is built upon the standard `typing` library. Virtually any
valid static type may be reflected and managed by Typical. Just
follow the rules defined by
[PEP 484](https://www.python.org/dev/peps/pep-0484/) and you're good
to go!

!!! important "Handling Unions"

    `Union` types will not be proactively transmuted to a type within 
     union's definition. This is because the resolution of a Union
     is inherently unclear. In such cases, you may define a
     [custom converter]() for handling your union-type.
    
    The major exception to this rule is `Optional`/`Union[..., None]`. 
    This is a defined use-case for union-types which as a clear 
    resolution.

Beyond classes, standard types, and the annotation syntax provided by
the `typing` library, Typical also natively supports extended types
defined in the following standard modules & bases:

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

The public interface for constraining types is the
`@typic.constrained` decorator. Specific keywords are defined by the
type which is being constrained.

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
