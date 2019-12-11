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

