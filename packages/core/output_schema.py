"""
Structured output schema handling for inter-agent communication.

Provides schema validation and LLM response_format conversion for
workflow steps that require structured output.
"""

import json
import logging

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Raised when output doesn't match the expected schema."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Schema validation failed: {'; '.join(errors)}")


def validate_output(data: dict, schema: dict) -> list[str]:
    """Validate a data dict against a JSON Schema (simplified).

    Checks required fields and basic type constraints. Does NOT implement
    the full JSON Schema spec -- just enough for workflow inter-agent contracts.

    Args:
        data: The parsed output to validate.
        schema: The JSON Schema to validate against.

    Returns:
        List of error messages. Empty = valid.
    """
    errors: list[str] = []

    if schema.get("type") != "object":
        return errors  # Only object schemas supported

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Check required fields
    for field_name in required:
        if field_name not in data:
            errors.append(f"Missing required field: '{field_name}'")

    # Check types for present fields
    for field_name, field_schema in properties.items():
        if field_name not in data:
            continue

        value = data[field_name]
        expected_type = field_schema.get("type")

        if expected_type == "string" and not isinstance(value, str):
            errors.append(f"Field '{field_name}' should be string, got {type(value).__name__}")
        elif expected_type == "integer" and not isinstance(value, int):
            errors.append(f"Field '{field_name}' should be integer, got {type(value).__name__}")
        elif expected_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Field '{field_name}' should be number, got {type(value).__name__}")
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Field '{field_name}' should be boolean, got {type(value).__name__}")
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{field_name}' should be array, got {type(value).__name__}")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{field_name}' should be object, got {type(value).__name__}")

        # Check enum constraint
        if "enum" in field_schema and value not in field_schema["enum"]:
            errors.append(
                f"Field '{field_name}' must be one of {field_schema['enum']}, got '{value}'"
            )

    return errors


def schema_to_litellm_format(schema: dict, name: str = "output") -> dict:
    """Convert a JSON Schema to LiteLLM's response_format parameter.

    Args:
        schema: JSON Schema dict.
        name: Name for the schema (used by some providers).

    Returns:
        Dict suitable for passing as response_format to LiteLLM.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema,
        },
    }


def schema_to_prompt_instruction(schema: dict) -> str:
    """Convert a JSON Schema to a prompt instruction string.

    Used as a fallback when the LLM provider doesn't support
    response_format with json_schema.

    Args:
        schema: JSON Schema dict.

    Returns:
        Instruction string to append to the agent's task prompt.
    """
    schema_str = json.dumps(schema, indent=2)
    return (
        "IMPORTANT: Respond with valid JSON matching this schema:\n"
        f"```json\n{schema_str}\n```\n"
        "Do not include any text outside the JSON object."
    )
