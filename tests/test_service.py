"""
Tests for the local service interface (Step 11 of M5 architecture).

Covers:
    - Valid ideal simulation request
    - Valid noisy simulation request
    - Correct request_id and run_id propagation
    - Correct "SIMULATION" result label
    - Correct backend result propagation
    - Invalid circuit request
    - Invalid shots
    - Unsupported gate
    - Invalid noise configuration
    - More than 8 qubits
    - Concurrency-limit error
    - Structured error response
    - No partial result on failure
    - Duplicate request handling
    - Malformed JSON-compatible input
    - Confirmation that service.py does not write files
    - Confirmation that service.py does not access the network
    - Confirmation that service.py does not access hardware
    - Confirmation that existing backend and concurrency components are used
    - Confirmation that input objects are not mutated
"""

import copy
import os
import pytest

from src.m5_simulator.service import (
    SimulationService,
    E_VALIDATION,
    E_SIMULATION_LIMIT,
    E_DUPLICATE_REQUEST,
    E_MALFORMED_INPUT,
)
from src.m5_simulator.concurrency import ConcurrencyController


# ==================================================================
# Fixtures
# ==================================================================

@pytest.fixture
def svc():
    """Return a fresh SimulationService with its own controller."""
    return SimulationService()


def _ideal_bell_request(
    *,
    shots: int = 1000,
    seed: int = 42,
    run_id: str = "run_svc_001",
    request_id: str = "req_svc_001",
) -> dict:
    """Valid ideal Bell-circuit request."""
    return {
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
        "mode": "ideal",
        "noise": {},
        "shots": shots,
        "seed": seed,
    }


def _noisy_bell_request(
    *,
    run_id: str = "run_noisy_svc",
    request_id: str = "req_noisy_svc",
) -> dict:
    """Valid noisy Bell-circuit request."""
    return {
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
        "mode": "noisy",
        "noise": {
            "gate_noise": {"model": "depolarizing", "probability": 0.01},
            "readout_noise": {"model": "bit_flip", "probability": 0.02},
            "decoherence": {"model": "none"},
        },
        "shots": 1000,
        "seed": 42,
    }


# ==================================================================
# Valid requests
# ==================================================================

class TestValidRequests:
    """Valid simulation requests."""

    def test_ideal_simulation(self, svc):
        """Valid ideal request returns a completed response."""
        resp = svc.submit(_ideal_bell_request())
        assert resp["status"] == "completed"
        assert "result" in resp

    def test_noisy_simulation(self, svc):
        """Valid noisy request returns a completed response."""
        resp = svc.submit(_noisy_bell_request())
        assert resp["status"] == "completed"
        assert resp["result"]["mode"] == "noisy"

    def test_ideal_result_counts(self, svc):
        """Ideal Bell result has expected counts keys."""
        resp = svc.submit(_ideal_bell_request())
        counts = resp["result"]["counts"]
        assert set(counts.keys()).issubset({"00", "11"})
        assert sum(counts.values()) == 1000


# ==================================================================
# Request ID and run ID propagation
# ==================================================================

class TestIdPropagation:
    """request_id and run_id are propagated."""

    def test_request_id_propagated(self, svc):
        """request_id is in the response."""
        resp = svc.submit(_ideal_bell_request(request_id="my_req"))
        assert resp["request_id"] == "my_req"

    def test_run_id_propagated(self, svc):
        """run_id is in the response."""
        resp = svc.submit(_ideal_bell_request(run_id="my_run"))
        assert resp["run_id"] == "my_run"

    def test_ids_in_error_response(self, svc):
        """request_id and run_id appear in error responses too."""
        req = _ideal_bell_request(request_id="err_req", run_id="err_run")
        req["mode"] = "invalid_mode"
        resp = svc.submit(req)
        assert resp["status"] == "error"
        assert resp["request_id"] == "err_req"
        assert resp["run_id"] == "err_run"

    def test_generated_run_id(self, svc):
        """Missing run_id is auto-generated."""
        req = _ideal_bell_request()
        del req["run_id"]
        resp = svc.submit(req)
        assert resp["status"] == "completed"
        assert resp["run_id"] is not None
        assert resp["run_id"].startswith("run_")


# ==================================================================
# Result label
# ==================================================================

