"""The coded values of the GTW-08 register map."""

from __future__ import annotations

from enum import IntEnum, IntFlag


class SeasonMode(IntEnum):
    """Register 385: the seasonal mode in effect."""

    WINTER = 0
    FROST_PROTECTION = 1
    SUMMER_NEUTRAL_BAND = 2
    SUMMER = 3


class HeatDemandStatus(IntFlag):
    """Register 275: what the zones' heat demand allows."""

    DIRECT_ZONES_ALLOWED = 1 << 0
    MIXING_CIRCUITS_ALLOWED = 1 << 1
    VALVES_OPEN_PUMP_RUNNING = 1 << 2
    """All valves are open and the pump runs, within safety limits."""
    MANUAL_HEAT_DEMAND = 1 << 3
    COOLING_ALLOWED = 1 << 4
    DHW_ALLOWED = 1 << 5
    HEAT_ENGINE_ACTIVE = 1 << 6


class GeneratorStatus(IntFlag):
    """Register 279: which heat generators run, and what needs attention."""

    FLAME_ON = 1 << 0
    HEAT_PUMP_ON = 1 << 1
    BACKUP_1_ON = 1 << 2
    """The first electrical backup stage."""
    BACKUP_2_ON = 1 << 3
    DHW_BACKUP_ON = 1 << 4
    """The electrical backup of the domestic hot water tank."""
    SERVICE_REQUIRED = 1 << 5
    RESET_NEEDED = 1 << 6
    """A power down or a manual reset is needed."""
    WATER_PRESSURE_LOW = 1 << 7


class HydraulicStatus(IntFlag):
    """Register 280: the pump, the three-way valve and what the heat goes to."""

    PUMP_ON = 1 << 0
    VALVE_OPEN = 1 << 1
    """The three-way valve is open."""
    VALVE = 1 << 2
    """The manual names this bit "3-way valve" and says no more."""
    VALVE_CLOSED = 1 << 3
    DHW_ACTIVE = 1 << 4
    CH_ACTIVE = 1 << 5
    """Central heating is active."""
    COOLING_ACTIVE = 1 << 6


class ApplianceStatus(IntEnum):
    """Register 411 (display code AM012): the appliance's main status."""

    STANDBY = 0
    HEAT_DEMAND = 1
    GENERATOR_START = 2
    GENERATOR_CH = 3
    """Running for central heating."""
    GENERATOR_DHW = 4
    """Running for domestic hot water."""
    GENERATOR_STOP = 5
    PUMP_POST_RUN = 6
    COOLING_ACTIVE = 7
    CONTROLLED_STOP = 8
    """The start conditions are not met."""
    BLOCKING_MODE = 9
    LOCKING_MODE = 10
    LOAD_TEST_MIN = 11
    LOAD_TEST_CH_MAX = 12
    LOAD_TEST_DHW_MAX = 13
    LOAD_TEST_CUSTOM = 14
    """Listed for the cascade producer status (register 7209) only."""
    MANUAL_HEAT_DEMAND = 15
    FROST_PROTECTION = 16
    DEAERATION = 17
    CONTROL_UNIT_COOLING = 18
    """The fan runs to cool the inside of the appliance."""
    RESET_IN_PROGRESS = 19
    AUTO_FILLING = 20
    HALTED = 21
    """Stopped until someone resets it by hand."""
    FORCED_CALIBRATION = 22
    FACTORY_TEST = 23
    HYDRONIC_BALANCING = 24
    DEVICE_MODE = 200
    """A service tool controls the appliance."""
    UNKNOWN = 254


