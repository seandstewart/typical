import os
import sys

ext_modules = None
if (
    not any(arg in sys.argv for arg in ["clean", "check"])
    and "SKIP_CYTHON" not in os.environ
):
    try:
        from Cython.Build import cythonize
    except ImportError:
        pass
    else:
        # For cython test coverage install with `make build-cython-trace`
        compiler_directives = {}
        if "CYTHON_TRACE" in sys.argv:
            compiler_directives["linetrace"] = True
        os.environ["CFLAGS"] = "-O3"
        ext_modules = cythonize(
            ["typic/*.py", "typic/*/*.py"],
            nthreads=int(os.getenv("CYTHON_NTHREADS", 0)),
            language_level=3,
            compiler_directives=compiler_directives,
        )


def build(setup_kwargs):
    setup_kwargs.update(ext_modules=ext_modules)
