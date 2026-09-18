"""
Tests for the ideal statevector engine (Step 4 of M5 architecture).

Covers:
    - Correct all-zero initial state (1 and 2 qubits)
    - Single-qubit gates: X, H, Z, S, T
    - Bell circuit: H(0) + CNOT(0,1)
    - Bell probabilities (0.5 for |00> and |11>, 0 for |01> and |10>)
    - Big-endian qubit ordering
    - Probability normalization after every supported gate
    - Statevector dimension == 2 ** num_qubits
    - Rejection of >8 qubits
    - Rejection of malformed / unsupported operations
    - Rejection of non-finite numerical values
"""

import math
import pytest
import numpy as np

from src.m5_simulator.circuit import Circuit
from src.m5_simulator.gates import ConfigRejectedError
from src.m5_simulator.schemas import SchemaValidationError
from src.m5_simulator.statevector import (
    Statevector,
    StatevectorError,
    execute_circuit,
    MAX_QUBITS,
    TOLERANCE,
)


# ==================================================================
# Initial state
# ==================================================================

class TestInitialState:
    """All-zero basis state initialisation."""

    def test_one_qubit_initial_state(self):
        """Correct all-zero initial state for one qubit."""
        sv = Statevector(num_qubits=1)
        assert sv.dim == 2
        assert sv.data[0] == 1.0 + 0j
        assert sv.data[1] == 0.0 + 0j

    def test_two_qubit_initial_state(self):
        """Correct all-zero initial state for two qubits."""
        sv = Statevector(num_qubits=2)
        assert sv.dim == 4
        assert sv.data[0] == 1.0 + 0j
        assert np.all(sv.data[1:] == 0)

    def test_dimension_equals_2_pow_n(self):
        """Statevector dimension equals 2 ** num_qubits for several sizes."""
        for n in range(1, MAX_QUBITS + 1):
            sv = Statevector(num_qubits=n)
            assert sv.dim == 2 ** n
            assert len(sv.data) == 2 ** n


# ==================================================================
# Single-qubit gates
# ==================================================================

