"""The top-level object for an appliance behind a GTW-08 Modbus gateway."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Self

from modbus_connection import GatewayTargetError
from modbus_connection.model import ComponentGroup, Device, Raw, read_optional

from .appliance import Appliance, HeatPumpPerformance, Service, SystemStatus
from .boards import BOARD_COUNT, Board, BoardSummary
from .cascade import Cascade, ProducerSerial
from .control import Fallback, SystemControl
from .model import UpdateReport
from .zone import ZONE_COUNT, Zone

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_LOGGER = logging.getLogger(__name__)

DEFAULT_UNIT_ID = 100
"""The gateway's address with its rotary dial at 0. Positions 1 to F add 1 to 15."""

# The gateway answers a register it has not fetched from the appliance yet
# with exception 0x0B. It has the value on a later try.
DETECT_ATTEMPTS = 5
DETECT_RETRY_DELAY = 2.0

READINGS = (
    "summary",
    "system_status",
    "appliance",
    "heat_pump",
    "service",
    "boards",
    "zones",
    "cascade",
)
SETTINGS = ("system_control", "fallback")


class NoApplianceError(Exception):
    """The gateway answered, but reports no control board behind it."""


class Gtw08Appliance(Device):
    """A heating appliance behind a GTW-08 gateway, reached through a ``ModbusUnit``."""

    def __init__(self, unit: ModbusUnit, *, timeout: float | None = None) -> None:
        """Set up the sub-systems."""
        super().__init__(unit)
        unit.require_timeout(timeout)

        self.summary = BoardSummary(unit)
        self.system_status = SystemStatus(unit)
        self.appliance = Appliance(unit)
        self.service = Service(unit)

        # Filled in by setup with what this appliance has.
        self.board_list: list[Board] = []
        self.boards: ComponentGroup | None = None
        self.heat_pump: HeatPumpPerformance | None = None
        self.zone_slots: dict[int, Zone] = {}
        self.zones: ComponentGroup | None = None
        self.cascade: Cascade | None = None
        self.system_control: SystemControl | None = None
        self.fallback: Fallback | None = None
        self.serial_number: int | None = None

    @classmethod
    async def async_detect(
        cls,
        unit: ModbusUnit,
        *,
        timeout: float | None = None,
        attempts: int = DETECT_ATTEMPTS,
        retry_delay: float = DETECT_RETRY_DELAY,
    ) -> Self:
        """Set up the appliance behind the gateway and read it once.

        Retries while the gateway is still fetching registers from the
        appliance. Raises ``NoApplianceError`` when the gateway reports no
        board, and ``ModbusError`` when it does not answer.
        """
        device = cls(unit, timeout=timeout)
        for attempt in range(1, attempts + 1):
            try:
                await device.async_update()
            except GatewayTargetError:
                if attempt == attempts:
                    raise
                _LOGGER.debug("Gateway still fetching, attempt %d", attempt)
                await asyncio.sleep(retry_delay)
            else:
                break
        return device

    @property
    def model(self) -> str | None:
        """The main control board's name, such as ``EHC-04``."""
        if not self.board_list:
            return None
        return self.board_list[0].model

    @property
    def readings_components(self) -> tuple[str, ...]:
        """Reading component names this device polls; partial before setup."""
        return tuple(name for name in READINGS if getattr(self, name) is not None)

    @property
    def settings_components(self) -> tuple[str, ...]:
        """Settings component names this device polls; empty before setup."""
        return tuple(name for name in SETTINGS if getattr(self, name) is not None)

    async def _async_setup(self) -> None:
        """Find the boards and zones, and settle which optional blocks exist."""
        unit = self.modbus_unit
        await self.summary.async_update(notify=False)
        board_count = self.summary.board_count
        if not board_count:
            raise NoApplianceError("the gateway reports no control board")

        boards = [
            Board(unit, number)
            for number in range(1, min(board_count, BOARD_COUNT) + 1)
        ]
        group = ComponentGroup(unit, boards)
        await group.async_update(notify=False)
        self.board_list, self.boards = boards, group

        self.heat_pump = await read_optional(HeatPumpPerformance(unit))
        self.system_control = await read_optional(SystemControl(unit))
        self.fallback = await read_optional(Fallback(unit))
        await self._async_find_cascade()
        await self._async_find_zones()
        _LOGGER.debug(
            "Appliance %s, serial number %s, boards %s, zones %s; readings: %s;"
            " settings: %s",
            self.model,
            self.serial_number,
            ", ".join(str(board.model) for board in self.board_list),
            ", ".join(
                f"{number} ({zone.function.name if zone.function else '?'})"
                for number, zone in self.zone_slots.items()
            )
            or "none",
            ", ".join(self.readings_components),
            ", ".join(self.settings_components) or "nothing",
        )

    async def _async_find_cascade(self) -> None:
        """Read the serial number, and keep the cascade block if it has producers."""
        unit = self.modbus_unit
        if (serial := await read_optional(ProducerSerial(unit))) is not None:
            self.serial_number = serial.serial_number or None
        cascade = await read_optional(Cascade(unit))
        if cascade is not None and (cascade.producer_count or 0) > 1:
            self.cascade = cascade

    async def _async_find_zones(self) -> None:
        """Keep each zone with a function, up to the count the appliance reports."""
        count = self.summary.zone_count
        last = ZONE_COUNT if count is None else min(count, ZONE_COUNT)
        found: dict[int, Zone] = {}
        for number in range(1, last + 1):
            zone = await read_optional(Zone(self.modbus_unit, number))
            if zone is None:
                _LOGGER.debug("Zone %d refuses its registers", number)
                continue
            if zone.is_configured:
                found[number] = zone
        self.zone_slots = found
        self.zones = (
            ComponentGroup(self.modbus_unit, list(found.values())) if found else None
        )

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the appliance measures, and its zones."""
        await self.async_ensure_setup()
        return await self.async_poll(READINGS)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh the remote control and fallback registers."""
        await self.async_ensure_setup()
        return await self.async_poll(SETTINGS)

    async def async_update(self) -> UpdateReport:
        """Refresh readings and settings together in one report."""
        await self.async_ensure_setup()
        return await self.async_poll((*READINGS, *SETTINGS))

    async def async_read_raw(self, names: Iterable[str] | None = None) -> Raw:
        """Every register this device reads, undecoded, for diagnostics."""
        if names is None:
            names = (*READINGS, *SETTINGS)
        return await super().async_read_raw(names)
