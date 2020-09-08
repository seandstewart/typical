# External Integrations

## MyPy

Typical comes packaged with a simple plugin for mypy which will
greatly improve the static type-checking of your `typic.klass`
objects.

All that’s needed is to add `typic.mypy` as a plugin in your
`mypy.ini` like so. A simple `mypy.ini` may look like so:

```ini
[mypy]
follow_imports = silent
plugins = typic.mypy
```

For more information on MyPy plugins and configuration,
[see their docs](https://mypy.readthedocs.io/en/stable/extending_mypy.html#extending-mypy-using-plugins).

## Pycharm Plugin

A basic, functional plugin is currently available. It is not hosted on
the Marketplace quite yet, as it is missing a few key features, but it
provides auto-completion for your model's parameters and type
introspection of the parameter's annotations.

The repository can be found
[here](https://github.com/seandstewart/typical-pycharm-plugin).
