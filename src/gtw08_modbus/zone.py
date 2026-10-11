"""Zones: the heating circuits and hot water tanks the appliance serves."""

from __future__ import annotations

from typing import Any

from modbus_connection import ModbusUnit

from .enums import ZoneActivity, ZoneFunction, ZoneMode
from .model import Gtw08Component, bool8, enum8, int16, uint8, uint16, uint32

ZONE_COUNT = 12
# Zone n sits ZONE_STRIDE * (n - 1) registers after zone 1. Tables 33, 35 and
# 40 list a few addresses that break this step. Zone 11's register 7169 in
# table 33 even collides with the cascade. The step must stay because those
# entries look like typos.
ZONE_STRIDE = 512


class ZoneConfig(Gtw08Component):
    """What a zone is. Read once, at setup."""

    function_code = uint8(641)
    """Display code CP02X, undecoded."""
    device_type = uint16(645)
    """The board that drives the zone, coded like ``Board.device_type``."""


class ZoneSettings(Gtw08Component):
    """A zone's writable settings."""

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


class ZoneReadings(Gtw08Component):
    """What a zone measures and does right now."""

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


def zone_offset(number: int) -> int:
    """How far zone ``number``'s registers sit from zone 1's."""
    if not 1 <= number <= ZONE_COUNT:
        raise ValueError(f"no zone {number}")
    return ZONE_STRIDE * (number - 1)


class Zone:
    """One zone, numbered from 1 like the manual's tables.

    ``config`` is read once at setup, ``readings`` with the appliance's
    readings and ``settings`` with its settings.
    """

    def __init__(self, unit: ModbusUnit, number: int) -> None:
        """Place the zone's components at its own addresses."""
        offset = zone_offset(number)
        self.number = number
        self.config = ZoneConfig(unit, base_offset=offset)
        self.readings = ZoneReadings(unit, base_offset=offset)
        self.settings = ZoneSettings(unit, base_offset=offset)

    @property
    def function_code(self) -> int | None:
        """The zone's function as the appliance reports it, undecoded."""
        return self.config.function_code

    @property
    def function(self) -> ZoneFunction | None:
        """What the zone heats, or ``None`` for a code the manual does not list."""
        code = self.function_code
        if code is None or code not in ZoneFunction:
            return None
        return ZoneFunction(code)

    @property
    def is_configured(self) -> bool:
        """Whether the appliance reports a function other than disabled."""
        return self.function_code not in (None, ZoneFunction.DISABLED)

    @property
    def device_type(self) -> int | None:
        """The board that drives the zone."""
        return self.config.device_type

    @property
    def flow_temperature(self) -> float | None:
        """The flow temperature, or a DHW zone's tank temperature, in °C."""
        return self.readings.flow_temperature

    @property
    def flow_setpoint(self) -> float | None:
        """The flow temperature setpoint in effect, in °C."""
        return self.readings.flow_setpoint

    @property
    def room_setpoint(self) -> float | None:
        """The room temperature setpoint in effect, in °C."""
        return self.readings.room_setpoint

    @property
    def activity(self) -> ZoneActivity | None:
        """The zone's current activity."""
        return self.readings.activity

    @property
    def mode(self) -> ZoneMode | None:
        """The operating mode in effect."""
        return self.readings.mode

    @property
    def pump_running(self) -> bool | None:
        """Whether the zone's pump runs."""
        return self.readings.pump_running

    @property
    def pump_hours(self) -> int | None:
        """The pump's operating hours."""
        return self.readings.pump_hours

    @property
    def pump_starts(self) -> int | None:
        """How often the pump started."""
        return self.readings.pump_starts

    @property
    def flow_setpoint_fixed(self) -> float | None:
        """The flow temperature for a zone set to a fixed flow, in °C."""
        return self.settings.flow_setpoint_fixed

    @property
    def mode_setting(self) -> ZoneMode | None:
        """The operating mode set."""
        return self.settings.mode_setting

    @property
    def room_setpoint_manual(self) -> float | None:
        """The room temperature the zone holds in manual mode, in °C."""
        return self.settings.room_setpoint_manual

    @property
    def heating_curve_gradient(self) -> float | None:
        """The gradient of the heating curve."""
        return self.settings.heating_curve_gradient

    @property
    def heating_curve_footpoint(self) -> float | None:
        """The comfort footpoint of the heating curve, in °C."""
        return self.settings.heating_curve_footpoint

    async def write(self, field: str, value: Any) -> None:
        """Write a setting by name.

        Raises ``AttributeError`` for a field that is not a setting and
        ``ValueError`` for a value out of range.
        """
        await self.settings.write(field, value)

    async def async_write_mode(self, mode: ZoneMode) -> None:
        """Switch the zone to scheduling, manual or off."""
        if mode is ZoneMode.TEMPORARY:
            raise ValueError("a temporary override cannot be set over Modbus")
        await self.write("mode_setting", mode)

    async def async_write_room_setpoint(self, temperature: float) -> None:
        """Set the room temperature the zone holds in manual mode."""
        await self.write("room_setpoint_manual", temperature)

    async def async_write_heating_curve_gradient(self, gradient: float) -> None:
        """Set the gradient of the heating curve."""
        await self.write("heating_curve_gradient", gradient)

    async def async_write_heating_curve_footpoint(self, temperature: float) -> None:
        """Set the comfort footpoint of the heating curve, in °C."""
        await self.write("heating_curve_footpoint", temperature)

    async def async_write_flow_setpoint_fixed(self, temperature: float) -> None:
        """Set the flow temperature for a zone set to a fixed flow, in °C."""
        await self.write("flow_setpoint_fixed", temperature)
