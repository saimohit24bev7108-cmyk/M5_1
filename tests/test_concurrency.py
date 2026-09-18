"""
Tests for simulation concurrency control (Step 10 of M5 architecture).

Covers:
    - First job admission succeeds
    - Four jobs can be admitted
    - A fifth active job is rejected
    - Active count is exactly 4 after four admissions
    - Active job IDs are reported correctly
    - Active job IDs are sorted deterministically
    - Releasing a job frees one slot
    - A new job can enter after a slot is released
    - Releasing an unknown job is rejected safely
    - Duplicate admission of the same job is rejected
    - Cancellation frees a slot
    - Failure cleanup frees a slot
    - Exception-safe cleanup does not leak a slot
    - More than four jobs cannot become active under concurrent admission
    - Consistent after mixed admit and release operations
    - Input job IDs are not mutated
    - No simulation logic is executed
    - No files are written
    - No external services are used
"""

import os
import threading
import pytest

from src.m5_simulator.concurrency import (
    ConcurrencyController,
    ConcurrencyError,
    SimulationLimitError,
    DuplicateJobError,
    UnknownJobError,
    MAX_ACTIVE_JOBS,
)


# ==================================================================
# Helpers
# ==================================================================

def _fresh_controller(max_active: int = MAX_ACTIVE_JOBS) -> ConcurrencyController:
    """Return a new controller with no active jobs."""
    return ConcurrencyController(max_active=max_active)


def _fill_controller(ctrl: ConcurrencyController, count: int = MAX_ACTIVE_JOBS):
    """Admit *count* jobs into *ctrl* and return the job IDs."""
    ids = [f"job_{i:03d}" for i in range(count)]
    for jid in ids:
        ctrl.admit(jid)
    return ids


# ==================================================================
# Basic admission
# ==================================================================

class TestAdmission:
    """Job admission behavior."""

    def test_first_job_admitted(self):
        """First job admission succeeds."""
        ctrl = _fresh_controller()
        ctrl.admit("job_001")
        assert ctrl.active_count() == 1

    def test_four_jobs_admitted(self):
        """Four jobs can be admitted."""
        ctrl = _fresh_controller()
        _fill_controller(ctrl, 4)
        assert ctrl.active_count() == 4

    def test_fifth_job_rejected(self):
        """A fifth active job is rejected with E_SIMULATION_LIMIT."""
        ctrl = _fresh_controller()
        _fill_controller(ctrl, 4)
        with pytest.raises(SimulationLimitError, match="E_SIMULATION_LIMIT"):
            ctrl.admit("job_extra")

    def test_fifth_job_does_not_increase_count(self):
        """Rejected fifth job does not increase active count."""
        ctrl = _fresh_controller()
        _fill_controller(ctrl, 4)
        try:
            ctrl.admit("job_extra")
        except SimulationLimitError:
            pass
        assert ctrl.active_count() == 4


# ==================================================================
# Active count and IDs
# ==================================================================

class TestActiveInspection:
    """Inspection of active count and job IDs."""

    def test_active_count_exactly_4(self):
        """Active count is exactly 4 after four admissions."""
        ctrl = _fresh_controller()
        _fill_controller(ctrl, 4)
        assert ctrl.active_count() == 4

    def test_active_job_ids_correct(self):
        """Active job IDs are reported correctly."""
        ctrl = _fresh_controller()
        ctrl.admit("alpha")
        ctrl.admit("beta")
        ids = ctrl.active_job_ids()
        assert "alpha" in ids
        assert "beta" in ids
        assert len(ids) == 2

    def test_active_job_ids_sorted(self):
        """Active job IDs are sorted deterministically."""
        ctrl = _fresh_controller()
        ctrl.admit("charlie")
        ctrl.admit("alpha")
        ctrl.admit("bravo")
        ids = ctrl.active_job_ids()
        assert ids == ["alpha", "bravo", "charlie"]

    def test_slot_available_when_empty(self):
        """slot_available returns True when no jobs are active."""
        ctrl = _fresh_controller()
        assert ctrl.slot_available() is True

    def test_slot_not_available_when_full(self):
        """slot_available returns False when all slots are used."""
        ctrl = _fresh_controller()
        _fill_controller(ctrl, 4)
        assert ctrl.slot_available() is False

    def test_active_count_zero_initially(self):
        """Active count is 0 for a fresh controller."""
        ctrl = _fresh_controller()
        assert ctrl.active_count() == 0

    def test_active_job_ids_empty_initially(self):
        """Active job IDs are empty for a fresh controller."""
        ctrl = _fresh_controller()
        assert ctrl.active_job_ids() == []


# ==================================================================
# Release
# ==================================================================

