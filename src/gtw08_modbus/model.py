"""The component base and field helpers the GTW-08 register map builds on.

The manual numbers registers by their protocol address, so a field takes the
manual's number as is. Each helper below matches one of the manual's data
types and decodes the value the gateway sends for "not available" to ``None``.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import Any, overload

from modbus_connection.model import Component, NumberField, UpdateReport

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
    registers merge into one read, and a gap splits it.
    """

    max_gap = 1


class LowByteField[T](NumberField[T]):
    """An 8-bit value in the low byte of one register.

    The manual's UINT8, ENUM8 and 8-bit bitfield types arrive this way.
    """

    def decode(self, words: list[int], scale_exponent: int | None = None) -> Any:
        """Decode the low byte, ignoring whatever the high byte holds."""
        return super().decode([words[0] & 0xFF], scale_exponent)


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
        writable=writable,
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
        writable=writable,
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
) -> LowByteField[int]: ...


@overload
def uint8(
    address: int,
    scale: float,
    *,
    unit: str | None = None,
    writable: bool = False,
) -> LowByteField[float]: ...


def uint8(
    address: int,
    scale: float = 1.0,
    *,
    unit: str | None = None,
    writable: bool = False,
) -> LowByteField[int] | LowByteField[float]:
    """An unsigned 8-bit value in the low byte of a register."""
    return LowByteField(
        address,
        scale=scale,
        signed=False,
        nan=UINT8_NOT_AVAILABLE,
        unit=unit,
        writable=writable,
        force_fc16=writable,
    )


def enum8[E: IntEnum](
    address: int, enum_type: type[E], *, writable: bool = False, stride: int = 0
) -> LowByteField[E]:
    """An ENUM8 value in the low byte of a register."""
    return LowByteField(
        address,
        signed=False,
        convert=enum_type,
        nan=UINT8_NOT_AVAILABLE,
        stride=stride,
        writable=writable,
        force_fc16=writable,
    )


_BOOLEAN_CODES = {0: False, 1: True}


def bool8(address: int) -> LowByteField[bool]:
    """A 0/1 value in the low byte of a register, as ``bool``."""
    return LowByteField(
        address, signed=False, convert=_BOOLEAN_CODES, nan=UINT8_NOT_AVAILABLE
    )


def flags8[F: IntFlag](address: int, flag_type: type[F]) -> LowByteField[F]:
    """An 8-bit bitfield in the low byte of a register."""
    return LowByteField(address, signed=False, convert=flag_type)
