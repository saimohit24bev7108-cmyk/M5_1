"""
Backend execution contract for the M5 simulator (Step 7).

This module implements the backend that connects all existing M5 components
into a complete simulation pipeline:

    circuit validation
    → configuration validation
    → ideal statevector execution
    → noise processing (when mode is "noisy")
    → finite-shot sampling
    → structured simulation result

Design decisions
----------------
* The backend **delegates** to existing modules — it does not duplicate any
  gate, statevector, sampling, or noise logic.
* Input objects (circuit dict, noise dict) are **never mutated**.
* On failure, a structured error dict is returned (not a partial result).
* The ``result_label`` is always ``"SIMULATION"`` (matches the M5 result
  schema constant).
* No result files are written; file serialization is a later step.
* No API keys, network calls, or external services.
"""

import copy
import uuid
from typing import Any, Dict, List, Optional

from src.m5_simulator.circuit import Circuit
from src.m5_simulator.gates import ConfigRejectedError
from src.m5_simulator.schemas import SchemaValidationError
from src.m5_simulator.errors import M5SimulatorError
from src.m5_simulator.noise import NoiseConfig, NoiseConfigError, apply_noise
from src.m5_simulator.sampling import sample, SamplingError
from src.m5_simulator.statevector import (
    Statevector,
    StatevectorError,
    execute_circuit,
    MAX_QUBITS,
)
from src.m5_simulator.version import __version__ as SIMULATOR_VERSION

# Schema version for the result envelope.
SCHEMA_VERSION = "1.0"

# The only allowed result label per the M5 result schema.
RESULT_LABEL = "SIMULATION"

# Supported execution modes.
_SUPPORTED_MODES = frozenset({"ideal", "noisy"})


# ======================================================================
# Exceptions
# ======================================================================

class BackendError(M5SimulatorError):
    """Raised when the backend encounters an unrecoverable error."""

    def __init__(self, message: str, code: str = "E_BACKEND_ERROR"):
        self.code = code
        super().__init__(f"{message} ({code})")


# ======================================================================
# Request validation helpers
# ======================================================================

def _validate_mode(mode: str) -> None:
    """Reject unsupported execution modes."""
    if mode not in _SUPPORTED_MODES:
        raise ConfigRejectedError(
            f"Unsupported execution mode '{mode}' (E_CONFIG_REJECTED)."
        )


def _validate_shots(shots: Any) -> None:
    """Reject invalid shot counts."""
    if not isinstance(shots, int) or isinstance(shots, bool) or shots < 1:
        raise BackendError(
            f"shots must be a positive integer, got {shots!r}",
            code="E_CONFIG_REJECTED",
        )


def _build_circuit(circuit_data: Dict[str, Any]) -> Circuit:
    """
    Build a Circuit from the request's circuit dict.

    Translates the request schema fields (``num_qubits``, ``schema_version``)
    to the Circuit constructor's expected fields (``qubits``, ``version``).
    """
    # Deep copy so we never mutate the caller's dict.
    data = copy.deepcopy(circuit_data)

    # Translate request field names → Circuit field names.
    if "num_qubits" in data and "qubits" not in data:
        data["qubits"] = data.pop("num_qubits")
    if "schema_version" in data and "version" not in data:
        data["version"] = data.pop("schema_version")

    # Remove request-only keys that Circuit.from_dict does not expect.
    for key in list(data.keys()):
        if key not in ("version", "qubits", "operations"):
            del data[key]

    return Circuit.from_dict(data)


def _build_noise_config(mode: str, noise_data: Optional[Dict[str, Any]]) -> NoiseConfig:
    """
    Build a NoiseConfig from the request's noise dict and mode.

    For ideal mode with empty/missing noise, returns an ideal NoiseConfig.
    For noisy mode, the noise dict must contain the required sections.
    """
    if mode == "ideal":
        return NoiseConfig(mode="ideal")

    # Noisy mode — the noise dict must be present and non-empty.
    if not noise_data:
        raise NoiseConfigError(
            "Noise configuration is required for noisy mode (E_CONFIG_REJECTED)."
        )
    cfg = copy.deepcopy(noise_data)
    cfg["mode"] = "noisy"
    return NoiseConfig.from_dict(cfg)


# ======================================================================
# Structured result builders
# ======================================================================

