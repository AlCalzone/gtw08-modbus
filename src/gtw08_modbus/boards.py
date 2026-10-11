"""The control boards in the appliance, and the error each one reports."""

from __future__ import annotations

from modbus_connection import ModbusUnit
from modbus_connection.model import raw_register

from .enums import BoardCategory, ErrorType
from .model import Gtw08Component, bool8, enum8, uint8

BOARD_COUNT = 8

NO_ERROR = 0xFFFF
BOARD_NOT_AVAILABLE = 0xFFFE


_MODEL_PREFIXES = {
    BoardCategory.CU_GH: "CU-GH",
    BoardCategory.CU_OH: "CU-OH",
    BoardCategory.EHC: "EHC-",
    BoardCategory.MK: "MK-",
    BoardCategory.SCB: "SCB-",
    BoardCategory.EEC: "EEC-",
    BoardCategory.GATEWAY: "GTW-",
}


def board_model(device_type: int | None) -> str | None:
    """Name a board by its device type: ``0x0008`` is a ``CU-GH08``.

    The high byte is the category and the low byte the number within it.
    """
    if device_type is None:
        return None
    category, number = device_type >> 8, device_type & 0xFF
    try:
        prefix = _MODEL_PREFIXES[BoardCategory(category)]
    except ValueError:
        return f"0x{device_type:04X}"
    return f"{prefix}{number:02d}"


class BoardSummary(Gtw08Component):
    """How many boards there are and whether any reports an error."""

    board_count = uint8(128)
    """How many control boards are connected, 0 to 16."""
    zone_count = uint8(189)
    """How many zones the appliance detected."""
    any_error = bool8(531)
    """At least one board reports an error."""


class Board(Gtw08Component):
    """One of the first eight control boards, numbered from 1."""

    def __init__(self, unit: ModbusUnit, number: int) -> None:
        """Place the board's fields at its own addresses."""
        if not 1 <= number <= BOARD_COUNT:
            raise ValueError(f"no board {number}")
        super().__init__(unit, index=number)
        self.number = number

    device_type = raw_register(129, stride=6)
    """The category in the high byte and the number in it in the low byte."""
    raw_error_code = raw_register(532, stride=2)
    _error_type = enum8(533, ErrorType, stride=2)

    @property
    def model(self) -> str | None:
        """The board's name, such as ``CU-GH08`` or ``SCB-10``."""
        return board_model(self.device_type)

    @property
    def is_available(self) -> bool:
        """Whether the board answers the gateway."""
        return self.raw_error_code not in (None, BOARD_NOT_AVAILABLE)

    @property
    def error_code(self) -> int | None:
        """The board's error code, or ``None`` without an error."""
        code = self.raw_error_code
        if code in (None, NO_ERROR, BOARD_NOT_AVAILABLE):
            return None
        return code

    @property
    def error_type(self) -> ErrorType | None:
        """How serious the board's error is, or ``None`` without an error."""
        if self.error_code is None:
            return None
        return self._error_type
