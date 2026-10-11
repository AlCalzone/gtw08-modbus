"""Every declared field against the value the manual's scale gives for the seed."""

from __future__ import annotations

from typing import Any

from modbus_connection.model import Component

from gtw08_modbus import (
    AnalogInputFunction,
    ApplianceStatus,
    ApplianceSubStatus,
    CascadeHeatDemand,
    CascadeManagement,
    CascadeMode,
    CascadeType,
    ErrorType,
    FallbackConfiguration,
    FallbackMode,
    GeneratorStatus,
    Gtw08Appliance,
    HeatDemandStatus,
    HeatDemandType,
    HydraulicStatus,
    RemoteControlMode,
    RemoteHeatDemand,
    SeasonMode,
    ServiceNotification,
    ZoneActivity,
    ZoneMode,
)

# Written from the manual's tables, not from the code: the seeded raw value
# with the table's resolution applied.
EXPECTED: dict[str, dict[str, Any]] = {
    "system_status": {
        "system_power": 45,
        "heat_demand": HeatDemandStatus.DIRECT_ZONES_ALLOWED
        | HeatDemandStatus.HEAT_ENGINE_ACTIVE,
        "error_list": 0x1234,
        "generator_status": GeneratorStatus.HEAT_PUMP_ON,
        "hydraulic_status": HydraulicStatus.PUMP_ON | HydraulicStatus.CH_ACTIVE,
        "outdoor_temperature": -3.5,
        "season_mode": SeasonMode.WINTER,
    },
    "appliance": {
        "flow_temperature": 35.12,
        "return_temperature": 30.2,
        "flue_gas_temperature": None,
        "heat_pump_flow_temperature": 35.8,
        "heat_pump_return_temperature": 30.5,
        "dhw_setpoint": 50,
        "water_pressure": 1.8,
        "status": ApplianceStatus.GENERATOR_CH,
        "sub_status": ApplianceSubStatus.NORMAL_INTERNAL_SETPOINT,
        "relative_power": 62,
        "generator_starts": 1001,
        "generator_hours": 1002,
        "backup_1_starts": 1003,
        "backup_1_hours": 1004,
        "backup_2_starts": 1005,
        "backup_2_hours": 1006,
        "mains_hours": 1007,
        "energy_consumed_ch": 1008,
        "energy_consumed_dhw": 1009,
        "energy_consumed_cooling": 1010,
        "energy_consumed_total": 1011,
        "energy_consumed_backup": 1012,
        "energy_delivered_total": 1013,
        "energy_delivered_ch": 1014,
        "energy_delivered_dhw": 1015,
        "energy_delivered_cooling": 1016,
        "energy_delivered_backup": 1017,
        "pump_speed": 65.5,
        "actual_power": 5.12,
    },
    "heat_pump": {"cop": 4.21, "cop_threshold": 2.5},
    "service": {
        "service_required": False,
        "notification": ServiceNotification.A,
        "hours_producing_since_service": 1500,
        "hours_since_service": 4000,
        "starts_since_service": 321,
    },
    "summary": {"any_error": False},
    "cascade": {
        "mode": CascadeMode.HEATING,
        "cascade_type": CascadeType.PARALLEL,
        "management": CascadeManagement.TEMPERATURE,
        "flow_temperature": 60.1,
        "producer_count": 3,
        "stages_available": 4,
        "stages_required": 2,
        "power_request": 70,
        "temperature_request": 55,
        "heat_demand_request": CascadeHeatDemand.CENTRAL_HEATING,
        "power_setpoint": 65,
        "temperature_setpoint": 54,
        "heat_demand_setpoint": CascadeHeatDemand.CENTRAL_HEATING,
        "requested_power": 24.5,
        "requested_power_percentage": 65.5,
        "primary_pump_active": True,
        "secondary_pump_active": False,
        "state": ApplianceStatus.GENERATOR_CH,
        "hours_ch": 1200,
        "hours_dhw": 65538,
        "return_temperature": 50.2,
        "header_flow_temperature": 59.9,
        "header_return_temperature": 49.9,
        "producer_status": ApplianceStatus.GENERATOR_DHW,
    },
    "system_control": {
        "power": 0,
        "temperature": 0,
        "mode": RemoteControlMode.MONITORING_ONLY,
        "heat_demand": RemoteHeatDemand.STANDBY,
    },
    "fallback": {
        "mode": FallbackMode.FALLBACK,
        "configuration": FallbackConfiguration.MAINTAIN_FALLBACK,
        "period": 10,
        "power": 50,
        "temperature": 45,
        "heat_demand": HeatDemandType.CENTRAL_HEATING,
        "analog_input_function": AnalogInputFunction.TEMPERATURE,
        "analog_input_voltage": 5.5,
    },
}

