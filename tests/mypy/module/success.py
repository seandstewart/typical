import typic


@typic.klass
class Klass:
    attr: str


if __name__ == "__main__":

    Klass(attr="foo")
    Klass("foo")
    Klass.transmute("foo")
    Klass.validate({"attr": "foo"})
    Klass("foo").primitive()
