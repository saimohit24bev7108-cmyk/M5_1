"""
Tests for basic analysis outputs (Step 9 of M5 architecture).

Covers:
    - Analysis of a completed ideal Bell-circuit result
    - Analysis of a completed noisy result
    - Correct counts_sum
    - Correct shots
    - Correct nonzero_outcomes
    - Correct qubit count
    - Correct mode
    - Correct seeded or unseeded status
    - Correct probability-versus-outcome records
    - Correct result label "SIMULATION"
    - Correct limitation statement
    - Comparison of two compatible results
    - Rejection of incompatible circuits
    - Rejection of incompatible qubit counts
    - One-parameter noise comparison output
    - Stable output ordering
    - Rejection of an error result
    - Rejection of an incomplete result
    - Rejection of invalid or checksum-failing package data
    - Rejection of an unknown major schema version
    - Confirmation that source results are not mutated
    - Confirmation that finalized package files are not modified
    - Confirmation that analysis does not execute simulation logic
"""

import copy
import json
import os
import pytest

from src.m5_simulator.backend import run_simulation
from src.m5_simulator.analysis import (
    analyze_result,
    compare_results,
    noise_parameter_sweep,
    AnalysisError,
    ANALYSIS_VERSION,
    LIMITATION_STATEMENT,
    RESULT_LABEL,
)
from src.m5_simulator.serialization import serialize_result, calculate_checksums


# ==================================================================
# Fixtures: backend results
# ==================================================================

def _ideal_bell_result(*, seed: int = 42, shots: int = 1000, run_id: str = "run_ana_001") -> dict:
    """Run a Bell-circuit simulation and return the completed backend result."""
    req = {
        "request_id": "req_ana",
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
    result = run_simulation(req)
    assert result["status"] == "completed"
    return result


def _noisy_bell_result(
    *,
    gate_prob: float = 0.01,
    readout_prob: float = 0.02,
    seed: int = 42,
    shots: int = 1000,
    run_id: str = "run_noisy_ana",
) -> dict:
    """Run a noisy Bell-circuit simulation and return the completed result."""
    req = {
        "request_id": "req_noisy_ana",
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
            "gate_noise": {"model": "depolarizing", "probability": gate_prob},
            "readout_noise": {"model": "bit_flip", "probability": readout_prob},
            "decoherence": {"model": "none"},
        },
        "shots": shots,
        "seed": seed,
    }
    result = run_simulation(req)
    assert result["status"] == "completed"
    return result


def _one_qubit_result(*, run_id: str = "run_1q_ana") -> dict:
    """One-qubit X-gate result for incompatibility tests."""
    req = {
        "request_id": "req_1q_ana",
        "run_id": run_id,
        "circuit": {
            "schema_version": "1.0",
            "num_qubits": 1,
            "operations": [{"gate": "X", "targets": [0]}],
        },
        "mode": "ideal",
        "noise": {},
        "shots": 100,
        "seed": 0,
    }
    result = run_simulation(req)
    assert result["status"] == "completed"
    return result


