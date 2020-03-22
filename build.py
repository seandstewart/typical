import os

ext_modules = None
NO_CYTHON = bool(int(os.getenv("NO_CYTHON", "0")))
CYTHON_TRACE = bool(int(os.getenv("CYTHON_TRACE", "0")))
CYTHON_NTHREADS = int(os.getenv("CYTHON_NTHREADS", "0"))

if not NO_CYTHON:
    try:
        from Cython.Build import cythonize

        # For cython test coverage install with `make build-cython-trace`
        compiler_directives = {}
        if CYTHON_TRACE:
            compiler_directives["linetrace"] = CYTHON_TRACE
        os.environ["CFLAGS"] = "-O3"
        ext_modules = cythonize(
            ["typic/*.py", "typic/*/*.py", "typic/*/*/*.py"],
            exclude=[
                "typic/generics.py",
                "typic/gen.py",
                "typic/obj.py",
                "typic/*/obj.py",
                "typic/*/*/obj.py",
            ],
            nthreads=CYTHON_NTHREADS,
            language_level=3,
            compiler_directives=compiler_directives,
        )

    except ImportError:
        pass


def build(setup_kwargs):
    setup_kwargs.update(ext_modules=ext_modules)
