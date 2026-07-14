from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from sqlalchemy.orm import Session


JSONSchema = dict[str, Any]
ToolHandler = Callable[[dict[str, Any], Session], dict[str, Any]]


class ToolValidationError(ValueError):
    """Raised when model-provided tool args do not match the tool contract."""


class AgentStopReason(str, Enum):
    FINAL_ANSWER = "final_answer"
    TOOL_CALL_VALIDATION_FAILED = "tool_call_validation_failed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    REPEATED_TOOL_FAILURE = "repeated_tool_failure"
    ITERATION_LIMIT = "iteration_limit"
    CLARIFICATION_REQUESTED = "clarification_requested"
    APPROVAL_REQUIRED = "approval_required"
    PROVIDER_LACKS_TOOL_CALLING = "provider_lacks_tool_calling"


class ToolPermission(str, Enum):
    READ = "read"
    DRAFT = "draft"
    WRITE = "write"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ToolCallResult:
    name: str
    ok: bool
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    summary: str = ""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    permission: ToolPermission
    tier: int
    required_scopes: frozenset[str]
    side_effects: frozenset[str]
    input_schema: JSONSchema
    output_schema: JSONSchema
    handler: ToolHandler
    is_terminal: bool = False
    result_size_limit: int = 16_000
    trace_redaction: frozenset[str] = field(default_factory=frozenset)

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(args, dict):
            raise ToolValidationError("tool args must be an object")
        _validate_json_object(args, self.input_schema)
        return dict(args)

    def to_model_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


def _type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float) and not isinstance(value, bool))
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "null":
        return value is None
    return True


def _validate_json_object(args: dict[str, Any], schema: JSONSchema) -> None:
    if schema.get("type") != "object":
        raise ToolValidationError("tool input schema must be an object schema")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise ToolValidationError("tool input schema properties must be an object")

    required = schema.get("required", [])
    if not isinstance(required, list):
        raise ToolValidationError("tool input schema required must be an array")

    for name in required:
        if name not in args:
            raise ToolValidationError(f"{name} is required")

    if schema.get("additionalProperties") is False:
        allowed = set(properties)
        extras = sorted(key for key in args if key not in allowed)
        if extras:
            raise ToolValidationError(f"unexpected argument: {extras[0]}")

    for name, value in args.items():
        property_schema = properties.get(name)
        if not isinstance(property_schema, dict):
            continue
        expected = property_schema.get("type")
        if isinstance(expected, list):
            if not any(isinstance(item, str) and _type_matches(value, item) for item in expected):
                raise ToolValidationError(f"{name} has invalid type")
        elif isinstance(expected, str) and not _type_matches(value, expected):
            raise ToolValidationError(f"{name} has invalid type")

        if isinstance(value, int | float) and not isinstance(value, bool):
            minimum = property_schema.get("minimum")
            maximum = property_schema.get("maximum")
            if isinstance(minimum, int | float) and value < minimum:
                raise ToolValidationError(f"{name} must be at least {minimum}")
            if isinstance(maximum, int | float) and value > maximum:
                raise ToolValidationError(f"{name} must be at most {maximum}")