class TestSingleQubitGates:
    """Application of single-qubit gates."""

    def test_x_gate_flips_zero_to_one(self):
        """X gate transforms |0> to |1>."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate("X", 0)
        assert sv.data[0] == 0.0 + 0j
        assert sv.data[1] == 1.0 + 0j
        assert sv.get_probabilities() == [0.0, 1.0]

    def test_h_gate_equal_superposition(self):
        """H gate produces equal probabilities for |0> and |1>."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate("H", 0)
        expected = 1.0 / math.sqrt(2)
        assert np.isclose(sv.data[0], expected)
        assert np.isclose(sv.data[1], expected)
        probs = sv.get_probabilities()
        assert np.allclose(probs, [0.5, 0.5])

    def test_z_gate_preserves_probabilities(self):
        """Z gate preserves computational-basis probabilities."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate("Z", 0)
        # |0> stays |0>; Z|0> = |0>
        probs = sv.get_probabilities()
        assert probs == [1.0, 0.0]

        # After H: equal superposition; Z flips phase of |1> but probs unchanged
        sv2 = Statevector(num_qubits=1)
        sv2.apply_single_qubit_gate("H", 0)
        sv2.apply_single_qubit_gate("Z", 0)
        probs2 = sv2.get_probabilities()
        assert np.allclose(probs2, [0.5, 0.5])

    def test_s_gate_preserves_normalization(self):
        """S gate preserves normalization."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_single_qubit_gate("S", 0)
        assert sv.validate_normalization() is True
        probs = sv.get_probabilities()
        assert np.isclose(sum(probs), 1.0)

    def test_t_gate_preserves_normalization(self):
        """T gate preserves normalization."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_single_qubit_gate("T", 0)
        assert sv.validate_normalization() is True
        probs = sv.get_probabilities()
        assert np.isclose(sum(probs), 1.0)

    def test_identity_gate_no_change(self):
        """I gate leaves the state unchanged."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate("H", 0)
        state_before = sv.get_statevector().copy()
        sv.apply_single_qubit_gate("I", 0)
        assert np.allclose(sv.get_statevector(), state_before)

    def test_y_gate_preserves_normalization(self):
        """Y gate preserves normalization."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate("Y", 0)
        assert sv.validate_normalization() is True


# ==================================================================
# Bell circuit
# ==================================================================

class TestBellCircuit:
    """Bell state creation and verification."""

    def test_bell_state_amplitudes(self):
        """Bell circuit H(0) followed by CNOT(0, 1)."""
        sv = Statevector(num_qubits=2)
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_cnot(0, 1)

        expected = 1.0 / math.sqrt(2)
        # |00> at index 0, |11> at index 3
        assert np.isclose(sv.data[0], expected)
        assert np.isclose(sv.data[3], expected)
        assert np.isclose(sv.data[1], 0.0)
        assert np.isclose(sv.data[2], 0.0)

    def test_bell_probabilities_00_and_11(self):
        """Bell circuit produces probabilities of 0.5 for |00> and |11>."""
        sv = Statevector(num_qubits=2)
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_cnot(0, 1)

        probs = sv.get_probabilities()
        assert np.isclose(probs[0], 0.5)  # |00>
        assert np.isclose(probs[3], 0.5)  # |11>

    def test_bell_zero_probability_01_and_10(self):
        """Bell circuit produces zero probability for |01> and |10> within tolerance."""
        sv = Statevector(num_qubits=2)
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_cnot(0, 1)

        probs = sv.get_probabilities()
        assert probs[1] < TOLERANCE  # |01>
        assert probs[2] < TOLERANCE  # |10>

    def test_bell_via_execute_circuit(self):
        """Bell circuit executed through execute_circuit produces correct probabilities."""
        c = Circuit(qubits=2)
        c.add_operation("H", [0])
        c.add_operation("CNOT", [0, 1])

        sv = execute_circuit(c)
        probs = sv.get_probabilities()
        assert np.allclose(probs, [0.5, 0.0, 0.0, 0.5])


# ==================================================================
# Big-endian qubit ordering
# ==================================================================

class TestBigEndianOrdering:
    """Verify big-endian convention: qubit 0 is the leftmost (most significant) bit."""

    def test_x_on_qubit_0_of_2(self):
        """X(0) on 2 qubits: |00> -> |10> which is index 2."""
        sv = Statevector(num_qubits=2)
        sv.apply_single_qubit_gate("X", 0)
        # Qubit 0 is MSB: |10> = index 2
        assert sv.data[2] == 1.0 + 0j
        assert sv.data[0] == 0.0 + 0j
        assert sv.data[1] == 0.0 + 0j
        assert sv.data[3] == 0.0 + 0j

    def test_x_on_qubit_1_of_2(self):
        """X(1) on 2 qubits: |00> -> |01> which is index 1."""
        sv = Statevector(num_qubits=2)
        sv.apply_single_qubit_gate("X", 1)
        # Qubit 1 is LSB: |01> = index 1
        assert sv.data[1] == 1.0 + 0j
        assert sv.data[0] == 0.0 + 0j

    def test_x_on_qubit_1_of_3(self):
        """X(1) on 3 qubits: |000> -> |010> which is index 2."""
        sv = Statevector(num_qubits=3)
        sv.apply_single_qubit_gate("X", 1)
        # qubit 1, bit_pos = 3-1-1 = 1, value = 2 → index 2
        assert sv.data[2] == 1.0 + 0j
        assert np.sum(np.abs(sv.data) > 0) == 1

    def test_nonzero_probabilities_display_order(self):
        """get_nonzero_probabilities returns big-endian labels."""
        sv = Statevector(num_qubits=2)
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_cnot(0, 1)

        nonzero = sv.get_nonzero_probabilities()
        assert "00" in nonzero
        assert "11" in nonzero
        assert "01" not in nonzero
        assert "10" not in nonzero
        assert np.isclose(nonzero["00"], 0.5)
        assert np.isclose(nonzero["11"], 0.5)

    def test_basis_labels_for_two_qubits(self):
        """For 2 qubits, the four basis states are labeled 00, 01, 10, 11."""
        sv = Statevector(num_qubits=2)
        # Apply H to both qubits for a uniform distribution
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_single_qubit_gate("H", 1)
        nonzero = sv.get_nonzero_probabilities()
        assert set(nonzero.keys()) == {"00", "01", "10", "11"}


# ==================================================================
# Normalization
# ==================================================================

class TestNormalization:
    """Probability normalization after gates."""

    @pytest.mark.parametrize("gate", ["I", "X", "Y", "Z", "H", "S", "T"])
    def test_normalization_after_single_gate(self, gate):
        """Probability normalization after every supported single-qubit gate."""
        sv = Statevector(num_qubits=1)
        sv.apply_single_qubit_gate(gate, 0)
        probs = sv.get_probabilities()
        assert np.isclose(sum(probs), 1.0)
        assert sv.validate_normalization() is True

    def test_normalization_after_cnot(self):
        """Normalization preserved after CNOT application."""
        sv = Statevector(num_qubits=2)
        sv.apply_single_qubit_gate("H", 0)
        sv.apply_cnot(0, 1)
        assert sv.validate_normalization() is True

    def test_normalization_multi_gate_sequence(self):
        """Normalization preserved through a longer gate sequence."""
        c = Circuit(qubits=3)
        c.add_operation("H", [0])
        c.add_operation("H", [1])
        c.add_operation("X", [2])
        c.add_operation("CNOT", [0, 1])

        sv = execute_circuit(c)
        probs = sv.get_probabilities()
        assert np.isclose(sum(probs), 1.0)
        assert sv.validate_normalization() is True


# ==================================================================
# Rejection: qubit count
# ==================================================================

class TestQubitCountRejection:
    """Reject circuits with invalid qubit counts."""

    def test_reject_more_than_8_qubits_statevector(self):
        """Statevector rejects more than 8 qubits directly."""
        with pytest.raises(ValueError, match="between 1 and 8"):
            Statevector(num_qubits=9)

    def test_reject_zero_qubits(self):
        """Statevector rejects 0 qubits."""
        with pytest.raises(ValueError):
            Statevector(num_qubits=0)

    def test_reject_negative_qubits(self):
        """Statevector rejects negative qubit count."""
        with pytest.raises(ValueError):
            Statevector(num_qubits=-1)

    def test_accept_max_qubits(self):
        """Statevector accepts exactly 8 qubits."""
        sv = Statevector(num_qubits=8)
        assert sv.dim == 256


# ==================================================================
# Rejection: unsupported / malformed operations
# ==================================================================

class TestMalformedOperationRejection:
    """Reject unsupported or malformed operations before statevector mutation."""

    def test_reject_unsupported_gate_on_statevector(self):
        """Unsupported gate name is rejected."""
        sv = Statevector(num_qubits=1)
        with pytest.raises(ConfigRejectedError):
            sv.apply_single_qubit_gate("TOFFOLI", 0)

    def test_reject_cnot_as_single_qubit(self):
        """CNOT cannot be applied as a single-qubit gate."""
        sv = Statevector(num_qubits=2)
        with pytest.raises(ValueError, match="Cannot apply CNOT"):
            sv.apply_single_qubit_gate("CNOT", 0)

    def test_reject_out_of_range_target(self):
        """Out-of-range qubit target is rejected."""
        sv = Statevector(num_qubits=1)
        with pytest.raises(ValueError, match="out of range"):
            sv.apply_single_qubit_gate("X", 1)

    def test_reject_cnot_same_control_target(self):
        """CNOT with identical control and target is rejected."""
        sv = Statevector(num_qubits=2)
        with pytest.raises(ValueError, match="distinct"):
            sv.apply_cnot(0, 0)

    def test_reject_cnot_out_of_range(self):
        """CNOT with out-of-range qubit index is rejected."""
        sv = Statevector(num_qubits=2)
        with pytest.raises(ValueError, match="out of range"):
            sv.apply_cnot(0, 2)

    def test_reject_unsupported_gate_in_circuit_execution(self):
        """execute_circuit rejects circuits with unsupported gate before mutation."""
        c = Circuit(qubits=1)
        # Manually inject an unsupported operation to bypass Circuit.add_operation validation
        c.operations.append({"gate": "TOFFOLI", "targets": [0]})
        with pytest.raises((ConfigRejectedError, SchemaValidationError)):
            execute_circuit(c)


# ==================================================================
# Non-finite value rejection
# ==================================================================

class TestNonFiniteRejection:
    """Non-finite numerical values are rejected."""

    def test_reject_nan_in_statevector(self):
        """NaN in statevector data is detected."""
        sv = Statevector(num_qubits=1)
        sv.data[0] = float("nan")
        with pytest.raises(StatevectorError, match="Non-finite"):
            sv._check_finite()

    def test_reject_inf_in_statevector(self):
        """Inf in statevector data is detected."""
        sv = Statevector(num_qubits=1)
        sv.data[0] = float("inf")
        with pytest.raises(StatevectorError, match="Non-finite"):
            sv._check_finite()

    def test_validate_normalization_rejects_nan(self):
        """validate_normalization detects non-finite amplitudes."""
        sv = Statevector(num_qubits=1)
        sv.data[0] = float("nan")
        with pytest.raises(StatevectorError):
            sv.validate_normalization()


# ==================================================================
# Statevector inspection methods
# ==================================================================

class TestStatevectorMethods:
    """Test get_statevector, get_probabilities, validate_normalization, get_nonzero_probabilities."""

    def test_get_statevector_returns_copy(self):
        """get_statevector returns a copy, not a reference."""
        sv = Statevector(num_qubits=1)
        vec = sv.get_statevector()
        vec[0] = 999.0
        # Original should be unchanged
        assert sv.data[0] == 1.0 + 0j

    def test_get_probabilities_length(self):
        """get_probabilities returns list of length 2**n."""
        for n in range(1, 5):
            sv = Statevector(num_qubits=n)
            probs = sv.get_probabilities()
            assert len(probs) == 2 ** n

    def test_validate_normalization_valid(self):
        """validate_normalization returns True for a valid state."""
        sv = Statevector(num_qubits=2)
        assert sv.validate_normalization() is True

    def test_validate_normalization_invalid(self):
        """validate_normalization raises for un-normalised state."""
        sv = Statevector(num_qubits=1)
        sv.data[0] = 2.0 + 0j  # Not normalised
        with pytest.raises(StatevectorError, match="not normalised"):
            sv.validate_normalization()

    def test_nonzero_probabilities_initial_state(self):
        """Initial state has only one non-zero probability at |0...0>."""
        sv = Statevector(num_qubits=2)
        nonzero = sv.get_nonzero_probabilities()
        assert len(nonzero) == 1
        assert "00" in nonzero
        assert np.isclose(nonzero["00"], 1.0)


# ==================================================================
# Operation order preservation
# ==================================================================

class TestOperationOrder:
    """Operations are applied in original circuit order."""

    def test_hx_vs_xh_different_results(self):
        """H then X gives a different state than X then H."""
        sv1 = Statevector(num_qubits=1)
        sv1.apply_single_qubit_gate("H", 0)
        sv1.apply_single_qubit_gate("X", 0)

        sv2 = Statevector(num_qubits=1)
        sv2.apply_single_qubit_gate("X", 0)
        sv2.apply_single_qubit_gate("H", 0)

        assert not np.allclose(sv1.data, sv2.data)


if __name__ == "__main__":
    pytest.main([__file__])
