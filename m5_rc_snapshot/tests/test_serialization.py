"""
Tests for deterministic result serialization and SHA-256 checksums
(Step 8 of M5 architecture).

Covers:
    - Successful package creation from an ideal Bell-circuit backend result
    - Successful package creation from a noisy backend result
    - Exact required package file list
    - Correct result label "SIMULATION"
    - Correct run ID and simulator version
    - Correct circuit.json contents
    - Correct configuration.json contents
    - Correct result.json contents
    - Correct histogram.json contents
    - Counts sum equals shots
    - Deterministic JSON output
    - Repeated serialization produces identical file contents (excluding timestamps)
    - Deterministic checksum generation
    - Successful checksum verification
    - Detection of a modified result file
    - Detection of a modified histogram file
    - Rejection of an existing run directory
    - Rejection of an incomplete backend result
    - Rejection of an error backend result
    - Rejection of missing package files
    - Rejection of unknown major schema versions
    - Confirmation that source backend results are not mutated
    - Confirmation that historical files are not modified
    - Confirmation that serialization does not execute simulation logic
"""

import copy
import json
import os
import pytest

from src.m5_simulator.backend import run_simulation
from src.m5_simulator.serialization import (
    serialize_result,
    validate_package,
    verify_checksums,
    calculate_checksums,
    load_package,
    SerializationError,
    PACKAGE_FILES,
    ALL_PACKAGE_FILES,
    CHECKSUM_FILE,
    RESULT_LABEL,
    _deterministic_json,
    _load_json,
)
from src.m5_simulator.version import __version__ as SIMULATOR_VERSION


# ==================================================================
# Fixtures: backend results
# ==================================================================

def _ideal_bell_result() -> dict:
    """Run a Bell-circuit simulation and return the backend result."""
    req = {
        "request_id": "req_ser_001",
        "run_id": "run_ser_001",
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
        "shots": 1000,
        "seed": 42,
    }
    result = run_simulation(req)
    assert result["status"] == "completed"
    return result


