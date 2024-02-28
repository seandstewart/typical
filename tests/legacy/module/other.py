from __future__ import annotations

from typical import magic


@magic.klass
class MyClass:
    field: int

    def __post_init__(self):
        print("other.py: MyClass is being constructed")


def factory():
    val = MyClass(field=1)
    return val
