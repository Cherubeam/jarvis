"""Unit tests for output schema validation."""

import pytest

from packages.core.output_schema import (
    validate_output,
    schema_to_litellm_format,
    schema_to_prompt_instruction,
    SchemaValidationError,
)


@pytest.mark.unit
class TestValidateOutput:

    SCHEMA = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "count": {"type": "integer"},
            "score": {"type": "number"},
            "active": {"type": "boolean"},
            "tags": {"type": "array"},
            "meta": {"type": "object"},
            "level": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["title", "count"],
    }

    def test_valid_output(self):
        errors = validate_output(
            {"title": "Test", "count": 5, "score": 0.9},
            self.SCHEMA,
        )
        assert errors == []

    def test_missing_required_field(self):
        errors = validate_output({"title": "Test"}, self.SCHEMA)
        assert len(errors) == 1
        assert "count" in errors[0]

    def test_wrong_type_string(self):
        errors = validate_output({"title": 42, "count": 5}, self.SCHEMA)
        assert any("title" in e for e in errors)

    def test_wrong_type_integer(self):
        errors = validate_output({"title": "T", "count": "five"}, self.SCHEMA)
        assert any("count" in e for e in errors)

    def test_wrong_type_number(self):
        errors = validate_output({"title": "T", "count": 1, "score": "high"}, self.SCHEMA)
        assert any("score" in e for e in errors)

    def test_wrong_type_boolean(self):
        errors = validate_output({"title": "T", "count": 1, "active": "yes"}, self.SCHEMA)
        assert any("active" in e for e in errors)

    def test_wrong_type_array(self):
        errors = validate_output({"title": "T", "count": 1, "tags": "a,b"}, self.SCHEMA)
        assert any("tags" in e for e in errors)

    def test_wrong_type_object(self):
        errors = validate_output({"title": "T", "count": 1, "meta": [1, 2]}, self.SCHEMA)
        assert any("meta" in e for e in errors)

    def test_enum_valid(self):
        errors = validate_output({"title": "T", "count": 1, "level": "high"}, self.SCHEMA)
        assert errors == []

    def test_enum_invalid(self):
        errors = validate_output({"title": "T", "count": 1, "level": "extreme"}, self.SCHEMA)
        assert any("level" in e for e in errors)

    def test_non_object_schema_no_validation(self):
        errors = validate_output({"anything": True}, {"type": "array"})
        assert errors == []


@pytest.mark.unit
class TestSchemaConversion:

    def test_to_litellm_format(self):
        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        result = schema_to_litellm_format(schema, name="my_output")
        assert result["type"] == "json_schema"
        assert result["json_schema"]["name"] == "my_output"
        assert result["json_schema"]["schema"] == schema

    def test_to_prompt_instruction(self):
        schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        instruction = schema_to_prompt_instruction(schema)
        assert "JSON" in instruction
        assert "title" in instruction
