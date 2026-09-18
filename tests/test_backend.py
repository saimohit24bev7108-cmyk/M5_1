"""
Tests for the backend execution contract (Step 7 of M5 architecture).

Covers:
    - Valid one-qubit ideal execution
    - Valid Bell-circuit ideal execution
    - Valid seeded execution
    - Exact reproducibility for identical requests
    - Correct result label "SIMULATION"
    - Correct simulator version and schema version
    - Correct qubit count and shot count
    - Correct histogram count total
    - Correct big-endian outcome keys
    - Valid noisy execution using implemented noise configuration
    - Explicit recording of ideal versus noisy mode
    - Rejection of invalid circuit configuration
    - Rejection of more than 8 qubits
    - Rejection of invalid shots
    - Rejection of unsupported mode
    - Rejection of unsupported gate
    - Rejection of invalid noise configuration
    - Confirmation that input objects are not mutated
    - Confirmation that no result files are written by backend.py
    - Failure results contain a structured error
    - Same request + seed + config produce the same structured result
"""

import copy
import json
import os
import tempfile
import pytest

from src.m5_simulator.backend import (
    run_simulation,
    SIMULATOR_VERSION,
    SCHEMA_VERSION,
    RESULT_LABEL,
)


# ==================================================================
# Helper factories
# ==================================================================

def _bell_request(
    *,
    shots: int = 1000,
    seed: int = 42,
    mode: str = "ideal",
    noise: dict = None,
    run_id: str = "run_test_001",
    request_id: str = "req_test_001",
) -> dict:
    """Return a valid Bell-circuit request."""
    req = {
        "request_id": request_id,
        "run_id": run_id,
        "circuit": {
            "schema_version": "1.0",
            "num_qubits": 2,
            "operations": [
                {"gate": "H", "targets": [0]},
                {"gate": "CNOT", "targets": [0, 1]},
            ],
        },
        "mode": mode,
        "noise": noise if noise is not None else {},
        "shots": shots,
        "seed": seed,
    }
    return req


def _one_qubit_x_request(*, shots: int = 100, seed: int = 0) -> dict:
    """Return a valid 1-qubit X-gate request."""
    return {
        "request_id": "req_1q",
        "run_id": "run_1q",
        "circuit": {
            "schema_version": "1.0",
            "num_qubits": 1,
            "operations": [{"gate": "X", "targets": [0]}],
        },
        "mode": "ideal",
        "noise": {},
        "shots": shots,
        "seed": seed,
    }


def _noisy_bell_request(
    *,
    gate_prob: float = 0.01,
    readout_prob: float = 0.02,
    shots: int = 1000,
    seed: int = 42,
) -> dict:
    """Return a valid noisy Bell-circuit request."""
    return {
        "request_id": "req_noisy",
        "run_id": "run_noisy",
        "circuit": {
            "schema_version": "1.0",
            "num_qubits": 2,
            "operations": [
                {"gate": "H", "targets": [0]},
                {"gate": "CNOT", "targets": [0, 1]},
            ],
        },
        "mode": "noisy",
        "noise": {
            "gate_noise": {"model": "depolarizing", "probability": gate_prob},
            "readout_noise": {"model": "bit_flip", "probability": readout_prob},
            "decoherence": {"model": "none"},
        },
        "shots": shots,
        "seed": seed,
    }


# ==================================================================
# Valid ideal execution
# ==================================================================

class TestIdealExecution:
    """Valid ideal-mode simulation runs."""

    def test_valid_one_qubit_ideal_execution(self):
        """One-qubit ideal execution returns a completed result."""
        req = _one_qubit_x_request()
        result = run_simulation(req)
        assert result["status"] == "completed"
        assert result["num_qubits"] == 1
        assert result["counts"] == {"1": 100}

    def test_valid_bell_circuit_ideal_execution(self):
        """Bell-circuit ideal execution returns a completed result."""
        req = _bell_request()
        result = run_simulation(req)
        assert result["status"] == "completed"
        assert result["num_qubits"] == 2
        assert set(result["counts"].keys()).issubset({"00", "11"})

    def test_valid_seeded_execution(self):
        """Seeded execution returns a completed result with the seed recorded."""
        req = _bell_request(seed=99)
        result = run_simulation(req)
        assert result["status"] == "completed"
        assert result["seed"] == 99


# ==================================================================
# Reproducibility
# ==================================================================

