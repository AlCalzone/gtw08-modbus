# gtw08-modbus

Read and control heating appliances behind a GTW-08 Modbus gateway, as typed
Python objects instead of register numbers.

The library maps the GTW-08 register set onto
[modbus-connection](https://github.com/home-assistant-libs/modbus-connection)'s
device model. You hand it a `ModbusUnit`, call `async_update()`, and read the
sub-systems as attributes. It owns no connection and no I/O policy. The caller
does.

## Supported devices

The GTW-08 Modbus gateway connects to the L-Bus of appliances made by the BDR
Thermea group and sold under the Remeha, Brötje, De Dietrich and Baxi brands.
It works with gas and oil boilers (CU-GH and CU-OH control units), heat pumps
(EHC control units) and hybrids, and with the SCB expansion boards that add
zones. The register map follows the manufacturer's configuration manual
7854678, version 01 of 15 September 2023.

What an appliance serves depends on its type. Blocks that only some appliances
have are probed once at setup, and a block the gateway refuses is never polled:

| Block | Registers | Probed |
| :--- | :--- | :--- |
| Board count, zone count, error flag | 128, 189, 531 | no |
| System status, outdoor temperature | 272–280, 384–385 | no |
| Appliance temperatures, status, counters, energy | 400–461 | no |
| Service | 512–517 | no |
| Boards and their errors | 129–171, 532–547 | no |
| Zones 1 to 12 | 641–1118, every 512 registers | yes |
| Remote control of the heat demand | 256–259 | yes |
| Heat pump COP | 9230–9231 | yes |
| Cascade | 7001–7209 | yes |
| Producer serial number | 7228–7229 | yes |
| Fallback scenario and 0-10 V input | 21020–21027 | yes |

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

        print("Model:", appliance.model)
        print("Status:", appliance.appliance.status)
        print("Flow:", appliance.appliance.flow_temperature, "°C")
        print("Outdoor:", appliance.system_status.outdoor_temperature, "°C")
        for number, zone in appliance.zone_slots.items():
            print(f"Zone {number}:", zone.function, zone.mode, zone.flow_temperature)
    finally:
        await connection.close()


asyncio.run(main())
```

`async_detect()` sets the appliance up and reads it once. A caller that wants
no I/O up front constructs `Gtw08Appliance(unit)` directly. The first poll then
sets it up.

### Link settings

The gateway speaks Modbus RTU on RS-485. Its DIP switches set the line:

| Switches 1–2 | Baud rate | Switches 3–4 | Parity |
| :--- | :--- | :--- | :--- |
| off–off | 9600 (default) | off–off | none (default) |
| on–off | 19200 | on–off | odd |
| off–on | 38400 | off–on | even |
| on–on | 57600 | on–on | none |

The rotary dial sets the unit ID: position 0 is unit 100, the default, and
position F is unit 115. An RS-485 to Ethernet converter makes the gateway
reachable over the network.

### Addresses and values

The manual numbers registers by protocol address, so a field's address is the
manual's number. The 8-bit types arrive in the low byte of a register, and the
library ignores the high byte:

```python
appliance.appliance.water_pressure  # 1.8, from register 409 holding 0x0012
```

A value the gateway has no reading for decodes to `None`. That is 0x7FFF or
0x8000 for a signed 16-bit value, 0xFF for an 8-bit value, and all bits set
for the unsigned types.

### Readings and settings refresh separately

`Gtw08Appliance` splits its poll by what it reads:

- `async_update_readings()` reads what the appliance measures: system status,
  temperatures, counters, service state, board errors, zones and the cascade.
- `async_update_settings()` reads the remote control and fallback registers,
  which change only when something writes them.
- `async_update()` reads both, in one merged report.

Each sub-system is read on its own, so one refused block does not take the rest
of the poll with it. Every update method returns an `UpdateReport`. A failed
component keeps its previous values and is listed by attribute name with its
error. A dead link (`ModbusConnectionError`) raises, and so does a timeout
before any component has answered:

```python
report = await appliance.async_update_readings()
for name, error in report.failed.items():
    print(f"{name} kept its previous values: {error}")
```

`readings_components` and `settings_components` name what this appliance
polls, once setup has settled it.

### The gateway fetches lazily

The gateway reads a register from the appliance the first time a client asks
for it. Until it has the value, it answers with exception 0x0B,
`GatewayTargetError` in modbus-connection. `async_detect()` retries for that,
five times two seconds apart by default. A later poll that hits it lists the
component in `report.failed`, and the next poll has the value.

Exception 0x0A, `GatewayPathUnavailableError`, means the gateway sees no
appliance on its L-Bus.

### Boards

The gateway reports up to 16 control boards. The manual documents the first
eight. Each `Board` names its model and its error:

```python
for board in appliance.board_list:
    print(board.number, board.model, board.error_code, board.error_type)
# 1 EHC-04 None None
# 2 SCB-04 531 ErrorType.WARNING
```

`error_code` and `error_type` are `None` while the board reports no error. `is_available` turns
false when the gateway cannot reach the board. `appliance.model` is the first
board's model.

### Zones

Setup reads the zone count from register 189 and keeps every zone up to that
count whose function is not `DISABLED`. Zone `n` sits `512 * (n - 1)` registers
after zone 1:

```python
zone = appliance.zone_slots[1]
zone.function  # ZoneFunction.DIRECT
zone.mode  # ZoneMode.SCHEDULING
zone.room_setpoint  # 20.5, the setpoint in effect

await zone.async_write_mode(ZoneMode.MANUAL)
await zone.async_write_room_setpoint(21.0)  # held while the zone is manual
await zone.write("heating_curve_gradient", 1.2)
await zone.write("flow_setpoint_fixed", 45.0)
```

A zone takes `SCHEDULING`, `MANUAL` or `OFF`. `TEMPORARY` shows up in
`zone.mode` only.

### Remote control

The gateway can take over the system's heat demand. While it does, the
appliance ignores its zones:

```python
control = appliance.system_control
await control.async_request(
    RemoteControlMode.TEMPERATURE,
    RemoteHeatDemand.HEATING,
    temperature=55.0,
)
await control.async_stop()  # back to monitoring only
```

The manual requires register 258 to be written first. `async_request()` writes
the mode, then the power and temperature, then the heat demand.

`appliance.fallback` holds what the gateway does when the controlling system
stops writing, and the function of the smart control board's 0-10 V input.

### Cascade

Setup keeps `appliance.cascade` when register 7102 reports two producers or
more. It holds the cascade's mode, requests, pumps, state, hours and low loss
header temperatures.

### Diagnostics

`async_read_raw()` dumps every register the device reads, undecoded, keyed by
address space and address. Quote it in an issue about a wrong value.
modbus-connection's mock replays it with `load_raw()`, so the dump can become a
test.

## Checking a real device

`script/query.py` reads one appliance once and prints every value it serves. It
is the quickest way to check the wiring and the link settings:

```bash
uv run script/query.py /dev/ttyUSB0
uv run script/query.py /dev/ttyUSB0 --baudrate 19200 --parity E --unit 101
uv run script/query.py socket://192.168.1.60:8899
uv run script/query.py 192.168.1.60 --transport tcp --raw
```

`--raw` adds every register it read, undecoded. The script prints the read
count too, which includes the probes setup makes.

## Timing

Reads cover only the registers the manual documents, and neighbouring
registers merge into one read. A heat pump with three zones takes about 45
reads per poll, a few seconds at 9600 baud. A caller who has measured their
link passes `timeout=` to the constructor or to `async_detect()`, which asks
for it through `ModbusUnit.require_timeout()`.

## Debug logging

The `gtw08_modbus` logger says at `DEBUG` which boards and zones setup found,
which zones refused their registers, and the final poll list.

## Known gaps

The manual leaves a few things open. The library takes these readings of it:

- Table 33 lists addresses for zones 7 to 12 of registers 1107, 1108, 1110 and
  1111 that do not follow the 512-register step every other zone register
  follows. Zone 7's register 1107 is listed at 5121, where the step gives 4179.
  The library uses the step. Table 35 and table 40 have single addresses off by
  one or two in the same way.
- The zone functions are listed without values. The library numbers them in
  the manual's order, from `DISABLED` as 0 to `OCCUPIED` as 13.
- The board number in a device type is read as decimal. `0x190A` is `SCB-10`.
- The values that mean "not available" are not documented. The library uses
  the conventions in "Addresses and values" above.
- Registers 514 and 515 give a resolution of "2 hours". The library reports
  the raw value in hours.
- Register 415 is described as a start counter with a resolution of 0.1 µA.
  The library does not read it. Register 1111 has no clear meaning and is not
  read either.
- Table 48 lists the cascade members' power, flow temperature, status and
  special request without data types. The library does not read them.
- The manual lists function code 16 as the write function for every data type.
  Every write goes out as function code 16.
