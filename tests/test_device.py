from __future__ import annotations

import pytest
from modbus_connection import (
    GatewayPathUnavailableError,
    GatewayTargetError,
    IllegalDataAddressError,
    ModbusConnectionError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent

from gtw08_modbus import (
    ApplianceStatus,
    ApplianceSubStatus,
    BoardCategory,
    ErrorType,
    GeneratorStatus,
    Gtw08Appliance,
    HeatDemandStatus,
    HydraulicStatus,
    NoApplianceError,
    RemoteControlMode,
    RemoteHeatDemand,
    SeasonMode,
    ServiceNotification,
    ZoneActivity,
    ZoneFunction,
    ZoneMode,
    board_model,
)

from .conftest import SERIAL_NUMBER, seed, uint32_words


async def test_detect_finds_boards_zones_and_blocks(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    appliance = await Gtw08Appliance.async_detect(mock_modbus_unit)

    assert appliance.model == "EHC-04"
    assert [board.model for board in appliance.board_list] == ["EHC-04", "SCB-04"]
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
    )
    assert appliance.settings_components == ("system_control", "fallback")


async def test_detect_retries_while_the_gateway_fetches(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.fail_read(128, GatewayTargetError())
    original = mock_modbus_unit.read_holding_registers
    calls = 0

    async def answer_the_second_time(address: int, count: int) -> list[int]:
        nonlocal calls
        if address == 128:
            calls += 1
            if calls == 2:
                mock_modbus_unit.fail_read(128, None)
        return await original(address, count)

    mock_modbus_unit.read_holding_registers = answer_the_second_time  # type: ignore[method-assign]
    appliance = await Gtw08Appliance.async_detect(mock_modbus_unit, retry_delay=0)

    assert appliance.model == "EHC-04"


async def test_detect_gives_up_after_the_last_attempt(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.fail_read(128, GatewayTargetError())

    with pytest.raises(GatewayTargetError):
        await Gtw08Appliance.async_detect(mock_modbus_unit, attempts=2, retry_delay=0)


async def test_detect_passes_on_a_missing_appliance(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    mock_modbus_unit.fail_requests(GatewayPathUnavailableError())

    with pytest.raises(GatewayPathUnavailableError):
        await Gtw08Appliance.async_detect(mock_modbus_unit)


async def test_setup_rejects_a_gateway_without_boards(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    with pytest.raises(NoApplianceError):
        await Gtw08Appliance(mock_modbus_unit).async_update()


async def test_requires_the_callers_timeout(mock_modbus_unit: MockModbusUnit) -> None:
    Gtw08Appliance(mock_modbus_unit, timeout=3)

    assert mock_modbus_unit.required_timeout == 3


async def test_system_status(appliance: Gtw08Appliance) -> None:
    report = await appliance.async_update_readings()

    assert report.complete
    status = appliance.system_status
    assert status.system_power == 45
    assert status.heat_demand == (
        HeatDemandStatus.DIRECT_ZONES_ALLOWED | HeatDemandStatus.HEAT_ENGINE_ACTIVE
    )
    assert status.generator_status == GeneratorStatus.HEAT_PUMP_ON
    assert status.hydraulic_status == (
        HydraulicStatus.PUMP_ON | HydraulicStatus.CH_ACTIVE
    )
    assert status.outdoor_temperature == -3.5
    assert status.season_mode is SeasonMode.WINTER


async def test_appliance(appliance: Gtw08Appliance) -> None:
    await appliance.async_update_readings()

    main = appliance.appliance
    assert main.flow_temperature == 35.12
    assert main.return_temperature == 30.2
    assert main.flue_gas_temperature is None
    assert main.heat_pump_flow_temperature == 35.8
    assert main.dhw_setpoint == 50
    assert main.water_pressure == 1.8
    assert main.status is ApplianceStatus.GENERATOR_CH
    assert main.sub_status is ApplianceSubStatus.NORMAL_INTERNAL_SETPOINT
    assert main.relative_power == 62
    assert main.generator_starts == 1234
    assert main.energy_consumed_total == 4050
    assert main.energy_delivered_total == 13200
    assert main.pump_speed == 65.5
    assert main.actual_power == 5.12


async def test_heat_pump_and_service(appliance: Gtw08Appliance) -> None:
    await appliance.async_update_readings()

    assert appliance.heat_pump is not None
    assert appliance.heat_pump.cop == 4.21
    assert appliance.heat_pump.cop_threshold == 2.5
    assert appliance.service.service_required is False
    assert appliance.service.notification is ServiceNotification.A
    assert appliance.service.hours_since_service == 4000
    assert appliance.service.starts_since_service == 321


async def test_boards(appliance: Gtw08Appliance) -> None:
    await appliance.async_update_readings()

    ehc, scb = appliance.board_list
    assert ehc.is_available
    assert ehc.error_code is None
    assert ehc.error_type is None
    assert appliance.summary.any_error is False
    assert scb.device_type == 0x1904


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
    await appliance.async_update_readings()

    direct, dhw, mixing = appliance.zone_slots.values()
    assert direct.function is ZoneFunction.DIRECT
    assert direct.function.is_room_heating
    assert direct.flow_temperature == 34.8
    assert direct.room_setpoint == 20.5
    assert direct.room_setpoint_manual == 21
    assert direct.activity is ZoneActivity.COMFORT
    assert direct.mode is ZoneMode.SCHEDULING
    assert direct.pump_running is True
    assert direct.heating_curve_gradient == 1.5
    assert direct.heating_curve_footpoint == 20
    assert direct.pump_hours == 4321

    assert dhw.function is ZoneFunction.DHW_TANK
    assert dhw.function.is_dhw
    assert dhw.flow_temperature == 48.9
    assert dhw.mode is ZoneMode.MANUAL

    assert mixing.number == 3
    assert mixing.function is ZoneFunction.MIXING_CIRCUIT
    assert mixing.mode is ZoneMode.OFF


async def test_zones_read_at_their_own_addresses(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update_readings()
    mock_modbus_unit.read_events.clear()

    await appliance.zone_slots[3].async_update()

    assert {event.address for event in mock_modbus_unit.read_events} == {
        1665,  # function
        1669,  # device type
        1672,  # fixed flow setpoint and mode
        1688,  # manual room setpoint
        1698,  # heating curve
        2124,  # flow temperature to room setpoint
        2131,  # activity and mode
        2134,  # pump
        2139,  # pump counters
    }


async def test_disabled_and_refused_zones_are_skipped(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding[641] = 0
    mock_modbus_unit.fail_read(1153, IllegalDataAddressError())
    appliance = Gtw08Appliance(mock_modbus_unit)
    await appliance.async_update_readings()

    assert list(appliance.zone_slots) == [3]


async def test_zone_count_bounds_the_probe(mock_modbus_unit: MockModbusUnit) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding[189] = 1
    appliance = Gtw08Appliance(mock_modbus_unit)
    await appliance.async_update_readings()

    assert list(appliance.zone_slots) == [1]


async def test_zone_writes(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update_readings()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    mixing = appliance.zone_slots[3]

    await mixing.async_write_mode(ZoneMode.MANUAL)
    await mixing.async_write_room_setpoint(20.5)
    await mixing.write("heating_curve_gradient", 0.7)

    assert mock_modbus_unit.holding[1673] == 1
    assert mock_modbus_unit.holding[1688] == 205
    assert mock_modbus_unit.holding[1698] == 7
    assert {write.register_type for write in writes} == {"holding"}
    with pytest.raises(ValueError, match="temporary"):
        await mixing.async_write_mode(ZoneMode.TEMPORARY)


async def test_remote_control_writes_the_mode_first(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    writes: list[WriteEvent] = []
    mock_modbus_unit.on_write(writes.append)
    control = appliance.system_control
    assert control is not None
    assert control.mode is RemoteControlMode.MONITORING_ONLY

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


async def test_fallback(appliance: Gtw08Appliance) -> None:
    await appliance.async_update_settings()

    assert appliance.fallback is not None
    assert appliance.fallback.period == 10
    assert appliance.fallback.temperature == 45


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
    assert appliance.settings_components == ()


async def test_a_cascade_with_producers(mock_modbus_unit: MockModbusUnit) -> None:
    seed(mock_modbus_unit)
    mock_modbus_unit.holding.update(
        {
            7001: 1,
            7101: 6010,
            7102: 3,
            7151: uint32_words(245),
            7157: 1,
            7159: 3,
            7168: 5990,
            7209: 3,
        }
    )
    appliance = Gtw08Appliance(mock_modbus_unit)
    await appliance.async_update_readings()

    cascade = appliance.cascade
    assert cascade is not None
    assert cascade.producer_count == 3
    assert cascade.flow_temperature == 60.1
    assert cascade.requested_power == 24.5
    assert cascade.primary_pump_active is True
    assert cascade.state is ApplianceStatus.GENERATOR_CH
    assert "cascade" in appliance.readings_components


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


async def test_raw_dump_round_trips(
    appliance: Gtw08Appliance, mock_modbus_unit: MockModbusUnit
) -> None:
    await appliance.async_update()
    raw = await appliance.async_read_raw()

    assert raw["holding"][409] == 0xFF00 | 18
    replay = MockModbusConnection().for_unit(100)
    replay.load_raw(raw)  # type: ignore[arg-type]
    copy = Gtw08Appliance(replay)
    await copy.async_update()
    assert copy.appliance.water_pressure == 1.8
    assert list(copy.zone_slots) == [1, 2, 3]