class TestReproducibility:
    """Exact reproducibility for identical requests."""

    def test_identical_requests_produce_identical_results(self):
        """Same request, including seed, produces the same structured result."""
        req = _bell_request(seed=42, shots=2000)
        r1 = run_simulation(copy.deepcopy(req))
        r2 = run_simulation(copy.deepcopy(req))
        # Compare all meaningful fields.
        assert r1["counts"] == r2["counts"]
        assert r1["probabilities"] == r2["probabilities"]
        assert r1["mode"] == r2["mode"]
        assert r1["num_qubits"] == r2["num_qubits"]
        assert r1["shots"] == r2["shots"]
        assert r1["seed"] == r2["seed"]

    def test_same_request_same_result_seeded(self):
        """Full deterministic match for seeded identical requests."""
        req = _bell_request(seed=123, shots=500)
        r1 = run_simulation(copy.deepcopy(req))
        r2 = run_simulation(copy.deepcopy(req))
        # Remove run_id (may be the same since we provide it) and check deep equality
        assert r1 == r2


# ==================================================================
# Result structure
# ==================================================================

class TestResultStructure:
    """Structured result fields are correct."""

    def test_result_label_simulation(self):
        """Result label is exactly 'SIMULATION'."""
        result = run_simulation(_bell_request())
        assert result["result_label"] == "SIMULATION"

    def test_simulator_version(self):
        """Simulator version matches the version module."""
        result = run_simulation(_bell_request())
        assert result["simulator_version"] == SIMULATOR_VERSION

    def test_schema_version(self):
        """Schema version is correct."""
        result = run_simulation(_bell_request())
        assert result["schema_version"] == SCHEMA_VERSION

    def test_correct_qubit_count(self):
        """num_qubits matches the circuit."""
        result = run_simulation(_bell_request())
        assert result["num_qubits"] == 2

    def test_correct_shot_count(self):
        """shots matches the request."""
        result = run_simulation(_bell_request(shots=500))
        assert result["shots"] == 500

    def test_histogram_count_total(self):
        """Histogram counts sum exactly to shots."""
        result = run_simulation(_bell_request(shots=1024))
        assert sum(result["counts"].values()) == 1024

    def test_contains_all_required_fields(self):
        """Result contains all required fields."""
        result = run_simulation(_bell_request())
        required = {
            "status", "run_id", "request_id", "simulator_version",
            "schema_version", "result_label", "num_qubits", "shots",
            "seed", "mode", "circuit", "probabilities", "counts",
            "noise", "warnings",
        }
        assert required.issubset(set(result.keys()))

    def test_probabilities_length(self):
        """Probabilities list has length 2^num_qubits."""
        result = run_simulation(_bell_request())
        assert len(result["probabilities"]) == 4  # 2^2

    def test_circuit_in_result(self):
        """Result includes the executed circuit."""
        result = run_simulation(_bell_request())
        assert "circuit" in result
        assert result["circuit"]["qubits"] == 2

    def test_noise_in_result(self):
        """Result includes the noise configuration."""
        result = run_simulation(_bell_request())
        assert "noise" in result
        assert "mode" in result["noise"]


# ==================================================================
# Big-endian outcome keys
# ==================================================================

class TestBigEndianKeys:
    """Big-endian outcome key formatting."""

    def test_two_qubit_keys_are_two_chars(self):
        """Two-qubit outcome keys are 2-character binary strings."""
        result = run_simulation(_bell_request())
        for key in result["counts"]:
            assert len(key) == 2
            assert all(c in "01" for c in key)

    def test_one_qubit_keys_are_one_char(self):
        """One-qubit outcome keys are 1-character binary strings."""
        result = run_simulation(_one_qubit_x_request())
        for key in result["counts"]:
            assert len(key) == 1
            assert key in ("0", "1")

    def test_bell_circuit_outcomes(self):
        """Bell circuit produces only 00 and 11 in ideal mode."""
        result = run_simulation(_bell_request(shots=5000))
        assert set(result["counts"].keys()).issubset({"00", "11"})


# ==================================================================
# Noisy execution
# ==================================================================

