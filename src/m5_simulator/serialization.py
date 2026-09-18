"""
Deterministic result serialization and SHA-256 checksums (Step 8).

This module serializes a completed backend result into an immutable M5
run package on disk.  It does **not** recalculate gates, statevectors,
noise, or sampling — it only writes, validates, and verifies packages
produced by the backend.

Package layout
--------------
::

    <output_dir>/<run_id>/
    ├── run.json
    ├── circuit.json
    ├── configuration.json
    ├── result.json
    ├── histogram.json
    ├── analysis.json
    └── checksum.sha256

Design decisions
----------------
* Deterministic JSON: sorted keys, 2-space indent, UTF-8, one trailing
  newline, ``ensure_ascii=False``.
* SHA-256 is the single, documented checksum algorithm.
* Files are staged in a temporary directory under *output_dir* then
  atomically renamed to the final run directory.
* An existing run directory is never overwritten.
* Finalized packages are treated as immutable: verification rejects any
  file whose SHA-256 no longer matches ``checksum.sha256``.
* No external services, API keys, or network calls.
"""

import copy
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.m5_simulator.version import __version__ as SIMULATOR_VERSION

# The files that make up a complete run package, in canonical order.
PACKAGE_FILES: List[str] = [
    "run.json",
    "circuit.json",
    "configuration.json",
    "result.json",
    "histogram.json",
    "analysis.json",
]

# The checksum manifest file (not itself checksummed).
CHECKSUM_FILE = "checksum.sha256"

# All files expected in a package directory.
ALL_PACKAGE_FILES: List[str] = PACKAGE_FILES + [CHECKSUM_FILE]

# Supported major schema versions.
_SUPPORTED_MAJOR_VERSIONS = {"1"}

# Result label constant.
RESULT_LABEL = "SIMULATION"


# ======================================================================
# Exceptions
# ======================================================================

class SerializationError(Exception):
    """Raised when serialization or verification fails."""

    def __init__(self, message: str, code: str = "E_SERIALIZATION_ERROR"):
        self.code = code
        super().__init__(f"{message} ({code})")


# ======================================================================
# Deterministic JSON
# ======================================================================

def _deterministic_json(data: Any) -> str:
    """
    Serialize *data* to a deterministic JSON string.

    * Sorted keys
    * 2-space indent
    * No trailing whitespace on lines
    * Exactly one trailing newline
    * ``ensure_ascii=False`` for readable UTF-8
    """
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _write_json(path: str, data: Any) -> None:
    """Write *data* as deterministic JSON to *path* (UTF-8)."""
    content = _deterministic_json(data)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ======================================================================
# SHA-256 helpers
# ======================================================================

def _sha256_file(path: str) -> str:
    """Return the hex SHA-256 digest of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def calculate_checksums(package_dir: str) -> Dict[str, str]:
    """
    Calculate SHA-256 checksums for all package files in *package_dir*.

    Returns a dict mapping filename → hex digest.  ``checksum.sha256``
    itself is excluded.
    """
    checksums: Dict[str, str] = {}
    for fname in PACKAGE_FILES:
        fpath = os.path.join(package_dir, fname)
        if os.path.isfile(fpath):
            checksums[fname] = _sha256_file(fpath)
    return checksums


def _write_checksum_file(package_dir: str, checksums: Dict[str, str]) -> None:
    """Write ``checksum.sha256`` in the standard ``sha256sum`` format."""
    lines = []
    for fname in PACKAGE_FILES:
        if fname in checksums:
            lines.append(f"{checksums[fname]}  {fname}")
    content = "\n".join(lines) + "\n"
    path = os.path.join(package_dir, CHECKSUM_FILE)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ======================================================================
# Validation helpers
# ======================================================================

def _validate_backend_result(result: Dict[str, Any]) -> None:
    """
    Validate that *result* is a completed backend result suitable for
    serialization.  Rejects error results and incomplete results.
    """
    if not isinstance(result, dict):
        raise SerializationError("Backend result must be a dict.")

    status = result.get("status")
    if status == "error":
        raise SerializationError(
            "Cannot serialize an error result.",
            code="E_SERIALIZATION_REJECTED",
        )
    if status != "completed":
        raise SerializationError(
            f"Backend result has unexpected status '{status}'.",
            code="E_SERIALIZATION_REJECTED",
        )

    # Check required fields.
    required_fields = [
        "run_id", "simulator_version", "schema_version", "result_label",
        "num_qubits", "shots", "mode", "circuit", "probabilities",
        "counts", "noise",
    ]
    for field in required_fields:
        if field not in result:
            raise SerializationError(
                f"Backend result is missing required field '{field}'.",
                code="E_SERIALIZATION_REJECTED",
            )

    if result.get("result_label") != RESULT_LABEL:
        raise SerializationError(
            f"result_label must be '{RESULT_LABEL}', "
            f"got '{result.get('result_label')}'.",
            code="E_SERIALIZATION_REJECTED",
        )

    # Validate major schema version.
    schema_version = result.get("schema_version", "")
    major = schema_version.split(".")[0] if schema_version else ""
    if major not in _SUPPORTED_MAJOR_VERSIONS:
        raise SerializationError(
            f"Unknown major schema version '{schema_version}'.",
            code="E_SERIALIZATION_REJECTED",
        )


def _validate_schema_version(version_str: str) -> None:
    """Reject unknown major schema versions."""
    major = version_str.split(".")[0] if version_str else ""
    if major not in _SUPPORTED_MAJOR_VERSIONS:
        raise SerializationError(
            f"Unknown major schema version '{version_str}'.",
            code="E_SERIALIZATION_REJECTED",
        )


# ======================================================================
# Package file builders
# ======================================================================

def _build_run_json(
    result: Dict[str, Any],
    checksums: Dict[str, str],
    start_ts: str,
    end_ts: str,
) -> Dict[str, Any]:
    """Build the ``run.json`` envelope."""
    return {
        "schema_version": result["schema_version"],
        "run_id": result["run_id"],
        "request_id": result.get("request_id"),
        "simulator_version": result["simulator_version"],
        "status": result["status"],
        "result_label": RESULT_LABEL,
        "timestamps": {
            "start": start_ts,
            "end": end_ts,
        },
        "num_qubits": result["num_qubits"],
        "shots": result["shots"],
        "seed": result.get("seed"),
        "mode": result["mode"],
        "noise": result["noise"],
        "warnings": result.get("warnings", []),
        "package_files": list(ALL_PACKAGE_FILES),
        "checksums": checksums,
    }


def _build_circuit_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build ``circuit.json`` from the backend circuit data."""
    return copy.deepcopy(result["circuit"])