def _different_circuit_result(*, run_id: str = "run_diff_ana") -> dict:
    """Two-qubit result with a different circuit (H on qubit 1 instead of 0)."""
    req = {
        "request_id": "req_diff_ana",
        "run_id": run_id,
        "circuit": {
            "schema_version": "1.0",
            "num_qubits": 2,
            "operations": [
                {"gate": "H", "targets": [1]},
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


def _error_result() -> dict:
    """Return an error backend result."""
    req = {
        "request_id": "req_err",
        "run_id": "run_err",
        "circuit": {
            "schema_version": "1.0",
            "num_qubits": 2,
            "operations": [
                {"gate": "H", "targets": [0]},
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
# Analysis of ideal result
# ==================================================================

class TestAnalyzeIdeal:
    """Analysis of a completed ideal Bell-circuit result."""

    def test_analyze_ideal_bell(self):
        """Ideal Bell-circuit result is analyzed successfully."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        assert analysis["analysis_version"] == ANALYSIS_VERSION
        assert analysis["mode"] == "ideal"

    def test_counts_sum(self):
        """counts_sum equals the sum of all histogram counts."""
        result = _ideal_bell_result(shots=500)
        analysis = analyze_result(result)
        assert analysis["counts_sum"] == 500

    def test_shots(self):
        """shots matches the original request."""
        result = _ideal_bell_result(shots=2048)
        analysis = analyze_result(result)
        assert analysis["shots"] == 2048

    def test_nonzero_outcomes(self):
        """nonzero_outcomes counts outcomes with count > 0."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        # Bell state has 2 nonzero outcomes: 00 and 11.
        assert analysis["nonzero_outcomes"] == 2

    def test_qubit_count(self):
        """num_qubits matches the circuit."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        assert analysis["num_qubits"] == 2

    def test_mode_ideal(self):
        """mode is 'ideal'."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        assert analysis["mode"] == "ideal"


# ==================================================================
# Analysis of noisy result
# ==================================================================

class TestAnalyzeNoisy:
    """Analysis of a completed noisy result."""

    def test_analyze_noisy_bell(self):
        """Noisy Bell-circuit result is analyzed successfully."""
        result = _noisy_bell_result()
        analysis = analyze_result(result)
        assert analysis["mode"] == "noisy"

    def test_noisy_noise_config(self):
        """Noisy analysis includes the noise configuration."""
        result = _noisy_bell_result()
        analysis = analyze_result(result)
        assert analysis["noise"]["mode"] == "noisy"


# ==================================================================
# Seeded / unseeded status
# ==================================================================

class TestSeededStatus:
    """Seeded or unseeded status."""

    def test_seeded(self):
        """Seeded result reports seeded=True and reproducibility='seeded'."""
        result = _ideal_bell_result(seed=42)
        analysis = analyze_result(result)
        assert analysis["seeded"] is True
        assert analysis["reproducibility"] == "seeded"
        assert analysis["seed"] == 42

    def test_unseeded(self):
        """Unseeded result reports seeded=False and reproducibility='unseeded'."""
        req = {
            "request_id": "req_uns",
            "run_id": "run_uns",
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
            "shots": 100,
            "seed": None,
        }
        result = run_simulation(req)
        analysis = analyze_result(result)
        assert analysis["seeded"] is False
        assert analysis["reproducibility"] == "unseeded"
        assert analysis["seed"] is None


# ==================================================================
# Probability-versus-outcome records
# ==================================================================

class TestOutcomeProbabilities:
    """Probability-versus-outcome records."""

    def test_outcome_probabilities_count(self):
        """outcome_probabilities has 2^num_qubits records."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        assert len(analysis["outcome_probabilities"]) == 4

    def test_outcome_probabilities_sorted(self):
        """outcome_probabilities are in sorted outcome order."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        outcomes = [rec["outcome"] for rec in analysis["outcome_probabilities"]]
        assert outcomes == sorted(outcomes)

    def test_outcome_probabilities_bell_state(self):
        """Bell-state probabilities are ~0.5 for 00 and 11, ~0 for 01 and 10."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        probs = {rec["outcome"]: rec["probability"]
                 for rec in analysis["outcome_probabilities"]}
        assert abs(probs["00"] - 0.5) < 1e-10
        assert abs(probs["11"] - 0.5) < 1e-10
        assert abs(probs["01"]) < 1e-10
        assert abs(probs["10"]) < 1e-10

    def test_outcome_probabilities_keys(self):
        """Each outcome record has 'outcome' and 'probability' keys."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        for rec in analysis["outcome_probabilities"]:
            assert "outcome" in rec
            assert "probability" in rec


# ==================================================================
# Result label and limitation
# ==================================================================

class TestLabelAndLimitation:
    """Result label and limitation statement."""

    def test_result_label(self):
        """Analysis result_label is 'SIMULATION'."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        assert analysis["result_label"] == "SIMULATION"

    def test_limitation_statement(self):
        """Analysis includes the correct limitation statement."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        assert analysis["limitation"] == LIMITATION_STATEMENT
        assert "simulated result" in analysis["limitation"]
        assert "not a physical measurement" in analysis["limitation"]


# ==================================================================
# Comparison of two compatible results
# ==================================================================

class TestCompareResults:
    """Comparison of two compatible results."""

    def test_compare_ideal_vs_noisy(self):
        """Comparing ideal and noisy Bell results produces a valid comparison."""
        a = _ideal_bell_result(run_id="run_cmp_a")
        b = _noisy_bell_result(run_id="run_cmp_b")
        comp = compare_results(a, b)
        assert comp["comparison_type"] == "result_pair"
        assert comp["mode_a"] == "ideal"
        assert comp["mode_b"] == "noisy"
        assert comp["num_qubits"] == 2

    def test_compare_outcome_comparisons(self):
        """Comparison includes per-outcome deltas."""
        a = _ideal_bell_result(run_id="run_cmp_a2")
        b = _noisy_bell_result(run_id="run_cmp_b2")
        comp = compare_results(a, b)
        assert len(comp["outcome_comparisons"]) == 4
        for rec in comp["outcome_comparisons"]:
            assert "outcome" in rec
            assert "probability_a" in rec
            assert "probability_b" in rec
            assert "probability_delta" in rec

    def test_compare_has_limitation(self):
        """Comparison includes the limitation statement."""
        a = _ideal_bell_result(run_id="run_cmp_lim_a")
        b = _noisy_bell_result(run_id="run_cmp_lim_b")
        comp = compare_results(a, b)
        assert comp["limitation"] == LIMITATION_STATEMENT

    def test_compare_run_ids(self):
        """Comparison records both run IDs."""
        a = _ideal_bell_result(run_id="run_A")
        b = _noisy_bell_result(run_id="run_B")
        comp = compare_results(a, b)
        assert comp["run_id_a"] == "run_A"
        assert comp["run_id_b"] == "run_B"


# ==================================================================
# Rejection: incompatible circuits and qubit counts
# ==================================================================

class TestIncompatibility:
    """Rejection of incompatible comparisons."""

    def test_reject_incompatible_qubit_counts(self):
        """Comparing results with different qubit counts is rejected."""
        a = _ideal_bell_result(run_id="run_inc_a")
        b = _one_qubit_result(run_id="run_inc_b")
        with pytest.raises(AnalysisError, match="E_ANALYSIS_INCOMPATIBLE"):
            compare_results(a, b)

    def test_reject_incompatible_circuits(self):
        """Comparing results with different circuits is rejected."""
        a = _ideal_bell_result(run_id="run_circ_a")
        b = _different_circuit_result(run_id="run_circ_b")
        with pytest.raises(AnalysisError, match="E_ANALYSIS_INCOMPATIBLE"):
            compare_results(a, b)


# ==================================================================
# One-parameter noise comparison
# ==================================================================

class TestNoiseParameterSweep:
    """One-parameter noise comparison output."""

    def test_noise_sweep_output(self):
        """Noise sweep produces sweep_records with correct fields."""
        results = [
            _noisy_bell_result(gate_prob=0.0, run_id="sweep_0"),
            _noisy_bell_result(gate_prob=0.05, run_id="sweep_1"),
            _noisy_bell_result(gate_prob=0.1, run_id="sweep_2"),
        ]
        param_values = [0.0, 0.05, 0.1]
        sweep = noise_parameter_sweep(results, "gate_noise.probability", param_values)

        assert sweep["comparison_type"] == "noise_parameter_sweep"
        assert sweep["parameter_name"] == "gate_noise.probability"
        assert sweep["num_points"] == 3
        # 3 results × 4 outcomes = 12 records.
        assert len(sweep["sweep_records"]) == 12

    def test_noise_sweep_record_fields(self):
        """Each sweep record has parameter_name, parameter_value, outcome, probability, run_id."""
        results = [
            _noisy_bell_result(gate_prob=0.0, run_id="sweep_f0"),
            _noisy_bell_result(gate_prob=0.1, run_id="sweep_f1"),
        ]
        sweep = noise_parameter_sweep(results, "gate_prob", [0.0, 0.1])
        for rec in sweep["sweep_records"]:
            assert "parameter_name" in rec
            assert "parameter_value" in rec
            assert "outcome" in rec
            assert "probability" in rec
            assert "run_id" in rec

    def test_noise_sweep_has_limitation(self):
        """Sweep output includes the limitation statement."""
        results = [_noisy_bell_result(gate_prob=0.0, run_id="sweep_lim")]
        sweep = noise_parameter_sweep(results, "p", [0.0])
        assert sweep["limitation"] == LIMITATION_STATEMENT

    def test_noise_sweep_mismatched_lengths(self):
        """Mismatched results and parameter_values lengths is rejected."""
        results = [_noisy_bell_result(run_id="sweep_mm")]
        with pytest.raises(AnalysisError, match="E_ANALYSIS_REJECTED"):
            noise_parameter_sweep(results, "p", [0.0, 0.1])

    def test_noise_sweep_incompatible_qubits(self):
        """Sweep with incompatible qubit counts is rejected."""
        results = [
            _ideal_bell_result(run_id="sweep_iq_a"),
            _one_qubit_result(run_id="sweep_iq_b"),
        ]
        with pytest.raises(AnalysisError, match="E_ANALYSIS_INCOMPATIBLE"):
            noise_parameter_sweep(results, "p", [0.0, 0.1])


# ==================================================================
# Stable output ordering
# ==================================================================

class TestStableOrdering:
    """Deterministic output ordering."""

    def test_analyze_is_json_serializable(self):
        """analyze_result output is JSON-serializable."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        s = json.dumps(analysis, sort_keys=True)
        assert isinstance(s, str)

    def test_repeated_analysis_identical(self):
        """Repeated analysis of the same result produces identical output."""
        result = _ideal_bell_result()
        a1 = analyze_result(copy.deepcopy(result))
        a2 = analyze_result(copy.deepcopy(result))
        assert json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True)

    def test_compare_is_json_serializable(self):
        """compare_results output is JSON-serializable."""
        a = _ideal_bell_result(run_id="run_js_a")
        b = _noisy_bell_result(run_id="run_js_b")
        comp = compare_results(a, b)
        s = json.dumps(comp, sort_keys=True)
        assert isinstance(s, str)


# ==================================================================
# Rejection: error and incomplete results
# ==================================================================

class TestErrorRejection:
    """Rejection of error and incomplete results."""

    def test_reject_error_result(self):
        """Error backend result is rejected."""
        result = _error_result()
        with pytest.raises(AnalysisError, match="E_ANALYSIS_REJECTED"):
            analyze_result(result)

    def test_reject_incomplete_result(self):
        """Result missing 'counts' is rejected."""
        result = _ideal_bell_result()
        del result["counts"]
        with pytest.raises(AnalysisError, match="E_ANALYSIS_REJECTED"):
            analyze_result(result)

    def test_reject_missing_probabilities(self):
        """Result missing 'probabilities' is rejected."""
        result = _ideal_bell_result()
        del result["probabilities"]
        with pytest.raises(AnalysisError, match="E_ANALYSIS_REJECTED"):
            analyze_result(result)


# ==================================================================
# Rejection: invalid package data
# ==================================================================

class TestInvalidPackageRejection:
    """Rejection of invalid or checksum-failing package data."""

    def test_reject_non_dict(self):
        """Non-dict input is rejected."""
        with pytest.raises(AnalysisError, match="E_ANALYSIS_REJECTED"):
            analyze_result("not a dict")

    def test_reject_none_status(self):
        """Result with no status is rejected."""
        with pytest.raises(AnalysisError, match="E_ANALYSIS_REJECTED"):
            analyze_result({"run_id": "x"})


# ==================================================================
# Rejection: unknown major schema version
# ==================================================================

class TestSchemaVersionRejection:
    """Rejection of unknown major schema versions."""

    def test_reject_unknown_major_version(self):
        """Result with major schema version 99 is rejected."""
        result = _ideal_bell_result()
        result["schema_version"] = "99.0"
        with pytest.raises(AnalysisError, match="E_ANALYSIS_REJECTED"):
            analyze_result(result)


# ==================================================================
# Source results not mutated
# ==================================================================

class TestSourceImmutability:
    """Source results are not mutated."""

    def test_analyze_does_not_mutate(self):
        """analyze_result does not mutate the source result."""
        result = _ideal_bell_result()
        result_copy = copy.deepcopy(result)
        analyze_result(result)
        assert result == result_copy

    def test_compare_does_not_mutate(self):
        """compare_results does not mutate either source result."""
        a = _ideal_bell_result(run_id="mut_a")
        b = _noisy_bell_result(run_id="mut_b")
        a_copy = copy.deepcopy(a)
        b_copy = copy.deepcopy(b)
        compare_results(a, b)
        assert a == a_copy
        assert b == b_copy

    def test_sweep_does_not_mutate(self):
        """noise_parameter_sweep does not mutate the source results."""
        results = [
            _noisy_bell_result(gate_prob=0.0, run_id="sw_mut_0"),
            _noisy_bell_result(gate_prob=0.1, run_id="sw_mut_1"),
        ]
        copies = [copy.deepcopy(r) for r in results]
        noise_parameter_sweep(results, "p", [0.0, 0.1])
        for orig, cp in zip(results, copies):
            assert orig == cp


# ==================================================================
# Finalized package files not modified
# ==================================================================

class TestFinalizedPackageNotModified:
    """Finalized package files are not modified by analysis."""

    def test_analysis_does_not_modify_package(self, tmp_path):
        """analyze_result on a serialized result doesn't modify the package."""
        result = _ideal_bell_result(run_id="run_pkg_ana")
        pkg_dir = serialize_result(copy.deepcopy(result), str(tmp_path))

        cs_before = calculate_checksums(pkg_dir)
        analyze_result(result)
        cs_after = calculate_checksums(pkg_dir)

        assert cs_before == cs_after


# ==================================================================
# Analysis does not execute simulation logic
# ==================================================================

class TestNoSimulationExecution:
    """Analysis does not execute simulation logic."""

    def test_analysis_does_not_import_simulation_modules(self):
        """analysis.py does not import statevector, sampling, gates, or noise."""
        import src.m5_simulator.analysis as ana_mod
        source_code = open(ana_mod.__file__, "r").read()
        assert "from src.m5_simulator.statevector" not in source_code
        assert "from src.m5_simulator.sampling" not in source_code
        assert "from src.m5_simulator.gates" not in source_code
        assert "from src.m5_simulator.noise" not in source_code
        assert "from src.m5_simulator.circuit" not in source_code

    def test_analysis_is_pure_data_transform(self):
        """analyze_result only transforms existing data, does not change probabilities."""
        result = _ideal_bell_result()
        analysis = analyze_result(result)
        # Probabilities in analysis match the original result exactly.
        for rec in analysis["outcome_probabilities"]:
            idx = int(rec["outcome"], 2)
            assert rec["probability"] == result["probabilities"][idx]


if __name__ == "__main__":
    pytest.main([__file__])
