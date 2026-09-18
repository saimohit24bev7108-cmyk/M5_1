import pytest
from src.m5_simulator.schemas import (
    validate_circuit, validate_configuration, validate_result, validate_run, SchemaValidationError
)

# --- Valid Data ---

VALID_CIRCUIT = {
    "version": "1.0",
    "qubits": 2,
    "operations": [
        {"gate": "H", "targets": [0]},
        {"gate": "CNOT", "targets": [0, 1]}
    ]
}

VALID_CONFIG = {
    "version": "1.0",
    "mode": "ideal",
    "shots": 1024,
    "seed": 42
}

VALID_RESULT = {
    "version": "1.0",
    "run_id": "run-123",
    "simulator_version": "0.1.0",
    "qubits": 2,
    "shots": 1024,
    "seed": 42,
    "probabilities": [0.5, 0, 0, 0.5],
    "histogram": {"00": 512, "11": 512},
    "result_label": "SIMULATION"
}

VALID_RUN = {
    "version": "1.0",
    "run_id": "run-123",
    "simulator_version": "0.1.0",
    "timestamps": {
        "start": "2026-09-18T10:00:00Z",
        "end": "2026-09-18T10:00:01Z"
    },
    "status": "completed",
    "checksums": {"result": "abc123def"},
    "result_label": "SIMULATION"
}

# --- Tests ---

def test_valid_acceptances():
    validate_circuit(VALID_CIRCUIT)
    validate_configuration(VALID_CONFIG)
    validate_result(VALID_RESULT)
    validate_run(VALID_RUN)

def test_circuit_qubits_range():
    # 0 qubits
    with pytest.raises(SchemaValidationError):
        validate_circuit({**VALID_CIRCUIT, "qubits": 0})
    # > 8 qubits
    with pytest.raises(SchemaValidationError):
        validate_circuit({**VALID_CIRCUIT, "qubits": 9})

def test_circuit_unknown_gate():
    with pytest.raises(SchemaValidationError):
        validate_circuit({
            **VALID_CIRCUIT,
            "operations": [{"gate": "UNKNOWN", "targets": [0]}]
        })

def test_circuit_single_qubit_gate_wrong_targets():
    # Too few
    with pytest.raises(SchemaValidationError):
        validate_circuit({
            **VALID_CIRCUIT,
            "operations": [{"gate": "H", "targets": []}]
        })
    # Too many
    with pytest.raises(SchemaValidationError):
        validate_circuit({
            **VALID_CIRCUIT,
            "operations": [{"gate": "H", "targets": [0, 1]}]
        })

def test_circuit_cnot_duplicate_targets():
    with pytest.raises(SchemaValidationError):
        validate_circuit({
            **VALID_CIRCUIT,
            "operations": [{"gate": "CNOT", "targets": [0, 0]}]
        })

def test_circuit_out_of_range_qubit():
    with pytest.raises(SchemaValidationError):
        validate_circuit({
            **VALID_CIRCUIT,
            "qubits": 2,
            "operations": [{"gate": "H", "targets": [2]}]
        })

def test_config_invalid_shots():
    with pytest.raises(SchemaValidationError):
        validate_configuration({**VALID_CONFIG, "shots": 0})
    with pytest.raises(SchemaValidationError):
        validate_configuration({**VALID_CONFIG, "shots": -1})

def test_config_unknown_mode():
    with pytest.raises(SchemaValidationError):
        validate_configuration({**VALID_CONFIG, "mode": "quantum"})

def test_result_missing_label():
    with pytest.raises(SchemaValidationError):
        invalid_result = VALID_RESULT.copy()
        del invalid_result["result_label"]
        validate_result(invalid_result)

def test_result_wrong_label():
    with pytest.raises(SchemaValidationError):
        validate_result({**VALID_RESULT, "result_label": "REAL_HARDWARE"})

def test_unknown_major_version():
    with pytest.raises(SchemaValidationError):
        validate_circuit({**VALID_CIRCUIT, "version": "2.0"})

def test_unexpected_properties():
    with pytest.raises(SchemaValidationError):
        validate_circuit({**VALID_CIRCUIT, "extra": "property"})

if __name__ == "__main__":
    pytest.main([__file__])
