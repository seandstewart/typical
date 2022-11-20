# flake8: noqa

import sys
from typing import Union

import pytest

import typic


def has_pandas():
    try:
        import pandas

        return True
    except (ModuleNotFoundError, ImportError):
        return False


pytestmark = pytest.mark.skipif(
    "not has_pandas()", reason=f"Pandas isn't installed. (Python {sys.version})"
)


def test_transmute_pandas_series():
    import pandas

    transmuted = typic.transmute(pandas.Series, [])
    assert isinstance(transmuted, pandas.Series)


def test_transmute_pandas_dataframe():
    import pandas

    transmuted = typic.transmute(pandas.DataFrame, {})
    assert isinstance(transmuted, pandas.DataFrame)


def test_transmute_pandas_union():
    import pandas

    transmuted = typic.transmute(Union[pandas.DataFrame, pandas.Series], {})
    assert isinstance(transmuted, pandas.DataFrame)