class TestResultLabel:
    """Result label is SIMULATION."""

    def test_simulation_label(self, svc):
        """Backend result carries result_label 'SIMULATION'."""
        resp = svc.submit(_ideal_bell_request())
        assert resp["result"]["result_label"] == "SIMULATION"


# ==================================================================
# Backend result propagation
# ==================================================================

class TestBackendPropagation:
    """Backend result fields are correctly propagated."""

    def test_probabilities(self, svc):
        """Backend probabilities are in the response."""
        resp = svc.submit(_ideal_bell_request())
        assert "probabilities" in resp["result"]
        assert len(resp["result"]["probabilities"]) == 4

    def test_counts(self, svc):
        """Backend counts are in the response."""
        resp = svc.submit(_ideal_bell_request())
        assert "counts" in resp["result"]

    def test_simulator_version(self, svc):
        """Backend simulator_version is in the response."""
        resp = svc.submit(_ideal_bell_request())
        assert "simulator_version" in resp["result"]

    def test_schema_version(self, svc):
        """Backend schema_version is in the response."""
        resp = svc.submit(_ideal_bell_request())
        assert "schema_version" in resp["result"]

    def test_num_qubits(self, svc):
        """Backend num_qubits is in the response."""
        resp = svc.submit(_ideal_bell_request())
        assert resp["result"]["num_qubits"] == 2

    def test_seed(self, svc):
        """Backend seed is in the response."""
        resp = svc.submit(_ideal_bell_request(seed=99))
        assert resp["result"]["seed"] == 99


# ==================================================================
# Validation errors
# ==================================================================

class TestValidationErrors:
    """Invalid requests produce structured validation errors."""

    def test_invalid_circuit(self, svc):
        """Request with malformed circuit is rejected."""
        req = _ideal_bell_request(run_id="inv_circ")
        req["circuit"] = {"bad": True}
        resp = svc.submit(req)
        assert resp["status"] == "error"
        assert "code" in resp["error"]

    def test_invalid_shots_zero(self, svc):
        """Zero shots is rejected."""
        req = _ideal_bell_request(run_id="inv_shots", shots=0)
        resp = svc.submit(req)
        assert resp["status"] == "error"

    def test_invalid_shots_negative(self, svc):
        """Negative shots is rejected."""
        req = _ideal_bell_request(run_id="neg_shots")
        req["shots"] = -5
        resp = svc.submit(req)
        assert resp["status"] == "error"

    def test_unsupported_gate(self, svc):
        """Unsupported gate is rejected."""
        req = _ideal_bell_request(run_id="bad_gate")
        req["circuit"]["operations"] = [{"gate": "TOFFOLI", "targets": [0]}]
        resp = svc.submit(req)
        assert resp["status"] == "error"

    def test_invalid_noise_config(self, svc):
        """Invalid noise configuration in noisy mode is rejected."""
        req = _noisy_bell_request(run_id="bad_noise")
        req["noise"]["gate_noise"]["model"] = "unknown"
        resp = svc.submit(req)
        assert resp["status"] == "error"

    def test_more_than_8_qubits(self, svc):
        """More than 8 qubits is rejected."""
        req = _ideal_bell_request(run_id="too_many_q")
        req["circuit"]["num_qubits"] = 9
        req["circuit"]["operations"] = [{"gate": "H", "targets": [0]}]
        resp = svc.submit(req)
        assert resp["status"] == "error"

    def test_missing_circuit(self, svc):
        """Missing circuit field is rejected."""
        req = _ideal_bell_request(run_id="no_circ")
        del req["circuit"]
        resp = svc.submit(req)
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_VALIDATION

    def test_missing_mode(self, svc):
        """Missing mode field is rejected."""
        req = _ideal_bell_request(run_id="no_mode")
        del req["mode"]
        resp = svc.submit(req)
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_VALIDATION

    def test_missing_shots(self, svc):
        """Missing shots field is rejected."""
        req = _ideal_bell_request(run_id="no_shots")
        del req["shots"]
        resp = svc.submit(req)
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_VALIDATION


# ==================================================================
# Concurrency-limit error
# ==================================================================

