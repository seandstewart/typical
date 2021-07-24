# flake8: noqa

import sys

import pytest
import typic


def has_pandas():
    try:
        import pandas

        return True
    except (ModuleNotFoundError, ImportError):
        return False


@pytest.mark.skipif(
    "not has_pandas()", reason=f"Pandas isn't installed. (Python {sys.version})"
)
def test_transmute_pandas_series():
    import pandas

    transmuted = typic.transmute(pandas.Series, [])
    assert isinstance(transmuted, pandas.Series)


@pytest.mark.skipif(
    "not has_pandas()", reason=f"Pandas isn't installed. (Python {sys.version})"
)
def test_transmute_pandas_dataframe():
    import pandas

    transmuted = typic.transmute(pandas.DataFrame, {})
    assert isinstance(transmuted, pandas.DataFrame)
