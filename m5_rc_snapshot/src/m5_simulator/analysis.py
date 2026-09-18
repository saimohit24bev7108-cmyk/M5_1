"""
Basic analysis outputs for the M5 simulator (Step 9).

This module provides analysis functions for completed M5 backend results
or finalized M5 result packages.  It does **not** rerun circuits, mutate
source results, or execute simulation logic.

Capabilities
------------
* **``analyze_result``** — Extract package-level facts, probability-vs-outcome
  records, mode, noise configuration, and reproducibility status from a
  single completed backend result.
* **``compare_results``** — Compare two compatible results (same circuit,
  same qubit count) with clearly recorded modes.
* **``noise_parameter_sweep``** — Generate data suitable for an
  outcome-probability-vs-noise-parameter graph by analyzing a list of
  pre-computed results produced at different noise parameter values.

Design decisions
----------------
* All outputs are JSON-compatible dicts with deterministic key ordering.
* Source results are **never mutated**; analysis works on deep copies.
* Error, incomplete, or malformed results are explicitly rejected.
* Every analysis output includes the limitation statement:
  ``"This is a simulated result, not a physical measurement."``
* No external dependencies, API keys, network calls, or cloud services.
"""

import copy
import math
from typing import Any, Dict, List, Optional

# Module version.
ANALYSIS_VERSION = "1.0"

# Limitation statement included in every analysis output.
LIMITATION_STATEMENT = "This is a simulated result, not a physical measurement."

# Result label that every valid result must carry.
RESULT_LABEL = "SIMULATION"

# Supported major schema versions.
_SUPPORTED_MAJOR_VERSIONS = {"1"}


# ======================================================================
# Exceptions
# ======================================================================

class AnalysisError(Exception):
    """Raised when analysis input is invalid or incompatible."""

    def __init__(self, message: str, code: str = "E_ANALYSIS_ERROR"):
        self.code = code
        super().__init__(f"{message} ({code})")


# ======================================================================
# Input validation
# ======================================================================

def _validate_result(result: Dict[str, Any]) -> None:
    """
    Validate that *result* is a completed backend result suitable for
    analysis.

    Raises AnalysisError for error, incomplete, or malformed results.
    """
    if not isinstance(result, dict):
        raise AnalysisError(
            "Result must be a dict.",
            code="E_ANALYSIS_REJECTED",
        )

    status = result.get("status")
    if status == "error":
        raise AnalysisError(
            "Cannot analyze an error result.",
            code="E_ANALYSIS_REJECTED",
        )
    if status != "completed":
        raise AnalysisError(
            f"Result has unexpected status '{status}'.",
            code="E_ANALYSIS_REJECTED",
        )

    # Check required fields.
    required = [
        "run_id", "simulator_version", "schema_version", "result_label",
        "num_qubits", "shots", "mode", "probabilities", "counts",
    ]
    for field in required:
        if field not in result:
            raise AnalysisError(
                f"Result is missing required field '{field}'.",
                code="E_ANALYSIS_REJECTED",
            )

    if result.get("result_label") != RESULT_LABEL:
        raise AnalysisError(
            f"result_label must be '{RESULT_LABEL}', "
            f"got '{result.get('result_label')}'.",
            code="E_ANALYSIS_REJECTED",
        )

    # Validate major schema version.
    schema_version = result.get("schema_version", "")
    major = schema_version.split(".")[0] if schema_version else ""
    if major not in _SUPPORTED_MAJOR_VERSIONS:
        raise AnalysisError(
            f"Unknown major schema version '{schema_version}'.",
            code="E_ANALYSIS_REJECTED",
        )


# ======================================================================
# Public API: analyze_result
# ======================================================================

