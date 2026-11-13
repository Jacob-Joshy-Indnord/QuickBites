"""Payable-total and minimum order value logic.

Functions: compute_payable_paise(subtotal, adjustments) returns the amount the
customer would pay: item subtotal minus discounts plus fees plus taxes (the
confirmed reading of the minimum order rule: it applies AFTER discounts and
INCLUDING delivery fee and taxes). compute_shortfall_paise(payable, minimum)
returns max(0, minimum - payable). BillAdjustments is a dataclass of discount,
fees and tax in paise; zero_adjustments is the default provider until the
bill engine and promotions tasks supply real values. All values are integer
paise.
"""
from dataclasses import dataclass


@dataclass
class BillAdjustments:
    discount_paise: int = 0
    fees_paise: int = 0
    tax_paise: int = 0


def zero_adjustments(outlet_id: str, subtotal_paise: int) -> BillAdjustments:
    return BillAdjustments()


def compute_payable_paise(subtotal_paise: int, adj: BillAdjustments) -> int:
    return max(0, subtotal_paise - adj.discount_paise + adj.fees_paise + adj.tax_paise)


def compute_shortfall_paise(payable_paise: int, minimum_paise: int) -> int:
    return max(0, minimum_paise - payable_paise)
