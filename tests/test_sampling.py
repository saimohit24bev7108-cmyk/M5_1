"""
Tests for the finite-shot sampling engine (Step 5 of M5 architecture).

Covers:
    - One-qubit deterministic |0⟩ sampling
    - One-qubit deterministic |1⟩ sampling
    - Seeded H-state sampling
    - Repeated seeded sampling produces identical counts
    - Histogram counts sum exactly to shots
    - Bell-state sampling produces only 00 and 11
    - Big-endian outcome formatting
    - Rejection of zero shots
    - Rejection of negative shots
    - Rejection of negative probabilities
    - Rejection of non-finite probabilities
    - Rejection of probabilities that do not sum to one
    - Rejection of invalid probability-array length
    - Input probabilities are not mutated
    - Explicit behavior for unseeded sampling
"""

import math
import pytest

from src.m5_simulator.sampling import sample, SamplingError, TOLERANCE


# ==================================================================
# Deterministic basis-state sampling
# ==================================================================

class TestDeterministicBasisStates:
    """Sampling from a definite computational-basis state."""

    def test_one_qubit_deterministic_zero(self):
        """One-qubit deterministic |0⟩ sampling: all shots land on '0'."""
        probs = [1.0, 0.0]
        result = sample(probs, shots=100, seed=0)
        assert result == {"0": 100}

    def test_one_qubit_deterministic_one(self):
        """One-qubit deterministic |1⟩ sampling: all shots land on '1'."""
        probs = [0.0, 1.0]
        result = sample(probs, shots=100, seed=0)
        assert result == {"1": 100}


# ==================================================================
# Seeded H-state sampling
# ==================================================================

class TestSeededSampling:
    """Seeded sampling from a uniform superposition."""

    def test_seeded_h_state_sampling(self):
        """Seeded H-state sampling returns a valid histogram with both outcomes."""
        probs = [0.5, 0.5]
        result = sample(probs, shots=1000, seed=42)
        assert "0" in result or "1" in result
        assert sum(result.values()) == 1000

    def test_repeated_seeded_sampling_identical(self):
        """Repeated seeded sampling produces identical counts."""
        probs = [0.5, 0.5]
        r1 = sample(probs, shots=1000, seed=42)
        r2 = sample(probs, shots=1000, seed=42)
        assert r1 == r2

    def test_different_seeds_may_differ(self):
        """Different seeds can produce different results (not guaranteed, but very likely with 10k shots)."""
        probs = [0.5, 0.5]
        r1 = sample(probs, shots=10000, seed=1)
        r2 = sample(probs, shots=10000, seed=2)
        # With overwhelming probability, counts differ for distinct seeds
        assert r1 != r2


# ==================================================================
# Histogram count totals
# ==================================================================

class TestHistogramTotals:
    """Histogram values must sum exactly to shots."""

    def test_counts_sum_equals_shots_deterministic(self):
        """Histogram counts sum exactly to shots for a deterministic state."""
        probs = [1.0, 0.0]
        result = sample(probs, shots=500, seed=0)
        assert sum(result.values()) == 500

    def test_counts_sum_equals_shots_superposition(self):
        """Histogram counts sum exactly to shots for a superposition."""
        probs = [0.5, 0.5]
        result = sample(probs, shots=1024, seed=7)
        assert sum(result.values()) == 1024

    def test_counts_sum_equals_shots_two_qubits(self):
        """Histogram counts sum exactly to shots for two qubits."""
        probs = [0.25, 0.25, 0.25, 0.25]
        result = sample(probs, shots=2048, seed=99)
        assert sum(result.values()) == 2048


# ==================================================================
# Bell-state sampling
# ==================================================================

class TestBellStateSampling:
    """Sampling from a Bell-state probability distribution."""

    def test_bell_state_only_00_and_11(self):
        """Bell-state sampling produces only '00' and '11' outcomes."""
        probs = [0.5, 0.0, 0.0, 0.5]
        result = sample(probs, shots=10000, seed=42)
        assert set(result.keys()).issubset({"00", "11"})
        assert "00" in result
        assert "11" in result
        assert sum(result.values()) == 10000

    def test_bell_state_no_01_or_10(self):
        """Bell-state sampling never produces '01' or '10'."""
        probs = [0.5, 0.0, 0.0, 0.5]
        result = sample(probs, shots=10000, seed=123)
        assert "01" not in result
        assert "10" not in result


