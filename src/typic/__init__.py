# flake8: noqa

import warnings

warnings.warn(
    "`typic` is considered a legacy interface and will be removed in a future version. "
    "Consider migrating to the v3 interface in the `typical` package.",
    stacklevel=2,
    category=DeprecationWarning,
)


from typical.api import *
from typical.checks import *
from typical.classes import *
from typical.desers import *
from typical.inspection import *
from typical.magic import *
from typical.magic.schema import *
from typical.types import *
