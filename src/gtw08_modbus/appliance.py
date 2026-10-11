"""The main appliance: its measurements, counters and service state."""

from __future__ import annotations

from .enums import (
    ApplianceStatus,
    ApplianceSubStatus,
    GeneratorStatus,
    HeatDemandStatus,
    HydraulicStatus,
    SeasonMode,
    ServiceNotification,
)
from .model import (
    Gtw08Component,
    bool8,
    enum8,
    flags8,
    int16,
    uint8,
    uint16,
    uint32,
)


class SystemStatus(Gtw08Component):
    """What the whole system does, registers 272 to 385."""

    system_power = uint8(272, unit="%")
    """The power the consumer manager of the zones asks for."""
    heat_demand = flags8(275, HeatDemandStatus)
    error_list = uint16(277)
    """The manual calls this the "list of errors for all connected devices"."""
    generator_status = flags8(279, GeneratorStatus)
    hydraulic_status = flags8(280, HydraulicStatus)
    outdoor_temperature = int16(384, 0.01, unit="°C")
    season_mode = enum8(385, SeasonMode)


class Appliance(Gtw08Component):
    """The main appliance's temperatures, status and counters, registers 400 to 461."""

    flow_temperature = int16(400, 0.01, unit="°C")
    """Display code AM016."""
    return_temperature = int16(401, 0.01, unit="°C")
    """Display code AM018."""
    flue_gas_temperature = int16(402, 0.01, unit="°C")
    """Display code AM036. Boilers only."""
    heat_pump_flow_temperature = int16(403, 0.01, unit="°C")
    """Display code HM001. Heat pumps only."""
    heat_pump_return_temperature = int16(404, 0.01, unit="°C")
    """Display code HM002. Heat pumps only."""
    dhw_setpoint = uint16(408, 0.01, unit="°C")
    """Display code DM004: the flow temperature setpoint for domestic hot water."""
    water_pressure = uint8(409, 0.1, unit="bar")
    """Display code AM019: the pressure of the primary circuit."""
    status = enum8(411, ApplianceStatus)
    """Display code AM012."""
    sub_status = enum8(412, ApplianceSubStatus, nan=None)
    """Display code AM014. Code 255 is a real state: out of safety unit resets."""
    relative_power = uint16(413, unit="%")
    """Display code AM024."""
    generator_starts = uint32(419)
    """Display code PC002: starts for heating and domestic hot water."""
    generator_hours = uint32(421, unit="h")
    """Display code PC003: hours producing heat for heating and domestic hot water."""
    backup_1_starts = uint32(423)
    """Display code AC030."""
    backup_1_hours = uint32(425, unit="h")
    """Display code AC028."""
    backup_2_starts = uint32(427)
    """Display code AC031."""
    backup_2_hours = uint32(429, unit="h")
    """Display code AC029."""
    mains_hours = uint32(431, unit="h")
    """Display code AC001: hours on mains power."""
    energy_consumed_ch = uint32(433, unit="kWh")
    """Display code AC005."""
    energy_consumed_dhw = uint32(435, unit="kWh")
    """Display code AC006."""
    energy_consumed_cooling = uint32(437, unit="kWh")
    """Display code AC007."""
    energy_consumed_total = uint32(439, unit="kWh")
    energy_consumed_backup = uint32(441, unit="kWh")
    """Display code AC018."""
    energy_delivered_total = uint32(443, unit="kWh")
    energy_delivered_ch = uint32(445, unit="kWh")
    """Display code AC008."""
    energy_delivered_dhw = uint32(447, unit="kWh")
    """Display code AC009."""
    energy_delivered_cooling = uint32(449, unit="kWh")
    """Display code AC010."""
    energy_delivered_backup = uint32(451, unit="kWh")
    """Display code AC019: delivered by the electrical or hydraulic backup."""
    pump_speed = uint16(459, 0.1, unit="%")
    """Display code AM010."""
    actual_power = uint32(460, 0.01, unit="kW")
    """Display code AM047."""


class HeatPumpPerformance(Gtw08Component):
    """The coefficient of performance, registers 9230 and 9231. Heat pumps only."""

    cop = uint16(9230, 0.001)
    """Display code HM031: the calculated instantaneous COP."""
    cop_threshold = uint16(9231, 0.001)
    """Display code HM032: the COP below which a hybrid switches to the boiler."""


class Service(Gtw08Component):
    """Service state and counters, registers 512 to 517."""

    service_required = bool8(512)
    """Display code AM011."""
    notification = enum8(513, ServiceNotification)
    """The current or upcoming service notification."""
    # The manual gives registers 514 and 515 a resolution of "2 hours". It is
    # unclear whether that is a factor, so they are read as plain hours until
    # a real appliance settles it.
    hours_producing_since_service = uint16(514, unit="h")
    """Display code AC002."""
    hours_since_service = uint16(515, unit="h")
    """Display code AC003."""
    starts_since_service = uint32(516)
    """Display code AC004."""
