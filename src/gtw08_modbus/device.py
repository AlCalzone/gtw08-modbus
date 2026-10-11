"""The top-level object for an appliance behind a GTW-08 Modbus gateway."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Self

from modbus_connection import GatewayPathUnavailableError, GatewayTargetError
from modbus_connection.model import (
    ComponentGroup,
    Device,
    Raw,
    read_optional,
)

from .appliance import Appliance, HeatPumpPerformance, Service, SystemStatus
from .boards import BOARD_COUNT, Board, BoardSummary, BoardType, ErrorSummary
from .cascade import Cascade, ProducerSerial
from .control import Fallback, SystemControl
from .errors import GatewayNotReadyError, InvalidValueError, NoApplianceError
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
# What setup reads once. Only async_read_raw() reads these again.
SETUP = ("_setup_summary", "_board_types", "_zone_configs")

# A probe returns whether it settled the block: found, or known to be absent.
type _Probe = Callable[[], Awaitable[bool]]


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
        the gateway is still fetching. They default to ``DETECT_ATTEMPTS`` and
        ``DETECT_RETRY_DELAY`` seconds. Raises ``InvalidValueError`` for fewer
        than one attempt.
        """
        super().__init__(unit)
        attempts = DETECT_ATTEMPTS if attempts is None else attempts
        if attempts < 1:
            raise InvalidValueError(f"attempts must be at least 1, not {attempts}")
        if timeout is not None:
            unit.require_timeout(timeout)
        self._attempts = attempts
        self._retry_delay = DETECT_RETRY_DELAY if retry_delay is None else retry_delay
        self._setup_lock = asyncio.Lock()
        self._pending: dict[str, _Probe] = {}

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
        self._setup_summary: BoardSummary | None = None
        self._board_types: ComponentGroup | None = None
        self._zone_configs: ComponentGroup | None = None

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
        ``NoApplianceError`` when the gateway reports no appliance,
        ``GatewayNotReadyError`` when it still has no board count after the
        last attempt, and ``ModbusError`` when it does not answer.
        """
        device = cls(unit, timeout=timeout, attempts=attempts, retry_delay=retry_delay)
        last = device._attempts
        for attempt in range(1, last + 1):
            try:
                report = await device.async_update()
            except (GatewayTargetError, GatewayNotReadyError):
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

    @property
    def pending_blocks(self) -> tuple[str, ...]:
        """Optional blocks the gateway was still fetching when setup gave up.

        Every update asks for them once more. A block found that way appears
        in ``readings_components`` or ``settings_components``, or in
        ``zone_slots`` for a zone.
        """
        return tuple(self._pending)

    async def async_ensure_setup(self) -> None:
        """Run setup once, even when two updates start together."""
        async with self._setup_lock:
            await super().async_ensure_setup()

    async def _async_setup(self) -> None:
        """Find the boards and zones, and settle which optional blocks exist."""
        try:
            await self._async_setup_once()
        except GatewayPathUnavailableError as err:
            raise NoApplianceError(
                "the gateway sees no appliance on its L-Bus"
            ) from err

    async def _async_setup_once(self) -> None:
        """Run setup; ``_async_setup`` turns a lost L-Bus into ``NoApplianceError``."""
        unit = self.modbus_unit
        summary = BoardSummary(unit)
        await summary.async_update(notify=False)
        if summary.board_count is None:
            raise GatewayNotReadyError("the gateway has no board count yet")
        if summary.board_count == 0:
            raise NoApplianceError("the gateway reports no control board")
        self._setup_summary = summary
        self.board_count = summary.board_count
        self.zone_count = summary.zone_count

        numbers = range(1, min(self.board_count, BOARD_COUNT) + 1)
        types = [BoardType(unit, number) for number in numbers]
        self._board_types = ComponentGroup(unit, types)
        await self._board_types.async_update(notify=False)
        self.board_list = [
            Board(unit, number, board_type.device_type)
            for number, board_type in zip(numbers, types, strict=True)
        ]
        self.boards = ComponentGroup(unit, self.board_list)

        # One deadline covers every optional block, so a gateway that answers
        # "not fetched yet" for blocks the appliance lacks cannot stall setup.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (self._attempts - 1) * self._retry_delay
        probes: dict[str, _Probe] = {
            "heat_pump": self._probe_heat_pump,
            "system_control": self._probe_system_control,
            "fallback": self._probe_fallback,
            "serial_number": self._probe_serial_number,
            "cascade": self._probe_cascade,
        }
        last = (
            ZONE_COUNT if self.zone_count is None else min(self.zone_count, ZONE_COUNT)
        )
        for number in range(1, last + 1):
            probes[f"zone_{number}"] = self._zone_probe(number)
        for name, probe in probes.items():
            while not await self._async_settle(name, probe):
                if loop.time() + self._retry_delay > deadline:
                    _LOGGER.warning(
                        "%s is still not fetched; asking again with every update",
                        name,
                    )
                    self._pending[name] = probe
                    break
                await asyncio.sleep(self._retry_delay)

        _LOGGER.debug(
            "Appliance %s, serial number %s, boards %s, zones %s; readings: %s;"
            " settings: %s; pending: %s",
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
            ", ".join(self._pending) or "nothing",
        )

    async def _async_settle(self, name: str, probe: _Probe) -> bool:
        """Run one probe; ``False`` while the gateway is still fetching."""
        try:
            return await probe()
        except GatewayTargetError:
            _LOGGER.debug("%s not fetched yet", name)
            return False

    async def _async_probe_pending(self) -> None:
        """Ask once more for each block setup gave up on."""
        for name, probe in list(self._pending.items()):
            if await self._async_settle(name, probe):
                _LOGGER.info("%s answered after setup", name)
                del self._pending[name]

    async def _probe_heat_pump(self) -> bool:
        self.heat_pump = await read_optional(HeatPumpPerformance(self.modbus_unit))
        return True

    async def _probe_system_control(self) -> bool:
        self.system_control = await read_optional(SystemControl(self.modbus_unit))
        return True

    async def _probe_fallback(self) -> bool:
        self.fallback = await read_optional(Fallback(self.modbus_unit))
        return True

    async def _probe_serial_number(self) -> bool:
        serial = await read_optional(ProducerSerial(self.modbus_unit))
        if serial is not None:
            self.serial_number = serial.serial_number or None
        return True

    async def _probe_cascade(self) -> bool:
        """Keep the cascade block if it has two producers or more."""
        cascade = await read_optional(Cascade(self.modbus_unit))
        if cascade is not None and (cascade.producer_count or 0) > 1:
            self.cascade = cascade
        return True

    def _zone_probe(self, number: int) -> _Probe:
        """Keep zone ``number`` if the appliance reports a function for it."""

        async def probe() -> bool:
            zone = Zone(self.modbus_unit, number)
            if await read_optional(zone.config) is None:
                _LOGGER.info("Zone %d refuses its registers, leaving it out", number)
                return True
            if zone.is_configured:
                self._add_zone(zone)
            return True

        return probe

    def _add_zone(self, zone: Zone) -> None:
        """Add a zone and rebuild the groups that poll the zones."""
        self.zone_slots = dict(sorted({**self.zone_slots, zone.number: zone}.items()))
        zones = list(self.zone_slots.values())
        unit = self.modbus_unit
        self.zones = ComponentGroup(unit, [zone.readings for zone in zones])
        self.zone_settings = ComponentGroup(unit, [zone.settings for zone in zones])
        self._zone_configs = ComponentGroup(unit, [zone.config for zone in zones])

    async def _async_prepare(self) -> None:
        """Set up, then ask again for the blocks setup gave up on."""
        await self.async_ensure_setup()
        if self._pending:
            async with self._setup_lock:
                await self._async_probe_pending()

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the appliance measures, and its zones."""
        await self._async_prepare()
        return await self.async_poll(READINGS)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh the remote control, fallback and zone settings."""
        await self._async_prepare()
        return await self.async_poll(SETTINGS)

    async def async_update(self) -> UpdateReport:
        """Refresh readings and settings together in one report."""
        await self._async_prepare()
        return await self.async_poll((*READINGS, *SETTINGS))

    async def async_read_raw(self, names: Iterable[str] | None = None) -> Raw:
        """Every register this device reads, setup included, undecoded."""
        if names is None:
            names = (*SETUP, *READINGS, *SETTINGS)
        return await super().async_read_raw(names)
