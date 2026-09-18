import math
from typing import List, Dict, Tuple
import numpy as np
from src.m5_simulator.circuit import Circuit
from src.m5_simulator.gates import GATES, CNOT_ID, get_gate, ConfigRejectedError

# Maximum number of qubits supported by this engine.
MAX_QUBITS = 8

# Numerical tolerance for normalization and probability checks.
TOLERANCE = 1e-10

# Set of gate names that are valid single-qubit gates.
_SUPPORTED_SINGLE_QUBIT_GATES = frozenset(GATES.keys())

# Complete set of supported gate names (single-qubit + CNOT).
_SUPPORTED_GATES = _SUPPORTED_SINGLE_QUBIT_GATES | {CNOT_ID}


class StatevectorError(Exception):
    """Raised when a statevector operation is invalid or produces invalid state."""
    pass


class Statevector:
    """
    Ideal statevector representation for the M5 simulator.

    Convention:
        Big-endian qubit ordering. Qubit 0 is the most significant (leftmost)
        bit in basis-state labels. For n qubits the basis is indexed as:
            index = q0 * 2^(n-1) + q1 * 2^(n-2) + ... + q_{n-1} * 2^0
        so |01> means qubit 0 = 0, qubit 1 = 1, stored at index 1.

    This class is responsible only for deterministic state evolution.
    Sampling, noise, and backend concerns are intentionally excluded.
    """

    def __init__(self, num_qubits: int):
        """
        Initialise the statevector to the all-zero basis state |0...0>.

        Args:
            num_qubits: Number of qubits (1 to MAX_QUBITS).

        Raises:
            ValueError: If num_qubits is outside [1, MAX_QUBITS].
        """
        if not isinstance(num_qubits, int) or not (1 <= num_qubits <= MAX_QUBITS):
            raise ValueError(
                f"Qubit count must be an integer between 1 and {MAX_QUBITS}, "
                f"got {num_qubits}."
            )

        self.num_qubits: int = num_qubits
        self.dim: int = 1 << num_qubits  # 2 ** num_qubits

        # All-zero initial state: |0...0>
        self.data: np.ndarray = np.zeros(self.dim, dtype=np.complex128)
        self.data[0] = 1.0 + 0j

    # ------------------------------------------------------------------
    # Gate application
    # ------------------------------------------------------------------

    def apply_single_qubit_gate(self, gate_name: str, target: int) -> None:
        """
        Apply a single-qubit gate to the statevector in-place.

        Uses big-endian indexing: qubit k maps to bit position
        (num_qubits - 1 - k) in the basis-state integer.

        Args:
            gate_name: Name of the gate (must be in GATES).
            target: Index of the qubit (0-indexed).

        Raises:
            ConfigRejectedError: If gate_name is unsupported.
            ValueError: If target is out of range or gate is CNOT.
            StatevectorError: If gate application produces non-finite values.
        """
        matrix = get_gate(gate_name)
        if matrix == CNOT_ID:
            raise ValueError("Cannot apply CNOT as a single-qubit gate.")

        if not (0 <= target < self.num_qubits):
            raise ValueError(
                f"Qubit index {target} out of range for {self.num_qubits} qubits."
            )

        # Convert gate matrix to numpy array
        g = np.array(matrix, dtype=np.complex128)

        # Map qubit index to bit position (big-endian)
        bit_pos = self.num_qubits - 1 - target
        bit_val = 1 << bit_pos

        # Iterate over pairs of basis states differing only at the target bit
        for i in range(self.dim):
            if not (i & bit_val):
                j = i | bit_val

                psi_0 = self.data[i]
                psi_1 = self.data[j]

                # Apply the 2x2 unitary:
                # |psi'_0> = g[0,0]*|psi_0> + g[0,1]*|psi_1>
                # |psi'_1> = g[1,0]*|psi_0> + g[1,1]*|psi_1>
                self.data[i] = g[0, 0] * psi_0 + g[0, 1] * psi_1
                self.data[j] = g[1, 0] * psi_0 + g[1, 1] * psi_1

        # Reject non-finite results
        self._check_finite()

    def apply_cnot(self, control: int, target: int) -> None:
        """
        Apply a CNOT gate: if the control qubit is |1>, flip the target qubit.

        Args:
            control: Index of the control qubit.
            target: Index of the target qubit.

        Raises:
            ValueError: If control == target or indices are out of range.
            StatevectorError: If the result contains non-finite values.
        """
        if control == target:
            raise ValueError("CNOT control and target must be distinct.")
        for idx in (control, target):
            if not (0 <= idx < self.num_qubits):
                raise ValueError(
                    f"Qubit index {idx} out of range for {self.num_qubits} qubits."
                )

        ctrl_pos = self.num_qubits - 1 - control
        trgt_pos = self.num_qubits - 1 - target

        ctrl_mask = 1 << ctrl_pos
        trgt_mask = 1 << trgt_pos

        # CNOT is a permutation; use a copy so reads are from the old state.
        old_data = np.copy(self.data)

        for i in range(self.dim):
            if i & ctrl_mask:
                # Control is 1 → flip target bit
                j = i ^ trgt_mask
                self.data[j] = old_data[i]
            else:
                self.data[i] = old_data[i]

        self._check_finite()

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------

    def get_statevector(self) -> np.ndarray:
        """
        Return a copy of the current statevector as a numpy array.

        Returns:
            Complex numpy array of length 2**num_qubits.
        """
        return np.copy(self.data)

    def get_probabilities(self) -> List[float]:
        """
        Return the Born-rule probabilities for all basis states.

        Probabilities are returned in big-endian display order:
        index 0 = |00...0>, index 2^n - 1 = |11...1>.

        Returns:
            List of non-negative floats summing to 1 (within tolerance).
        """
        probs = (np.abs(self.data) ** 2).tolist()
        return probs

    def get_nonzero_probabilities(self) -> Dict[str, float]:
        """
        Return basis-state probabilities that are non-zero (above TOLERANCE),
        keyed by big-endian bit-string labels.

        Returns:
            Dict mapping basis labels like '00', '01' to their probability.
        """
        probs = self.get_probabilities()
        result: Dict[str, float] = {}
        for idx, p in enumerate(probs):
            if p > TOLERANCE:
                label = format(idx, f"0{self.num_qubits}b")
                result[label] = p
        return result

    def validate_normalization(self) -> bool:
        """
        Check that the statevector is normalised: sum of probabilities == 1
        within TOLERANCE, and all probabilities are non-negative.

        Returns:
            True if the state is valid.

        Raises:
            StatevectorError: If normalization or non-negativity is violated.
        """
        probs = np.abs(self.data) ** 2
        total = float(np.sum(probs))

        # Check non-negativity (should always hold for |a|^2, but guard
        # against numerical pathologies).
        if np.any(probs < -TOLERANCE):
            raise StatevectorError(
                f"Negative probability detected (min = {float(np.min(probs))})."
            )

        if not math.isclose(total, 1.0, abs_tol=TOLERANCE):
            raise StatevectorError(
                f"State is not normalised: total probability = {total}."
            )

        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_finite(self) -> None:
        """Raise StatevectorError if any amplitude is non-finite."""
        if not np.all(np.isfinite(self.data)):
            raise StatevectorError(
                "Non-finite value detected in statevector after gate application."
            )