class TestNoisyExecution:
    """Noisy-mode simulation execution."""

    def test_valid_noisy_execution(self):
        """Valid noisy execution returns a completed result."""
        req = _noisy_bell_request()
        result = run_simulation(req)
        assert result["status"] == "completed"
        assert result["mode"] == "noisy"

    def test_noisy_has_noise_applied_warning(self):
        """Noisy execution records 'noise_applied' in warnings."""
        req = _noisy_bell_request()
        result = run_simulation(req)
        assert "noise_applied" in result["warnings"]

    def test_noisy_result_may_have_01_10_outcomes(self):
        """Noisy Bell circuit may produce 01/10 outcomes (due to readout noise)."""
        req = _noisy_bell_request(readout_prob=0.2, shots=10000)
        result = run_simulation(req)
        # With 20% readout noise, 01 and 10 should appear with high probability
        total = sum(result["counts"].values())
        assert total == 10000

    def test_noisy_noise_config_in_result(self):
        """Noisy result includes the full noise configuration."""
        req = _noisy_bell_request()
        result = run_simulation(req)
        assert result["noise"]["mode"] == "noisy"
        assert result["noise"]["gate_noise"]["model"] == "depolarizing"
        assert result["noise"]["readout_noise"]["model"] == "bit_flip"

    def test_noisy_histogram_sums_to_shots(self):
        """Noisy histogram counts sum exactly to shots."""
        req = _noisy_bell_request(shots=2048)
        result = run_simulation(req)
        assert sum(result["counts"].values()) == 2048


# ==================================================================
# Ideal vs noisy mode recording
# ==================================================================

class TestModeRecording:
    """Explicit recording of ideal versus noisy mode."""

    def test_ideal_mode_recorded(self):
        """Ideal mode is recorded in the result."""
        result = run_simulation(_bell_request(mode="ideal"))
        assert result["mode"] == "ideal"

    def test_noisy_mode_recorded(self):
        """Noisy mode is recorded in the result."""
        result = run_simulation(_noisy_bell_request())
        assert result["mode"] == "noisy"

    def test_ideal_no_noise_warning(self):
        """Ideal execution does not have 'noise_applied' in warnings."""
        result = run_simulation(_bell_request(mode="ideal"))
        assert "noise_applied" not in result["warnings"]


# ==================================================================
# Rejection: invalid configurations
# ==================================================================

class TestRejection:
    """Rejection of invalid requests."""

    def test_reject_invalid_circuit(self):
        """Missing operations in circuit is rejected."""
        req = _bell_request()
        req["circuit"] = {"num_qubits": 2}  # missing operations
        result = run_simulation(req)
        assert result["status"] == "error"
        assert "code" in result["error"]

    def test_reject_more_than_8_qubits(self):
        """Circuit with more than 8 qubits is rejected."""
        req = _bell_request()
        req["circuit"]["num_qubits"] = 9
        req["circuit"]["operations"] = [{"gate": "H", "targets": [0]}]
        result = run_simulation(req)
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_CONFIG_REJECTED"

    def test_reject_zero_shots(self):
        """Zero shots is rejected."""
        req = _bell_request(shots=0)
        result = run_simulation(req)
        assert result["status"] == "error"
        assert "E_CONFIG_REJECTED" in result["error"]["code"]

    def test_reject_negative_shots(self):
        """Negative shots is rejected."""
        req = _bell_request()
        req["shots"] = -10
        result = run_simulation(req)
        assert result["status"] == "error"

    def test_reject_unsupported_mode(self):
        """Unsupported mode is rejected with E_CONFIG_REJECTED."""
        req = _bell_request(mode="quantum_hardware")
        result = run_simulation(req)
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_CONFIG_REJECTED"

    def test_reject_unsupported_gate(self):
        """Unsupported gate is rejected."""
        req = _bell_request()
        req["circuit"]["operations"] = [{"gate": "TOFFOLI", "targets": [0]}]
        result = run_simulation(req)
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_CONFIG_REJECTED"

    def test_reject_invalid_noise_configuration(self):
        """Invalid noise config in noisy mode is rejected."""
        req = _bell_request(
            mode="noisy",
            noise={
                "gate_noise": {"model": "unknown_model", "probability": 0.01},
                "readout_noise": {"model": "bit_flip", "probability": 0.02},
                "decoherence": {"model": "none"},
            },
        )
        result = run_simulation(req)
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_CONFIG_REJECTED"

    def test_reject_noisy_mode_missing_noise(self):
        """Noisy mode with empty noise dict is rejected."""
        req = _bell_request(mode="noisy", noise={})
        result = run_simulation(req)
        assert result["status"] == "error"
        assert result["error"]["code"] == "E_CONFIG_REJECTED"

    def test_reject_missing_circuit(self):
        """Missing circuit field is rejected."""
        req = {
            "request_id": "req_bad",
            "run_id": "run_bad",
            "mode": "ideal",
            "noise": {},
            "shots": 100,
            "seed": 0,
        }
        result = run_simulation(req)
        assert result["status"] == "error"

    def test_reject_out_of_range_qubit_target(self):
        """Qubit target out of range is rejected."""
        req = _bell_request()
        req["circuit"]["operations"] = [{"gate": "H", "targets": [5]}]
        result = run_simulation(req)
        assert result["status"] == "error"


