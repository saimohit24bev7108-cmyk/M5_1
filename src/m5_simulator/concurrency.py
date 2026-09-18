"""
Simulation concurrency control for the M5 simulator (Step 10).

This module provides a thread-safe concurrency controller that enforces a
maximum number of active simulation jobs.  It does **not** execute
simulations, write files, persist state, or use external services.

Design decisions
----------------
* Maximum 4 active jobs (``MAX_ACTIVE_JOBS``).
* Each job is tracked by a unique string job ID.
* Duplicate admission of the same job ID is rejected.
* A fifth concurrent job is rejected with ``E_SIMULATION_LIMIT``.
* Slots are released on completion, failure, cancellation, or explicit stop.
* All operations are protected by a ``threading.Lock`` for thread safety.
* ``active_job_ids()`` returns IDs in deterministic sorted order.
* No simulation, serialization, analysis, or backend logic is executed.
"""

import threading
from typing import List, Set

from src.m5_simulator.errors import M5SimulatorError

# Maximum number of simultaneous active simulation jobs.
MAX_ACTIVE_JOBS = 4


# ======================================================================
# Exceptions
# ======================================================================

class ConcurrencyError(M5SimulatorError):
    """Raised when a concurrency constraint is violated."""

    def __init__(self, message: str, code: str = "E_CONCURRENCY_ERROR"):
        self.code = code
        super().__init__(f"{message} ({code})")


class SimulationLimitError(ConcurrencyError):
    """Raised when the active-job limit has been reached."""

    def __init__(self, message: str = "Maximum active simulation jobs reached"):
        super().__init__(message, code="E_SIMULATION_LIMIT")


class DuplicateJobError(ConcurrencyError):
    """Raised when a job ID is already active."""

    def __init__(self, job_id: str):
        super().__init__(
            f"Job '{job_id}' is already active",
            code="E_DUPLICATE_JOB",
        )


class UnknownJobError(ConcurrencyError):
    """Raised when an operation targets a job ID that is not active."""

    def __init__(self, job_id: str):
        super().__init__(
            f"Job '{job_id}' is not active",
            code="E_UNKNOWN_JOB",
        )


# ======================================================================
# Concurrency controller
# ======================================================================

class ConcurrencyController:
    """
    Thread-safe controller enforcing a maximum of ``MAX_ACTIVE_JOBS``
    simultaneous simulation jobs.

    Public API
    ----------
    * ``admit(job_id)`` — reserve a slot for the job.
    * ``release(job_id)`` — release the slot after completion or failure.
    * ``cancel(job_id)`` — cancel and release a running job.
    * ``active_count()`` — current number of active jobs (read-only).
    * ``active_job_ids()`` — sorted list of active job IDs (read-only).
    * ``slot_available()`` — whether at least one slot is free (read-only).

    Notes
    -----
    * All mutating operations are protected by a ``threading.Lock``.
    * No simulation logic is executed.
    * No files are written or read.
    * No state is persisted; a process restart clears all tracked jobs.
    """

    def __init__(self, max_active: int = MAX_ACTIVE_JOBS):
        if max_active < 1:
            raise ConcurrencyError(
                f"max_active must be >= 1, got {max_active}",
                code="E_CONCURRENCY_ERROR",
            )
        self._max_active = max_active
        self._active: Set[str] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------

    def admit(self, job_id: str) -> None:
        """
        Reserve an active slot for *job_id*.

        Raises
        ------
        SimulationLimitError
            If ``MAX_ACTIVE_JOBS`` are already active.
        DuplicateJobError
            If *job_id* is already active.
        """
        with self._lock:
            if job_id in self._active:
                raise DuplicateJobError(job_id)
            if len(self._active) >= self._max_active:
                raise SimulationLimitError()
            self._active.add(job_id)

    def release(self, job_id: str) -> None:
        """
        Release the slot held by *job_id*.

        Raises
        ------
        UnknownJobError
            If *job_id* is not currently active.
        """
        with self._lock:
            if job_id not in self._active:
                raise UnknownJobError(job_id)
            self._active.discard(job_id)

    def cancel(self, job_id: str) -> None:
        """
        Cancel *job_id* and release its slot.

        Semantically identical to ``release`` — provided as a distinct
        entry point for clarity in caller code.

        Raises
        ------
        UnknownJobError
            If *job_id* is not currently active.
        """
        self.release(job_id)

    # ------------------------------------------------------------------
    # Read-only inspection
    # ------------------------------------------------------------------

    def active_count(self) -> int:
        """Return the number of currently active jobs."""
        with self._lock:
            return len(self._active)

    def active_job_ids(self) -> List[str]:
        """Return the active job IDs in deterministic sorted order."""
        with self._lock:
            return sorted(self._active)

    def slot_available(self) -> bool:
        """Return ``True`` if at least one slot is free."""
        with self._lock:
            return len(self._active) < self._max_active

    # ------------------------------------------------------------------
    # Context-manager support for exception-safe cleanup
    # ------------------------------------------------------------------

    class _JobContext:
        """Context manager that releases the slot on exit."""

        def __init__(self, controller: "ConcurrencyController", job_id: str):
            self._controller = controller
            self._job_id = job_id

        def __enter__(self) -> str:
            return self._job_id

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            self._controller.release(self._job_id)
            return None  # do not suppress exceptions

    def managed(self, job_id: str) -> _JobContext:
        """
        Admit *job_id* and return a context manager that releases the
        slot on exit — even if an exception is raised.

        Usage::

            with controller.managed("job_123"):
                # do work
            # slot is automatically released
        """
        self.admit(job_id)
        return self._JobContext(self, job_id)
