from __future__ import annotations

import pytest

from typical.types import DirectoryPath, FilePath


@pytest.mark.parametrize(
    argnames=("path", "cls"),
    argvalues=[("/some/path/", FilePath), ("/some/path.pth", DirectoryPath)],
)
def test_invalid_path(path, cls):
    with pytest.raises(ValueError):
        cls(path)
