# Automated Settings Management

A great use-case for type-coercion is the automatic resolution of
environment variables. Typical has your back with the `typic.settings`
decorator:

## `@typic.settings(...)`

> Create a typed class which sets its defaults from env vars.
>
> The resolution order of values is default(s) -> env value(s) ->
> passed value(s).
>
> Settings instances are indistinguishable from other typical
> dataclasses at run-time and are frozen by default. If you really
> want your settings to be mutable, you may pass in frozen=False
> manually.


### Parameters
prefix: str = ''
> A string which all the target variables with begin with, i.e., APP_

case_sensitive: bool = False
> Whether to respect the case of environment variables.

frozen: bool = True
> Whether the resulting dataclass should be immutable.

aliases: Mapping = None
> A mapping of full-name aliases for the defined attributes.
> {'other_foo': 'foo'} will locate the env var OTHER_FOO and place it
> on the Bar.foo attribute.

!!! info ""

    Environment variables are resolved at compile-time, so updating 
    your env after your typed classes are loaded into the namespace 
    will not work.

    If you are using dotenv based configuration, you should read your 
    dotenv file(s) into the env before initializing the module where 
    your settings are located.

    A structure might look like:

    ```
    my-project/
    -- env/
    ..  -- .env.default
    ..  -- .env.local
    ..      ...
    ..  -- __init__.py  # load your dotenv files here
    ..  -- settings.py  # define your classes
    ```

    This will ensure your dotenv files are loaded into the environment 
    before the Python interpreter parses & compiles your config 
    classes, since the Python parser parses the init file before 
    parsing anything else under the directory.

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