class ApplianceSubStatus(IntEnum):
    """Register 412 (display code AM014): what the appliance does right now."""

    STANDBY = 0
    ANTI_CYCLING = 1
    CLOSE_HYDRAULIC_VALVE = 2
    CLOSE_PUMP = 3
    WAITING_FOR_START_CONDITIONS = 4
    CLOSE_EXTERNAL_GAS_VALVE = 10
    START_TO_FLUE_GAS_VALVE = 11
    CLOSE_FLUE_GAS_VALVE = 12
    FAN_TO_PRE_PURGE = 13
    WAIT_FOR_RELEASE_SIGNAL = 14
    BURNER_ON_COMMAND_TO_SAFETY_UNIT = 15
    VALVE_PROVING_TEST = 16
    PRE_IGNITION = 17
    IGNITION = 18
    FLAME_CHECK = 19
    INTERPURGE = 20
    GENERATOR_STARTING = 21
    NORMAL_INTERNAL_SETPOINT = 30
    LIMITED_INTERNAL_SETPOINT = 31
    NORMAL_POWER_CONTROL = 32
    GRADIENT_LEVEL_1_POWER_CONTROL = 33
    GRADIENT_LEVEL_2_POWER_CONTROL = 34
    GRADIENT_LEVEL_3_POWER_CONTROL = 35
    PROTECT_FLAME_POWER_CONTROL = 36
    STABILIZATION_TIME = 37
    COLD_START = 38
    CH_RESUME = 39
    SAFETY_UNIT_REMOVE_BURNER = 40
    FAN_TO_POST_PURGE = 41
    OPEN_EXTERNAL_FLUE_GAS_VALVE = 42
    STOP_FAN_TO_FLUE_GAS_VALVE_RPM = 43
    STOP_FAN = 44
    LIMITED_POWER_ON_FLUE_GAS_TEMPERATURE = 45
    AUTO_FILLING_INSTALLATION = 46
    AUTO_FILLING_TOP_UP = 47
    REDUCED_SETPOINT = 48
    OFFSET_ADAPTION = 49
    PUMP_POST_RUNNING = 60
    OPEN_PUMP = 61
    OPEN_HYDRAULIC_VALVE = 62
    START_ANTI_CYCLE_TIME = 63
    COMPRESSOR_RELIEVED = 65
    HEAT_PUMP_TMAX_BACKUP_ON = 66
    OUTDOOR_LIMIT_HEAT_PUMP_OFF = 67
    HEAT_PUMP_STOP_BY_HYBRID = 68
    DEFROST_WITH_HEAT_PUMP = 69
    DEFROST_WITH_BACKUP = 70
    DEFROST_HEAT_PUMP_BACKUP = 71
    SOURCE_PUMP_BACKUP = 72
    HEAT_PUMP_FLOW_OVER_TMAX = 73
    SOURCE_PUMP_POST_RUN = 74
    HEAT_PUMP_OFF_HIGH_HUMIDITY = 75
    HEAT_PUMP_OFF_WATER_FLOW = 76
    HUMIDITY_SETPOINT = 78
    GENERATORS_RELIEVED = 79
    HEAT_PUMP_RELIEVED_COOLING = 80
    HEAT_PUMP_STOP_OUTDOOR_TEMPERATURE = 81
    HEAT_PUMP_OFF_FLOW_TMAX = 82
    DEAIR_PUMP_VALVE_CH = 83
    DEAIR_PUMP_VALVE_DHW = 84
    DEAIR_VALVE_CH = 85
    DEAIR_VALVE_DHW = 86
    BLOCKING_INPUT_BACKUP_OFF = 88
    BLOCKING_INPUT_HEAT_PUMP_OFF = 89
    BLOCKING_INPUT_HEAT_PUMP_BACKUP_OFF = 90
    LOW_TARIFF = 91
    PV_WITH_HEAT_PUMP = 92
    PV_HEAT_PUMP_AND_BACKUP = 93
    SMART_GRID = 94
    WAITING_FOR_WATER_PRESSURE = 95
    NO_PRODUCER_AVAILABLE = 96
    INCREASED_MIN_POWER = 97
    DECREASED_MAX_POWER = 98
    FREE_COOLING_PUMP_OFF = 102
    FREE_COOLING_PUMP_ON = 103
    SOURCE_PUMP_PRE_RUN = 104
    CALIBRATION = 105
    BLOCKING_ACTIVE = 106
    WARM_UP = 107
    DEFROST_CURATIVE = 108
    DEFROST_PREVENTIVE = 109
    INITIALISING_DONE = 200
    INITIALISING_CSU = 201
    INITIALISING_IDENTIFIERS = 202
    INITIALISING_BLOCKING_PARAMETERS = 203
    INITIALISING_SAFETY_UNIT = 204
    INITIALISING_BLOCKING = 205
    UNKNOWN = 254
    SAFETY_UNIT_OUT_OF_RESETS = 255
    """Too many resets: wait an hour, or switch the power off and on."""


class RemoteControlMode(IntEnum):
    """Register 258: what the gateway takes over from the appliance's own control."""

    TEMPERATURE_AND_POWER = 0
    POWER = 1
    TEMPERATURE = 2
    MONITORING_ONLY = 3
    """The default. Registers 256, 257 and 259 have no effect."""


class RemoteHeatDemand(IntEnum):
    """Register 259: the heat demand the gateway requests."""

    STANDBY = 0
    HEATING = 7
    COOLING = 8


class CascadeHeatDemand(IntEnum):
    """Registers 7107 and 7110: the kind of heat demand on the cascade."""

    AUTOMATIC = 0
    HEATING = 1
    COOLING = 2
    PROCESS_HEAT = 3
    SCREED_DRYING = 4
    DHW_MEDIUM_PRIORITY = 5
    DHW_LOW_PRIORITY = 6
    CENTRAL_HEATING = 7
    CENTRAL_COOLING = 8
    ELECTRICAL_ACTIVE = 9
    ELECTRICAL_REACTIVE = 10