class TestRelease:
    """Slot release behavior."""

    def test_release_frees_one_slot(self):
        """Releasing a job frees one slot."""
        ctrl = _fresh_controller()
        _fill_controller(ctrl, 4)
        ctrl.release("job_000")
        assert ctrl.active_count() == 3
        assert ctrl.slot_available() is True

    def test_new_job_after_release(self):
        """A new job can enter after a slot is released."""
        ctrl = _fresh_controller()
        _fill_controller(ctrl, 4)
        ctrl.release("job_000")
        ctrl.admit("job_new")
        assert ctrl.active_count() == 4
        assert "job_new" in ctrl.active_job_ids()

    def test_release_unknown_rejected(self):
        """Releasing an unknown job is rejected safely."""
        ctrl = _fresh_controller()
        with pytest.raises(UnknownJobError, match="E_UNKNOWN_JOB"):
            ctrl.release("nonexistent")

    def test_double_release_rejected(self):
        """Releasing the same job twice is rejected."""
        ctrl = _fresh_controller()
        ctrl.admit("job_x")
        ctrl.release("job_x")
        with pytest.raises(UnknownJobError, match="E_UNKNOWN_JOB"):
            ctrl.release("job_x")


# ==================================================================
# Duplicate admission
# ==================================================================

class TestDuplicateAdmission:
    """Duplicate job ID admission."""

    def test_duplicate_admission_rejected(self):
        """Duplicate admission of the same job is rejected."""
        ctrl = _fresh_controller()
        ctrl.admit("job_dup")
        with pytest.raises(DuplicateJobError, match="E_DUPLICATE_JOB"):
            ctrl.admit("job_dup")

    def test_duplicate_does_not_increase_count(self):
        """Rejected duplicate does not increase active count."""
        ctrl = _fresh_controller()
        ctrl.admit("job_dup")
        try:
            ctrl.admit("job_dup")
        except DuplicateJobError:
            pass
        assert ctrl.active_count() == 1


# ==================================================================
# Cancellation
# ==================================================================

class TestCancellation:
    """Cancellation frees a slot."""

    def test_cancel_frees_slot(self):
        """Cancellation frees a slot."""
        ctrl = _fresh_controller()
        ctrl.admit("job_cancel")
        ctrl.cancel("job_cancel")
        assert ctrl.active_count() == 0
        assert ctrl.slot_available() is True

    def test_cancel_unknown_rejected(self):
        """Cancelling an unknown job is rejected."""
        ctrl = _fresh_controller()
        with pytest.raises(UnknownJobError, match="E_UNKNOWN_JOB"):
            ctrl.cancel("ghost")


# ==================================================================
# Failure cleanup
# ==================================================================

class TestFailureCleanup:
    """Failure cleanup frees a slot."""

    def test_release_after_simulated_failure(self):
        """Releasing after a job failure still frees the slot."""
        ctrl = _fresh_controller()
        ctrl.admit("job_fail")
        # Simulate failure by catching an exception, then release.
        try:
            raise RuntimeError("simulated failure")
        except RuntimeError:
            ctrl.release("job_fail")
        assert ctrl.active_count() == 0


# ==================================================================
# Exception-safe cleanup (context manager)
# ==================================================================

class TestExceptionSafeCleanup:
    """Exception-safe cleanup does not leak a slot."""

    def test_managed_cleanup_on_success(self):
        """managed() releases the slot on normal exit."""
        ctrl = _fresh_controller()
        with ctrl.managed("job_ctx"):
            assert ctrl.active_count() == 1
        assert ctrl.active_count() == 0

    def test_managed_cleanup_on_exception(self):
        """managed() releases the slot when an exception is raised."""
        ctrl = _fresh_controller()
        with pytest.raises(ValueError):
            with ctrl.managed("job_exc"):
                assert ctrl.active_count() == 1
                raise ValueError("boom")
        assert ctrl.active_count() == 0

    def test_managed_no_slot_leak_after_exception(self):
        """No slot is leaked after an exception inside managed()."""
        ctrl = _fresh_controller()
        for i in range(10):
            try:
                with ctrl.managed(f"leak_test_{i}"):
                    if i % 2 == 0:
                        raise RuntimeError("every other fails")
            except RuntimeError:
                pass
        # All slots should be freed.
        assert ctrl.active_count() == 0


# ==================================================================
# Concurrent admission safety
# ==================================================================