class TestConcurrencyLimit:
    """Concurrency-limit errors."""

    def test_fifth_job_rejected(self):
        """Fifth concurrent job returns E_SIMULATION_LIMIT."""
        # Use a controller with max_active=1 for easy testing.
        ctrl = ConcurrencyController(max_active=1)
        svc = SimulationService(controller=ctrl)

        # First job succeeds.
        resp1 = svc.submit(_ideal_bell_request(run_id="c_1"))
        assert resp1["status"] == "completed"

        # Since the first job completes synchronously and releases its
        # slot, we need to keep a slot occupied externally.
        ctrl.admit("blocker")
        resp2 = svc.submit(_ideal_bell_request(run_id="c_2"))
        assert resp2["status"] == "error"
        assert resp2["error"]["code"] == E_SIMULATION_LIMIT
        ctrl.release("blocker")

    def test_concurrency_limit_with_4_jobs(self):
        """With 4 slots full, the 5th returns E_SIMULATION_LIMIT."""
        ctrl = ConcurrencyController(max_active=4)
        svc = SimulationService(controller=ctrl)

        # Fill 4 slots externally.
        for i in range(4):
            ctrl.admit(f"blocker_{i}")

        resp = svc.submit(_ideal_bell_request(run_id="blocked"))
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_SIMULATION_LIMIT

        # Clean up.
        for i in range(4):
            ctrl.release(f"blocker_{i}")


# ==================================================================
# Structured error response
# ==================================================================

class TestStructuredError:
    """Error responses are properly structured."""

    def test_error_has_code_and_message(self, svc):
        """Error response contains code and message."""
        req = _ideal_bell_request(run_id="struct_err")
        req["mode"] = "invalid_mode"
        resp = svc.submit(req)
        assert resp["status"] == "error"
        assert "code" in resp["error"]
        assert "message" in resp["error"]
        assert isinstance(resp["error"]["code"], str)
        assert isinstance(resp["error"]["message"], str)


# ==================================================================
# No partial result on failure
# ==================================================================

class TestNoPartialResult:
    """Error responses never contain a partial successful result."""

    def test_no_result_key_on_error(self, svc):
        """Error response does not contain a 'result' key."""
        req = _ideal_bell_request(run_id="no_partial")
        req["mode"] = "invalid_mode"
        resp = svc.submit(req)
        assert resp["status"] == "error"
        assert "result" not in resp

    def test_no_counts_on_error(self, svc):
        """Error response does not contain 'counts'."""
        req = _ideal_bell_request(run_id="no_counts")
        req["mode"] = "invalid_mode"
        resp = svc.submit(req)
        assert "counts" not in resp

    def test_no_probabilities_on_error(self, svc):
        """Error response does not contain 'probabilities'."""
        req = _ideal_bell_request(run_id="no_probs")
        req["mode"] = "invalid_mode"
        resp = svc.submit(req)
        assert "probabilities" not in resp


# ==================================================================
# Duplicate request handling
# ==================================================================

class TestDuplicateRequest:
    """Duplicate request handling."""

    def test_duplicate_run_id_rejected(self):
        """Submitting a run_id that is currently active is rejected."""
        ctrl = ConcurrencyController()
        svc = SimulationService(controller=ctrl)

        # Manually keep a slot occupied.
        ctrl.admit("dup_run")

        resp = svc.submit(_ideal_bell_request(run_id="dup_run"))
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_DUPLICATE_REQUEST

        ctrl.release("dup_run")

    def test_same_run_id_after_completion(self, svc):
        """Same run_id can be reused after the previous job completes."""
        resp1 = svc.submit(_ideal_bell_request(run_id="reuse"))
        assert resp1["status"] == "completed"

        resp2 = svc.submit(_ideal_bell_request(run_id="reuse"))
        assert resp2["status"] == "completed"


# ==================================================================
# Malformed input
# ==================================================================

class TestMalformedInput:
    """Malformed JSON-compatible input."""

    def test_non_dict_input(self, svc):
        """Non-dict input returns an error."""
        resp = svc.submit("not a dict")
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_MALFORMED_INPUT

    def test_none_input(self, svc):
        """None input returns an error."""
        resp = svc.submit(None)
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_MALFORMED_INPUT

    def test_list_input(self, svc):
        """List input returns an error."""
        resp = svc.submit([1, 2, 3])
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_MALFORMED_INPUT

    def test_int_input(self, svc):
        """Integer input returns an error."""
        resp = svc.submit(42)
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_MALFORMED_INPUT


# ==================================================================
# No files written
# ==================================================================

