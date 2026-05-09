from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


MONEY_PLACES = Decimal("0.01")


def to_decimal(value: int | float | str | Decimal | None) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ItemCalculationResult:
    quantity: int | None
    weight: Decimal | None
    unit_price: Decimal
    value: Decimal


def calculate_item(quantity: int | None, weight: Decimal | None, unit_price: Decimal | None, value: Decimal | None) -> ItemCalculationResult:
    has_quantity = quantity is not None and quantity > 0
    has_weight = weight is not None and weight > 0

    if has_quantity == has_weight:
        raise ValueError("Podaj dokladnie jedno pole: ilosc albo waga.")

    measure = Decimal(quantity) if has_quantity else weight
    if measure is None or measure <= 0:
        raise ValueError("Miara pozycji musi byc wieksza od zera.")

    has_unit_price = unit_price is not None and unit_price > 0
    has_value = value is not None and value > 0

    if not has_unit_price and not has_value:
        raise ValueError("Podaj cene jednostkowa albo wartosc pozycji.")

    if has_unit_price and has_value:
        resolved_unit_price = money(unit_price)
        resolved_value = money(value)
        expected_value = money(measure * resolved_unit_price)
        if resolved_value != expected_value:
            raise ValueError("Cena jednostkowa i wartosc pozycji nie sa ze soba zgodne.")
    elif has_unit_price:
        resolved_unit_price = money(unit_price)
        resolved_value = money(measure * resolved_unit_price)
    else:
        resolved_value = money(value)
        resolved_unit_price = money(resolved_value / measure)

    return ItemCalculationResult(
        quantity=quantity if has_quantity else None,
        weight=weight if has_weight else None,
        unit_price=resolved_unit_price,
        value=resolved_value,
    )


def calculate_total(values: list[Decimal]) -> Decimal:
    total = sum(values, Decimal("0.00"))
    return money(total)