``typical`` Example
===================

I could spend all day talking about the benefits of automatic, guaranteed coercion.
Instead, I'll show you by building a simple web application with typical, ``ducks-api``.

    Note: I'm using ``starlette`` here, but whatever you like is fine.

First, let's define some models:

.. code-block:: python


    # ducks-api/models.py
    import dataclasses
    import datetime
    import enum
    import uuid

    import typic

    class DuckType(str, enum.Enum):
        WHT: "white"
        BLK: "black"
        MLD: "mallard"


    @typic.al
    @dataclasses.dataclass
    class Duck:
        name: str
        type: DuckType
        created_on: datetime.datetime = dataclasses.field(
            default_factory=datetime.datetime.utcnow
        )
        id: uuid.UUID = dataclasses.field(
            default_factory=uuid.uuid4
        )


Next, let's define a place to store our ducks

.. code-block:: python

    # ducks-api/registry.py
    import uuid
    from typing import Union, List

    import typic

    from .models import DuckType, Duck


    class DuckRegistry:
    """A Registry for all the ducks.

    Note - an in-memory dictionary is definitely NOT a production-ready datastore :)
    """

        @typic.al
        def __init__(self, *ducks: Duck):
            self._reg = {x.id: x for x in ducks}

        def all() -> List[Duck]:
            return [*self._reg.values()]

        @typic.al
        def add(self, duck: Duck) -> Duck:
            self._reg[duck.id] = duck
            return duck

        @typic.al
        def get(self, id: uuid.UUID) -> Optional[Duck]:
            return self._reg.get(id)

        def find_by_name(name: str) -> List[Duck]:
            return [y for y in self._reg.values() if y.name == name]

        @typic.al
        def find_by_type(type: DuckType) -> List[Duck]:
            return [y for y in self._reg.values() if y.type == type]


Finally, let's build our web-service layer:

.. code-block:: python

    # ducks-api/api.py
    from starlette.application import Starlette
    from starlette.responses import JSONResponse
    from starlette.exceptions import HTTPException

    from .registry import DuckRegistry

    app = Starlette("ducks-api")
    reg = DuckRegistry()

    @app.route("ducks/", methods=["GET"])
    def list_ducks(request):
        return JSONResponse([x.primitive() for x in reg.all()])


    @app.route("ducks/{id}", methods=["GET"])
    def get_duck(request):
        try:
            duck = reg.get(request.path_params["id"])
        # raised when we try to coerce an invalid 'id' string to a UUID
        except ValueError as err:
            raise HTTPException(400, str(err))

        if duck:
            return JSONResponse(duck.primitive())
        raise HTTPException(404, f"Duck with ID {request.path_params['id']!r} not found")



    @app.route("ducks/", methods=["POST"])
    async def make_duck(request)
        try:
            duck = reg.add(await request.body())
        # Missing required fields, or invalid value provided for a field
        except (TypeError, ValueError) as err:
            raise HTTPException(400, str(err))

        return JSONResponse(duck.primitive())

    @app.route("ducks/type/{type}", methods=["GET"])
    def list_ducks_by_type(request):
        try:
            ducks = [
                x.primitive()
                for x in reg.find_by_type(request.path_params['type'])
            ]
        except ValueError as err:
            raise HTTPException(400, str(err))

        return JSONResponse(ducks)


    @app.route("ducks/name/{name}", methods=["GET"])
    def list_ducks_by_name(request):
        return JSONResponse(
            [
                x.primitive()
                for x in reg.find_by_name(request.path_params['name'])
            ]
         )


The handler layer is where we see ``typical`` really shine:
    - At no point in the handler did we have to convert anything from the external
      input into something our lower layer understands - it's done!
    - And returning a JSON response was as easy as calling ``primitive()``.

We also get the benefit of input validation:
    - In ``get_duck``, if coercion to a UUID fails, we get a predictable
      ``ValueError`` which can be reported back to the user.
    - In ``list_ducks_by_type``, if coercion to DuckType fails, we get a predictable
      ``ValueError`` which can be reported back to the user.
    - In ``make_duck``, if fields are missing in the request body, we get a
      ``TypeError`` and if any of those fields are invalid we get a ``ValueError``,
      which we can, again, report directly back to the user.


All of this is provided by simply wrapping your annotated functions, methods, and/or
classes with ``@typic.al``.
