"""Read and control heating appliances behind a GTW-08 Modbus gateway."""

from .appliance import Appliance, HeatPumpPerformance, Service, SystemStatus
from .boards import Board, ErrorSummary
from .cascade import Cascade
from .control import Fallback, SystemControl
from .device import DEFAULT_UNIT_ID, Gtw08Appliance
from .enums import (
    AnalogInputFunction,
    ApplianceStatus,
    ApplianceSubStatus,
    BoardCategory,
    CascadeHeatDemand,
    CascadeManagement,
    CascadeMode,
    CascadeType,
    ErrorType,
    FallbackConfiguration,
    FallbackMode,
    GeneratorStatus,
    HeatDemandStatus,
    HeatDemandType,
    HydraulicStatus,
    RemoteControlMode,
    RemoteHeatDemand,
    SeasonMode,
    ServiceNotification,
    ZoneActivity,
    ZoneFunction,
    ZoneMode,
)
from .errors import (
    GatewayNotReadyError,
    Gtw08Error,
    InvalidValueError,
    NoApplianceError,
)
from .model import UpdateReport
from .zone import Zone

__all__ = [
    "DEFAULT_UNIT_ID",
    "AnalogInputFunction",
    "Appliance",
    "ApplianceStatus",
    "ApplianceSubStatus",
    "Board",
    "BoardCategory",
    "Cascade",
    "CascadeHeatDemand",
    "CascadeManagement",
    "CascadeMode",
    "CascadeType",
    "ErrorSummary",
    "ErrorType",
    "Fallback",
    "FallbackConfiguration",
    "FallbackMode",
    "GatewayNotReadyError",
    "GeneratorStatus",
    "Gtw08Appliance",
    "Gtw08Error",
    "HeatDemandStatus",
    "HeatDemandType",
    "HeatPumpPerformance",
    "HydraulicStatus",
    "InvalidValueError",
    "NoApplianceError",
    "RemoteControlMode",
    "RemoteHeatDemand",
    "SeasonMode",
    "Service",
    "ServiceNotification",
    "SystemControl",
    "SystemStatus",
    "UpdateReport",
    "Zone",
    "ZoneActivity",
    "ZoneFunction",
    "ZoneMode",
]