def _build_configuration_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build ``configuration.json`` with the complete execution config."""
    return {
        "schema_version": result["schema_version"],
        "mode": result["mode"],
        "shots": result["shots"],
        "seed": result.get("seed"),
        "noise": result["noise"],
        "num_qubits": result["num_qubits"],
        "simulator_version": result["simulator_version"],
    }


def _build_result_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build ``result.json`` with probabilities, counts, etc."""
    return {
        "schema_version": result["schema_version"],
        "simulator_version": result["simulator_version"],
        "result_label": RESULT_LABEL,
        "status": result["status"],
        "run_id": result["run_id"],
        "mode": result["mode"],
        "seed": result.get("seed"),
        "num_qubits": result["num_qubits"],
        "shots": result["shots"],
        "probabilities": list(result["probabilities"]),
        "counts": dict(sorted(result["counts"].items())),
    }


def _build_histogram_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build ``histogram.json`` with deterministic sorted outcome keys."""
    sorted_counts = dict(sorted(result["counts"].items()))
    return {
        "schema_version": result["schema_version"],
        "run_id": result["run_id"],
        "num_qubits": result["num_qubits"],
        "shots": result["shots"],
        "counts": sorted_counts,
    }


def _build_analysis_json(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build ``analysis.json`` with basic package-level facts.

    Advanced analysis is deferred to a later step.
    """
    counts = result["counts"]
    counts_sum = sum(counts.values())
    return {
        "schema_version": result["schema_version"],
        "run_id": result["run_id"],
        "counts_sum": counts_sum,
        "nonzero_outcomes": len(counts),
        "shots": result["shots"],
        "reproducibility": "seeded" if result.get("seed") is not None else "unseeded",
        "mode": result["mode"],
    }


# ======================================================================
# Public API: serialize
# ======================================================================

