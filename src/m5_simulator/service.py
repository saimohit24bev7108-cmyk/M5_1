"""
Local service interface for the M5 simulator (Step 11).

This module provides a local-only, in-process service that accepts
JSON-compatible simulation requests, validates them, enforces concurrency
limits, delegates to the backend for execution, and returns JSON-compatible
responses.

Design decisions
----------------
* **In-process only** — no public network endpoint, no sockets.
* **Delegates** to ``backend.run_simulation`` for execution and
  ``ConcurrencyController`` for job-slot management.  Does not duplicate
  any backend, statevector, sampling, noise, or concurrency logic.
* **Strict JSON-compatible** request/response dicts.
* On failure, returns a structured error response — never a partial
  successful result.
* ``request_id`` and ``run_id`` are preserved in every response.
* ``result_label`` is always ``"SIMULATION"``.
* No files are written.
* No network, cloud, API key, authentication, or hardware access.
"""

import copy
import uuid
from typing import Any, Dict, Optional

from src.m5_simulator.backend import run_simulation, RESULT_LABEL, SCHEMA_VERSION
from src.m5_simulator.concurrency import (
    ConcurrencyController,
    SimulationLimitError,
    DuplicateJobError,
)
from src.m5_simulator.version import __version__ as SIMULATOR_VERSION


# ======================================================================
# Service error codes
# ======================================================================

E_VALIDATION = "E_VALIDATION_ERROR"
E_SIMULATION_LIMIT = "E_SIMULATION_LIMIT"
E_DUPLICATE_REQUEST = "E_DUPLICATE_REQUEST"
E_MALFORMED_INPUT = "E_MALFORMED_INPUT"
E_SERVICE_ERROR = "E_SERVICE_ERROR"


# ======================================================================
# Response builders
# ======================================================================

def _success_response(
    result: Dict[str, Any],
    request_id: Optional[str],
    run_id: str,
) -> Dict[str, Any]:
    """Wrap a completed backend result in the service envelope."""
    return {
        "status": "completed",
        "request_id": request_id,
        "run_id": run_id,
        "result": result,
    }


def _error_response(
    *,
    code: str,
    message: str,
    request_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a structured error response — never includes partial results."""
    return {
        "status": "error",
        "request_id": request_id,
        "run_id": run_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


# ======================================================================
# Request pre-validation
# ======================================================================

def _pre_validate(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Perform lightweight structural validation before backend delegation.

    Returns an error-response dict on failure, or ``None`` if the request
    looks structurally sound.
    """
    request_id = request.get("request_id")
    run_id = request.get("run_id")

    if not isinstance(request, dict):
        return _error_response(
            code=E_MALFORMED_INPUT,
            message="Request must be a JSON-compatible dict.",
            request_id=request_id,
            run_id=run_id,
        )

    if "circuit" not in request:
        return _error_response(
            code=E_VALIDATION,
            message="Missing required field 'circuit'.",
            request_id=request_id,
            run_id=run_id,
        )

    if "mode" not in request:
        return _error_response(
            code=E_VALIDATION,
            message="Missing required field 'mode'.",
            request_id=request_id,
            run_id=run_id,
        )

    if "shots" not in request:
        return _error_response(
            code=E_VALIDATION,
            message="Missing required field 'shots'.",
            request_id=request_id,
            run_id=run_id,
        )

    return None


# ======================================================================
# SimulationService
# ======================================================================

class SimulationService:
    """
    Local-only M5 simulation service.

    Public API
    ----------
    * ``submit(request)`` — validate, admit, execute, release, return response.
    * ``active_count()`` — number of active jobs (delegates to controller).
    * ``active_job_ids()`` — sorted active job IDs (delegates to controller).

    The service is **in-process only**: it does not open sockets, listen
    on ports, or expose any network endpoint.
    """

    def __init__(self, controller: Optional[ConcurrencyController] = None):
        self._controller = controller or ConcurrencyController()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, request: Any) -> Dict[str, Any]:
        """
        Submit a simulation request and return the response.

        Parameters
        ----------
        request : dict
            A JSON-compatible simulation request.  Required fields:

            * ``circuit`` — circuit definition dict
            * ``mode`` — ``"ideal"`` or ``"noisy"``
            * ``shots`` — positive integer
            * ``seed`` — integer or ``None`` (optional)
            * ``noise`` — noise config dict (required for noisy mode)
            * ``request_id`` — string (optional, preserved in response)
            * ``run_id`` — string (optional, generated if absent)

        Returns
        -------
        dict
            A JSON-compatible response dict.  On success::

                {
                    "status": "completed",
                    "request_id": ...,
                    "run_id": ...,
                    "result": { <backend result> }
                }

            On failure::

                {
                    "status": "error",
                    "request_id": ...,
                    "run_id": ...,
                    "error": {"code": "...", "message": "..."}
                }
        """
        # --- Guard: malformed input -----------------------------------
        if not isinstance(request, dict):
            return _error_response(
                code=E_MALFORMED_INPUT,
                message="Request must be a JSON-compatible dict.",
            )

        # Deep-copy so we never mutate the caller's input.
        req = copy.deepcopy(request)

        request_id = req.get("request_id")
        run_id = req.get("run_id") or f"run_{uuid.uuid4().hex[:12]}"
        req["run_id"] = run_id

        # --- Pre-validate structure -----------------------------------
        err = _pre_validate(req)
        if err is not None:
            # Ensure request_id and run_id are set from the request.
            err["request_id"] = request_id
            err["run_id"] = run_id
            return err

        # --- Concurrency admission ------------------------------------
        try:
            self._controller.admit(run_id)
        except SimulationLimitError:
            return _error_response(
                code=E_SIMULATION_LIMIT,
                message="Maximum active simulation jobs reached. "
                        "Try again after an active job completes.",
                request_id=request_id,
                run_id=run_id,
            )
        except DuplicateJobError:
            return _error_response(
                code=E_DUPLICATE_REQUEST,
                message=f"A job with run_id '{run_id}' is already active.",
                request_id=request_id,
                run_id=run_id,
            )

        # --- Execute via backend (always release slot) ----------------
        try:
            result = run_simulation(req)
        except Exception as exc:
            # Unexpected backend exception — should not normally happen
            # since run_simulation returns error dicts, but guard anyway.
            return _error_response(
                code=E_SERVICE_ERROR,
                message=str(exc),
                request_id=request_id,
                run_id=run_id,
            )
        finally:
            self._controller.release(run_id)

        # --- Map backend result to service response -------------------
        if result.get("status") == "error":
            # Backend returned a structured error — propagate it as a
            # service-level error so the response never contains a
            # partial successful result.
            backend_error = result.get("error", {})
            return _error_response(
                code=backend_error.get("code", E_SERVICE_ERROR),
                message=backend_error.get("message", "Backend error"),
                request_id=request_id,
                run_id=run_id,
            )

        return _success_response(result, request_id, run_id)

    # ------------------------------------------------------------------
    # Inspection (delegates to controller)
    # ------------------------------------------------------------------

    def active_count(self) -> int:
        """Return the number of currently active simulation jobs."""
        return self._controller.active_count()

    def active_job_ids(self):
        """Return the sorted list of active job IDs."""
        return self._controller.active_job_ids()
