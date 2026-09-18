"""
Finite-shot sampling engine for the M5 simulator (Step 5).

This module is strictly separated from statevector evolution.  It accepts
a validated probability distribution (as produced by ``Statevector.get_probabilities()``)
and draws finite-shot samples from it, returning a histogram of outcome counts
keyed by big-endian binary strings.

Design decisions
----------------
* **Zero-count outcomes are omitted** from the returned histogram.  The M5
  result schema allows ``"minimum": 0`` for histogram values, but the
  established test fixture (``{"00": 512, "11": 512}``) omits zero-count
  entries.  Omitting them keeps histograms compact and consistent with that
  convention.
* **Unseeded mode** is selected by passing ``seed=None``.  In this mode a
  fresh, non-deterministic ``numpy.random.Generator`` is used, so results
  will vary between calls.
* The input probability list is **never mutated**.
* Invalid distributions are **rejected, never silently normalised**.
"""

import math
from typing import Dict, List, Optional

import numpy as np

# Numerical tolerance – matches the statevector engine's constant.
TOLERANCE = 1e-10


class SamplingError(Exception):
    """Raised when a sampling request is invalid."""
    pass


# ======================================================================
# Probability validation
# ======================================================================

def _validate_probabilities(probabilities: List[float]) -> None:
    """
    Validate that *probabilities* is a well-formed distribution.

    Checks (in order):
        1. Length is a positive power of two (2^n for n in [1, 8]).
        2. All values are finite.
        3. No value is negative beyond numerical tolerance.
        4. Total probability equals 1 within numerical tolerance.

    Raises:
        SamplingError: On any violation.
    """
    # --- length ---
    length = len(probabilities)
    if length < 2 or (length & (length - 1)) != 0:
        raise SamplingError(
            f"Probability array length must be a power of two >= 2, "
            f"got {length}."
        )
    # num_qubits would be log2(length); verify it is in [1, 8]
    num_qubits = int(math.log2(length))
    if num_qubits < 1 or num_qubits > 8 or (1 << num_qubits) != length:
        raise SamplingError(
            f"Probability array length {length} does not correspond to "
            f"1–8 qubits."
        )

    arr = np.asarray(probabilities, dtype=np.float64)

    # --- finiteness ---
    if not np.all(np.isfinite(arr)):
        raise SamplingError(
            "Probability array contains non-finite values."
        )

    # --- non-negativity ---
    if np.any(arr < -TOLERANCE):
        raise SamplingError(
            f"Probability array contains negative values "
            f"(min = {float(np.min(arr))})."
        )

    # --- normalisation ---
    total = float(np.sum(arr))
    if not math.isclose(total, 1.0, abs_tol=TOLERANCE):
        raise SamplingError(
            f"Probabilities do not sum to 1 (sum = {total})."
        )


# ======================================================================
# Public API
# ======================================================================

def sample(
    probabilities: List[float],
    shots: int,
    seed: Optional[int] = None,
) -> Dict[str, int]:
    """
    Draw *shots* samples from *probabilities* and return a histogram.

    Parameters
    ----------
    probabilities : list of float
        Born-rule probability distribution in big-endian display order, as
        returned by ``Statevector.get_probabilities()``.  Must be a valid
        distribution (see ``_validate_probabilities``).
    shots : int
        Number of measurement shots.  Must be >= 1.
    seed : int or None
        If an ``int``, the sampling is deterministic: the same
        (probabilities, shots, seed) triple always yields the same
        histogram.  If ``None``, a non-deterministic generator is used.

    Returns
    -------
    dict[str, int]
        Histogram mapping big-endian binary-string outcome keys to their
        counts.  Zero-count outcomes are **omitted**.  The total of all
        values equals *shots* exactly.  Keys are sorted in ascending
        lexicographic (= numerical) order for stable output.

    Raises
    ------
    SamplingError
        If *shots* is not a positive integer, or *probabilities* is
        invalid (non-finite, negative, wrong length, or un-normalised).
    """
    # --- validate shots ---
    if not isinstance(shots, int) or shots < 1:
        raise SamplingError(
            f"shots must be a positive integer, got {shots!r}."
        )

    # --- validate probabilities (before touching any state) ---
    _validate_probabilities(probabilities)

    # --- derive qubit count from the distribution length ---
    num_qubits = int(math.log2(len(probabilities)))

    # --- build a clean probability array (do NOT mutate the caller's list) ---
    probs = np.array(probabilities, dtype=np.float64)

    # Clamp tiny negative values that are within tolerance to zero,
    # then re-normalise so numpy's multinomial is happy.  This is NOT
    # "silent normalisation of an invalid distribution" — the distribution
    # already passed validation; we are only compensating for float64
    # rounding so that numpy.random does not raise on sum != 1.0 exactly.
    probs = np.maximum(probs, 0.0)
    probs_sum = probs.sum()
    if probs_sum != 1.0:
        probs = probs / probs_sum

    # --- set up RNG ---
    rng = np.random.default_rng(seed)

    # --- sample ---
    counts_array = rng.multinomial(shots, probs)

    # --- build histogram (omit zero-count outcomes, sorted keys) ---
    histogram: Dict[str, int] = {}
    for idx, count in enumerate(counts_array):
        if count > 0:
            label = format(idx, f"0{num_qubits}b")
            histogram[label] = int(count)

    # Return with sorted keys for deterministic ordering.
    return dict(sorted(histogram.items()))
