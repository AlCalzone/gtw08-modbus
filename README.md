# gtw08-modbus

Read and control Remeha, Brötje, De Dietrich and Baxi heat pumps and boilers through a GTW-08 gateway over Modbus RTU.

## Installation

```bash
pip install gtw08-modbus
```

It needs Python 3.12 or later and [modbus-connection](https://github.com/home-assistant-libs/modbus-connection) 4.12.4 or later.

## Device setup

- **Protocol:** install a GTW-08 Modbus gateway on the appliance's L-Bus. It speaks Modbus RTU on RS-485 and needs no further enabling.
- **Connection:** DIP switches 1 and 2 set the baud rate (9600, 19200, 38400 or 57600; default 9600). DIP switches 3 and 4 set the parity (none, odd or even; default none). One stop bit.
- **Unit ID:** 100 plus the position of the rotary dial, so 100 to 115. The default is 100 (`DEFAULT_UNIT_ID`).
- **Supported devices:** appliances with an L-Bus: heat pumps with an EHC control unit, gas and oil boilers with a CU-GH or CU-OH control unit, hybrids and cascades. Zones on SCB expansion boards are read too.
- **Network:** wire the gateway to a USB to RS-485 adapter, or to an RS-485 to Ethernet converter.

## Usage

The library builds on modbus-connection. You open the connection and pass the library a `ModbusUnit`. The library never opens or closes the connection itself.

```python
import asyncio

from modbus_connection import ModbusSerialParams
from modbus_connection.tmodbus import ModbusConnection
from gtw08_modbus import DEFAULT_UNIT_ID, Gtw08Appliance, ZoneMode


async def main() -> None:
    connection = ModbusConnection(ModbusSerialParams(device="/dev/ttyUSB0"))
    try:
        appliance = await Gtw08Appliance.async_detect(
            connection.for_unit(DEFAULT_UNIT_ID)
        )
        await appliance.async_update()
        print("Model:", appliance.model)
        print("Status:", appliance.appliance.status)
        print("Flow:", appliance.appliance.flow_temperature, "°C")
        await appliance.zone_slots[1].async_write_mode(ZoneMode.MANUAL)
    finally:
        await connection.close()


asyncio.run(main())
```

Behind a transparent RS-485 to Ethernet converter, open the serial link through a socket URL:

```python
ModbusSerialParams(device="socket://192.168.1.60:8899")
```

Every value is `None` until the first update. Each update returns an `UpdateReport`. `report.updated` names the components that refreshed. `report.failed` maps the others to their error, and those keep their previous values. A lost connection raises `ModbusConnectionError`.

## Gotchas

- **Lazy gateway:** the gateway fetches each value from the appliance the first time it is asked, and answers `GatewayTargetError` until it has it. `async_detect()` retries for this. A later poll can list a component as failed once.
- **No appliance:** `GatewayPathUnavailableError` means the gateway sees no appliance on its L-Bus.
- **Remote control:** while `system_control.mode` is anything but `MONITORING_ONLY`, the appliance ignores the heat demand of its zones.
- **Missing values:** a value the appliance does not have, such as the flue gas temperature of a heat pump, stays `None`.
- **Testing:** built from the manufacturer's configuration manual 7854678 (September 2023) and tested against modbus-connection's mock. It has not been tested on real hardware.

## API

### `Gtw08Appliance(unit, *, timeout=None)`

The appliance behind one GTW-08 gateway. Construction does no I/O.

- `await Gtw08Appliance.async_detect(unit, *, timeout=None)`: build the appliance, set it up and read it once.
- `await async_update_readings()`: refresh the measurements, boards, zones and cascade.
- `await async_update_settings()`: refresh the remote control and fallback settings.
- `await async_update()`: refresh both.
- `await async_read_raw()`: every register read, undecoded.
- `model`: the main control board, such as `EHC-04`.
- `serial_number`: the producer serial number, or `None`.
- `readings_components`, `settings_components`: the names of the components this appliance polls.
- `summary`, `system_status`, `appliance`, `service`, `board_list`, `heat_pump`, `zone_slots`, `cascade`, `system_control`, `fallback`: the components below.

### `summary` (`BoardSummary`)

- `board_count`: how many control boards are connected.
- `zone_count`: how many zones the appliance detected.
- `any_error`: at least one board reports an error.

### `system_status` (`SystemStatus`)

- `system_power`: the power the zones ask for, in %.
- `heat_demand`: what the zones' heat demand allows (`HeatDemandStatus`).
- `error_list`: the error word for all connected devices.
- `generator_status`: flame, heat pump, backup stages, service, reset and low pressure flags (`GeneratorStatus`).
- `hydraulic_status`: pump, valve, hot water, heating and cooling flags (`HydraulicStatus`).
- `outdoor_temperature`: in °C.
- `season_mode`: winter, frost protection, summer neutral band or summer (`SeasonMode`).

### `appliance` (`Appliance`)

- `flow_temperature`, `return_temperature`: in °C.
- `flue_gas_temperature`: boilers only, in °C.
- `heat_pump_flow_temperature`, `heat_pump_return_temperature`: heat pumps only, in °C.
- `dhw_setpoint`: the hot water flow setpoint, in °C.
- `water_pressure`: of the primary circuit, in bar.
- `status`: the main status (`ApplianceStatus`).
- `sub_status`: what the appliance does right now (`ApplianceSubStatus`).
- `relative_power`: in %.
- `actual_power`: the heat output, in kW.
- `pump_speed`: in %.
- `generator_starts`, `backup_1_starts`, `backup_2_starts`: start counters.
- `generator_hours`, `backup_1_hours`, `backup_2_hours`, `mains_hours`: in h.
- `energy_consumed_total`, `energy_consumed_ch`, `energy_consumed_dhw`, `energy_consumed_cooling`, `energy_consumed_backup`: electricity consumed, in kWh.
- `energy_delivered_total`, `energy_delivered_ch`, `energy_delivered_dhw`, `energy_delivered_cooling`, `energy_delivered_backup`: heat delivered, in kWh.

### `service` (`Service`)

- `service_required`: a service is due.
- `notification`: the current or upcoming service (`ServiceNotification`).
- `hours_producing_since_service`, `hours_since_service`: in h.
- `starts_since_service`: starts since the last service.

### `board_list` (`list[Board]`)

- `number`: the board's position, from 1.
- `model`: the board's name, such as `CU-GH08` or `SCB-10`.
- `device_type`: the raw device type.
- `is_available`: the gateway reaches the board.
- `error_code`: the board's error code, or `None` without an error.
- `error_type`: locking, blocking or warning (`ErrorType`), or `None` without an error.

### `heat_pump` (`HeatPumpPerformance`)

Optional. Present when the appliance serves it, which heat pumps do.

- `cop`: the instantaneous coefficient of performance.
- `cop_threshold`: the COP below which a hybrid switches to the boiler.

### `zone_slots` (`dict[int, Zone]`)

Zones by number, from 1. Only zones with a function are listed.

- `number`: the zone's number.
- `function`: what the zone heats (`ZoneFunction`), with `is_dhw` and `is_room_heating`.
- `device_type`: the board that drives the zone.
- `flow_temperature`: the flow temperature, or the tank temperature of a hot water zone, in °C.
- `flow_setpoint`: the flow setpoint in effect, in °C.
- `room_setpoint`: the room setpoint in effect, in °C.
- `activity`: off, eco, comfort or anti-legionella (`ZoneActivity`).
- `mode`: the operating mode in effect (`ZoneMode`).
- `pump_running`: the zone pump runs.
- `pump_hours`: in h.
- `pump_starts`: pump start counter.
- `mode_setting`: the operating mode set (`ZoneMode`). Writable.
- `room_setpoint_manual`: the room temperature held in manual mode, in °C. Writable.
- `heating_curve_gradient`: writable.
- `heating_curve_footpoint`: in °C. Writable.
- `flow_setpoint_fixed`: the flow temperature of a fixed-flow zone, in °C. Writable.
- `await async_write_mode(mode)`: set `SCHEDULING`, `MANUAL` or `OFF`.
- `await async_write_room_setpoint(temperature)`: set the manual room temperature.
- `await write(name, value)`: write any writable field by name.

### `cascade` (`Cascade`)

Optional. Present when the cascade reports two producers or more.

- `mode`, `cascade_type`, `management`: the cascade settings (`CascadeMode`, `CascadeType`, `CascadeManagement`).
- `flow_temperature`, `return_temperature`: in °C.
- `header_flow_temperature`, `header_return_temperature`: on the secondary side of the low loss header, in °C.
- `producer_count`, `stages_available`, `stages_required`: counts.
- `power_request`, `power_setpoint`: in %.
- `temperature_request`, `temperature_setpoint`: in °C.
- `heat_demand_request`, `heat_demand_setpoint`: the kind of demand (`CascadeHeatDemand`).
- `requested_power`: in kW.
- `requested_power_percentage`: in %.
- `primary_pump_active`, `secondary_pump_active`: the cascade pumps run.
- `state`, `producer_status`: the cascade's and this producer's status (`ApplianceStatus`).
- `hours_ch`, `hours_dhw`: in h.

### `system_control` (`SystemControl`)

Optional. Present when the gateway serves remote control.

- `mode`: what the gateway takes over (`RemoteControlMode`). Writable.
- `heat_demand`: the requested demand (`RemoteHeatDemand`). Writable.
- `power`: the requested power, in %. Writable.
- `temperature`: the requested flow temperature, in °C. Writable.
- `await async_request(mode, heat_demand, *, power=None, temperature=None)`: take over the heat demand.
- `await async_stop()`: hand the heat demand back to the zones.

### `fallback` (`Fallback`)

Optional. Present when the gateway serves it. Every field is writable.

- `mode`: follow the controlling system or the fallback (`FallbackMode`).
- `configuration`: what happens when the controlling system goes quiet (`FallbackConfiguration`).
- `period`: how long it may stay quiet, in min.
- `power`: the fallback power, in %.
- `temperature`: the fallback temperature, in °C.
- `heat_demand`: the fallback demand (`HeatDemandType`).
- `analog_input_function`: what the 0-10 V input controls (`AnalogInputFunction`).
- `analog_input_voltage`: in V.

### Enums

- `ApplianceStatus`: `STANDBY`, `HEAT_DEMAND`, `GENERATOR_START`, `GENERATOR_CH`, `GENERATOR_DHW`, `GENERATOR_STOP`, `PUMP_POST_RUN`, `COOLING_ACTIVE`, `CONTROLLED_STOP`, `BLOCKING_MODE`, `LOCKING_MODE`, the load tests, `MANUAL_HEAT_DEMAND`, `FROST_PROTECTION`, `DEAERATION`, `HALTED`, `UNKNOWN` and more; see [`enums.py`](src/gtw08_modbus/enums.py).
- `ApplianceSubStatus`: about a hundred states; see [`enums.py`](src/gtw08_modbus/enums.py).
- `SeasonMode`: `WINTER`, `FROST_PROTECTION`, `SUMMER_NEUTRAL_BAND`, `SUMMER`.
- `HeatDemandStatus`, `GeneratorStatus`, `HydraulicStatus`: flag sets; see [`enums.py`](src/gtw08_modbus/enums.py).
- `ServiceNotification`: `NONE`, `A`, `B`, `C`, `CUSTOM`, `D`.
- `BoardCategory`: `CU_GH`, `CU_OH`, `EHC`, `MK`, `SCB`, `EEC`, `GATEWAY`.
- `ErrorType`: `LOCKING`, `BLOCKING`, `WARNING`.
- `ZoneFunction`: `DISABLED`, `DIRECT`, `MIXING_CIRCUIT`, `SWIMMING_POOL`, `HIGH_TEMPERATURE`, `FAN_CONVECTOR`, `DHW_TANK`, `ELECTRICAL_DHW`, `TIME_PROGRAM`, `PROCESS_HEAT`, `DHW_LAYERED`, `DHW_INTERNAL_TANK`, `DHW_COMMERCIAL_TANK`, `OCCUPIED`.
- `ZoneMode`: `SCHEDULING`, `MANUAL`, `OFF`, `TEMPORARY`.
- `ZoneActivity`: `OFF`, `ECO`, `COMFORT`, `ANTI_LEGIONELLA`.
- `RemoteControlMode`: `TEMPERATURE_AND_POWER`, `POWER`, `TEMPERATURE`, `MONITORING_ONLY`.
- `RemoteHeatDemand`: `STANDBY`, `HEATING`, `COOLING`.
- `CascadeMode`: `AUTOMATIC`, `HEATING`, `COOLING`.
- `CascadeType`: `TRADITIONAL`, `PARALLEL`.
- `CascadeManagement`: `TEMPERATURE`, `POWER`.
- `CascadeHeatDemand`, `HeatDemandType`: the kinds of heat demand; see [`enums.py`](src/gtw08_modbus/enums.py).
- `FallbackMode`: `BMS`, `FALLBACK`.
- `FallbackConfiguration`: `CANCEL_DIRECTLY`, `NEVER_CANCEL`, `MAINTAIN_FALLBACK`.
- `AnalogInputFunction`: `OFF`, `TEMPERATURE`, `POWER`.

### Errors

- `NoApplianceError`: setup finds no control board behind the gateway.
- `GatewayTargetError` (from modbus-connection): `async_detect()` ran out of retries while the gateway was still fetching.
- `ValueError`: `async_write_mode(ZoneMode.TEMPORARY)`, or `async_request()` without the power or temperature its mode needs.

The register addresses are in the component modules under [`src/gtw08_modbus`](src/gtw08_modbus), taken from the manufacturer's configuration manual 7854678.

## Troubleshooting

`script/query.py` reads the device once and prints every value:

```bash
uv run script/query.py /dev/ttyUSB0 --baudrate 9600 --parity N --unit 100
```

Add `--raw` to include the undecoded registers. A bug report about a wrong value needs them.

The `gtw08_modbus` logger reports at `DEBUG` which boards and zones setup found, which zones refused their registers, and what it polls.