def analyze_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a completed backend result and return package-level facts.

    Parameters
    ----------
    result : dict
        A completed backend result (``status == "completed"``).

    Returns
    -------
    dict
        A JSON-compatible analysis dict containing:

        * ``analysis_version`` — version of this analysis implementation
        * ``result_label`` — always ``"SIMULATION"``
        * ``limitation`` — limitation statement
        * ``run_id``
        * ``schema_version``
        * ``simulator_version``
        * ``num_qubits``
        * ``shots``
        * ``counts_sum`` — sum of all histogram counts
        * ``nonzero_outcomes`` — number of distinct outcomes with count > 0
        * ``mode`` — ``"ideal"`` or ``"noisy"``
        * ``noise`` — complete noise configuration dict
        * ``seed`` — the seed value or ``None``
        * ``seeded`` — boolean
        * ``reproducibility`` — ``"seeded"`` or ``"unseeded"``
        * ``outcome_probabilities`` — list of ``{outcome, probability}`` records
          in stable (sorted) outcome order

    Raises
    ------
    AnalysisError
        On invalid, error, or incomplete results.
    """
    _validate_result(result)

    # Deep-copy so we never mutate the source.
    r = copy.deepcopy(result)

    counts = r["counts"]
    probabilities = r["probabilities"]
    num_qubits = r["num_qubits"]
    shots = r["shots"]
    seed = r.get("seed")

    counts_sum = sum(counts.values())
    nonzero_outcomes = len(counts)

    # Build probability-vs-outcome records in stable sorted order.
    num_states = 2 ** num_qubits
    outcome_probabilities = []
    for idx in range(num_states):
        outcome = format(idx, f"0{num_qubits}b")
        prob = probabilities[idx] if idx < len(probabilities) else 0.0
        outcome_probabilities.append({
            "outcome": outcome,
            "probability": prob,
        })

    return {
        "analysis_version": ANALYSIS_VERSION,
        "result_label": RESULT_LABEL,
        "limitation": LIMITATION_STATEMENT,
        "run_id": r["run_id"],
        "schema_version": r["schema_version"],
        "simulator_version": r["simulator_version"],
        "num_qubits": num_qubits,
        "shots": shots,
        "counts_sum": counts_sum,
        "nonzero_outcomes": nonzero_outcomes,
        "mode": r["mode"],
        "noise": r.get("noise", {}),
        "seed": seed,
        "seeded": seed is not None,
        "reproducibility": "seeded" if seed is not None else "unseeded",
        "outcome_probabilities": outcome_probabilities,
    }


# ======================================================================
# Public API: compare_results
# ======================================================================

def compare_results(
    result_a: Dict[str, Any],
    result_b: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare two compatible completed results.

    Compatibility requires:
    * Same ``num_qubits``.
    * Same circuit (by value).

    Parameters
    ----------
    result_a, result_b : dict
        Completed backend results.

    Returns
    -------
    dict
        A JSON-compatible comparison dict containing per-outcome deltas,
        modes, and a limitation statement.

    Raises
    ------
    AnalysisError
        On incompatible circuits, qubit counts, or invalid results.
    """
    _validate_result(result_a)
    _validate_result(result_b)

    a = copy.deepcopy(result_a)
    b = copy.deepcopy(result_b)

    # Check compatibility: qubit count.
    if a["num_qubits"] != b["num_qubits"]:
        raise AnalysisError(
            f"Incompatible qubit counts: {a['num_qubits']} vs {b['num_qubits']}.",
            code="E_ANALYSIS_INCOMPATIBLE",
        )

    # Check compatibility: circuit.
    circuit_a = a.get("circuit", {})
    circuit_b = b.get("circuit", {})
    if circuit_a != circuit_b:
        raise AnalysisError(
            "Incompatible circuits: circuits must be identical for comparison.",
            code="E_ANALYSIS_INCOMPATIBLE",
        )

    num_qubits = a["num_qubits"]
    num_states = 2 ** num_qubits

    # Build per-outcome comparison records.
    outcome_comparisons = []
    for idx in range(num_states):
        outcome = format(idx, f"0{num_qubits}b")
        prob_a = a["probabilities"][idx] if idx < len(a["probabilities"]) else 0.0
        prob_b = b["probabilities"][idx] if idx < len(b["probabilities"]) else 0.0
        count_a = a["counts"].get(outcome, 0)
        count_b = b["counts"].get(outcome, 0)
        outcome_comparisons.append({
            "outcome": outcome,
            "probability_a": prob_a,
            "probability_b": prob_b,
            "probability_delta": prob_b - prob_a,
            "count_a": count_a,
            "count_b": count_b,
            "count_delta": count_b - count_a,
        })

    return {
        "analysis_version": ANALYSIS_VERSION,
        "result_label": RESULT_LABEL,
        "limitation": LIMITATION_STATEMENT,
        "comparison_type": "result_pair",
        "run_id_a": a["run_id"],
        "run_id_b": b["run_id"],
        "num_qubits": num_qubits,
        "mode_a": a["mode"],
        "mode_b": b["mode"],
        "shots_a": a["shots"],
        "shots_b": b["shots"],
        "outcome_comparisons": outcome_comparisons,
    }


