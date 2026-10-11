"""Fixtures: a heat pump behind a GTW-08, on modbus-connection's in-memory mock."""

from __future__ import annotations

import pytest
from modbus_connection.mock import MockModbusUnit

from gtw08_modbus import Gtw08Appliance


def int16(value: int) -> int:
    """A signed 16-bit value as the register holds it."""
    return value & 0xFFFF


def uint32_words(value: int) -> list[int]:
    """A uint32, high word first."""
    return [value >> 16, value & 0xFFFF]


def zone(
    number: int, registers: dict[int, int | list[int]]
) -> dict[int, int | list[int]]:
    """Shift zone 1's register numbers to zone ``number``."""
    return {address + 512 * (number - 1): value for address, value in registers.items()}


SERIAL_NUMBER = 2312345678

# An EHC-04 heat pump with an SCB-04, as in the manual's table 31: zone 1 a
# direct circuit and zone 2 the hot water tank on the EHC-04, zone 3 a mixing
# circuit on the SCB-04.
HOLDING: dict[int, int | list[int]] = {
    # -- remote control: monitoring only --
    256: 0,
    257: 0,
    258: 3,
    259: 0,
    # -- system status --
    272: 45,
    275: 0b1000001,  # direct zones allowed, heat engine active
    277: 0,
    279: 0b00000010,  # heat pump on
    280: 0b0100001,  # pump on, central heating active
    384: int16(-350),  # -3.5 °C
    385: 0,  # winter
    # -- boards --
    128: 2,
    129: 0x0204,  # EHC-04
    135: 0x1904,  # SCB-04
    189: 3,
    531: 0,
    532: [0xFFFF, 0, 0xFFFF, 0],
    # -- appliance --
    400: 3512,
    401: 3020,
    402: 0x7FFF,  # no flue gas sensor on a heat pump
    403: 3580,
    404: 3050,
    408: 5000,
    409: 0xFF00 | 18,  # 1.8 bar, with junk in the high byte
    411: 3,  # running for central heating
    412: 30,
    413: 62,
    419: uint32_words(1234),
    421: uint32_words(5678),
    423: uint32_words(12),
    425: uint32_words(34),
    427: uint32_words(0),
    429: uint32_words(0),
    431: uint32_words(20000),
    433: uint32_words(3100),
    435: uint32_words(900),
    437: uint32_words(50),
    439: uint32_words(4050),
    441: uint32_words(120),
    443: uint32_words(13200),
    445: uint32_words(10100),
    447: uint32_words(2900),
    449: uint32_words(200),
    451: uint32_words(110),
    459: 655,  # 65.5 %
    460: uint32_words(512),  # 5.12 kW
    # -- service --
    512: 0,
    513: 1,
    514: 1500,
    515: 4000,
    516: uint32_words(321),
    # -- heat pump performance --
    9230: 4210,
    9231: 2500,
    # -- serial number --
    7228: uint32_words(SERIAL_NUMBER),
    # -- fallback --
    21020: 0,
    21021: 0,
    21022: 10,
    21023: 50,
    21024: 4500,
    21025: 7,
    21026: 0,
    21027: 0,
    # -- zones --
    **zone(
        1,
        {
            641: 1,  # direct
            645: 0x0204,
            648: 4000,
            649: 0,
            664: 210,
            674: 15,
            675: 200,
            1100: 3480,
            1101: 3500,
            1102: 205,
            1107: 2,
            1108: 0,
            1110: 1,
            1115: uint32_words(4321),
            1117: uint32_words(876),
        },
    ),
    **zone(
        2,
        {
            641: 6,  # DHW tank
            645: 0x0204,
            648: 0,
            649: 1,
            664: 550,
            674: 0,
            675: 0,
            1100: 4890,
            1101: 5500,
            1102: 550,
            1107: 1,
            1108: 1,
            1110: 0,
            1115: uint32_words(100),
            1117: uint32_words(20),
        },
    ),
    **zone(
        3,
        {
            641: 2,  # mixing circuit
            645: 0x1904,
            648: 0,
            649: 2,
            664: 190,
            674: 8,
            675: 180,
            1100: 2210,
            1101: 0,
            1102: 60,
            1107: 0,
            1108: 2,
            1110: 0,
            1115: uint32_words(0),
            1117: uint32_words(0),
        },
    ),
}


def seed(unit: MockModbusUnit, holding: dict[int, int | list[int]] = HOLDING) -> None:
    """Load register values into the mock."""
    for address, value in holding.items():
        unit.holding[address] = value


@pytest.fixture
def appliance(mock_modbus_unit: MockModbusUnit) -> Gtw08Appliance:
    """An EHC-04 heat pump with an SCB-04 and three zones."""
    seed(mock_modbus_unit)
    return Gtw08Appliance(mock_modbus_unit)
