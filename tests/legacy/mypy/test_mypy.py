from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
from mypy import api as mypy_api

cases = (
    ("mypy.ini", "success.py", "success.txt"),
    ("mypy.ini", "fail.py", "fail.txt"),
)
executable_modules = ("success",)

CUR_DIR = Path(__file__).resolve().parent


@pytest.mark.xfail()
@pytest.mark.parametrize("config_filename,python_filename,output_filename", cases)
def test_mypy_results(config_filename, python_filename, output_filename):
    full_config_filename = CUR_DIR / "config" / config_filename
    full_filename = CUR_DIR / "module" / python_filename
    output_path = (
        None if output_filename is None else CUR_DIR / "output" / output_filename
    )

    # Specifying a different cache dir for each configuration dramatically speeds up
    # subsequent execution.
    # It also prevents cache-invalidation-related bugs in the tests
    cache_dir = f".mypy_cache/test-{config_filename[:-4]}"
    command = [
        str(full_filename),
        "--config-file",
        str(full_config_filename),
        "--cache-dir",
        str(cache_dir),
        "--show-error-codes",
        "--show-traceback",
    ]
    print(
        f"\nExecuting: mypy {' '.join(command)}"
    )  # makes it easier to debug as necessary
    actual_result = mypy_api.run(command)
    actual_out, actual_err, actual_returncode = actual_result
    # Need to strip filenames due to differences in formatting by OS
    actual_out = "\n".join(
        [".py:".join(line.split(".py:")[1:]) for line in actual_out.split("\n") if line]
    ).strip()
    actual_out = re.sub(r"\n\s*\n", r"\n", actual_out)

    if actual_out:
        print(
            "{0}\n{1:^100}\n{0}\n{2}\n{0}".format("=" * 100, "mypy output", actual_out)
        )

    assert actual_err == ""
    expected_returncode = 0 if "success" in output_filename else 1
    assert actual_returncode == expected_returncode

    if output_path and not output_path.exists():
        output_path.write_text(actual_out)
        raise RuntimeError(
            f"wrote actual output to {output_path} since file did not exist"
        )

    expected_out = Path(output_path).read_text() if output_path else ""
    assert actual_out.rstrip() == expected_out.rstrip(), actual_out


@pytest.mark.xfail()
@pytest.mark.parametrize("module", executable_modules)
def test_success_cases_run(module):
    """
    Ensure the "success" files can actually be executed
    """
    importlib.import_module(f"tests.mypy.module.{module}")
