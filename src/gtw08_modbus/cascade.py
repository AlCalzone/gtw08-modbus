"""The cascade: several appliances that share one heat demand."""

from __future__ import annotations

from .enums import (
    ApplianceStatus,
    CascadeHeatDemand,
    CascadeManagement,
    CascadeMode,
    CascadeType,
)
from .model import Gtw08Component, bool8, enum8, int16, uint8, uint32


class Cascade(Gtw08Component):
    """The cascade's settings and measurements, registers 7001 to 7228."""

    mode = enum8(7001, CascadeMode)
    """Display code NP014."""
    cascade_type = enum8(7002, CascadeType)
    """Display code NP006."""
    management = enum8(7009, CascadeManagement)
    """Display code NP011."""
    flow_temperature = int16(7101, 0.01, unit="°C")
    """Display code NM001."""
    producer_count = uint8(7102)
    """Display code NM028: how many producers the cascade recognized."""
    stages_available = uint8(7103)
    """Display code NM022."""
    stages_required = uint8(7104)
    """Display code NM023."""
    power_request = uint8(7105, unit="%")
    temperature_request = int16(7106, 0.01, unit="°C")
    heat_demand_request = enum8(7107, CascadeHeatDemand)
    power_setpoint = uint8(7108, unit="%")
    temperature_setpoint = int16(7109, 0.01, unit="°C")
    heat_demand_setpoint = enum8(7110, CascadeHeatDemand)
    requested_power = uint32(7151, 0.1, unit="kW")
    """Display code NM112."""
    requested_power_percentage = int16(7155, 0.1, unit="%")
    """Display code NM170."""
    primary_pump_active = bool8(7157)
    """Display code NM166."""
    secondary_pump_active = bool8(7158)
    """Display code NM167."""
    state = enum8(7159, ApplianceStatus)
    """Display code NM163."""
    hours_ch = uint32(7160, unit="h")
    """Display code NC000: hours spent on central heating."""
    hours_dhw = uint32(7162, unit="h")
    """Display code NC001: hours spent on domestic hot water."""
    return_temperature = int16(7163, 0.01, unit="°C")
    """Display code NM165."""
    header_flow_temperature = int16(7168, 0.01, unit="°C")
    """Display code EM012: the flow on the secondary side of the low loss header."""
    header_return_temperature = int16(7169, 0.01, unit="°C")
    """Display code EM013: the return on the secondary side of the low loss header."""
    producer_status = enum8(7209, ApplianceStatus)
    """Display code EM058: the main status of this producer."""


class ProducerSerial(Gtw08Component):
    """The serial number of the producer the gateway is connected to."""

    serial_number = uint32(7228)
    """Display code EM228."""