class TestConcurrentAdmission:
    """More than four jobs cannot become active under concurrent admission."""

    def test_concurrent_admits_respect_limit(self):
        """At most MAX_ACTIVE_JOBS succeed under concurrent admission attempts."""
        ctrl = _fresh_controller()
        admitted = []
        rejected = []
        barrier = threading.Barrier(8)

        def try_admit(jid):
            barrier.wait()
            try:
                ctrl.admit(jid)
                admitted.append(jid)
            except SimulationLimitError:
                rejected.append(jid)

        threads = [
            threading.Thread(target=try_admit, args=(f"t_{i}",))
            for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(admitted) == MAX_ACTIVE_JOBS
        assert len(rejected) == 4
        assert ctrl.active_count() == MAX_ACTIVE_JOBS

    def test_concurrent_admit_and_release(self):
        """Controller remains consistent under concurrent admit + release."""
        ctrl = _fresh_controller()

        def admit_and_release(jid):
            ctrl.admit(jid)
            ctrl.release(jid)

        threads = [
            threading.Thread(target=admit_and_release, args=(f"ar_{i}",))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert ctrl.active_count() == 0


# ==================================================================
# Mixed admit and release consistency
# ==================================================================

class TestMixedOperations:
    """Consistent after mixed admit and release operations."""

    def test_mixed_admit_release(self):
        """Controller tracks state correctly through a mixed sequence."""
        ctrl = _fresh_controller()

        ctrl.admit("a")
        ctrl.admit("b")
        assert ctrl.active_count() == 2

        ctrl.release("a")
        assert ctrl.active_count() == 1

        ctrl.admit("c")
        ctrl.admit("d")
        ctrl.admit("e")
        assert ctrl.active_count() == 4

        # Fifth should fail.
        with pytest.raises(SimulationLimitError):
            ctrl.admit("f")

        ctrl.release("b")
        ctrl.admit("f")
        assert ctrl.active_count() == 4
        assert "f" in ctrl.active_job_ids()

    def test_readmit_after_release(self):
        """A job ID can be readmitted after being released."""
        ctrl = _fresh_controller()
        ctrl.admit("reuse")
        ctrl.release("reuse")
        ctrl.admit("reuse")
        assert ctrl.active_count() == 1
        assert "reuse" in ctrl.active_job_ids()


# ==================================================================
# Input job IDs not mutated
# ==================================================================

class TestInputImmutability:
    """Input job IDs are not mutated."""

    def test_job_id_string_not_mutated(self):
        """The job_id string passed to admit is not mutated."""
        jid = "immutable_id"
        ctrl = _fresh_controller()
        ctrl.admit(jid)
        assert jid == "immutable_id"
        ctrl.release(jid)
        assert jid == "immutable_id"

    def test_active_job_ids_returns_copy(self):
        """active_job_ids returns a new list, not the internal set."""
        ctrl = _fresh_controller()
        ctrl.admit("probe")
        ids = ctrl.active_job_ids()
        ids.append("tamper")
        assert ctrl.active_count() == 1
        assert "tamper" not in ctrl.active_job_ids()


# ==================================================================
# No simulation logic
# ==================================================================

class TestNoSimulationLogic:
    """No simulation logic is executed."""

    def test_concurrency_does_not_import_simulation_modules(self):
        """concurrency.py does not import simulation modules."""
        import src.m5_simulator.concurrency as cc_mod
        source = open(cc_mod.__file__, "r").read()
        assert "from src.m5_simulator.statevector" not in source
        assert "from src.m5_simulator.sampling" not in source
        assert "from src.m5_simulator.gates" not in source
        assert "from src.m5_simulator.noise" not in source
        assert "from src.m5_simulator.backend" not in source
        assert "from src.m5_simulator.serialization" not in source
        assert "from src.m5_simulator.analysis" not in source


# ==================================================================
# No files written
# ==================================================================

class TestNoFileOutput:
    """No files are written."""

    def test_no_files_written(self):
        """Admit/release cycle writes no files to the working directory."""
        cwd = os.getcwd()
        before = set(os.listdir(cwd))
        ctrl = _fresh_controller()
        ctrl.admit("file_test")
        ctrl.release("file_test")
        after = set(os.listdir(cwd))
        assert after == before


# ==================================================================
# No external services
# ==================================================================

class TestNoExternalServices:
    """No external services are used."""

    def test_no_network_imports(self):
        """concurrency.py does not import network libraries."""
        import src.m5_simulator.concurrency as cc_mod
        source = open(cc_mod.__file__, "r").read()
        assert "import requests" not in source
        assert "import urllib" not in source
        assert "import http" not in source
        assert "import socket" not in source


# ==================================================================
# Error hierarchy
# ==================================================================

class TestErrorHierarchy:
    """Error classes follow M5 conventions."""

    def test_simulation_limit_error_is_concurrency_error(self):
        """SimulationLimitError is a ConcurrencyError."""
        assert issubclass(SimulationLimitError, ConcurrencyError)

    def test_duplicate_job_error_is_concurrency_error(self):
        """DuplicateJobError is a ConcurrencyError."""
        assert issubclass(DuplicateJobError, ConcurrencyError)

    def test_unknown_job_error_is_concurrency_error(self):
        """UnknownJobError is a ConcurrencyError."""
        assert issubclass(UnknownJobError, ConcurrencyError)

    def test_concurrency_error_has_code(self):
        """ConcurrencyError carries a structured error code."""
        err = ConcurrencyError("test", code="E_TEST")
        assert err.code == "E_TEST"


if __name__ == "__main__":
    pytest.main([__file__])