EXPECTED_BOARDS = [
    {"raw_error_code": 0xFFFF, "_error_type": ErrorType.LOCKING},
    {"raw_error_code": 0xFFFF, "_error_type": ErrorType.LOCKING},
]

EXPECTED_ZONES: dict[int, dict[str, dict[str, Any]]] = {
    1: {
        "config": {"function_code": 1, "device_type": 0x0204},
        "settings": {
            "flow_setpoint_fixed": 40,
            "mode_setting": ZoneMode.SCHEDULING,
            "room_setpoint_manual": 21,
            "heating_curve_gradient": 1.5,
            "heating_curve_footpoint": 20,
        },
        "readings": {
            "flow_temperature": 34.8,
            "flow_setpoint": 35,
            "room_setpoint": 20.5,
            "activity": ZoneActivity.COMFORT,
            "mode": ZoneMode.SCHEDULING,
            "pump_running": True,
            "pump_hours": 4321,
            "pump_starts": 876,
        },
    },
    2: {
        "config": {"function_code": 6, "device_type": 0x0204},
        "settings": {
            "flow_setpoint_fixed": 0,
            "mode_setting": ZoneMode.MANUAL,
            "room_setpoint_manual": 55,
            "heating_curve_gradient": 0,
            "heating_curve_footpoint": 0,
        },
        "readings": {
            "flow_temperature": 48.9,
            "flow_setpoint": 55,
            "room_setpoint": 55,
            "activity": ZoneActivity.ECO,
            "mode": ZoneMode.MANUAL,
            "pump_running": False,
            "pump_hours": 100,
            "pump_starts": 20,
        },
    },
    3: {
        "config": {"function_code": 2, "device_type": 0x1904},
        "settings": {
            "flow_setpoint_fixed": 0,
            "mode_setting": ZoneMode.OFF,
            "room_setpoint_manual": 19,
            "heating_curve_gradient": 0.8,
            "heating_curve_footpoint": 18,
        },
        "readings": {
            "flow_temperature": 22.1,
            "flow_setpoint": 0,
            "room_setpoint": 6,
            "activity": ZoneActivity.OFF,
            "mode": ZoneMode.OFF,
            "pump_running": False,
            "pump_hours": 7,
            "pump_starts": 3,
        },
    },
}


def _assert_fields(component: Component, expected: dict[str, Any]) -> None:
    """Check every declared field, and that the table names each one."""
    assert set(expected) == set(component.declared_fields), type(component).__name__
    actual = {name: getattr(component, name) for name in expected}
    assert actual == expected, type(component).__name__


async def test_every_field(appliance: Gtw08Appliance) -> None:
    report = await appliance.async_update()

    assert report.complete
    for name, expected in EXPECTED.items():
        _assert_fields(getattr(appliance, name), expected)
    for board, expected_board in zip(
        appliance.board_list, EXPECTED_BOARDS, strict=True
    ):
        _assert_fields(board, expected_board)
    assert list(appliance.zone_slots) == list(EXPECTED_ZONES)
    for number, parts in EXPECTED_ZONES.items():
        zone = appliance.zone_slots[number]
        for part, expected in parts.items():
            _assert_fields(getattr(zone, part), expected)