class HeatDemandType(IntEnum):
    """Register 21025: the kind of fallback heat demand."""

    NONE = 0
    DHW_PRIMARY = 1
    DHW_HIGH_PRIORITY = 2
    PROCESS_HEAT = 3
    SCREED_DRYING = 4
    DHW_MEDIUM_PRIORITY = 5
    DHW_LOW_PRIORITY = 6
    CENTRAL_HEATING = 7
    COOLING = 8
    ELECTRICAL_ACTIVE = 9
    ELECTRICAL_REACTIVE = 10


class ServiceNotification(IntEnum):
    """Register 513: the current or upcoming service."""

    NONE = 0
    A = 1
    B = 2
    C = 3
    CUSTOM = 4
    D = 5


class BoardCategory(IntEnum):
    """The high byte of a board's device type: what kind of board it is."""

    CU_GH = 0x00
    """Control unit of a gas boiler."""
    CU_OH = 0x01
    """Control unit of an oil boiler."""
    EHC = 0x02
    """Control unit of a heat pump."""
    MK = 0x14
    SCB = 0x19
    """Smart control board, an expansion board for zones."""
    EEC = 0x1B
    GATEWAY = 0x1E


class ErrorType(IntEnum):
    """Registers 533, 535, ...: how serious a board's error is."""

    LOCKING = 0
    """The appliance stays off until someone resets it."""
    BLOCKING = 3
    """The appliance is off until the cause goes away."""
    WARNING = 6


class ZoneFunction(IntEnum):
    """Registers 641, 1153, ... (display code CP02X): what a zone heats.

    The manual lists the names without their values. These follow its order.
    """

    DISABLED = 0
    DIRECT = 1
    MIXING_CIRCUIT = 2
    SWIMMING_POOL = 3
    HIGH_TEMPERATURE = 4
    FAN_CONVECTOR = 5
    DHW_TANK = 6
    ELECTRICAL_DHW = 7
    TIME_PROGRAM = 8
    PROCESS_HEAT = 9
    DHW_LAYERED = 10
    DHW_INTERNAL_TANK = 11
    DHW_COMMERCIAL_TANK = 12
    OCCUPIED = 13

    @property
    def is_dhw(self) -> bool:
        """Whether the zone heats domestic hot water."""
        return self in _DHW_FUNCTIONS

    @property
    def is_room_heating(self) -> bool:
        """Whether the zone heats rooms and takes a room temperature setpoint."""
        return self in _ROOM_HEATING_FUNCTIONS


_DHW_FUNCTIONS = frozenset(
    {
        ZoneFunction.DHW_TANK,
        ZoneFunction.ELECTRICAL_DHW,
        ZoneFunction.DHW_LAYERED,
        ZoneFunction.DHW_INTERNAL_TANK,
        ZoneFunction.DHW_COMMERCIAL_TANK,
    }
)
_ROOM_HEATING_FUNCTIONS = frozenset(
    {
        ZoneFunction.DIRECT,
        ZoneFunction.MIXING_CIRCUIT,
        ZoneFunction.HIGH_TEMPERATURE,
        ZoneFunction.FAN_CONVECTOR,
    }
)


class ZoneMode(IntEnum):
    """Registers 649, 1108, ... (display codes CP32X, CM12X): how a zone is run."""

    SCHEDULING = 0
    """The zone follows its time program."""
    MANUAL = 1
    """The zone holds the manual setpoint."""
    OFF = 2
    """Frost protection only."""
    TEMPORARY = 3
    """A temporary override of the time program. Read only."""


class ZoneActivity(IntEnum):
    """Registers 1107, 1619, ... (display code CM13X): the zone's current activity."""

    OFF = 0
    ECO = 1
    COMFORT = 2
    ANTI_LEGIONELLA = 3


class CascadeMode(IntEnum):
    """Register 7001: what the cascade produces."""

    AUTOMATIC = 0
    HEATING = 1
    COOLING = 2


class CascadeType(IntEnum):
    """Register 7002: how the cascade starts its producers."""

    TRADITIONAL = 0
    PARALLEL = 1


class CascadeManagement(IntEnum):
    """Register 7009: what the cascade controls for."""

    TEMPERATURE = 0
    POWER = 1


class FallbackMode(IntEnum):
    """Register 21020: whether the gateway falls back to its own heat demand."""

    BMS = 0
    """Follow the heat demand the BMS last set."""
    FALLBACK = 1
    """Use the fallback heat demand in registers 21023 to 21025."""


class FallbackConfiguration(IntEnum):
    """Register 21021: what happens to the heat demand when the BMS goes quiet."""

    CANCEL_DIRECTLY = 0
    NEVER_CANCEL = 1
    MAINTAIN_FALLBACK = 2


class AnalogInputFunction(IntEnum):
    """Register 21026 (display code EP014): what the 0-10 V input controls."""

    OFF = 0
    TEMPERATURE = 1
    POWER = 2
