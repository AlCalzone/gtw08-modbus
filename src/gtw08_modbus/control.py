"""Remote control of the system's heat demand, and what happens when it stops."""

from __future__ import annotations

from .enums import (
    AnalogInputFunction,
    FallbackConfiguration,
    FallbackMode,
    HeatDemandType,
    RemoteControlMode,
    RemoteHeatDemand,
)
from .model import Gtw08Component, enum8, int16, uint8, uint16


class SystemControl(Gtw08Component):
    """The system's temperature and power request, registers 256 to 259.

    While ``mode`` is anything other than ``MONITORING_ONLY``, the appliance
    ignores the heat demand of its zones.
    """

    power = uint8(256, unit="%", writable=True)
    """The requested power, between the system's minimum (0) and maximum (100)."""
    temperature = uint16(257, 0.01, unit="°C", writable=True)
    """The requested flow temperature."""
    mode = enum8(258, RemoteControlMode, writable=True)
    heat_demand = enum8(259, RemoteHeatDemand, writable=True)

    async def async_request(
        self,
        mode: RemoteControlMode,
        heat_demand: RemoteHeatDemand,
        *,
        power: float | None = None,
        temperature: float | None = None,
    ) -> None:
        """Take over the heat demand.

        Pass ``power`` in percent for the power modes and ``temperature`` in °C
        for the temperature modes. Raises ``ValueError`` when one the mode
        needs is missing.
        """
        if mode is RemoteControlMode.MONITORING_ONLY:
            raise ValueError("use async_stop() to return to monitoring only")
        needs_power = mode in (
            RemoteControlMode.TEMPERATURE_AND_POWER,
            RemoteControlMode.POWER,
        )
        needs_temperature = mode in (
            RemoteControlMode.TEMPERATURE_AND_POWER,
            RemoteControlMode.TEMPERATURE,
        )
        if needs_power and power is None:
            raise ValueError(f"{mode.name} needs a power")
        if needs_temperature and temperature is None:
            raise ValueError(f"{mode.name} needs a temperature")

        # The gateway ignores registers 256, 257 and 259 until 258 leaves
        # monitoring only, so the mode must go first.
        await self.write("mode", mode)
        if power is not None:
            await self.write("power", power)
        if temperature is not None:
            await self.write("temperature", temperature)
        await self.write("heat_demand", heat_demand)

    async def async_stop(self) -> None:
        """Hand the heat demand back to the zones."""
        await self.write("mode", RemoteControlMode.MONITORING_ONLY)


class Fallback(Gtw08Component):
    """What the gateway does when the BMS goes quiet, registers 21020 to 21027."""

    mode = enum8(21020, FallbackMode, writable=True)
    configuration = enum8(21021, FallbackConfiguration, writable=True)
    period = uint8(21022, unit="min", writable=True)
    """How long the BMS may stay quiet before the fallback starts."""
    power = uint8(21023, unit="%", writable=True)
    temperature = int16(21024, 0.01, unit="°C", writable=True)
    heat_demand = enum8(21025, HeatDemandType, writable=True)
    analog_input_function = enum8(21026, AnalogInputFunction, writable=True)
    """Display code EP014: what the smart control board's 0-10 V input controls."""
    analog_input_voltage = uint8(21027, 0.1, unit="V", writable=True)
    """Display code AM028."""