# ======================================================================
# Public API: noise_parameter_sweep
# ======================================================================

def noise_parameter_sweep(
    results: List[Dict[str, Any]],
    parameter_name: str,
    parameter_values: List[float],
) -> Dict[str, Any]:
    """
    Generate data for an outcome-probability-vs-noise-parameter graph.

    Each entry in *results* corresponds to a pre-computed simulation at the
    noise parameter value given by the matching entry in *parameter_values*.

    Parameters
    ----------
    results : list of dict
        Completed backend results, one per parameter value.
    parameter_name : str
        Name of the varied noise parameter (e.g. ``"gate_noise.probability"``).
    parameter_values : list of float
        The parameter value used for each result.

    Returns
    -------
    dict
        A JSON-compatible sweep dict containing:

        * ``parameter_name``
        * ``sweep_records`` — one record per (parameter_value, outcome) pair

    Raises
    ------
    AnalysisError
        On invalid results, incompatible qubit counts, or length mismatches.
    """
    if len(results) != len(parameter_values):
        raise AnalysisError(
            f"results ({len(results)}) and parameter_values "
            f"({len(parameter_values)}) must have the same length.",
            code="E_ANALYSIS_REJECTED",
        )

    if not results:
        raise AnalysisError(
            "At least one result is required for a sweep.",
            code="E_ANALYSIS_REJECTED",
        )

    # Validate all results.
    for i, r in enumerate(results):
        _validate_result(r)

    # Check qubit compatibility.
    ref_qubits = results[0]["num_qubits"]
    for i, r in enumerate(results):
        if r["num_qubits"] != ref_qubits:
            raise AnalysisError(
                f"Incompatible qubit counts at index {i}: "
                f"{r['num_qubits']} vs {ref_qubits}.",
                code="E_ANALYSIS_INCOMPATIBLE",
            )

    num_states = 2 ** ref_qubits

    # Build sweep records.
    sweep_records = []
    for r, pval in zip(results, parameter_values):
        r = copy.deepcopy(r)
        for idx in range(num_states):
            outcome = format(idx, f"0{ref_qubits}b")
            prob = r["probabilities"][idx] if idx < len(r["probabilities"]) else 0.0
            sweep_records.append({
                "parameter_name": parameter_name,
                "parameter_value": pval,
                "outcome": outcome,
                "probability": prob,
                "run_id": r["run_id"],
            })

    return {
        "analysis_version": ANALYSIS_VERSION,
        "result_label": RESULT_LABEL,
        "limitation": LIMITATION_STATEMENT,
        "comparison_type": "noise_parameter_sweep",
        "parameter_name": parameter_name,
        "num_qubits": ref_qubits,
        "num_points": len(results),
        "sweep_records": sweep_records,
    }
