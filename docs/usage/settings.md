# Automated Settings Management

A great use-case for type-coercion is the automatic resolution of
environment variables. Typical has your back with the `typic.settings`
decorator:

## `typic.environ`

> A proxy for `os.environ` which facilitates geting/setting of strongly-typed data.

### `typic.environ.getenv(...)`
> Fetch the value assigned to the given variable.

#### Parameters
var: str
> The environment variable to lookup.

t: Type = Any
> An optional type to coerce the value at `var`.

ci: bool = True
> Whether the environment variable should be considered case-insensitive.


### `typic.environ.setenv(...)`
> Set a value at the target variable.

#### Parameters
var: str
> The environment variable to set.

value: Any
> The value to set at the given variable.


### `typic.register(...)`
> Registers a handler for resolving variables with type `t`.

#### Parameters
t: Type
> The target type to create and register a handler for.

name: str = None
> An optional name to register the handler with.


### Usage

??? example "Fetching & Setting Values"

```python
import typic

typic.environ.setenv("USE_FOO", True)

use_foo = typic.environ.getenv("use_foo", t=bool)
print(use_foo)
#> True
```

??? example "Using a Type Handler"

`typic.environ` ships with handlers for all native types and typical's own extended
types.

```python
import typic

typic.environ.setenv("USE_FOO", True)

print(typic.environ.bool("use_foo"))
#> True

print(typic.environ.str("use_foo"))
#> true

print(typic.environ.int("use_foo"))
#> 1

typic.environ.setenv("DATABASE_URL", "postgres://localhost:5432/db")

dsn = typic.environ.DSN("DATABASE_URL")

print(dsn)
#> postgres://localhost:5432/db

print(dsn.info)
#> DSNInfo(driver='postgres', username='', password=, host='localhost', port=5432, name='/db', qs='', is_ip=False)
```

??? example "Register a Custom Handler"

```python
import dataclasses

import typic


@dataclasses.dataclass
class Foo:
    bar: str = None


typic.register(Foo)
typic.environ.setenv("THIS_FOO", Foo())

print(typic.environ.Foo("THIS_FOO"))
#> Foo(bar=None)

```


## `@typic.settings(...)`

> Create a typed class which sets its defaults from env vars.
>
> The resolution order of values is default(s) -> env value(s) -> passed value(s).
>
> Settings instances are indistinguishable from other typical dataclasses at run-time
> and are frozen by default. If you really want your settings to be mutable, you may
> pass in frozen=False manually.


### Parameters
prefix: str = ''
> A string which all the target variables with begin with, i.e., 'APP_'

case_sensitive: bool = False
> Whether to respect the case of environment variables.

frozen: bool = True
> Whether the resulting dataclass should be immutable.

aliases: Mapping = None
> A mapping of full-name aliases for the defined attributes.
> {'other_foo': 'foo'} will locate the env var OTHER_FOO and place it
> on the Bar.foo attribute.

!!! info ""

    Environment Variables for settings classes are resolved via `typic.environ` getters,
    which are set as default factories.

    If your class has defaults assigned, we will not try to resolve via the environment.

    If you pass in a value for a given attribute, that will override any default.

??? example "Using Settings"

    ```python
    import os
    import typic

    os.environ['FOO'] = "1"

    @typic.settings
    class Bar:
        foo: int


    print(Bar())
    #> Bar(foo=1)

    print(Bar("3"))
    #> Bar(foo=3)

    bar = Bar()
    bar.foo = 2
    #> Traceback (most recent call last):
    #>   ...
    #> dataclasses.FrozenInstanceError: cannot assign to field 'foo'
    ```

!!! warning ""

    When the final dataclass is generated, all matching environment
    variables will be resolved as default values for the matching
    attribute (or a default factory in the case of a mutable default).

    When the class itself is initialized, values passed in will
    override variables provided in your environment.
