import typic


@typic.klass
class Klass:
    attr: str


class Other:
    def __init__(self, attr: str):
        self.attr = attr


if __name__ == "__main__":

    Klass(attr="foo")
    Klass("foo")
    Klass.transmute("foo")
    Klass.validate({"attr": "foo"})
    Klass("foo").primitive()
    Klass("foo").primitive(lazy=True)
    Klass("foo").tojson()
    Klass("foo").tojson(indent=0)
    Klass("foo").tojson(ensure_ascii=False)
    typic.primitive(Klass("foo"))
    k: Klass = typic.transmute(Klass, "foo")
    v = typic.validate(Klass, {"attr": "foo"})
    j: str = typic.tojson(Klass("foo"))
    o: Other = Klass("foo").translate(Other)
    fields = [*Klass("foo").iterate()]
    iterfields = [*Klass("foo")]
