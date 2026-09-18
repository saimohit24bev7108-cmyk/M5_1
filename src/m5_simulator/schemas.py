import json
import os
from typing import Any, Dict, List, Optional, Union
import jsonschema
from jsonschema import validate, ValidationError

class SchemaValidationError(Exception):
    """Raised when data does not conform to the M5 simulator schemas."""
    def __init__(self, message: str, path: Optional[List[str]] = None):
        self.message = message
        self.path = path
        super().__init__(self.message)

    def __str__(self):
        path_str = " -> ".join(self.path) if self.path else "root"
        return f"SchemaValidationError at {path_str}: {self.message}"

def load_schema(schema_name: str) -> Dict[str, Any]:
    """Loads a JSON schema from the schemas directory."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schemas", f"{schema_name}.schema.json")
    try:
        with open(schema_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(f"Schema file {schema_path} not found.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to decode schema {schema_path}: {e}")

def validate_circuit(data: Dict[str, Any]) -> None:
    """
    Validates a circuit definition against the M5 circuit schema.
    Includes cross-field validation for qubit ranges.
    """
    schema = load_schema("circuit")
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise SchemaValidationError(e.message, list(e.path))

    # Cross-field validation: qubit range
    qubits_count = data.get("qubits")
    for i, op in enumerate(data.get("operations", [])):
        targets = op.get("targets", [])
        for target in targets:
            if target < 0 or target >= qubits_count:
                raise SchemaValidationError(
                    f"Qubit index {target} out of range for circuit with {qubits_count} qubits",
                    ["operations", str(i), "targets"]
                )

def validate_configuration(data: Dict[str, Any]) -> None:
    """Validates configuration against the M5 configuration schema."""
    schema = load_schema("configuration")
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise SchemaValidationError(e.message, list(e.path))

def validate_result(data: Dict[str, Any]) -> None:
    """Validates result against the M5 result schema."""
    schema = load_schema("result")
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise SchemaValidationError(e.message, list(e.path))

def validate_run(data: Dict[str, Any]) -> None:
    """Validates run metadata against the M5 run schema."""
    schema = load_schema("run")
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise SchemaValidationError(e.message, list(e.path))
