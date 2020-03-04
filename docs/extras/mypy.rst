``typical`` MyPy
================
``typical`` comes packaged with a simple plugin for mypy which will greatly improve
the static type-checking of your ``typic.klass`` objects.

All that's needed is to add ``typic.mypy`` as a plugin in your ``mypy.ini`` like so.
A simple ``mypy.ini`` may look like so:

.. code-block::

    [mypy]
    follow_imports = silent
    plugins = typic.mypy

For more information on MyPy plugins and configuration,
`see their docs <https://mypy.readthedocs.io/en/stable/extending_mypy.html#extending-mypy-using-plugins>`_.
