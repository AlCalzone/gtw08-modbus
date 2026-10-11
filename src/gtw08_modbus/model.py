"""The component base and field helpers the GTW-08 register map builds on.

The manual numbers registers by their protocol address, so a field takes the
manual's number as is. Each helper below matches one of the manual's data
types and decodes the value the gateway sends for "not available" to ``None``.
The manual documents none of these values. They are the conventions of the
data types.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from enum import IntEnum, IntFlag
from typing import Any, overload

from modbus_connection.model import (
    Component,
    NumberField,
    UpdateReport,
    WriteValidator,
)

from .errors import InvalidValueError

__all__ = [
    "Gtw08Component",
    "LowByteField",
    "UpdateReport",
    "bool8",
    "enum8",
    "flags8",
    "int16",
    "uint8",
    "uint16",
    "uint32",
]

# What the gateway sends for a value it has no reading for.
INT16_NOT_AVAILABLE = frozenset({0x7FFF, 0x8000})
UINT8_NOT_AVAILABLE = 0xFF
UINT16_NOT_AVAILABLE = 0xFFFF
UINT32_NOT_AVAILABLE = 0xFFFFFFFF


class Gtw08Component(Component):
    """A sub-system of the GTW-08 register map.

    Reads cover only the registers the manual documents. Neighbouring
    registers merge into one read. A gap splits it.
    """

    max_gap = 1


class LowByteField[T](NumberField[T]):
    """An 8-bit value in the low byte of one register.

    The manual's UINT8, ENUM8 and 8-bit bitfield types arrive this way.
    """

    def decode(self, words: list[int], scale_exponent: int | None = None) -> Any:
        """Decode the low byte, ignoring whatever the high byte holds."""
        return super().decode([words[0] & 0xFF], scale_exponent)


def _decimals(scale: float) -> int:
    """The decimal places a scale keeps, as ``NumberField`` counts them."""
    return max(0, len(f"{scale:.10f}".rstrip("0").split(".")[1]))


def _in_range(
    low: int,
    high: int,
    scale: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> WriteValidator:
    """Reject a value whose encoded form falls outside ``low`` to ``high``.

    The raw bounds leave out the "not available" values, so a write can never
    send one. ``minimum`` and ``maximum`` narrow the range to what the manual
    allows, in the field's unit.
    """
    decimals = _decimals(scale)

    def validate(value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise InvalidValueError(f"{value!r} is not a number")
        if not math.isfinite(value):
            raise InvalidValueError(f"{value} is not a finite number")
        if minimum is not None and value < minimum:
            raise InvalidValueError(f"{value} is below {minimum:g}")
        if maximum is not None and value > maximum:
            raise InvalidValueError(f"{value} is above {maximum:g}")
        # Round the way NumberField.encode does, so the check sees the raw
        # value that is sent.
        raw = round(round(float(value), decimals) / scale)
        if not low <= raw <= high:
            raise InvalidValueError(
                f"{value} is outside {low * scale:g} to {high * scale:g}"
            )
        return value

    return validate


def _member_of(
    enum_type: type[IntEnum], allowed: Iterable[IntEnum] | None = None
) -> WriteValidator:
    """Accept a member of ``enum_type``, or its number, out of ``allowed``."""
    members = frozenset(enum_type if allowed is None else allowed)

    def validate(value: Any) -> Any:
        if isinstance(value, IntEnum) and not isinstance(value, enum_type):
            raise InvalidValueError(f"{value!r} is not a {enum_type.__name__}")
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidValueError(f"{value!r} is not a {enum_type.__name__}")
        try:
            member = enum_type(value)
        except ValueError:
            raise InvalidValueError(f"{value} is not a {enum_type.__name__}") from None
        if member not in members:
            raise InvalidValueError(f"{member.name} cannot be written")
        return member

    return validate


def int16(
    address: int,
    scale: float = 1.0,
    *,
    unit: str | None = None,
    writable: bool = False,
) -> NumberField[float]:
    """A signed 16-bit value, such as a temperature in 0.01 °C."""
    return NumberField(
        address,
        scale=scale,
        signed=True,
        nan=INT16_NOT_AVAILABLE,
        unit=unit,
        writable=_in_range(-0x7FFF, 0x7FFE, scale) if writable else False,
        force_fc16=writable,
    )


@overload
def uint16(
    address: int,
    *,
    unit: str | None = None,
    writable: bool = False,
    stride: int = 0,
) -> NumberField[int]: ...


@overload
def uint16(
    address: int,
    scale: float,
    *,
    unit: str | None = None,
    writable: bool = False,
    stride: int = 0,
) -> NumberField[float]: ...


def uint16(
    address: int,
    scale: float = 1.0,
    *,
    unit: str | None = None,
    writable: bool = False,
    stride: int = 0,
) -> NumberField[int] | NumberField[float]:
    """An unsigned 16-bit value."""
    return NumberField(
        address,
        scale=scale,
        signed=False,
        nan=UINT16_NOT_AVAILABLE,
        unit=unit,
        stride=stride,
        writable=_in_range(0, UINT16_NOT_AVAILABLE - 1, scale) if writable else False,
        force_fc16=writable,
    )


@overload
def uint32(
    address: int,
    *,
    unit: str | None = None,
) -> NumberField[int]: ...


@overload
def uint32(
    address: int,
    scale: float,
    *,
    unit: str | None = None,
) -> NumberField[float]: ...


def uint32(
    address: int,
    scale: float = 1.0,
    *,
    unit: str | None = None,
) -> NumberField[int] | NumberField[float]:
    """An unsigned 32-bit value over two registers, high word first."""
    return NumberField(
        address,
        count=2,
        scale=scale,
        signed=False,
        nan=UINT32_NOT_AVAILABLE,
        unit=unit,
    )


@overload
def uint8(
    address: int,
    *,
    unit: str | None = None,
    writable: bool = False,
    maximum: float | None = None,
) -> LowByteField[int]: ...


@overload
def uint8(
    address: int,
    scale: float,
    *,
    unit: str | None = None,
    writable: bool = False,
    maximum: float | None = None,
) -> LowByteField[float]: ...


def uint8(
    address: int,
    scale: float = 1.0,
    *,
    unit: str | None = None,
    writable: bool = False,
    maximum: float | None = None,
) -> LowByteField[int] | LowByteField[float]:
    """An unsigned 8-bit value in the low byte of a register.

    ``maximum`` caps a write at the manual's limit, in the field's unit.
    """
    validator = _in_range(0, UINT8_NOT_AVAILABLE - 1, scale, maximum=maximum)
    return LowByteField(
        address,
        scale=scale,
        signed=False,
        nan=UINT8_NOT_AVAILABLE,
        unit=unit,
        writable=validator if writable else False,
        force_fc16=writable,
    )


def enum8[E: IntEnum](
    address: int,
    enum_type: type[E],
    *,
    writable: bool | Iterable[E] = False,
    stride: int = 0,
    nan: int | Iterable[int] | None = UINT8_NOT_AVAILABLE,
) -> LowByteField[E]:
    """An ENUM8 value in the low byte of a register.

    Pass the members a write may send as ``writable`` when only some may be
    written. Pass ``nan=None`` for an enum that uses 255 as a real value.
    """
    allowed = None if isinstance(writable, bool) else list(writable)
    can_write = allowed is not None or writable is True
    return LowByteField(
        address,
        signed=False,
        convert=enum_type,
        nan=nan,
        stride=stride,
        writable=_member_of(enum_type, allowed) if can_write else False,
        force_fc16=can_write,
    )


_BOOLEAN_CODES = {0: False, 1: True}


def bool8(address: int) -> LowByteField[bool]:
    """A 0/1 value in the low byte of a register, as ``bool``."""
    return LowByteField(
        address, signed=False, convert=_BOOLEAN_CODES, nan=UINT8_NOT_AVAILABLE
    )


def flags8[F: IntFlag](
    address: int, flag_type: type[F], *, nan: int | None = None
) -> LowByteField[F]:
    """An 8-bit bitfield in the low byte of a register.

    Pass ``nan=0xFF`` for a bitfield whose top bit is never set.
    """
    return LowByteField(address, signed=False, convert=flag_type, nan=nan)
