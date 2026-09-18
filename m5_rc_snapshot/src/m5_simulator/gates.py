import math
from typing import Dict, Any, List, Union
from src.m5_simulator.errors import M5SimulatorError

class ConfigRejectedError(M5SimulatorError):
    """Raised when a configuration or gate is rejected (E_CONFIG_REJECTED)."""
    pass

# Gate matrices (deterministic values)
# I: Identity
# X: Pauli-X
# Y: Pauli-Y
# Z: Pauli-Z
# H: Hadamard
# S: Phase
# T: pi/8 gate
GATES = {
    "I": [[1.0 + 0j, 0.0 + 0j], [0.0 + 0j, 1.0 + 0j]],
    "X": [[0.0 + 0j, 1.0 + 0j], [1.0 + 0j, 0.0 + 0j]],
    "Y": [[0.0 + 0j, 0.0 - 1j], [0.0 + 1j, 0.0 + 0j]],
    "Z": [[1.0 + 0j, 0.0 + 0j], [0.0 + 0j, -1.0 + 0j]],
    "H": [
        [1/math.sqrt(2) + 0j, 1/math.sqrt(2) + 0j],
        [1/math.sqrt(2) + 0j, -1/math.sqrt(2) + 0j]
    ],
    "S": [[1.0 + 0j, 0.0 + 0j], [0.0 + 0j, 0.0 + 1j]],
    "T": [
        [1.0 + 0j, 0.0 + 0j],
        [0.0 + 0j, math.cos(math.pi/4) + 1j*math.sin(math.pi/4)]
    ],
}

CNOT_ID = "CNOT"

def get_gate(gate_name: str) -> Union[List[List[complex]], str]:
    """
    Retrieves the matrix representation for a supported gate.
    Returns the CNOT identifier for CNOT.
    Raises ConfigRejectedError if the gate is unknown.
    """
    if gate_name == CNOT_ID:
        return CNOT_ID

    if gate_name in GATES:
        return GATES[gate_name]

    raise ConfigRejectedError(f"Unsupported gate: {gate_name} (E_CONFIG_REJECTED)")
