"""The top-level object for an appliance behind a GTW-08 Modbus gateway."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Self

from modbus_connection import (
    GatewayPathUnavailableError,
    GatewayTargetError,
    ModbusError,
)
from modbus_connection.model import (
    Component,
    ComponentGroup,
    Device,
    Raw,
    read_optional,
)

from .appliance import Appliance, HeatPumpPerformance, Service, SystemStatus
from .boards import BOARD_COUNT, Board, BoardSummary, BoardType, ErrorSummary
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
SETTINGS = ("system_control", "fallback", "zone_settings")


class NoApplianceError(ModbusError):
    """The gateway answered, but reports no appliance behind it."""


def _still_fetching(report: UpdateReport) -> bool:
    """Whether a component failed only because the gateway is still fetching."""
    return any(isinstance(err, GatewayTargetError) for err in report.failed.values())


class Gtw08Appliance(Device):
    """A heating appliance behind a GTW-08 gateway, reached through a ``ModbusUnit``."""

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        timeout: float | None = None,
        attempts: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        """Set up the sub-systems.

        ``attempts`` and ``retry_delay`` set how often setup asks again while
        the gateway is still fetching a block. They default to
        ``DETECT_ATTEMPTS`` and ``DETECT_RETRY_DELAY`` seconds.
        """
        super().__init__(unit)
        unit.require_timeout(timeout)
        self._attempts = DETECT_ATTEMPTS if attempts is None else attempts
        self._retry_delay = DETECT_RETRY_DELAY if retry_delay is None else retry_delay
        self._setup_lock = asyncio.Lock()

        self.summary = ErrorSummary(unit)
        self.system_status = SystemStatus(unit)
        self.appliance = Appliance(unit)
        self.service = Service(unit)

        # Filled in by setup with what this appliance has.
        self.board_count: int | None = None
        self.zone_count: int | None = None
        self.serial_number: int | None = None
        self.board_list: list[Board] = []
        self.boards: ComponentGroup | None = None
        self.heat_pump: HeatPumpPerformance | None = None
        self.zone_slots: dict[int, Zone] = {}
        self.zones: ComponentGroup | None = None
        self.zone_settings: ComponentGroup | None = None
        self.cascade: Cascade | None = None
        self.system_control: SystemControl | None = None
        self.fallback: Fallback | None = None
        self.detect_report: UpdateReport | None = None

    @classmethod
    async def async_detect(
        cls,
        unit: ModbusUnit,
        *,
        timeout: float | None = None,
        attempts: int | None = None,
        retry_delay: float | None = None,
    ) -> Self:
        """Set up the appliance behind the gateway and read it once.

        Asks again while the gateway is still fetching registers from the
        appliance. The last update's report is in ``detect_report``. Raises
        ``NoApplianceError`` when the gateway reports no appliance, and
        ``ModbusError`` when it does not answer.
        """
        device = cls(unit, timeout=timeout, attempts=attempts, retry_delay=retry_delay)
        last = device._attempts
        for attempt in range(1, last + 1):
            try:
                report = await device.async_update()
            except GatewayTargetError:
                if attempt == last:
                    raise
            else:
                device.detect_report = report
                if attempt == last or not _still_fetching(report):
                    break
            _LOGGER.debug("Gateway still fetching, attempt %d", attempt)
            await asyncio.sleep(device._retry_delay)
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

    async def async_ensure_setup(self) -> None:
        """Run setup once, even when two updates start together."""
        async with self._setup_lock:
            await super().async_ensure_setup()

    async def _async_setup(self) -> None:
        """Find the boards and zones, and settle which optional blocks exist."""
        unit = self.modbus_unit
        summary = BoardSummary(unit)
        try:
            await summary.async_update(notify=False)
        except GatewayPathUnavailableError as err:
            raise NoApplianceError(
                "the gateway sees no appliance on its L-Bus"
            ) from err
        if summary.board_count is None:
            raise GatewayTargetError(message="the gateway has no board count yet")
        if summary.board_count == 0:
            raise NoApplianceError("the gateway reports no control board")
        self.board_count = summary.board_count
        self.zone_count = summary.zone_count

        numbers = range(1, min(self.board_count, BOARD_COUNT) + 1)
        types = [BoardType(unit, number) for number in numbers]
        await ComponentGroup(unit, types).async_update(notify=False)
        self.board_list = [
            Board(unit, number, board_type.device_type)
            for number, board_type in zip(numbers, types, strict=True)
        ]
        self.boards = ComponentGroup(unit, self.board_list)

        self.heat_pump = await self._async_read_optional(HeatPumpPerformance(unit))
        self.system_control = await self._async_read_optional(SystemControl(unit))
        self.fallback = await self._async_read_optional(Fallback(unit))
        await self._async_find_cascade()
        await self._async_find_zones()
        _LOGGER.debug(
            "Appliance %s, serial number %s, boards %s, zones %s; readings: %s;"
            " settings: %s",
            self.model,
            self.serial_number,
            ", ".join(str(board.model) for board in self.board_list),
            ", ".join(
                f"{number} ({zone.function_code})"
                for number, zone in self.zone_slots.items()
            )
            or "none",
            ", ".join(self.readings_components),
            ", ".join(self.settings_components) or "nothing",
        )

    async def _async_read_optional[C: Component](self, component: C) -> C | None:
        """Read a block the appliance may lack; ``None`` if it does.

        A block the gateway keeps answering with "not fetched yet" counts as
        missing after the last attempt.
        """
        for attempt in range(1, self._attempts + 1):
            try:
                return await read_optional(component)
            except GatewayTargetError:
                if attempt == self._attempts:
                    _LOGGER.info(
                        "%s still not fetched after %d attempts, leaving it out",
                        type(component).__name__,
                        attempt,
                    )
                    return None
            await asyncio.sleep(self._retry_delay)
        return None

    async def _async_find_cascade(self) -> None:
        """Read the serial number, and keep the cascade block if it has producers."""
        unit = self.modbus_unit
        if (
            serial := await self._async_read_optional(ProducerSerial(unit))
        ) is not None:
            self.serial_number = serial.serial_number or None
        cascade = await self._async_read_optional(Cascade(unit))
        if cascade is not None and (cascade.producer_count or 0) > 1:
            self.cascade = cascade

    async def _async_find_zones(self) -> None:
        """Keep each zone with a function, up to the count the appliance reports."""
        count = self.zone_count
        last = ZONE_COUNT if count is None else min(count, ZONE_COUNT)
        found: dict[int, Zone] = {}
        for number in range(1, last + 1):
            zone = Zone(self.modbus_unit, number)
            if await self._async_read_optional(zone.config) is None:
                _LOGGER.info("Zone %d refuses its registers, leaving it out", number)
                continue
            if zone.is_configured:
                found[number] = zone
        self.zone_slots = found
        if not found:
            return
        zones = list(found.values())
        unit = self.modbus_unit
        self.zones = ComponentGroup(unit, [zone.readings for zone in zones])
        self.zone_settings = ComponentGroup(unit, [zone.settings for zone in zones])

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the appliance measures, and its zones."""
        await self.async_ensure_setup()
        return await self.async_poll(READINGS)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh the remote control, fallback and zone settings."""
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
