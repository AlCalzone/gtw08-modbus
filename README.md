# gtw08-modbus

Read and control heat pumps and boilers behind a GTW-08 Modbus gateway, as typed Python objects. The gateway is sold for Remeha, Brötje, De Dietrich and Baxi appliances.

The library builds on [modbus-connection](https://github.com/home-assistant-libs/modbus-connection). You hand it a `ModbusUnit` and it reads the appliance. It opens no connection itself.

## Installation

The package is not on PyPI yet. Install it from git:

```bash
pip install "gtw08-modbus @ git+https://github.com/AlCalzone/gtw08-modbus@main"
```

## Usage

```python
import asyncio

from modbus_connection import ModbusSerialParams
from modbus_connection.tmodbus import ModbusConnection
from gtw08_modbus import DEFAULT_UNIT_ID, Gtw08Appliance


async def main() -> None:
    connection = ModbusConnection(ModbusSerialParams(device="/dev/ttyUSB0"))
    try:
        appliance = await Gtw08Appliance.async_detect(
            connection.for_unit(DEFAULT_UNIT_ID)
        )
        print(appliance.model, appliance.appliance.status)
        print(appliance.appliance.flow_temperature, "°C")
        for number, zone in appliance.zone_slots.items():
            print(number, zone.function, zone.mode)
    finally:
        await connection.close()


asyncio.run(main())
```

To check a device from the command line, run `uv run script/query.py /dev/ttyUSB0` in a checkout. It prints every value once.

## Requirements and gotchas

- The gateway speaks Modbus RTU on RS-485. Reach it with a USB to RS-485 adapter, or over the network with an RS-485 to Ethernet converter.
- Factory settings are 9600 baud, no parity and unit ID 100 (`DEFAULT_UNIT_ID`). The DIP switches change baud rate and parity. The rotary dial adds 0 to 15 to the unit ID.
- The gateway fetches each value from the appliance the first time it is asked. Until then it answers with `GatewayTargetError`. `async_detect()` retries for this. A later poll may list a component as failed once.
- `GatewayPathUnavailableError` means the gateway sees no appliance on its L-Bus.
- While `system_control.mode` is anything but `MONITORING_ONLY`, the appliance ignores the heat demand of its zones.
- The register map comes from the manufacturer's configuration manual 7854678 (September 2023). It has not been tested against a real gateway yet.

## API

### `Gtw08Appliance`

- `Gtw08Appliance(unit, *, timeout=None)`: wrap a `ModbusUnit`. No I/O until the first update.
- `await Gtw08Appliance.async_detect(unit, *, timeout=None)`: build, set up and read the appliance once. Raises `NoApplianceError` if the gateway reports no board.
- `await async_update_readings()`: refresh measurements, boards, zones and the cascade.
- `await async_update_settings()`: refresh remote control and fallback settings.
- `await async_update()`: refresh both.
- `await async_read_raw()`: every register read, undecoded, for bug reports.
- `model`: the main control board, such as `EHC-04`.
- `serial_number`: the producer serial number, or `None`.
- `readings_components`, `settings_components`: names of the components this appliance polls.

Each update returns an `UpdateReport`. `report.failed` maps a component name to its error. A failed component keeps its last values. A dead link raises `ModbusConnectionError`.

### Components

Every value is `None` until read, or when the appliance has no reading for it.

- `system_status` (`SystemStatus`): `outdoor_temperature`, `season_mode`, `system_power`, `heat_demand`, `generator_status` (flame, heat pump, backup stages, low pressure, reset needed), `hydraulic_status` (pump, valve, hot water, heating, cooling).
- `appliance` (`Appliance`): flow, return, flue gas and heat pump temperatures, `dhw_setpoint`, `water_pressure`, `status`, `sub_status`, `relative_power`, `actual_power`, `pump_speed`, start and hour counters, and energy consumed and delivered for heating, hot water, cooling and backup.
- `heat_pump` (`HeatPumpPerformance`, heat pumps only): `cop`, `cop_threshold`.
- `service` (`Service`): `service_required`, `notification`, hours and starts since the last service.
- `summary` (`BoardSummary`): `board_count`, `zone_count`, `any_error`.
- `board_list` (list of `Board`): `number`, `model`, `is_available`, `error_code`, `error_type`.
- `zone_slots` (dict of `Zone` by number): see below.
- `cascade` (`Cascade`, only with two producers or more): mode, flow and return temperatures, producer count, requests, pumps, `state`, hours.
- `system_control` (`SystemControl`): see below.
- `fallback` (`Fallback`): what the gateway does when the controlling system goes quiet, and the 0-10 V input function.

### `Zone`

- `function`: what the zone heats (`ZoneFunction`), with `is_dhw` and `is_room_heating`.
- `flow_temperature`, `flow_setpoint`, `room_setpoint`, `activity`, `mode`, `pump_running`, `pump_hours`, `pump_starts`: the current state.
- `mode_setting`, `room_setpoint_manual`, `heating_curve_gradient`, `heating_curve_footpoint`, `flow_setpoint_fixed`: writable settings.
- `await async_write_mode(mode)`: set `SCHEDULING`, `MANUAL` or `OFF`.
- `await async_write_room_setpoint(temperature)`: the temperature held in manual mode.
- `await write(name, value)`: write any writable setting by name.

### `SystemControl`

- `mode`, `heat_demand`, `power`, `temperature`: the remote control request.
- `await async_request(mode, heat_demand, *, power=None, temperature=None)`: take over the heat demand. Writes the registers in the order the gateway needs.
- `await async_stop()`: hand the heat demand back to the zones.

### Enums and errors

`ApplianceStatus`, `ApplianceSubStatus`, `SeasonMode`, `ServiceNotification`, `ZoneFunction`, `ZoneMode`, `ZoneActivity`, `RemoteControlMode`, `RemoteHeatDemand`, `ErrorType`, `BoardCategory`, `CascadeMode` and the other enums are exported from `gtw08_modbus`. `NoApplianceError` is the library's own error. Modbus errors come from `modbus_connection`.

The register addresses live in the component modules under [`src/gtw08_modbus`](src/gtw08_modbus).

## Debug logging

The `gtw08_modbus` logger reports at `DEBUG` which boards and zones setup found and what it polls.
