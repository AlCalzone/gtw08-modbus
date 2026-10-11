"""Zones: the heating circuits and hot water tanks the appliance serves."""

from __future__ import annotations

from modbus_connection import ModbusUnit

from .enums import ZoneActivity, ZoneFunction, ZoneMode
from .model import Gtw08Component, bool8, enum8, int16, uint8, uint16, uint32

ZONE_COUNT = 12
ZONE_STRIDE = 512
"""How far apart two zones' registers are."""


class Zone(Gtw08Component):
    """One zone, numbered from 1 like the manual's tables.

    The fields carry zone 1's addresses. Zone ``number`` sits
    ``ZONE_STRIDE * (number - 1)`` registers further on.
    """

    def __init__(self, unit: ModbusUnit, number: int) -> None:
        """Place the zone's fields at its own addresses."""
        if not 1 <= number <= ZONE_COUNT:
            raise ValueError(f"no zone {number}")
        super().__init__(unit, base_offset=ZONE_STRIDE * (number - 1))
        self.number = number

    function = enum8(641, ZoneFunction)
    """Display code CP02X."""
    device_type = uint16(645)
    """The board that drives the zone, coded like ``Board.device_type``."""
    flow_setpoint_fixed = uint16(648, 0.01, unit="°C", writable=True)
    """Display code CP01X: the flow temperature for a zone set to a fixed flow."""
    mode_setting = enum8(649, ZoneMode, writable=True)
    """Display code CP32X. Takes ``SCHEDULING``, ``MANUAL`` or ``OFF``."""
    room_setpoint_manual = uint16(664, 0.1, unit="°C", writable=True)
    """Display code CP20X: the room temperature the zone holds in manual mode."""
    heating_curve_gradient = uint8(674, 0.1, writable=True)
    """Display code CP23X."""
    heating_curve_footpoint = uint16(675, 0.1, unit="°C", writable=True)
    """Display code CP21X: the comfort footpoint of the heating curve."""

    flow_temperature = int16(1100, 0.01, unit="°C")
    """Display code CM04X: the flow temperature, or a DHW zone's tank temperature."""
    flow_setpoint = uint16(1101, 0.01, unit="°C")
    """Display code CM07X: the flow temperature setpoint in effect."""
    room_setpoint = int16(1102, 0.1, unit="°C")
    """Display code CM19X: the room temperature setpoint in effect."""
    activity = enum8(1107, ZoneActivity)
    """Display code CM13X."""
    mode = enum8(1108, ZoneMode)
    """Display code CM12X: the operating mode in effect."""
    pump_running = bool8(1110)
    """Display code CM05X."""
    pump_hours = uint32(1115, unit="h")
    """Display code CC00X."""
    pump_starts = uint32(1117)
    """Display code CC01X."""

    @property
    def is_configured(self) -> bool:
        """Whether the zone has a function other than disabled."""
        return self.function not in (None, ZoneFunction.DISABLED)

    async def async_write_mode(self, mode: ZoneMode) -> None:
        """Switch the zone to scheduling, manual or off."""
        if mode is ZoneMode.TEMPORARY:
            raise ValueError("a temporary override cannot be set over Modbus")
        await self.write("mode_setting", mode)

    async def async_write_room_setpoint(self, temperature: float) -> None:
        """Set the room temperature the zone holds in manual mode."""
        await self.write("room_setpoint_manual", temperature)
