# Why Typical?

There are many libaries out there that do some or most of what
Typical can do. Why should you pick Typical out of the pack?
Here's a short list:

1. Simplicity.
    - Typical doesn't require you to learn a new DSL - all you need to know is how to
      use Python's standard type-annotations.


2. No Metaclasses.
    - Typical doesn't use metaclasses. We don't infect your inheritance. When you wrap a
      class with `@typic.al`, the class you get is the one you defined. That's it.

3. Flexibility.
    - Typical works for you and doesn't enforce arbitrarily strict rules.
    - Because of an emphasis on simplicity and an aversion to inheritance-mangling,
      you're free to use this library as it works for your use-case.

4. Performance.
    - Typical is the fastest pure-Python (no Cython!) library out there. Just check out
      the histograms below. It achieves this performance with finely-tuned
      code-generation which allows Typical to localize namespaces and minimize branching
      logic.

5. Compliance.
    - Typical is fully-compliant with
      [PEP 563](https://www.python.org/dev/peps/pep-0563/). The entire codebase uses the
      `annotations` future, and this is the recommended mode of operation for all
      consumers of this library,
      *[unlike Pydantic](https://github.com/samuelcolvin/pydantic/issues/2678)*.

## Benchmarks

The following benchmarks Typical's three public APIs against:

- [Django Rest Framework (DRF)](https://www.django-rest-framework.org/)
- [Marshmallow](https://marshmallow.readthedocs.io/en/stable/)
- [Pydantic](https://pydantic-docs.helpmanual.io/)

As can be seen, Typical's three APIs comparable in speed to Pydantic (and in many cases
slightly faster), without the need for Cython as a build-dependency, making it far more
portable.


### Validation Only

[![Average time (in μs) for validation of invalid data in
a complex, nested
object.][validate-invalid]][validate-invalid]

[![Average time (in μs) for validation of valid data in a
complex, nested object.][validate-valid]][validate-valid]


### Deserialization & Validation

[![Average time (in μs) for attempted deserialization of
invalid data in a complex, nested
object.][deser-invalid]][deser-invalid]

[![Average time (in μs) for deserialization of valid data in a
complex, nested object.][deser-valid]][deser-valid]


### Serialization & Validation

*It should be noted that at the time of this writing, both
Pydantic and Marshmallow will passively allow or ignore
invalid data in certain cases by default. This was the
case with the test-case used for these benchmarks, which
can be found
[here](https://github.com/seandstewart/typical/blob/master/benchmark/test_benchmarks.py).*

[![Average time (in μs) for attempted serialization of
invalid data in a complex, nested
object.][ser-invalid]][ser-invalid]

[![Average time (in μs) for serialization of valid data in
a complex, nested object.][ser-valid]][ser-valid]

### Translate *to* an Arbitrary Class

Typical supports automated translation of one known,
custom class to an unknown, unlike other popular
libraries.

[![Average time (in μs) for translation of a known class
to another unknown class a complex, nested
object.][trans-to]][trans-to]


### Translate *from* an Arbitrary Class

Typical also supports translation from an arbitrary class
to a known class. Pydantic supports this feature with the
`from_orm()` method.

[![Average time (in μs) for translation of a known class
to another unknown class a complex, nested
object.][trans-from]][trans-from]


[validate-invalid]: static/Validate_Invalid_Data.svg
[validate-valid]: static/Validate_Valid_Data.svg
[deser-invalid]: static/Deserialize_Invalid_Data.svg
[deser-valid]: static/Deserialize_Valid_Data.svg
[ser-invalid]: static/Serialize_Invalid_Data.svg
[ser-valid]: static/Serialize_Valid_Data.svg
[trans-to]: static/Translate_to_Arbitrary_Class.svg
[trans-from]: static/Translate_from_Arbitrary_Class.svg
