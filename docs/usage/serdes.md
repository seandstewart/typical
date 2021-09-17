# The Ser/Des Protocol
The core of Typical's protocol resolution logic is the `Resolver`. It provides the
central entry-point for our APIs, which allows us to maintain feature symmetry between
the [Object API](api.md#the-object-api), the
[Functional API](api.md#the-functional-api), and the
[The Protocol API](api.md#the-protocol-api). The `Resolver` is responsible for the
following work:

- Resolve the type or annotation to an operational runtime description.
- Generate a protocol for deserialization, translation, and validation of incoming data.
- Generate a protocol for the translation and serialization of outgoing data.

The result of this work is a single `SerdesProtocol` object which understands how to
interact with inputs and outputs which conform to the type annotation it's been given.
The Protocol API exposes this object directly, the Object API binds this protocol to the
type definition, and the Functional API uses this protocol internally.

We won't go over the API of the `SerdesProtocol` again, as it has already been described
in detail in [Using Typical](api.md). Instead, we're going to focus on how you can
customize the protocol to suite your needs.

## Customizing Your Ser/Des Protocol

Typical provides a path for you to customize *how* your data is transmuted into your
custom classes, and how it is dumped back to its primitive form. It all starts with this
factory:

###  `typic.flags`

`case: Optional[typic.common.Case] = None`
> Select the case-style for the input/output fields.

`exclude: Optional[Iterable[str]] = None`
> Provide a set of fields which will be excluded from the output.

`fields: Union[Tuple[str, ...], Mapping[str, str], None] = None`
> Ensure a set of fields are included in the output. If given a mapping, provide a
> mapping to the output field name.

`omit: Optional[Tuple[Union[Type, Any], ...]] = None`
> Provide a tuple of types or values which should be omitted on serialization.

`signature_only: bool = False`
> Restrict the output of serialization to the class signature.

`encoder: Callable[..., bytes] = None`
> Provide a callable which will encode the data to a custom wire format.

`decoder: Callable[..., Any] = None`
> Provide a callable which will decode the data from a custom wire format.

The simplest method for customizing your protocol is via the Protocol API.

??? example "Customizing a dataclass Protocol"

    ```python
    import dataclasses
    import json

    import typic


    def encode(o):
        return json.dumps(o).encode("utf-8-sig")
    
    
    def decode(o):
        return json.loads(o.decode("utf-8-sig"))
    
    
    @dataclasses.dataclass
    class Foo:
        bar: str
        exclude: str = None
    
    
    foo = Foo("bar", "exc")
    flags = typic.flags(fields={"bar": "Bar"}, exclude=("exclude",), decoder=decode, encoder=encode)
    proto = typic.protocol(Foo, flags=flags)
    
    print(proto.primitive(foo))
    #> {'Bar': 'bar'}
    
    print(proto.tojson(foo))
    #> '{"Bar":"bar"}'
    
    print(proto.encode(foo))
    #> b'\xef\xbb\xbf{"Bar": "bar"}'
    
    print(proto.decode(b'\xef\xbb\xbf{"Bar": "bar"}'))
    #> Foo(bar='bar', exclude=None)
    ```

You can also assign the `__serde_flags__` attribute on any class.

??? example "Pinned Customization on Classes"

    ```python
    class Foo:
        __serde_flags__ = typic.flags(fields=("bar", "prop"))
        prop: int
        bar: str = ""
    
        @property
        def prop(self) -> int:
            return 0
    
    proto = typic.protocol(Foo)
    proto.primitive(Foo())
    #> {'prop': 0, 'bar': ''}
    ```

Or even pass in pre-defined flags when creating a protocol for an arbitrary annotation.

??? example "Pre-defined Flags for Arbitrary Protocols"

    ```python
    import typic
    from typing import Mapping
    
    flags = typic.flags(case=typic.Case.CAMEL)
    mapping_proto = typic.protocol(Mapping, flags=flags)
    
    print(mapping_proto.tojson({"foo_bar": 1}))
    #> '{"fooBar":1}'
    ```
