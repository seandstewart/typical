import typic


@typic.klass
class MyClass:
    field: int

    def __post_init__(self):
        print("other.py: MyClass is being constructed")


def factory():
    val = MyClass(field=1)
    return val