# ==================================================================
# Input immutability
# ==================================================================

class TestInputImmutability:
    """Input objects are not mutated."""

    def test_request_not_mutated(self):
        """The input request dict is not mutated by run_simulation."""
        req = _bell_request()
        req_copy = copy.deepcopy(req)
        run_simulation(req)
        assert req == req_copy

    def test_circuit_data_not_mutated(self):
        """The circuit sub-dict is not mutated."""
        req = _bell_request()
        circuit_copy = copy.deepcopy(req["circuit"])
        run_simulation(req)
        assert req["circuit"] == circuit_copy

    def test_noise_data_not_mutated(self):
        """The noise sub-dict is not mutated."""
        req = _noisy_bell_request()
        noise_copy = copy.deepcopy(req["noise"])
        run_simulation(req)
        assert req["noise"] == noise_copy


# ==================================================================
# No result files written
# ==================================================================

class TestNoFileOutput:
    """Backend does not write result files."""

    def test_no_files_written(self):
        """run_simulation does not create any files in the working directory."""
        # Snapshot files before
        cwd = os.getcwd()
        before = set(os.listdir(cwd))
        run_simulation(_bell_request())
        after = set(os.listdir(cwd))
        # No new files
        assert after == before

    def test_no_files_written_temp(self):
        """run_simulation does not create files in a temp directory either."""
        tmpdir = tempfile.gettempdir()
        before = set(os.listdir(tmpdir))
        run_simulation(_bell_request())
        after = set(os.listdir(tmpdir))
        # Allow for OS temp changes but no M5-specific files
        new_files = after - before
        for f in new_files:
            assert "m5" not in f.lower()
            assert "run_" not in f.lower()
            assert "result" not in f.lower()


# ==================================================================
# Structured errors
# ==================================================================

class TestStructuredErrors:
    """Failure results contain structured error information."""

    def test_error_result_has_status_error(self):
        """Error result has status 'error'."""
        req = _bell_request(mode="invalid_mode")
        result = run_simulation(req)
        assert result["status"] == "error"

    def test_error_result_has_error_dict(self):
        """Error result contains an 'error' dict with code and message."""
        req = _bell_request(mode="invalid_mode")
        result = run_simulation(req)
        assert "error" in result
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert isinstance(result["error"]["code"], str)
        assert isinstance(result["error"]["message"], str)

    def test_error_result_has_run_id(self):
        """Error results still include the run_id."""
        req = _bell_request(mode="invalid_mode")
        result = run_simulation(req)
        assert "run_id" in result
        assert result["run_id"] == "run_test_001"

    def test_error_result_has_no_partial_success(self):
        """Error results do not contain partial success fields."""
        req = _bell_request(mode="invalid_mode")
        result = run_simulation(req)
        assert "counts" not in result
        assert "probabilities" not in result

    def test_error_result_has_simulator_version(self):
        """Error results include simulator and schema versions."""
        req = _bell_request(mode="invalid_mode")
        result = run_simulation(req)
        assert result["simulator_version"] == SIMULATOR_VERSION
        assert result["schema_version"] == SCHEMA_VERSION


# ==================================================================
# Full deterministic reproducibility
# ==================================================================

class TestFullDeterminism:
    """Same request + seed + config produce the same structured result."""

    def test_full_result_deterministic_ideal(self):
        """Identical ideal requests produce identical JSON-serialized results."""
        req = _bell_request(seed=42, shots=1000)
        r1 = run_simulation(copy.deepcopy(req))
        r2 = run_simulation(copy.deepcopy(req))
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)

    def test_full_result_deterministic_noisy(self):
        """Identical noisy requests produce identical JSON-serialized results."""
        req = _noisy_bell_request(seed=42, shots=1000)
        r1 = run_simulation(copy.deepcopy(req))
        r2 = run_simulation(copy.deepcopy(req))
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


# ==================================================================
# Unseeded execution
# ==================================================================

class TestUnseededExecution:
    """Unseeded (seed=None) execution works correctly."""

    def test_unseeded_execution(self):
        """Unseeded execution returns a completed result."""
        req = _bell_request()
        req["seed"] = None
        result = run_simulation(req)
        assert result["status"] == "completed"
        assert result["seed"] is None

    def test_missing_seed_defaults_to_none(self):
        """Missing seed field defaults to None (unseeded)."""
        req = _bell_request()
        del req["seed"]
        result = run_simulation(req)
        assert result["status"] == "completed"
        assert result["seed"] is None


if __name__ == "__main__":
    pytest.main([__file__])