def _build_success_result(
    *,
    run_id: str,
    request_id: Optional[str],
    num_qubits: int,
    shots: int,
    seed: Optional[int],
    mode: str,
    circuit_data: Dict[str, Any],
    probabilities: List[float],
    counts: Dict[str, int],
    noise_config: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    """Assemble a structured success result."""
    return {
        "status": "completed",
        "run_id": run_id,
        "request_id": request_id,
        "simulator_version": SIMULATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "result_label": RESULT_LABEL,
        "num_qubits": num_qubits,
        "shots": shots,
        "seed": seed,
        "mode": mode,
        "circuit": circuit_data,
        "probabilities": probabilities,
        "counts": counts,
        "noise": noise_config,
        "warnings": warnings,
    }


def _build_error_result(
    *,
    run_id: str,
    request_id: Optional[str],
    code: str,
    message: str,
) -> Dict[str, Any]:
    """Assemble a structured error result."""
    return {
        "status": "error",
        "run_id": run_id,
        "request_id": request_id,
        "simulator_version": SIMULATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "error": {
            "code": code,
            "message": message,
        },
    }


# ======================================================================
# Public API
# ======================================================================

def run_simulation(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a complete M5 simulation from a structured request dict.

    Pipeline
    --------
    1. Validate and build the circuit.
    2. Validate mode and configuration.
    3. Execute ideal statevector evolution.
    4. Apply noise (when mode == "noisy").
    5. Perform finite-shot sampling.
    6. Return the structured result.

    Parameters
    ----------
    request : dict
        A simulation request with the following shape::

            {
                "request_id": str,          # optional
                "run_id": str,              # optional (generated if absent)
                "circuit": { ... },         # required
                "mode": "ideal" | "noisy",  # required
                "noise": { ... },           # required for noisy mode
                "shots": int,               # required, >= 1
                "seed": int | None          # optional
            }

    Returns
    -------
    dict
        A structured result dict.  On success the ``"status"`` field is
        ``"completed"``; on failure it is ``"error"`` and an ``"error"``
        sub-dict contains ``"code"`` and ``"message"``.

    Notes
    -----
    * The input *request* dict is **never mutated**.
    * No result files are written.
    * No network calls or external services are used.
    """
    # Deep-copy the request so we never mutate the caller's dict.
    req = copy.deepcopy(request)

    run_id = req.get("run_id") or f"run_{uuid.uuid4().hex[:12]}"
    request_id = req.get("request_id")

    try:
        # ----- 1. Validate and build circuit --------------------------
        circuit_data = req.get("circuit")
        if circuit_data is None:
            raise BackendError("Missing 'circuit' in request", code="E_CONFIG_REJECTED")

        circuit = _build_circuit(circuit_data)

        if circuit.qubits > MAX_QUBITS:
            raise BackendError(
                f"Circuit has {circuit.qubits} qubits; maximum is {MAX_QUBITS}",
                code="E_CONFIG_REJECTED",
            )

        # ----- 2. Validate mode and configuration --------------------
        mode = req.get("mode")
        if mode is None:
            raise BackendError("Missing 'mode' in request", code="E_CONFIG_REJECTED")
        _validate_mode(mode)

        shots = req.get("shots")
        if shots is None:
            raise BackendError("Missing 'shots' in request", code="E_CONFIG_REJECTED")
        _validate_shots(shots)

        seed = req.get("seed")  # None means unseeded

        noise_data = req.get("noise")
        noise_config = _build_noise_config(mode, noise_data)

        # ----- 3. Ideal statevector execution ------------------------
        sv = execute_circuit(circuit)
        probabilities = sv.get_probabilities()

        # ----- 4. Noise processing (noisy mode only) -----------------
        warnings: List[str] = []
        if mode == "noisy":
            probabilities = apply_noise(probabilities, noise_config, seed=seed)
            warnings.append("noise_applied")

        # ----- 5. Finite-shot sampling --------------------------------
        counts = sample(probabilities, shots, seed=seed)

        # ----- 6. Structured result ----------------------------------
        return _build_success_result(
            run_id=run_id,
            request_id=request_id,
            num_qubits=circuit.qubits,
            shots=shots,
            seed=seed,
            mode=mode,
            circuit_data=circuit.to_dict(),
            probabilities=probabilities,
            counts=counts,
            noise_config=noise_config.to_dict(),
            warnings=warnings,
        )

    except SchemaValidationError as exc:
        # SchemaValidationError.__str__ can crash when path contains
        # integers; use .message directly for safe extraction.
        return _build_error_result(
            run_id=run_id,
            request_id=request_id,
            code="E_CONFIG_REJECTED",
            message=exc.message,
        )
    except ConfigRejectedError as exc:
        return _build_error_result(
            run_id=run_id,
            request_id=request_id,
            code="E_CONFIG_REJECTED",
            message=str(exc),
        )
    except (BackendError,) as exc:
        return _build_error_result(
            run_id=run_id,
            request_id=request_id,
            code=exc.code,
            message=str(exc),
        )
    except (ValueError, IndexError) as exc:
        return _build_error_result(
            run_id=run_id,
            request_id=request_id,
            code="E_CONFIG_REJECTED",
            message=str(exc),
        )
    except (StatevectorError, SamplingError) as exc:
        return _build_error_result(
            run_id=run_id,
            request_id=request_id,
            code="E_EXECUTION_ERROR",
            message=str(exc),
        )
    except Exception as exc:
        return _build_error_result(
            run_id=run_id,
            request_id=request_id,
            code="E_INTERNAL_ERROR",
            message=str(exc),
        )
