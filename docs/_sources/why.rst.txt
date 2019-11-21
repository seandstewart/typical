Why ``typical``?
================
There are many libaries out there that do some or most of what ``typical`` can do. Why
should you pick ``typical`` out of the pack? Here's a short list:

#. Simplicity.
    - ``typical`` doesn't require you to learn to learn a new DSL - all you need to
      know is how to use Python's type-annotations.


#. Flexibility.
    - ``typical`` works for you and doesn't enforce arbitrarily strict rules.


#. No Metaclasses.
    - ``typical`` doesn't use metaclasses. We don't infect your inheritance. When you
      wrap a class with ``@typic.al``, the class you get is the one you defined. That's
      it.


#. Performance.
    - ``typical`` is the fastest pure-Python (no Cython!) library out there. Just check
      out the histogram below:


.. figure:: _static/benchmark_20191106_223028-Invalid_Data.svg
    :target: _static/benchmark_20191106_223028-Invalid_Data.svg
    :alt: Click to expand and interact!

    Average time (in us) for validation and attempted initialization of invalid data in a
    complex, nested object.


.. figure:: _static/benchmark_20191106_223028-Valid_Data.svg
    :target: _static/benchmark_20191106_223028-Invalid_Data.svg
    :alt: Click to expand and interact!

    Average time (in us) for validation and initialization of invalid data in a
    complex, nested object.
