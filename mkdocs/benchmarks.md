# Why Typical?

There are many libaries out there that do some or most of what
Typical can do. Why should you pick Typical out of the pack?
Here's a short list:

1. Simplicity.
    - Typical doesn't require you to learn a new DSL - all
      you need to know is how to use Python's standard
      type-annotations.


2. No Metaclasses.
    - Typical doesn't use metaclasses. We don't infect
      your inheritance. When you wrap a class with
      `@typic.al`, the class you get is the one you
      defined. That's it.

3. Flexibility.
    - Typical works for you and doesn't enforce
      arbitrarily strict rules.
    - Because of an emphasis on simplicity and an aversion
      to inheritance-mangling, you're free to use this
      library as it works for your use-case.

4. Performance.
    - Typical is the fastest pure-Python (no Cython!)
      library out there. Just check out the histograms
      below.


## Benchmarks

The following benchmarks Typical's three public APIs against:

- [Django Rest Framework (DRF)](https://www.django-rest-framework.org/)
- [Marshmallow](https://marshmallow.readthedocs.io/en/stable/)
- [Pydantic](https://pydantic-docs.helpmanual.io/)


### Deserialization & Validation


[![Average time (in μs) for attempted deserialization of
invalid data in a complex, nested
object.][deser-invalid]][deser-invalid]


[![Average time (in μs) for deserializatino of valid data in a
complex, nested object.][deser-valid]][deser-valid]

### Validation Only

[![Average time (in μs) for validation of invalid data in
a complex, nested
object.][validate-invalid]][validate-invalid]


[![Average time (in μs) for validation of valid data in a
complex, nested object.][validate-valid]][validate-valid]

[validate-invalid]: static/Validate_Invalid_Data.svg
[validate-valid]: static/Validate_Valid_Data.svg
[deser-invalid]: static/Deserialize_Invalid_Data.svg
[deser-valid]: static/Deserialize_Valid_Data.svg