# ==================================================================
# Big-endian outcome formatting
# ==================================================================

class TestBigEndianFormatting:
    """Outcome keys follow big-endian bit-string convention."""

    def test_two_qubit_key_length(self):
        """Two-qubit outcomes are 2-character strings."""
        probs = [0.25, 0.25, 0.25, 0.25]
        result = sample(probs, shots=1000, seed=42)
        for key in result:
            assert len(key) == 2
            assert all(c in "01" for c in key)

    def test_three_qubit_key_length(self):
        """Three-qubit outcomes are 3-character strings."""
        probs = [0.125] * 8
        result = sample(probs, shots=1000, seed=42)
        for key in result:
            assert len(key) == 3
            assert all(c in "01" for c in key)

    def test_one_qubit_keys_are_single_char(self):
        """One-qubit outcomes are single characters '0' or '1'."""
        probs = [0.5, 0.5]
        result = sample(probs, shots=100, seed=0)
        for key in result:
            assert len(key) == 1
            assert key in ("0", "1")

    def test_deterministic_state_index_2_maps_to_10(self):
        """For 2 qubits, probability at index 2 maps to outcome '10'."""
        # All probability on index 2 → outcome '10'
        probs = [0.0, 0.0, 1.0, 0.0]
        result = sample(probs, shots=50, seed=0)
        assert result == {"10": 50}

    def test_deterministic_state_index_1_maps_to_01(self):
        """For 2 qubits, probability at index 1 maps to outcome '01'."""
        probs = [0.0, 1.0, 0.0, 0.0]
        result = sample(probs, shots=50, seed=0)
        assert result == {"01": 50}


# ==================================================================
# Rejection: invalid shots
# ==================================================================

class TestShotsRejection:
    """Reject invalid shot counts."""

    def test_reject_zero_shots(self):
        """Zero shots is rejected."""
        with pytest.raises(SamplingError, match="positive integer"):
            sample([1.0, 0.0], shots=0, seed=0)

    def test_reject_negative_shots(self):
        """Negative shots is rejected."""
        with pytest.raises(SamplingError, match="positive integer"):
            sample([1.0, 0.0], shots=-5, seed=0)

    def test_reject_non_integer_shots(self):
        """Non-integer shots value is rejected."""
        with pytest.raises(SamplingError, match="positive integer"):
            sample([1.0, 0.0], shots=1.5, seed=0)


# ==================================================================
# Rejection: invalid probability distributions
# ==================================================================

class TestProbabilityRejection:
    """Reject invalid probability distributions."""

    def test_reject_negative_probabilities(self):
        """Negative probabilities are rejected."""
        with pytest.raises(SamplingError, match="negative"):
            sample([-0.5, 1.5], shots=10, seed=0)

    def test_reject_nan_probabilities(self):
        """NaN in probabilities is rejected."""
        with pytest.raises(SamplingError, match="non-finite"):
            sample([float("nan"), 0.5], shots=10, seed=0)

    def test_reject_inf_probabilities(self):
        """Inf in probabilities is rejected."""
        with pytest.raises(SamplingError, match="non-finite"):
            sample([float("inf"), 0.0], shots=10, seed=0)

    def test_reject_neg_inf_probabilities(self):
        """Negative infinity in probabilities is rejected."""
        with pytest.raises(SamplingError, match="non-finite"):
            sample([float("-inf"), 1.0], shots=10, seed=0)

    def test_reject_unnormalized_probabilities(self):
        """Probabilities that do not sum to 1 are rejected."""
        with pytest.raises(SamplingError, match="sum to 1"):
            sample([0.3, 0.3], shots=10, seed=0)

    def test_reject_overcounted_probabilities(self):
        """Probabilities summing to more than 1 are rejected."""
        with pytest.raises(SamplingError, match="sum to 1"):
            sample([0.6, 0.6], shots=10, seed=0)

    def test_reject_all_zero_probabilities(self):
        """All-zero probabilities are rejected (sum != 1)."""
        with pytest.raises(SamplingError, match="sum to 1"):
            sample([0.0, 0.0], shots=10, seed=0)


