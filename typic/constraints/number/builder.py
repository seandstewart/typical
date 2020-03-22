import decimal
import warnings
from typing import Tuple, List, Dict, Any, TYPE_CHECKING

from typic import gen, util

from ..common import ConstraintSyntaxError, ConstraintValueError, ChecksT, ContextT

if TYPE_CHECKING:
    from .obj import NumberConstraints


def _get_digits(tup: decimal.DecimalTuple):
    if tup.exponent >= 0:
        # A positive exponent adds that many trailing zeros.
        digits = len(tup.digits) + tup.exponent
        decimals = 0
    else:
        # If the absolute value of the negative exponent is larger than the
        # number of digits, then it's the same as the number of digits,
        # because it'll consume all of the digits in digit_tuple and then
        # add abs(exponent) - len(digit_tuple) leading zeros after the
        # decimal point.
        if abs(tup.exponent) > len(tup.digits):
            digits = decimals = abs(tup.exponent)
        else:
            digits = len(tup.digits)
            decimals = abs(tup.exponent)
    whole_digits = digits - decimals
    return whole_digits, digits, decimals


def _check_syntax(constr: "NumberConstraints"):
    if constr.gt is not None:
        if constr.ge is not None:
            raise ConstraintSyntaxError(
                f"Values must either be '>' or '>=', not both."
            ) from None
        if constr.gt in {constr.lt, constr.le}:
            msg = (
                f"Values for '>' and '<|<=' are equal "
                f"({constr.gt}, {constr.lt}|{constr.le}), "
                f"this will always be false."
            )
            raise ConstraintSyntaxError(msg) from None
    if constr.lt is not None:
        if constr.le is not None:
            raise ConstraintSyntaxError(
                f"Values must either be '<' or '<=', not both."
            ) from None
        if constr.lt in {constr.gt, constr.ge}:
            msg = (
                f"Values for '<' and '>|>=' are equal "
                f"({constr.lt}, {constr.gt}|{constr.ge}), "
                f"this will always be false."
            )
            raise ConstraintSyntaxError(msg) from None


def _build_validator(
    constr: "NumberConstraints", func: gen.Block
) -> Tuple[ChecksT, ContextT]:
    # Sanity check the syntax
    _check_syntax(constr)
    # Generate the validator
    checks: List[str] = []
    context: Dict[str, Any] = {}
    if constr.gt is not None:
        checks.append(f"{constr.VAL} > {constr.gt}")
    if constr.ge is not None:
        checks.append(f"{constr.VAL} >= {constr.ge}")
    if constr.lt is not None:
        checks.append(f"{constr.VAL} < {constr.lt}")
    if constr.le is not None:
        checks.append(f"{constr.VAL} <= {constr.le}")
    if constr.mul is not None:
        checks.append(f"{constr.VAL} % {constr.mul} == 0")

    if util.origin(constr.type) is decimal.Decimal:
        max_digits, decimal_places = (
            getattr(constr, "max_digits", None),
            getattr(constr, "decimal_places", None),
        )
        context.update(decimal=decimal, Decimal=decimal.Decimal)
        if {max_digits, decimal_places} != {None, None}:
            # Update the global namespace for the validator
            # Add setup/sanity checks for decimals.
            func.l(f"{constr.VAL} = decimal.Decimal({constr.VAL})")
            with func.b(
                f"if {constr.VAL}.is_infinite():",
                ConstraintValueError=ConstraintValueError,
            ) as b:
                b.l("raise ConstraintValueError('Cannot validate infinite values.')")
            func.l(f"tup = {constr.VAL}.as_tuple()")
            func.l(
                "whole, digits, decimals = _get_digits(tup)", _get_digits=_get_digits,
            )
            if max_digits is not None:
                checks.append(f"digits <= {max_digits}")
            if decimal_places is not None:
                checks.append(f"decimals <= {decimal_places}")
            # Special syntax rules for Decimals
            if decimal_places is not None and max_digits is not None:
                if max_digits < decimal_places:
                    msg = (
                        f"Contraint <decimal_places={decimal_places!r}> "
                        f"should never be greater than "
                        f"Constraint <max_digits={max_digits!r}>"
                    )
                    raise ConstraintSyntaxError(msg) from None
                elif max_digits == decimal_places:
                    msg = (
                        f"Contraint <decimal_places={decimal_places!r}> equals "
                        f"Constraint <max_digits={max_digits!r}>. "
                        f"This may be unintentional. "
                        "Only partial numbers < '1.0' will be allowed."
                    )
                    warnings.warn(msg)
                checks.append(f"whole <= ({max_digits} - {decimal_places})")

    return checks, context
