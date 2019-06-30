#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import pathlib


__all__ = ("FilePathError", "FilePath", "DirectoryPathError", "DirectoryPath")


PathType = pathlib.Path().__class__  # type: ignore


class FilePathError(ValueError):
    """Generic error raised when the given value is not a File-Path."""

    pass


class FilePath(PathType):  # type: ignore
    """A path object pointing to a file.

    See Also
    --------
    :py:class:`pathlib.Path`
    """

    def __init__(self, *pathsegments: str):
        super().__init__()
        if not self.is_file():
            raise FilePathError(f"{self} is not a valid file-path") from None


class DirectoryPathError(ValueError):
    """Generic error raised when the given value is not a Directory-Path."""

    pass


class DirectoryPath(PathType):  # type: ignore
    """A path object pointing to a directory.

    See Also
    --------
    :py:class:`pathlib.Path`
    """

    def __init__(self, *pathsegments: str):
        super().__init__()
        if not self.is_dir():
            raise DirectoryPathError(f"{self} is not a valid directory-path") from None
