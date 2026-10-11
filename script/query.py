#!/usr/bin/env python3

"""Query the appliance behind a GTW-08 gateway and print every value."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from modbus_connection import ModbusError
from modbus_connection.cli_helper import (
    CountingUnit,
    add_connection_args,
    connect_from_args,
    print_component,
)

from gtw08_modbus import DEFAULT_UNIT_ID, Gtw08Appliance, NoApplianceError

# The gateway speaks Modbus RTU on RS-485. An RS-485 to Ethernet converter
# makes it reachable as Modbus TCP, or as RTU through a socket:// URL.
CONNECTIONS = (("serial", None), ("tcp", None))

EXAMPLES = """examples:
  uv run script/query.py /dev/ttyUSB0
  uv run script/query.py /dev/ttyUSB0 --baudrate 19200 --parity E --unit 101
  uv run script/query.py socket://192.168.1.60:8899
  uv run script/query.py 192.168.1.60 --transport tcp --raw
"""


def print_appliance(appliance: Gtw08Appliance) -> None:
    """Print each component the appliance serves, under its attribute name."""
    for name in ("summary", "system_status", "appliance", "heat_pump", "service"):
        if (component := getattr(appliance, name)) is not None:
            print_component(component, title=name)
            print()
    print(f"serial_number  {appliance.serial_number}")
    print(f"board_count    {appliance.board_count}")
    print(f"zone_count     {appliance.zone_count}")
    for board in appliance.board_list:
        title = f"board_{board.number}"
        print(f"\n{title}\n{'-' * len(title)}")
        print(f"  model       {board.model}")
        print(f"  available   {board.is_available}")
        print(f"  error_code  {board.error_code}")
        print(f"  error_type  {board.error_type}")
    for number, zone in appliance.zone_slots.items():
        print(f"\nzone_{number}  function {zone.function_code} ({zone.function})")
        print_component(zone.readings, title=f"zone_{number}_readings")
        print()
        print_component(zone.settings, title=f"zone_{number}_settings")
    for name in ("cascade", "system_control", "fallback"):
        if (component := getattr(appliance, name)) is not None:
            print()
            print_component(component, title=name)


async def main() -> int:
    """Read one appliance and print it."""
    # The backend logs a failed connect at ERROR with its traceback; the
    # messages below say it in one line.
    logging.getLogger().addHandler(logging.NullHandler())

    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_connection_args(parser, connections=CONNECTIONS)
    parser.add_argument(
        "--unit",
        type=int,
        default=DEFAULT_UNIT_ID,
        help="Modbus unit id: 100 plus the rotary dial position",
    )
    parser.add_argument(
        "--raw", action="store_true", help="also dump every register read, as JSON"
    )
    args = parser.parse_args()

    try:
        connection = await connect_from_args(args)
    except ModbusError as err:
        # A connect timeout arrives with no message of its own.
        detail = str(err) or type(err).__name__
        print(f"Could not connect to {args.target}: {detail}")
        return 1

    counting = CountingUnit(connection.for_unit(args.unit))
    try:
        appliance = await Gtw08Appliance.async_detect(counting)
        # A raw dump re-reads everything, so count the detection alone.
        poll_reads = counting.reads
        raw = await appliance.async_read_raw() if args.raw else None
    except NoApplianceError as err:
        print(f"No appliance behind the gateway: {err}")
        return 1
    except ModbusError as err:
        print(f"Could not read the appliance: {str(err) or type(err).__name__}")
        return 1
    finally:
        await connection.close()

    print_appliance(appliance)
    if raw is not None:
        print("\nRaw registers")
        # The dump arrives address-ordered; sorting keys would undo that.
        print(json.dumps(raw, indent=2))
    print(f"\n{poll_reads} Modbus reads")
    return 0


raise SystemExit(asyncio.run(main()))
