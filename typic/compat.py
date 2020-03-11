#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# flake8: noqa
try:
    from typing import Final, TypedDict  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import Final, TypedDict  # type: ignore
try:
    from sqlalchemy import MetaData as SQLAMetaData  # type: ignore
except ImportError:  # pragma: nocover

    class SQLAMetaData:  # type: ignore
        ...
