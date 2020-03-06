**v2.0.0b20**
Bugfixes:
- Fix regression when transmuting booleans.

Improvements:
- More informative error messaging for Contraints.
- Parametrizing symbols for Contraints code-gen.
- Add high-level `typic.validate` to public API. 
  [Docs](https://python-typical.org/usage/advanced#helpers)

**v2.0.0b19**  
Features:
- MyPy support. [See the docs](https://python-typical.org/extras/mypy) for more
  information.

**v2.0.0b17**  
Bugfixes:
- Fix handling of datetime subclasses.
- Use `transmute` internally instead of `coerce`
- Add `py.typed` to help mypy out.

**v2.0.0b16**  
Optimizations:
- api.py: Wrapper for typed classes now produces faster setattr method
- api.py: Delayed typed classes are now slightly slower on init, but
  still within an optimal range.
- resolver.py: Fix checks for `Resolver.seen`
- des.py: Use `Annotation.resolved` when checking if class has been
  "seen"
- des.py: Use cached subclass check in lieu of instance check.

Extras:
- Add `validate` method to wrapped classes.

**v2.0.0b15**  
Bugfixes:
- Fix issue resolving serializer for Enums which are
  ClassVars/ReadOnly.

**v2.0.0b14**  
Features:
- Introducing `SerdeProtocol` for fast, dynamic serialization &
  deserialization. See [the docs](https://python-typical.org/usage/advanced).

Improvements:
- Re-organized for better maintainability and modularization.

**v2.0.0b13**  
Bugfixes:
- Fix regex pattern coercion
- Fix setattr locator

Improvements:
- Faster & simpler name creation for generated code
- Improved tracebacks and debugging for generated code
- More tests & improved coverage
- Remove unused code-paths

**v2.0.0b12**  
Bugfixes:
- Coerce nested contrained values
- Map `NetworkAddress` to a constraint factory
- Properly support subclasses of builtins on coercion

Improvements:
- Improve management of strict-mode state
- Add tests for type-constraints.

**v2.0.0b11**  
Bugfixes:
- Fix handling of `typing.Any` in contraints & schema gen.

Also:
- #25: Remove now-inaccurate statement regarding pydantic in docs.


**v2.0.0b10**  
Bugfixes:
- Properly handle Unions/MultiConstraints within arrays and dicts
- Add coverage reports back to travis config

Also:
- Improve overall test coverage.

**v2.0.0b8**  
Runtime Validation:

This feature is inspired by the discussion found in #19. Taking
advantage of "strict-mode", it's now possible to provide some runtime
enforcement of Union types.

Expand constraints scope for runtime validation:
- Migrate Array/Mapping Constraints to more Pythonic type syntax.
- Add `MultiConstraints` for Union types.
- Add `TypeConstraints` for higher-level builtin types.
- Add `typic.get_constraints` for generating constraints from a given
  type.
- Add `typic.Strict`, `typic.StrictStrT`, `strict` keyword to
  decorators, and `typic.strict_mode` flagging "strict-mode" at
  run-time.
- Add docs: strict-mode.rst, index.rst

Also:
- Fix bug coercing constrained types.
- Fix ``checks.isoptionaltype`` to account for optionals nested in unions.
- Improve coverage for mapping.py and fix some bugs

**v2.0.0b7**
1. #14: Improve TypedDict support:
   - respect total=False flag on coercion & schema gen
   - Proper support for typing.Optional in schema gen.
2. #21: Properly handle enums:
   - Downgrade enums to their held values on calls to typic.primitive
3. Also:
   - Fix lazy evaluation of value for default factories in settings
   - Treat subclasses of builtins as builtins in coercer

**v2.0.0b1**  
This release brings an entirely new annotation resolution engine which
is backwards-incompatible with v1. The high-level API remains largely
the same.

New features include:
1. ``@typic.constrained`` for definining restricted versions of
   builtin types.
2. ``@typic.settings`` for resolving the default values of a dataclass
   from your environment variables
3. A whole new suite of useful types, including:
   - ``FrozenDict``, a hashable, immutable dictionary
   - ``DSN``, a JSON-serializable string-type for your database URIs
   - ``URL``, a JSON-serializable string-type for your URLs
   - ``Email``, a JSON-serializable string-type for emails
   - ``SecretString``, a JSON-serializable string-type for hiding
     secrets when logging or printing
4. ``typic.schema`` for getting a valid JSON Schema definition for
   your classes and type annotations. ``typical`` classes also have
   access to this as a classmethod.
5. ``typic.primitive`` for extracting a valid JSON-serializable
   primitive from just about anything. ``typical`` classes also have
   access to this as an instance method.

And so much more. Check out the documentation for details!

**v1.10.0**
1. Added the ability to resolve delayed annotations with a
   module-level callable, i.e.:
   ```python
   import typic

   @typic.klass(delay=True)
   class SomeClass:
       some_attr: str
   
   typic.resolve()
   ```
**v1.9.2**
1. Added the `delay` keyword-arg to wrappers to allow user to delay
   annotation resolution until the first call of the wrapped object.
2. Added the `coerce` keyword-arg to `typic.bind` to allow users to
   bind args without coercing them.

**v1.9.1**
1. Squashed a bug that broke annotation resolution when wrapping bound
   methods of classes.

**v1.9.0**
1. Introducing `typic.bind`:
   - An optimized version of `inspect.Signature.bind` which will also
     coerce inputs given.
2. `typic.al` is now up to ~30% faster on wrapped callables.

**v1.5.0**
1. Frozen dataclasses are now supported.

**v1.4.1**
1. Fixed a nasty bug in wrapped classes that resulted in
   infinite recursion.

**v1.4.0**
1. A new wrapper has been added to simplify dataclass usage:

    ```python
    import typic
    
    @typic.klass
    class Foo:
        bar: str
    
    ```
    is equivalent to
    ```python
    import dataclasses
    import typic
    
    @typic.al
    @dataclasses.dataclass
    class Foo:
        bar: str
    
    ```
    All standard dataclass syntax is supported with
    `typic.klass`

**v1.3.2**
1. Resolution time is better than ever.
2. Custom Unions are now supported via registering custom coercers with
   `typic.register`, as a result of raising the priority of
   user-registered coercers.

**v1.3.1_:
1. Improved caching strategy and resolution times.

**v1.3.0**
1. Custom coercers may now be registered, e.g.:
    ```python
    import typic
    
    class MyCustomClass:
    
        def __init__(self, value):
            self.value = value
    
        @classmethod
        def factory(cls, value):
            return cls(value)
    
    
    def custom_class_coercer(value, annotation: MyCustomClass):
        return annotation.factory(value)
    
    
    def ismycustomclass(obj) -> bool:
        return obj is MyCustomClass
        
    
    typic.register(custom_class_coercer, ismycustomclass)
    ```

2. Squashed a few bugs:
   -  Nested calls of `Coercer.coerce_value` didn't account for values
      that didn't need coercion. This sometimes broke evaluation, and
      definitely resulted in sub-optimal type resolution performance.
   -  In the final attempt to coerce a custom class, calling
      `typic.evals.safe_eval` could reveal that a value is null. In this
      case, we should respect whether the annotation was optional.
   -  Sometimes people are using a version of PyYAML that's older than
      5.1. We should support that.

**v1.2.0**
1. Values set to annotated attributes are automagically resolved.

**v1.1.0**
1. `typing.Optional` and `typing.ClassVar` are now supported.

