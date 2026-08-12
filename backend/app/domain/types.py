from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SystemState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    OPENING_VALVE = "OPENING_VALVE"
    FEEDING = "FEEDING"
    CLOSING_VALVE = "CLOSING_VALVE"
    WAITING_FOR_FRUIT = "WAITING_FOR_FRUIT"
    ACQUIRING = "ACQUIRING"
    CLASSIFYING = "CLASSIFYING"
    SORTING_SAFE = "SORTING_SAFE"
    SORTING_UNSAFE = "SORTING_UNSAFE"
    PURGING = "PURGING"
    CYCLE_COMPLETE = "CYCLE_COMPLETE"
    ATTENTION_REQUIRED = "ATTENTION_REQUIRED"
    PAUSED = "PAUSED"
    MANUAL = "MANUAL"
    MAINTENANCE = "MAINTENANCE"
    ERROR = "ERROR"
    E_STOPPED = "E_STOPPED"


class ControlOwner(str, Enum):
    NONE = "NONE"
    AUTOMATION = "AUTOMATION"
    MANUAL = "MANUAL"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY = "EMERGENCY"


class FruitCondition(str, Enum):
    FRESH = "FRESH"
    ROTTEN = "ROTTEN"
    FORMALIN_CONTAMINATED = "FORMALIN_CONTAMINATED"
    CALCIUM_CARBIDE_CONTAMINATED = "CALCIUM_CARBIDE_CONTAMINATED"
    INCONCLUSIVE = "INCONCLUSIVE"


class Route(str, Enum):
    SAFE = "SAFE"
    UNSAFE = "UNSAFE"


class StateVersionRequest(BaseModel):
    expected_state_version: int = Field(alias="expectedStateVersion", ge=0)


class OperatorRequest(StateVersionRequest):
    operator: str = Field(min_length=1, max_length=80)


class ManualCommandRequest(OperatorRequest):
    command: str = Field(min_length=1, max_length=80)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ConfigurationSaveRequest(OperatorRequest):
    description: str = Field(min_length=1, max_length=240)
    values: dict[str, Any]


class ResetConfigurationRequest(OperatorRequest):
    source: str = Field(default="reset_values")


class ApiError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