class TestNoFileOutput:
    """Service does not write files."""

    def test_no_files_written(self, svc):
        """submit() does not create any files in the working directory."""
        cwd = os.getcwd()
        before = set(os.listdir(cwd))
        svc.submit(_ideal_bell_request(run_id="file_test"))
        after = set(os.listdir(cwd))
        assert after == before


# ==================================================================
# No network access
# ==================================================================

class TestNoNetworkAccess:
    """Service does not access the network."""

    def test_no_network_imports(self):
        """service.py does not import network libraries."""
        import src.m5_simulator.service as svc_mod
        source = open(svc_mod.__file__, "r").read()
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import http.server" not in source
        assert "import socket" not in source
        assert "import flask" not in source
        assert "import fastapi" not in source
        assert "import aiohttp" not in source


# ==================================================================
# No hardware access
# ==================================================================

class TestNoHardwareAccess:
    """Service does not access hardware."""

    def test_no_hardware_imports(self):
        """service.py does not import hardware libraries."""
        import src.m5_simulator.service as svc_mod
        source = open(svc_mod.__file__, "r").read()
        assert "import serial" not in source
        assert "import gpio" not in source
        assert "import qiskit.providers" not in source


# ==================================================================
# Uses existing backend and concurrency
# ==================================================================

class TestUsesExistingComponents:
    """Service uses existing backend and concurrency components."""

    def test_imports_backend(self):
        """service.py imports from backend."""
        import src.m5_simulator.service as svc_mod
        source = open(svc_mod.__file__, "r").read()
        assert "from src.m5_simulator.backend import" in source

    def test_imports_concurrency(self):
        """service.py imports from concurrency."""
        import src.m5_simulator.service as svc_mod
        source = open(svc_mod.__file__, "r").read()
        assert "from src.m5_simulator.concurrency import" in source

    def test_does_not_import_simulation_core(self):
        """service.py does not import statevector, sampling, gates, or noise."""
        import src.m5_simulator.service as svc_mod
        source = open(svc_mod.__file__, "r").read()
        assert "from src.m5_simulator.statevector" not in source
        assert "from src.m5_simulator.sampling" not in source
        assert "from src.m5_simulator.gates" not in source
        assert "from src.m5_simulator.noise" not in source

    def test_custom_controller_is_used(self):
        """SimulationService uses the injected controller."""
        ctrl = ConcurrencyController(max_active=2)
        svc = SimulationService(controller=ctrl)

        # Fill both slots externally.
        ctrl.admit("ext_1")
        ctrl.admit("ext_2")

        resp = svc.submit(_ideal_bell_request(run_id="blocked_by_ctrl"))
        assert resp["status"] == "error"
        assert resp["error"]["code"] == E_SIMULATION_LIMIT

        ctrl.release("ext_1")
        ctrl.release("ext_2")


# ==================================================================
# Input immutability
# ==================================================================

class TestInputImmutability:
    """Input objects are not mutated."""

    def test_request_not_mutated(self, svc):
        """submit() does not mutate the input request dict."""
        req = _ideal_bell_request()
        req_copy = copy.deepcopy(req)
        svc.submit(req)
        assert req == req_copy

    def test_circuit_not_mutated(self, svc):
        """submit() does not mutate the circuit sub-dict."""
        req = _ideal_bell_request()
        circuit_copy = copy.deepcopy(req["circuit"])
        svc.submit(req)
        assert req["circuit"] == circuit_copy

    def test_noise_not_mutated(self, svc):
        """submit() does not mutate the noise sub-dict."""
        req = _noisy_bell_request()
        noise_copy = copy.deepcopy(req["noise"])
        svc.submit(req)
        assert req["noise"] == noise_copy


# ==================================================================
# Slot release after execution
# ==================================================================

class TestSlotRelease:
    """Slot is released after execution (success or failure)."""

    def test_slot_released_on_success(self, svc):
        """Active count is 0 after a successful submission."""
        svc.submit(_ideal_bell_request(run_id="slot_s"))
        assert svc.active_count() == 0

    def test_slot_released_on_error(self, svc):
        """Active count is 0 after a failed submission."""
        req = _ideal_bell_request(run_id="slot_e")
        req["mode"] = "invalid_mode"
        svc.submit(req)
        assert svc.active_count() == 0


if __name__ == "__main__":
    pytest.main([__file__])
