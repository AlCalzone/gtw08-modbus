from __future__ import annotations

import asyncio
import logging

import pytest
from modbus_connection import (
    GatewayPathUnavailableError,
    GatewayTargetError,
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent

from gtw08_modbus import (
    AnalogInputFunction,
    ApplianceStatus,
    ApplianceSubStatus,
    BoardCategory,
    ErrorType,
    FallbackConfiguration,
    FallbackMode,
    GatewayNotReadyError,
    Gtw08Appliance,
    Gtw08Error,
    HeatDemandType,
    NoApplianceError,
    RemoteControlMode,
    RemoteHeatDemand,
    ZoneFunction,
    ZoneMode,
)
from gtw08_modbus.boards import board_model

from .conftest import SERIAL_NUMBER, seed


def fail_first_reads(
    unit: MockModbusUnit, failing: int, times: int, error: Exception
) -> list[int]:
    """Make the first ``times`` reads starting at ``failing`` raise ``error``."""
    original = unit.read_holding_registers
    calls = [0]

    async def read(address: int, count: int) -> list[int]:
        if address == failing:
            calls[0] += 1
            if calls[0] <= times:
                raise error
        return await original(address, count)

    unit.read_holding_registers = read  # type: ignore[method-assign]
    return calls


def read_starts(unit: MockModbusUnit) -> list[int]:
    return [event.address for event in unit.read_events]


async def test_detect_finds_boards_zones_and_blocks(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    appliance = await Gtw08Appliance.async_detect(mock_modbus_unit)

    assert appliance.model == "EHC-04"
    assert [board.model for board in appliance.board_list] == ["EHC-04", "SCB-04"]
    assert appliance.board_count == 2
    assert appliance.zone_count == 3
    assert appliance.serial_number == SERIAL_NUMBER
    assert list(appliance.zone_slots) == [1, 2, 3]
    assert appliance.readings_components == (
        "summary",
        "system_status",
        "appliance",
        "heat_pump",
        "service",
        "boards",
        "zones",
        "cascade",
    )
    assert appliance.settings_components == (
        "system_control",
        "fallback",
        "zone_settings",
    )
    assert appliance.detect_report is not None
    assert appliance.detect_report.complete


async def test_detect_retries_while_setup_meets_an_unfetched_register(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    calls = fail_first_reads(mock_modbus_unit, 128, 1, GatewayTargetError())

    appliance = await Gtw08Appliance.async_detect(mock_modbus_unit, retry_delay=0)

    assert calls[0] == 2
    assert appliance.model == "EHC-04"


async def test_detect_retries_while_a_poll_meets_an_unfetched_register(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    # Setup reads no register 400, so the first failure lands in the report
    calls = fail_first_reads(mock_modbus_unit, 400, 1, GatewayTargetError())

    appliance = await Gtw08Appliance.async_detect(mock_modbus_unit, retry_delay=0)

    assert calls[0] == 2
    assert appliance.appliance.flow_temperature == 35.12
    assert appliance.detect_report is not None
    assert appliance.detect_report.complete


async def test_detect_returns_a_partial_report_after_the_last_attempt(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.fail_read(400, GatewayTargetError())

    appliance = await Gtw08Appliance.async_detect(
        mock_modbus_unit, attempts=2, retry_delay=0
    )

    assert appliance.detect_report is not None
    assert set(appliance.detect_report.failed) == {"appliance"}


async def test_detect_gives_up_after_the_last_attempt(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.fail_read(128, GatewayTargetError())

    with pytest.raises(GatewayTargetError):
        await Gtw08Appliance.async_detect(mock_modbus_unit, attempts=2, retry_delay=0)


async def test_an_empty_l_bus_is_no_appliance(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    mock_modbus_unit.fail_requests(GatewayPathUnavailableError())

    with pytest.raises(NoApplianceError) as err:
        await Gtw08Appliance.async_detect(mock_modbus_unit)
    assert isinstance(err.value, Gtw08Error)


async def test_setup_rejects_a_gateway_without_boards(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    with pytest.raises(NoApplianceError):
        await Gtw08Appliance(mock_modbus_unit).async_update()


async def test_an_unknown_board_count_is_not_ready_yet(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding[128] = 0xFF
    appliance = Gtw08Appliance(mock_modbus_unit)

    with pytest.raises(GatewayNotReadyError):
        await appliance.async_update()

    mock_modbus_unit.holding[128] = 2
    assert (await appliance.async_update()).complete


async def test_requires_the_callers_timeout(mock_modbus_unit: MockModbusUnit) -> None:
    Gtw08Appliance(mock_modbus_unit, timeout=3)

    assert mock_modbus_unit.required_timeout == 3


async def test_leaves_the_timeout_alone_without_one(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    mock_modbus_unit.require_timeout(7)
    Gtw08Appliance(mock_modbus_unit)

    assert mock_modbus_unit.required_timeout == 7


async def test_detect_retries_until_the_board_count_arrives(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding[128] = 0xFF

    with pytest.raises(GatewayNotReadyError):
        await Gtw08Appliance.async_detect(mock_modbus_unit, attempts=2, retry_delay=0)


async def test_setup_runs_once_for_concurrent_updates(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await asyncio.gather(
        appliance.async_update_readings(), appliance.async_update_settings()
    )

    assert read_starts(mock_modbus_unit).count(128) == 1


async def test_static_registers_are_read_at_setup_only(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    mock_modbus_unit.read_events.clear()

    await appliance.async_update_readings()
    readings = set(read_starts(mock_modbus_unit))
    mock_modbus_unit.read_events.clear()
    await appliance.async_update_settings()
    settings = set(read_starts(mock_modbus_unit))

    for static in (128, 129, 135, 189, 641, 645, 1153, 1157, 1665, 1669):
        assert static not in readings | settings
    assert {648, 664, 674} <= settings
    assert not {648, 664, 674} & readings
    # 26 for the appliance and three zones, 8 for the cascade
    assert len(readings) == 34
    assert len(settings) == 11


async def test_sub_status_out_of_resets(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    mock_modbus_unit.holding[412] = 255
    await appliance.async_update_readings()

    assert (
        appliance.appliance.sub_status is ApplianceSubStatus.SAFETY_UNIT_OUT_OF_RESETS
    )


async def test_values_the_appliance_does_not_have(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    mock_modbus_unit.holding.update(
        {409: 0xFF, 411: 0xFF, 400: 0x8000, 419: [0xFFFF] * 2}
    )
    await appliance.async_update_readings()

    assert appliance.appliance.water_pressure is None
    assert appliance.appliance.status is None
    assert appliance.appliance.flow_temperature is None
    assert appliance.appliance.generator_starts is None


async def test_an_unknown_enum_value(
    appliance: Gtw08Appliance,
    mock_modbus_unit: MockModbusUnit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_modbus_unit.holding[411] = 99
    await appliance.async_update_readings()

    assert appliance.appliance.status is None
    assert "no mapping for value 99" in caplog.text


async def test_a_board_error(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    mock_modbus_unit.holding[531] = 1
    mock_modbus_unit.holding[532] = [0x0213, 6, 0xFFFE, 0]
    await appliance.async_update_readings()

    ehc, scb = appliance.board_list
    assert appliance.summary.any_error is True
    assert ehc.error_code == 0x0213
    assert ehc.error_type is ErrorType.WARNING
    assert not scb.is_available
    assert scb.error_code is None
    assert scb.error_type is None


@pytest.mark.parametrize(
    ("device_type", "model"),
    [
        (0x0008, "CU-GH08"),
        (0x190A, "SCB-10"),
        (0x0102, "CU-OH02"),
        (0x1E08, "GTW-08"),
        (0x7701, "0x7701"),
        (None, None),
    ],
)
def test_board_model(device_type: int | None, model: str | None) -> None:
    assert board_model(device_type) == model


def test_board_categories_cover_the_manual() -> None:
    assert {category.value for category in BoardCategory} == {
        0x00,
        0x01,
        0x02,
        0x14,
        0x19,
        0x1B,
        0x1E,
    }


async def test_zones(appliance: Gtw08Appliance) -> None:
    await appliance.async_update()

    direct, dhw, mixing = appliance.zone_slots.values()
    assert direct.function is ZoneFunction.DIRECT
    assert direct.function.is_room_heating
    assert direct.room_setpoint == 20.5
    assert direct.room_setpoint_manual == 21
    assert dhw.function is ZoneFunction.DHW_TANK
    assert dhw.function.is_dhw
    assert mixing.number == 3
    assert mixing.mode is ZoneMode.OFF


async def test_zones_read_at_their_own_addresses(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    mock_modbus_unit.read_events.clear()

    zone = appliance.zone_slots[3]
    await zone.readings.async_update()
    await zone.settings.async_update()

    assert set(read_starts(mock_modbus_unit)) == {
        1672,  # fixed flow setpoint and mode
        1688,  # manual room setpoint
        1698,  # heating curve
        2124,  # flow temperature to room setpoint
        2131,  # activity and mode
        2134,  # pump
        2139,  # pump counters
    }


@pytest.mark.parametrize(
    ("function_code", "kept", "function"),
    [
        pytest.param(0, False, None, id="disabled"),
        pytest.param(0xFF, False, None, id="not_available"),
        pytest.param(20, True, None, id="unknown_code"),
        pytest.param(13, True, ZoneFunction.OCCUPIED, id="last_listed"),
    ],
)
async def test_which_zones_are_kept(
    mock_modbus_unit: MockModbusUnit,
    function_code: int,
    kept: bool,
    function: ZoneFunction | None,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding[641] = function_code
    appliance = Gtw08Appliance(mock_modbus_unit)
    await appliance.async_update_readings()

    assert (1 in appliance.zone_slots) is kept
    if kept:
        assert appliance.zone_slots[1].function is function


async def test_a_refused_zone_is_left_out_and_logged(
    mock_modbus_unit: MockModbusUnit, caplog: pytest.LogCaptureFixture
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.fail_read(1153, IllegalDataAddressError())
    appliance = Gtw08Appliance(mock_modbus_unit)
    with caplog.at_level(logging.INFO, logger="gtw08_modbus"):
        await appliance.async_update_readings()

    assert list(appliance.zone_slots) == [1, 3]
    assert "Zone 2 refuses its registers" in caplog.text


async def test_zone_count_bounds_the_probe(mock_modbus_unit: MockModbusUnit) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding[189] = 1
    appliance = Gtw08Appliance(mock_modbus_unit)
    await appliance.async_update_readings()

    assert list(appliance.zone_slots) == [1]


async def test_zone_writes(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    mixing = appliance.zone_slots[3]

    await mixing.async_write_mode(ZoneMode.MANUAL)
    await mixing.async_write_room_setpoint(20.5)
    await mixing.async_write_heating_curve_gradient(0.7)
    await mixing.async_write_heating_curve_footpoint(22)
    await mixing.async_write_flow_setpoint_fixed(45)

    assert mock_modbus_unit.holding[1673] == 1
    assert mock_modbus_unit.holding[1688] == 205
    assert mock_modbus_unit.holding[1698] == 7
    assert mock_modbus_unit.holding[1699] == 220
    assert mock_modbus_unit.holding[1672] == 4500
    assert {write.register_type for write in writes} == {"holding"}
    with pytest.raises(ValueError, match="temporary"):
        await mixing.async_write_mode(ZoneMode.TEMPORARY)
    with pytest.raises(AttributeError):
        await mixing.write("flow_temperature", 30)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("heating_curve_gradient", 25.5, id="uint8_not_available"),
        pytest.param("heating_curve_gradient", 30, id="uint8_too_high"),
        pytest.param("heating_curve_gradient", -0.1, id="uint8_negative"),
        pytest.param("room_setpoint_manual", -1, id="uint16_negative"),
        pytest.param("room_setpoint_manual", 6553.5, id="uint16_not_available"),
        pytest.param("mode_setting", 7, id="enum_not_a_member"),
    ],
)
async def test_writes_out_of_range_are_refused(
    appliance: Gtw08Appliance,
    mock_modbus_unit: MockModbusUnit,
    field: str,
    value: float,
) -> None:
    await appliance.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)

    with pytest.raises(ValueError):
        await appliance.zone_slots[1].write(field, value)
    assert writes == []


async def test_remote_control_writes_the_mode_first(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    control = appliance.system_control
    assert control is not None

    await control.async_request(
        RemoteControlMode.TEMPERATURE_AND_POWER,
        RemoteHeatDemand.HEATING,
        power=60,
        temperature=50,
    )

    assert [write.address for write in writes] == [258, 256, 257, 259]
    assert mock_modbus_unit.holding[256] == 60
    assert mock_modbus_unit.holding[257] == 5000
    assert mock_modbus_unit.holding[259] == 7

    await control.async_stop()
    assert mock_modbus_unit.holding[258] == 3


async def test_remote_control_switches_off_without_setpoints(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    assert appliance.system_control is not None

    await appliance.system_control.async_request(
        RemoteControlMode.TEMPERATURE_AND_POWER, RemoteHeatDemand.STANDBY
    )

    assert mock_modbus_unit.holding[258] == 0
    assert mock_modbus_unit.holding[259] == 0


@pytest.mark.parametrize(
    ("kwargs", "failing"),
    [
        pytest.param({"power": 60, "temperature": 50}, 259, id="write_fails"),
        pytest.param({"power": 60, "temperature": -1}, None, id="out_of_range"),
    ],
)
async def test_remote_control_falls_back_to_monitoring(
    appliance: Gtw08Appliance,
    mock_modbus_unit: MockModbusUnit,
    kwargs: dict[str, float],
    failing: int | None,
) -> None:
    await appliance.async_update()
    assert appliance.system_control is not None
    if failing is not None:
        mock_modbus_unit.fail_write(failing, ModbusTimeoutError())

    with pytest.raises((ModbusTimeoutError, ValueError)):
        await appliance.system_control.async_request(
            RemoteControlMode.TEMPERATURE_AND_POWER,
            RemoteHeatDemand.HEATING,
            **kwargs,
        )

    assert mock_modbus_unit.holding[258] == RemoteControlMode.MONITORING_ONLY


async def test_remote_control_requests_do_not_interleave(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    control = appliance.system_control
    assert control is not None

    await asyncio.gather(
        control.async_request(
            RemoteControlMode.POWER, RemoteHeatDemand.HEATING, power=40
        ),
        control.async_request(
            RemoteControlMode.TEMPERATURE, RemoteHeatDemand.COOLING, temperature=15
        ),
    )

    assert [write.address for write in writes] == [258, 256, 259, 258, 257, 259]
    assert mock_modbus_unit.holding[259] == RemoteHeatDemand.COOLING


async def test_remote_control_checks_what_the_mode_needs(
    appliance: Gtw08Appliance,
) -> None:
    await appliance.async_update()
    control = appliance.system_control
    assert control is not None

    with pytest.raises(ValueError, match="power"):
        await control.async_request(RemoteControlMode.POWER, RemoteHeatDemand.HEATING)
    with pytest.raises(ValueError, match="temperature"):
        await control.async_request(
            RemoteControlMode.TEMPERATURE, RemoteHeatDemand.COOLING
        )
    with pytest.raises(ValueError, match="async_stop"):
        await control.async_request(
            RemoteControlMode.MONITORING_ONLY, RemoteHeatDemand.STANDBY
        )


async def test_fallback_writes(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    fallback = appliance.fallback
    assert fallback is not None

    await fallback.async_write_mode(FallbackMode.BMS)
    await fallback.async_write_configuration(FallbackConfiguration.NEVER_CANCEL)
    await fallback.async_write_period(15)
    await fallback.async_write_power(80)
    await fallback.async_write_temperature(-5)
    await fallback.async_write_heat_demand(HeatDemandType.COOLING)
    await fallback.async_write_analog_input_function(AnalogInputFunction.POWER)
    await fallback.async_write_analog_input_voltage(7.5)

    assert [mock_modbus_unit.holding[address] for address in range(21020, 21028)] == [
        0,
        1,
        15,
        80,
        0xFFFF & -500,
        8,
        2,
        75,
    ]
    with pytest.raises(ValueError):
        await fallback.async_write_temperature(327.67)


async def test_optional_blocks_the_gateway_refuses(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    for address in (9230, 7228, 256, 21020, 7001):
        mock_modbus_unit.fail_read(address, IllegalDataAddressError())
    appliance = Gtw08Appliance(mock_modbus_unit)
    await appliance.async_update()

    assert appliance.heat_pump is None
    assert appliance.serial_number is None
    assert appliance.system_control is None
    assert appliance.fallback is None
    assert appliance.cascade is None
    assert appliance.settings_components == ("zone_settings",)


async def test_an_optional_block_still_unfetched_counts_as_missing(
    mock_modbus_unit: MockModbusUnit, caplog: pytest.LogCaptureFixture
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.fail_read(9230, GatewayTargetError())
    appliance = Gtw08Appliance(mock_modbus_unit, attempts=3, retry_delay=0)
    with caplog.at_level(logging.INFO, logger="gtw08_modbus"):
        await appliance.async_update()

    assert appliance.heat_pump is None
    assert read_starts(mock_modbus_unit).count(9230) == 3
    assert "HeatPumpPerformance still not fetched" in caplog.text


async def test_an_optional_block_fetched_on_a_retry(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    fail_first_reads(mock_modbus_unit, 9230, 1, GatewayTargetError())
    appliance = Gtw08Appliance(mock_modbus_unit, retry_delay=0)
    await appliance.async_update()

    assert appliance.heat_pump is not None
    assert appliance.heat_pump.cop == 4.21


async def test_a_single_producer_is_no_cascade(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding[7102] = 1
    appliance = Gtw08Appliance(mock_modbus_unit)
    await appliance.async_update_readings()

    assert appliance.cascade is None


async def test_cascade_return_temperature_skips_the_dhw_hours(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    mock_modbus_unit.holding.update({7162: 0x0001, 7163: 0x0002, 7164: 4870})
    await appliance.async_update_readings()

    assert appliance.cascade is not None
    assert appliance.cascade.hours_dhw == 0x00010002
    assert appliance.cascade.return_temperature == 48.7
    assert appliance.cascade.state is ApplianceStatus.GENERATOR_CH


async def test_a_failed_block_keeps_the_rest(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update_readings()
    mock_modbus_unit.fail_read(400, GatewayTargetError())

    report = await appliance.async_update_readings()

    assert set(report.failed) == {"appliance"}
    assert "system_status" in report.updated
    assert appliance.appliance.flow_temperature == 35.12


async def test_a_dead_link_raises(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update_readings()
    mock_modbus_unit.fail_requests(ModbusConnectionError("gone"))

    with pytest.raises(ModbusConnectionError):
        await appliance.async_update_readings()


async def test_raw_dump_round_trips(appliance: Gtw08Appliance) -> None:
    await appliance.async_update()
    raw = await appliance.async_read_raw()

    assert raw["holding"][409] == 0xFF00 | 18
    replay = MockModbusConnection().for_unit(100)
    replay.holding.update({128: 2, 129: 0x0204, 135: 0x1904, 189: 3})
    replay.holding.update({641: 1, 1153: 6, 1665: 2})
    replay.load_raw(raw)  # type: ignore[arg-type]
    copy = Gtw08Appliance(replay)
    await copy.async_update()
    assert copy.appliance.water_pressure == 1.8
    assert list(copy.zone_slots) == [1, 2, 3]