def _noisy_bell_result() -> dict:
    """Run a noisy Bell-circuit simulation and return the backend result."""
    req = {
        "request_id": "req_noisy_ser",
        "run_id": "run_noisy_ser",
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
    result = run_simulation(req)
    assert result["status"] == "completed"
    return result


def _error_result() -> dict:
    """Return a backend error result."""
    req = {
        "request_id": "req_err",
        "run_id": "run_err",
        "circuit": {
            "schema_version": "1.0",
            "num_qubits": 2,
            "operations": [
                {"gate": "H", "targets": [0]},
                {"gate": "CNOT", "targets": [0, 1]},
            ],
        },
        "mode": "invalid_mode",
        "noise": {},
        "shots": 1000,
        "seed": 42,
    }
    result = run_simulation(req)
    assert result["status"] == "error"
    return result


# ==================================================================
# Successful package creation
# ==================================================================

class TestPackageCreation:
    """Successful package creation."""

    def test_ideal_bell_package(self, tmp_path):
        """Ideal Bell-circuit result serializes to a complete package."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        assert os.path.isdir(pkg_dir)
        for fname in ALL_PACKAGE_FILES:
            assert os.path.isfile(os.path.join(pkg_dir, fname))

    def test_noisy_bell_package(self, tmp_path):
        """Noisy Bell-circuit result serializes to a complete package."""
        result = _noisy_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        assert os.path.isdir(pkg_dir)
        for fname in ALL_PACKAGE_FILES:
            assert os.path.isfile(os.path.join(pkg_dir, fname))


# ==================================================================
# Exact required package file list
# ==================================================================

class TestPackageFileList:
    """Package contains exactly the required files."""

    def test_exact_file_list(self, tmp_path):
        """Package directory contains exactly the expected files."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        actual_files = sorted(os.listdir(pkg_dir))
        expected_files = sorted(ALL_PACKAGE_FILES)
        assert actual_files == expected_files


# ==================================================================
# Result label
# ==================================================================

class TestResultLabel:
    """Correct result label."""

    def test_result_label_simulation(self, tmp_path):
        """result.json has result_label 'SIMULATION'."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        result_data = _load_json(os.path.join(pkg_dir, "result.json"))
        assert result_data["result_label"] == "SIMULATION"

    def test_run_json_result_label(self, tmp_path):
        """run.json has result_label 'SIMULATION'."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        run_data = _load_json(os.path.join(pkg_dir, "run.json"))
        assert run_data["result_label"] == "SIMULATION"


# ==================================================================
# Run ID and simulator version
# ==================================================================

class TestRunIdAndVersion:
    """Correct run ID and simulator version."""

    def test_run_id(self, tmp_path):
        """run.json has the correct run_id."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        run_data = _load_json(os.path.join(pkg_dir, "run.json"))
        assert run_data["run_id"] == "run_ser_001"

    def test_simulator_version(self, tmp_path):
        """run.json has the correct simulator_version."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        run_data = _load_json(os.path.join(pkg_dir, "run.json"))
        assert run_data["simulator_version"] == SIMULATOR_VERSION


# ==================================================================
# Individual file contents
# ==================================================================

class TestCircuitJson:
    """Correct circuit.json contents."""

    def test_circuit_json_qubits(self, tmp_path):
        """circuit.json has the correct qubit count."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        circuit = _load_json(os.path.join(pkg_dir, "circuit.json"))
        assert circuit["qubits"] == 2

    def test_circuit_json_operations(self, tmp_path):
        """circuit.json has the correct operations."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        circuit = _load_json(os.path.join(pkg_dir, "circuit.json"))
        assert len(circuit["operations"]) == 2
        assert circuit["operations"][0]["gate"] == "H"
        assert circuit["operations"][1]["gate"] == "CNOT"


class TestConfigurationJson:
    """Correct configuration.json contents."""

    def test_configuration_mode(self, tmp_path):
        """configuration.json has the correct mode."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        config = _load_json(os.path.join(pkg_dir, "configuration.json"))
        assert config["mode"] == "ideal"

    def test_configuration_shots(self, tmp_path):
        """configuration.json has the correct shots."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        config = _load_json(os.path.join(pkg_dir, "configuration.json"))
        assert config["shots"] == 1000

    def test_configuration_noise(self, tmp_path):
        """configuration.json includes noise configuration."""
        result = _noisy_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        config = _load_json(os.path.join(pkg_dir, "configuration.json"))
        assert config["noise"]["mode"] == "noisy"
        assert config["noise"]["gate_noise"]["model"] == "depolarizing"


class TestResultJson:
    """Correct result.json contents."""

    def test_result_json_probabilities(self, tmp_path):
        """result.json contains probabilities."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        rdata = _load_json(os.path.join(pkg_dir, "result.json"))
        assert "probabilities" in rdata
        assert len(rdata["probabilities"]) == 4

    def test_result_json_counts(self, tmp_path):
        """result.json contains counts."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        rdata = _load_json(os.path.join(pkg_dir, "result.json"))
        assert "counts" in rdata
        assert sum(rdata["counts"].values()) == 1000

    def test_result_json_mode(self, tmp_path):
        """result.json has the correct mode."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        rdata = _load_json(os.path.join(pkg_dir, "result.json"))
        assert rdata["mode"] == "ideal"

    def test_result_json_seed(self, tmp_path):
        """result.json has the correct seed."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        rdata = _load_json(os.path.join(pkg_dir, "result.json"))
        assert rdata["seed"] == 42


class TestHistogramJson:
    """Correct histogram.json contents."""

    def test_histogram_sorted_keys(self, tmp_path):
        """histogram.json has sorted outcome keys."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        hdata = _load_json(os.path.join(pkg_dir, "histogram.json"))
        keys = list(hdata["counts"].keys())
        assert keys == sorted(keys)

    def test_histogram_shots(self, tmp_path):
        """histogram.json records the correct shots value."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        hdata = _load_json(os.path.join(pkg_dir, "histogram.json"))
        assert hdata["shots"] == 1000


# ==================================================================
# Counts sum equals shots
# ==================================================================

class TestCountsSum:
    """Histogram counts sum equals shots."""

    def test_counts_sum_equals_shots(self, tmp_path):
        """Counts in histogram.json sum exactly to shots."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        hdata = _load_json(os.path.join(pkg_dir, "histogram.json"))
        assert sum(hdata["counts"].values()) == hdata["shots"]

    def test_analysis_counts_sum(self, tmp_path):
        """analysis.json counts_sum equals shots."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        adata = _load_json(os.path.join(pkg_dir, "analysis.json"))
        assert adata["counts_sum"] == adata["shots"]


# ==================================================================
# Deterministic JSON output
# ==================================================================

class TestDeterministicJson:
    """JSON output is deterministic."""

    def test_deterministic_json_sorted_keys(self):
        """_deterministic_json produces sorted keys."""
        data = {"z": 1, "a": 2, "m": 3}
        output = _deterministic_json(data)
        parsed_keys = list(json.loads(output).keys())
        assert parsed_keys == ["a", "m", "z"]

    def test_deterministic_json_trailing_newline(self):
        """_deterministic_json ends with exactly one newline."""
        output = _deterministic_json({"a": 1})
        assert output.endswith("\n")
        assert not output.endswith("\n\n")

    def test_repeated_serialization_identical_contents(self, tmp_path):
        """Repeated serialization produces identical file contents (except timestamps)."""
        result = _ideal_bell_result()
        ts = "2026-01-01T00:00:00+00:00"

        dir1 = str(tmp_path / "out1")
        os.makedirs(dir1)
        pkg1 = serialize_result(
            copy.deepcopy(result), dir1,
            start_timestamp=ts, end_timestamp=ts,
        )

        dir2 = str(tmp_path / "out2")
        os.makedirs(dir2)
        pkg2 = serialize_result(
            copy.deepcopy(result), dir2,
            start_timestamp=ts, end_timestamp=ts,
        )

        for fname in PACKAGE_FILES:
            with open(os.path.join(pkg1, fname), "r") as f1, \
                 open(os.path.join(pkg2, fname), "r") as f2:
                assert f1.read() == f2.read(), f"{fname} contents differ"


# ==================================================================
# Checksums
# ==================================================================

class TestChecksums:
    """Checksum generation and verification."""

    def test_deterministic_checksum_generation(self, tmp_path):
        """Checksums are deterministic for the same input."""
        result = _ideal_bell_result()
        ts = "2026-01-01T00:00:00+00:00"

        dir1 = str(tmp_path / "chk1")
        os.makedirs(dir1)
        pkg1 = serialize_result(
            copy.deepcopy(result), dir1,
            start_timestamp=ts, end_timestamp=ts,
        )

        dir2 = str(tmp_path / "chk2")
        os.makedirs(dir2)
        pkg2 = serialize_result(
            copy.deepcopy(result), dir2,
            start_timestamp=ts, end_timestamp=ts,
        )

        cs1 = calculate_checksums(pkg1)
        cs2 = calculate_checksums(pkg2)
        assert cs1 == cs2

    def test_successful_checksum_verification(self, tmp_path):
        """Checksum verification passes on an unmodified package."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        # Should not raise.
        verify_checksums(pkg_dir)

    def test_detection_of_modified_result_file(self, tmp_path):
        """Modified result.json is detected by checksum verification."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))

        # Tamper with result.json.
        rpath = os.path.join(pkg_dir, "result.json")
        with open(rpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["shots"] = 9999
        with open(rpath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with pytest.raises(SerializationError, match="E_CHECKSUM_MISMATCH"):
            verify_checksums(pkg_dir)

    def test_detection_of_modified_histogram_file(self, tmp_path):
        """Modified histogram.json is detected by checksum verification."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))

        # Tamper with histogram.json.
        hpath = os.path.join(pkg_dir, "histogram.json")
        with open(hpath, "a", encoding="utf-8") as f:
            f.write("tampered\n")

        with pytest.raises(SerializationError, match="E_CHECKSUM_MISMATCH"):
            verify_checksums(pkg_dir)


# ==================================================================
# Rejection: existing run directory
# ==================================================================

class TestExistingRunDirectory:
    """Reject existing run directory."""

    def test_reject_existing_run_directory(self, tmp_path):
        """Existing run directory is not overwritten."""
        result = _ideal_bell_result()
        serialize_result(copy.deepcopy(result), str(tmp_path))

        # Second attempt with the same run_id should fail.
        with pytest.raises(SerializationError, match="E_SERIALIZATION_REJECTED"):
            serialize_result(copy.deepcopy(result), str(tmp_path))


# ==================================================================
# Rejection: incomplete and error results
# ==================================================================

class TestIncompleteAndErrorRejection:
    """Reject incomplete and error results."""

    def test_reject_error_result(self, tmp_path):
        """Error backend result is rejected."""
        result = _error_result()
        with pytest.raises(SerializationError, match="E_SERIALIZATION_REJECTED"):
            serialize_result(result, str(tmp_path))

    def test_reject_incomplete_result(self, tmp_path):
        """Incomplete backend result (missing counts) is rejected."""
        result = _ideal_bell_result()
        del result["counts"]
        with pytest.raises(SerializationError, match="E_SERIALIZATION_REJECTED"):
            serialize_result(result, str(tmp_path))

    def test_reject_missing_probabilities(self, tmp_path):
        """Backend result missing probabilities is rejected."""
        result = _ideal_bell_result()
        del result["probabilities"]
        with pytest.raises(SerializationError, match="E_SERIALIZATION_REJECTED"):
            serialize_result(result, str(tmp_path))


# ==================================================================
# Rejection: missing package files
# ==================================================================

class TestMissingPackageFiles:
    """Reject packages with missing files."""

    def test_reject_missing_result_json(self, tmp_path):
        """Package missing result.json fails validation."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))

        # Remove result.json.
        os.remove(os.path.join(pkg_dir, "result.json"))

        with pytest.raises(SerializationError, match="E_PACKAGE_INVALID"):
            validate_package(pkg_dir)

    def test_reject_missing_checksum_file(self, tmp_path):
        """Package missing checksum.sha256 fails validation."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))

        os.remove(os.path.join(pkg_dir, CHECKSUM_FILE))

        with pytest.raises(SerializationError, match="E_PACKAGE_INVALID"):
            validate_package(pkg_dir)


# ==================================================================
# Rejection: unknown major schema versions
# ==================================================================

class TestSchemaVersionRejection:
    """Reject unknown major schema versions."""

    def test_reject_unknown_major_version(self, tmp_path):
        """Backend result with unknown major schema version is rejected."""
        result = _ideal_bell_result()
        result["schema_version"] = "99.0"
        with pytest.raises(SerializationError, match="E_SERIALIZATION_REJECTED"):
            serialize_result(result, str(tmp_path))


# ==================================================================
# Input immutability
# ==================================================================

class TestInputImmutability:
    """Source backend results are not mutated."""

    def test_backend_result_not_mutated(self, tmp_path):
        """serialize_result does not mutate the input result dict."""
        result = _ideal_bell_result()
        result_copy = copy.deepcopy(result)
        serialize_result(result, str(tmp_path))
        assert result == result_copy


# ==================================================================
# Historical files not modified
# ==================================================================

class TestHistoricalFiles:
    """Serialization does not modify historical/project files."""

    def test_no_modification_to_project_files(self, tmp_path):
        """Serialization only writes inside the output directory."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))

        # The package is under tmp_path, not the project root.
        assert str(tmp_path) in pkg_dir


# ==================================================================
# Serialization does not execute simulation logic
# ==================================================================

class TestNoSimulationExecution:
    """Serialization does not execute simulation logic."""

    def test_serialization_does_not_import_statevector(self, tmp_path):
        """serialization.py does not import statevector, sampling, or gates."""
        import src.m5_simulator.serialization as ser_mod
        source_code = open(ser_mod.__file__, "r").read()
        # serialization.py should not import the simulation modules.
        assert "from src.m5_simulator.statevector" not in source_code
        assert "from src.m5_simulator.sampling" not in source_code
        assert "from src.m5_simulator.gates" not in source_code
        assert "from src.m5_simulator.noise" not in source_code

    def test_result_passes_through_unchanged(self, tmp_path):
        """Probabilities and counts in the package match the backend result exactly."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(copy.deepcopy(result), str(tmp_path))

        rdata = _load_json(os.path.join(pkg_dir, "result.json"))
        assert rdata["probabilities"] == result["probabilities"]
        assert rdata["counts"] == result["counts"]


# ==================================================================
# Analysis.json basic facts
# ==================================================================

class TestAnalysisJson:
    """analysis.json contains basic package-level facts."""

    def test_analysis_basic_fields(self, tmp_path):
        """analysis.json has counts_sum, nonzero_outcomes, shots, mode, reproducibility."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        adata = _load_json(os.path.join(pkg_dir, "analysis.json"))

        assert "counts_sum" in adata
        assert "nonzero_outcomes" in adata
        assert "shots" in adata
        assert "mode" in adata
        assert "reproducibility" in adata

    def test_analysis_reproducibility_seeded(self, tmp_path):
        """Seeded run reports reproducibility = 'seeded'."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        adata = _load_json(os.path.join(pkg_dir, "analysis.json"))
        assert adata["reproducibility"] == "seeded"


# ==================================================================
# Load package
# ==================================================================

class TestLoadPackage:
    """Load a finalized package without modifying it."""

    def test_load_package_success(self, tmp_path):
        """load_package returns all package data."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        package = load_package(pkg_dir)

        assert "run" in package
        assert "circuit" in package
        assert "configuration" in package
        assert "result" in package
        assert "histogram" in package
        assert "analysis" in package
        assert "checksums" in package

    def test_load_package_does_not_modify_files(self, tmp_path):
        """load_package does not modify any files."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))

        # Record checksums before load.
        cs_before = calculate_checksums(pkg_dir)
        load_package(pkg_dir)
        cs_after = calculate_checksums(pkg_dir)

        assert cs_before == cs_after


# ==================================================================
# Run.json package_files and checksums
# ==================================================================

class TestRunJsonMetadata:
    """run.json includes package_files and checksums."""

    def test_run_json_package_files(self, tmp_path):
        """run.json lists all package files."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        run_data = _load_json(os.path.join(pkg_dir, "run.json"))
        assert set(ALL_PACKAGE_FILES).issubset(set(run_data["package_files"]))

    def test_run_json_checksums(self, tmp_path):
        """run.json contains per-file SHA-256 checksums."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        run_data = _load_json(os.path.join(pkg_dir, "run.json"))
        for fname in PACKAGE_FILES:
            assert fname in run_data["checksums"]
            assert len(run_data["checksums"][fname]) == 64  # SHA-256 hex

    def test_run_json_timestamps(self, tmp_path):
        """run.json contains ISO 8601 timestamps."""
        result = _ideal_bell_result()
        pkg_dir = serialize_result(result, str(tmp_path))
        run_data = _load_json(os.path.join(pkg_dir, "run.json"))
        assert "timestamps" in run_data
        assert "start" in run_data["timestamps"]
        assert "end" in run_data["timestamps"]


if __name__ == "__main__":
    pytest.main([__file__])