def serialize_result(
    result: Dict[str, Any],
    output_dir: str,
    *,
    start_timestamp: Optional[str] = None,
    end_timestamp: Optional[str] = None,
) -> str:
    """
    Serialize a completed backend result into an M5 run package.

    Parameters
    ----------
    result : dict
        A completed backend result (``status == "completed"``).
    output_dir : str
        Parent directory under which ``<run_id>/`` will be created.
    start_timestamp : str or None
        ISO 8601 UTC start time (generated if absent).
    end_timestamp : str or None
        ISO 8601 UTC end time (generated if absent).

    Returns
    -------
    str
        Absolute path to the finalized package directory.

    Raises
    ------
    SerializationError
        On invalid input, existing directory, or staging failure.
    """
    # Deep-copy so we never mutate the caller's result.
    result = copy.deepcopy(result)

    # ----- Validate the backend result --------------------------------
    _validate_backend_result(result)

    run_id = result["run_id"]
    package_dir = os.path.join(output_dir, run_id)

    # ----- Reject existing run directory ------------------------------
    if os.path.exists(package_dir):
        raise SerializationError(
            f"Run directory already exists: {package_dir}",
            code="E_SERIALIZATION_REJECTED",
        )

    # ----- Timestamps -------------------------------------------------
    now = datetime.now(timezone.utc).isoformat()
    start_ts = start_timestamp or now
    end_ts = end_timestamp or now

    # ----- Stage in a temporary directory -----------------------------
    staging_dir = None
    try:
        staging_dir = tempfile.mkdtemp(
            prefix=f".m5_staging_{run_id}_",
            dir=output_dir,
        )

        # Build and write data files (everything except run.json and checksum).
        circuit_data = _build_circuit_json(result)
        _write_json(os.path.join(staging_dir, "circuit.json"), circuit_data)

        config_data = _build_configuration_json(result)
        _write_json(os.path.join(staging_dir, "configuration.json"), config_data)

        result_data = _build_result_json(result)
        _write_json(os.path.join(staging_dir, "result.json"), result_data)

        histogram_data = _build_histogram_json(result)
        _write_json(os.path.join(staging_dir, "histogram.json"), histogram_data)

        analysis_data = _build_analysis_json(result)
        _write_json(os.path.join(staging_dir, "analysis.json"), analysis_data)

        # Write a placeholder run.json (checksums will be updated).
        placeholder_checksums: Dict[str, str] = {}
        run_data = _build_run_json(result, placeholder_checksums, start_ts, end_ts)
        _write_json(os.path.join(staging_dir, "run.json"), run_data)

        # Calculate checksums over all package files.
        checksums = calculate_checksums(staging_dir)

        # Rewrite run.json with the real checksums.
        run_data["checksums"] = checksums
        _write_json(os.path.join(staging_dir, "run.json"), run_data)

        # Recalculate run.json checksum now that it contains the other checksums.
        checksums["run.json"] = _sha256_file(
            os.path.join(staging_dir, "run.json")
        )

        # Write the checksum manifest.
        _write_checksum_file(staging_dir, checksums)

        # ----- Validate the staged package ----------------------------
        _validate_package_files(staging_dir)

        # ----- Atomically move staging → final ------------------------
        os.rename(staging_dir, package_dir)
        staging_dir = None  # prevent cleanup

        return os.path.abspath(package_dir)

    finally:
        # Clean up staging on failure.
        if staging_dir and os.path.exists(staging_dir):
            shutil.rmtree(staging_dir, ignore_errors=True)


# ======================================================================
# Public API: validate
# ======================================================================

def _validate_package_files(package_dir: str) -> None:
    """
    Validate that *package_dir* contains all required files.

    Raises SerializationError on missing files.
    """
    for fname in ALL_PACKAGE_FILES:
        fpath = os.path.join(package_dir, fname)
        if not os.path.isfile(fpath):
            raise SerializationError(
                f"Missing required package file: {fname}",
                code="E_PACKAGE_INVALID",
            )


def validate_package(package_dir: str) -> Dict[str, Any]:
    """
    Validate a finalized run package.

    Checks:
    * All required files are present.
    * ``run.json`` is readable and has a supported schema version.
    * ``checksum.sha256`` matches all package files.

    Returns the parsed ``run.json`` data on success.

    Raises SerializationError on any validation failure.
    """
    # Check file presence.
    _validate_package_files(package_dir)

    # Load and validate run.json.
    run_data = _load_json(os.path.join(package_dir, "run.json"))
    sv = run_data.get("schema_version", "")
    _validate_schema_version(sv)

    # Verify checksums.
    verify_checksums(package_dir)

    return run_data


# ======================================================================
# Public API: checksums
# ======================================================================

def verify_checksums(package_dir: str) -> None:
    """
    Verify that all package files match the checksums in
    ``checksum.sha256``.

    Raises SerializationError on any mismatch or missing file.
    """
    checksum_path = os.path.join(package_dir, CHECKSUM_FILE)
    if not os.path.isfile(checksum_path):
        raise SerializationError(
            f"Missing {CHECKSUM_FILE} in package.",
            code="E_CHECKSUM_MISMATCH",
        )

    expected = _parse_checksum_file(checksum_path)

    for fname, expected_hash in expected.items():
        fpath = os.path.join(package_dir, fname)
        if not os.path.isfile(fpath):
            raise SerializationError(
                f"Checksum references missing file: {fname}",
                code="E_CHECKSUM_MISMATCH",
            )
        actual_hash = _sha256_file(fpath)
        if actual_hash != expected_hash:
            raise SerializationError(
                f"Checksum mismatch for {fname}: "
                f"expected {expected_hash}, got {actual_hash}",
                code="E_CHECKSUM_MISMATCH",
            )


def _parse_checksum_file(path: str) -> Dict[str, str]:
    """Parse a ``sha256sum``-format checksum file."""
    checksums: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("  ", 1)
            if len(parts) == 2:
                checksums[parts[1]] = parts[0]
    return checksums


# ======================================================================
# Public API: load
# ======================================================================

def load_package(package_dir: str) -> Dict[str, Any]:
    """
    Load a finalized run package without modifying it.

    Returns a dict with all parsed package files keyed by filename
    (without extension), plus the ``"checksums"`` dict.

    Validates the package first — raises SerializationError on failure.
    """
    # Validate (includes checksum verification).
    validate_package(package_dir)

    package: Dict[str, Any] = {}
    for fname in PACKAGE_FILES:
        key = fname.replace(".json", "")
        package[key] = _load_json(os.path.join(package_dir, fname))

    package["checksums"] = _parse_checksum_file(
        os.path.join(package_dir, CHECKSUM_FILE)
    )

    return package


def _load_json(path: str) -> Any:
    """Load and parse a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
