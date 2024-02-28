from __future__ import annotations

from typical import magic


@magic.klass
class MyClass:
    field: int

    def __post_init__(self):
        print("index.py: MyClass is being constructed")
