from __future__ import annotations

import pytest

from typic.types import FilePath, DirectoryPath


@pytest.mark.skip(reason="Inconsistent behavior across Python versions.")
@pytest.mark.parametrize(
    argnames=("path", "cls"),
    argvalues=[("/some/path/", FilePath), ("/some/path", DirectoryPath)],
)
def test_invalid_path(path, cls):
    with pytest.raises(ValueError):
        cls(path)