# ======================================================================
# Circuit execution
# ======================================================================

def _validate_circuit_for_execution(circuit: Circuit) -> None:
    """
    Pre-flight validation: reject circuits before any statevector mutation.

    Checks:
        - Qubit count in [1, MAX_QUBITS].
        - Every operation has a supported gate name.
        - Target counts match gate arity.
        - All target indices are within qubit range.

    Raises:
        ValueError: For qubit-count or target-range violations.
        ConfigRejectedError: For unsupported gates.
    """
    if not (1 <= circuit.qubits <= MAX_QUBITS):
        raise ValueError(
            f"Circuit has {circuit.qubits} qubits; maximum is {MAX_QUBITS}."
        )

    for idx, op in enumerate(circuit.operations):
        gate = op["gate"]
        targets = op["targets"]

        # Validate gate name
        if gate not in _SUPPORTED_GATES:
            raise ConfigRejectedError(
                f"Unsupported gate '{gate}' in operation {idx} (E_CONFIG_REJECTED)."
            )

        # Validate target count
        if gate == CNOT_ID:
            if len(targets) != 2:
                raise ValueError(
                    f"CNOT requires exactly 2 targets, got {len(targets)} "
                    f"in operation {idx}."
                )
            if targets[0] == targets[1]:
                raise ValueError(
                    f"CNOT targets must be distinct in operation {idx}."
                )
        else:
            if len(targets) != 1:
                raise ValueError(
                    f"Gate '{gate}' requires exactly 1 target, got {len(targets)} "
                    f"in operation {idx}."
                )

        # Validate qubit range
        for t in targets:
            if not (0 <= t < circuit.qubits):
                raise ValueError(
                    f"Qubit index {t} out of range for {circuit.qubits} qubits "
                    f"in operation {idx}."
                )


def execute_circuit(circuit: Circuit) -> Statevector:
    """
    Execute a Circuit on a fresh statevector and return the final state.

    All operations are validated before any statevector mutation occurs.
    Operations are applied in their original circuit order.

    This function performs only deterministic state evolution.
    Sampling and noise are intentionally excluded.

    Args:
        circuit: A Circuit instance to execute.

    Returns:
        The Statevector after all operations have been applied.

    Raises:
        ValueError: For invalid qubit counts, targets, or gate arities.
        ConfigRejectedError: For unsupported gate names.
        StatevectorError: For non-finite numerical results.
    """
    # Validate the schema-level structure
    circuit.validate()

    # Additional pre-flight validation
    _validate_circuit_for_execution(circuit)

    sv = Statevector(circuit.qubits)

    for op in circuit.operations:
        gate = op["gate"]
        targets = op["targets"]

        if gate == CNOT_ID:
            sv.apply_cnot(targets[0], targets[1])
        else:
            sv.apply_single_qubit_gate(gate, targets[0])

    return sv