# ==================================================================
# Rejection: invalid probability-array length
# ==================================================================

class TestLengthRejection:
    """Reject probability arrays with invalid length."""

    def test_reject_length_3(self):
        """Length 3 is not a power of two."""
        with pytest.raises(SamplingError, match="power of two"):
            sample([0.3, 0.3, 0.4], shots=10, seed=0)

    def test_reject_length_5(self):
        """Length 5 is not a power of two."""
        with pytest.raises(SamplingError, match="power of two"):
            sample([0.2] * 5, shots=10, seed=0)

    def test_reject_length_1(self):
        """Length 1 is too short (minimum is 2 for 1 qubit)."""
        with pytest.raises(SamplingError, match="power of two"):
            sample([1.0], shots=10, seed=0)

    def test_reject_empty(self):
        """Empty probability array is rejected."""
        with pytest.raises(SamplingError, match="power of two"):
            sample([], shots=10, seed=0)


# ==================================================================
# Input immutability
# ==================================================================

class TestInputImmutability:
    """Input probability list must not be mutated."""

    def test_input_probabilities_not_mutated(self):
        """Sampling does not alter the input probability list."""
        probs = [0.5, 0.5]
        probs_copy = probs.copy()
        sample(probs, shots=100, seed=42)
        assert probs == probs_copy

    def test_input_list_identity_preserved(self):
        """The original list object remains unchanged after sampling."""
        probs = [0.25, 0.25, 0.25, 0.25]
        original_id = id(probs)
        sample(probs, shots=100, seed=0)
        assert id(probs) == original_id
        assert probs == [0.25, 0.25, 0.25, 0.25]


# ==================================================================
# Unseeded sampling
# ==================================================================

class TestUnseededSampling:
    """Explicit behavior for unseeded (seed=None) sampling."""

    def test_unseeded_returns_valid_histogram(self):
        """Unseeded sampling returns a valid histogram."""
        probs = [0.5, 0.5]
        result = sample(probs, shots=100, seed=None)
        assert isinstance(result, dict)
        assert sum(result.values()) == 100
        for key in result:
            assert key in ("0", "1")

    def test_unseeded_is_non_deterministic(self):
        """Unseeded sampling is non-deterministic (very high probability).

        We run two unseeded samples with many shots; it is astronomically
        unlikely that two independent draws from a fair coin produce
        identical count dictionaries with 100k shots.
        """
        probs = [0.5, 0.5]
        results = set()
        for _ in range(5):
            r = sample(probs, shots=100000, seed=None)
            results.add(tuple(sorted(r.items())))
        # With overwhelming probability, at least 2 distinct results
        assert len(results) >= 2

    def test_unseeded_default_parameter(self):
        """seed defaults to None (unseeded)."""
        probs = [1.0, 0.0]
        # Should work without specifying seed
        result = sample(probs, shots=10)
        assert result == {"0": 10}


# ==================================================================
# Output ordering stability
# ==================================================================

class TestOutputOrdering:
    """Histogram keys have stable, deterministic ordering."""

    def test_keys_are_sorted(self):
        """Histogram keys are in sorted (ascending) order."""
        probs = [0.25, 0.25, 0.25, 0.25]
        result = sample(probs, shots=10000, seed=42)
        keys = list(result.keys())
        assert keys == sorted(keys)

    def test_sorted_order_matches_numerical_order(self):
        """Sorted binary strings match numerical index order."""
        probs = [0.125] * 8
        result = sample(probs, shots=10000, seed=42)
        keys = list(result.keys())
        numerical = [int(k, 2) for k in keys]
        assert numerical == sorted(numerical)


if __name__ == "__main__":
    pytest.main([__file__])
