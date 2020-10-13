# Experimental Features

The following page describes typical's experimental features. These are not included in
official releases. In order to use these features, you must install from our git
repository on the branch the features are grouped under.

## v2.1

### Literal Types

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

### Tagged Unions (Polymorphic Types)

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


