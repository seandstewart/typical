from __future__ import annotations

import pathlib
import sys
from typing import TYPE_CHECKING

__all__ = ("FilePathError", "FilePath", "DirectoryPathError", "DirectoryPath")


PathType = pathlib.Path().__class__  # type: ignore


class FilePathError(ValueError):
    """Generic error raised when the given value is not a File-Path."""

    pass


class DirectoryPathError(ValueError):
    """Generic error raised when the given value is not a Directory-Path."""

    pass


if TYPE_CHECKING:

    class FilePath(pathlib.Path): ...

    class DirectoryPath(pathlib.Path): ...

else:

    class FilePath(PathType):  # type: ignore
        """A path object pointing to a file.

        See Also:
            - :py:class:`pathlib.Path`
        """

        if sys.version_info >= (3, 12):

            def __init__(self, *pathsegments: str):
                super().__init__(*pathsegments)
                if not self.is_file():
                    raise FilePathError(f"{self} is not a valid file-path") from None

        else:

            def __init__(self, *pathsegments: str):
                super().__init__()
                if not self.is_file():
                    raise FilePathError(f"{self} is not a valid file-path") from None

    class DirectoryPath(PathType):  # type: ignore
        """A path object pointing to a directory.

        See Also:
            - :py:class:`pathlib.Path`
        """

        if sys.version_info >= (3, 12):

            def __init__(self, *pathsegments: str):
                super().__init__(*pathsegments)
                if not self.is_dir():
                    raise DirectoryPathError(
                        f"{self} is not a valid directory-path"
                    ) from None

        else:

            def __init__(self, *pathsegments: str):
                super().__init__()
                if not self.is_dir():
                    raise DirectoryPathError(
                        f"{self} is not a valid directory-path"
                    ) from None
