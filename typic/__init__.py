#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from .checks import *  # noqa: F403 (we've defined __all__)
from .klass import klass  # noqa: F401
from .typed import *  # noqa: F403 (we've defined __all__)

al = typed  # noqa: F405
register = coerce.register  # noqa: F405
