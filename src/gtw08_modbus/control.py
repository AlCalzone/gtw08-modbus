"""Remote control of the system's heat demand, and what happens when it stops."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from modbus_connection import ModbusUnit

from .enums import (
    AnalogInputFunction,
    FallbackConfiguration,
    FallbackMode,
    HeatDemandType,
    RemoteControlMode,
    RemoteHeatDemand,
)
from .errors import InvalidValueError
from .model import Gtw08Component, enum8, int16, uint8, uint16

_LOGGER = logging.getLogger(__name__)


def _as_member[E: (RemoteControlMode, RemoteHeatDemand)](
    enum_type: type[E], value: object
) -> E:
    """Accept a member of ``enum_type`` and nothing else."""
    if not isinstance(value, enum_type):
        raise InvalidValueError(f"{value!r} is not a {enum_type.__name__}")
    return value


class SystemControl(Gtw08Component):
    """The system's temperature and power request, registers 256 to 259.

    While ``mode`` is anything other than ``MONITORING_ONLY``, the appliance
    ignores the heat demand of its zones.
    """

    def __init__(self, unit: ModbusUnit) -> None:
        """Set up the lock that keeps two requests from interleaving."""
        super().__init__(unit)
        self._lock = asyncio.Lock()

    power = uint8(256, unit="%", writable=True, maximum=100)
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
        for the temperature modes. ``STANDBY`` needs neither. Raises
        ``InvalidValueError`` when one the mode needs is missing. When a write
        fails, the gateway is put back to monitoring only and the error is
        raised.
        """
        mode = _as_member(RemoteControlMode, mode)
        heat_demand = _as_member(RemoteHeatDemand, heat_demand)
        if mode is RemoteControlMode.MONITORING_ONLY:
            raise InvalidValueError("use async_stop() to return to monitoring only")
        if heat_demand is not RemoteHeatDemand.STANDBY:
            if mode is not RemoteControlMode.TEMPERATURE and power is None:
                raise InvalidValueError(f"{mode.name} needs a power")
            if mode is not RemoteControlMode.POWER and temperature is None:
                raise InvalidValueError(f"{mode.name} needs a temperature")
        # Check every value before the first write, so a bad argument sends
        # nothing.
        if power is not None:
            self._validate("power", power)
        if temperature is not None:
            self._validate("temperature", temperature)

        async with self._lock:
            try:
                # The mode must go first because the gateway ignores registers
                # 256, 257 and 259 until 258 leaves monitoring only.
                await self.write("mode", mode)
                if power is not None:
                    await self.write("power", power)
                if temperature is not None:
                    await self.write("temperature", temperature)
                await self.write("heat_demand", heat_demand)
            except BaseException:
                # Roll back a failed mode write too because a write that timed
                # out may still have reached the gateway. The rollback runs
                # as its own task and must finish, even if this one is
                # cancelled again while it waits.
                rollback = asyncio.create_task(self._async_roll_back())
                while not rollback.done():
                    with contextlib.suppress(asyncio.CancelledError):
                        await asyncio.shield(rollback)
                raise

    def _validate(self, field: str, value: object) -> None:
        """Run a field's write check without writing."""
        validator = self.declared_fields[field].writable
        if callable(validator):
            validator(value)

    async def _async_roll_back(self) -> None:
        """Put the gateway back to monitoring only, logging a failure."""
        try:
            await self.write("mode", RemoteControlMode.MONITORING_ONLY)
        except Exception as err:
            _LOGGER.warning(
                "Could not put the gateway back to monitoring only: %s", err
            )

    async def async_stop(self) -> None:
        """Hand the heat demand back to the zones."""
        async with self._lock:
            await self.write("mode", RemoteControlMode.MONITORING_ONLY)


class Fallback(Gtw08Component):
    """What the gateway does when the BMS goes quiet, registers 21020 to 21027."""

    mode = enum8(21020, FallbackMode, writable=True)
    configuration = enum8(21021, FallbackConfiguration, writable=True)
    period = uint8(21022, unit="min", writable=True)
    """How long the BMS may stay quiet before the fallback starts."""
    power = uint8(21023, unit="%", writable=True, maximum=100)
    temperature = int16(21024, 0.01, unit="°C", writable=True)
    heat_demand = enum8(21025, HeatDemandType, writable=True)
    analog_input_function = enum8(21026, AnalogInputFunction, writable=True)
    """Display code EP014: what the smart control board's 0-10 V input controls."""
    analog_input_voltage = uint8(21027, 0.1, unit="V", writable=True, maximum=25)
    """Display code AM028."""

    async def async_write_mode(self, mode: FallbackMode) -> None:
        """Follow the controlling system, or the fallback heat demand."""
        await self.write("mode", mode)

    async def async_write_configuration(
        self, configuration: FallbackConfiguration
    ) -> None:
        """Set what happens when the controlling system goes quiet."""
        await self.write("configuration", configuration)

    async def async_write_period(self, minutes: int) -> None:
        """Set how long the controlling system may stay quiet."""
        await self.write("period", minutes)

    async def async_write_power(self, power: float) -> None:
        """Set the fallback power, in percent."""
        await self.write("power", power)

    async def async_write_temperature(self, temperature: float) -> None:
        """Set the fallback temperature, in °C."""
        await self.write("temperature", temperature)

    async def async_write_heat_demand(self, heat_demand: HeatDemandType) -> None:
        """Set the kind of fallback heat demand."""
        await self.write("heat_demand", heat_demand)

    async def async_write_analog_input_function(
        self, function: AnalogInputFunction
    ) -> None:
        """Set what the 0-10 V input controls."""
        await self.write("analog_input_function", function)

    async def async_write_analog_input_voltage(self, voltage: float) -> None:
        """Set the value of the 0-10 V input, in V."""
        await self.write("analog_input_voltage", voltage)
