import typical


@typical.klass
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
    typical.primitive(Klass("foo"))
    k: Klass = typical.transmute(Klass, "foo")
    v = typical.validate(Klass, {"attr": "foo"})
    j: str = typical.tojson(Klass("foo"))
    o: Other = Klass("foo").translate(Other)
    fields = [*Klass("foo").iterate()]
    iterfields = [*Klass("foo")]
