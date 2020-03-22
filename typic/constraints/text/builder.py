from typing import Tuple, Dict, Any

from typic import gen

from ..common import ChecksT, ContextT


def _build_validator(self, func: gen.Block) -> Tuple[ChecksT, ContextT]:
    # Set up the local env.
    if self.curtail_length is not None:
        func.l(f"{self.VAL} = {self.VAL}[:{self.curtail_length}]")
    if self.strip_whitespace:
        func.l(f"{self.VAL} = {self.VAL}.strip()")
    if {self.min_length, self.max_length} != {None, None}:
        func.l(f"size = len({self.VAL})")
    # Build the validation.
    checks = []
    context: Dict[str, Any] = {}
    if self.max_length is not None:
        checks.append(f"size <= {self.max_length}")
    if self.min_length is not None:
        checks.append(f"size >= {self.min_length}")
    if self.regex is not None:
        context.update(__pattern=self.regex)
        checks.append(f"__pattern.match({self.VAL})")

    return checks, context
