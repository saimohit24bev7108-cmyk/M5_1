from typing import List, Dict, Any, Union
from src.m5_simulator.gates import get_gate, CNOT_ID, ConfigRejectedError
from src.m5_simulator.schemas import validate_circuit as schema_validate_circuit

class Circuit:
    """
    Represents a quantum circuit for the M5 simulator.
    Compatible with the M5 circuit JSON schema.
    """

    def __init__(self, qubits: int, version: str = "1.0"):
        if not (1 <= qubits <= 8):
            raise ValueError("Qubit count must be between 1 and 8.")

        self.version = version
        self.qubits = qubits
        self.operations: List[Dict[str, Any]] = []

    def add_operation(self, gate: str, targets: List[int]) -> None:
        """
        Adds a quantum operation to the circuit.
        Validates the gate and targets immediately.
        """
        # Validate gate existence
        get_gate(gate)

        # Validate target count
        if gate == CNOT_ID:
            if len(targets) != 2:
                raise ValueError(f"CNOT requires exactly 2 targets, got {len(targets)}.")
            if targets[0] == targets[1]:
                raise ValueError("CNOT targets must be distinct.")
        else:
            if len(targets) != 1:
                raise ValueError(f"Gate {gate} requires exactly 1 target, got {len(targets)}.")

        # Validate qubit range
        for t in targets:
            if not (0 <= t < self.qubits):
                raise IndexError(f"Qubit index {t} is out of range for {self.qubits} qubits.")

        # Store operation
        self.operations.append({
            "gate": gate,
            "targets": list(targets)
        })

    def validate(self) -> None:
        """
        Validates the complete circuit against the defined schema and internal rules.
        """
        data = self.to_dict()
        # This calls the JSON schema validation from schemas.py
        schema_validate_circuit(data)

    def to_dict(self) -> Dict[str, Any]:
        """Returns a JSON-compatible dictionary representation of the circuit."""
        return {
            "version": self.version,
            "qubits": self.qubits,
            "operations": [op.copy() for op in self.operations]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Circuit':
        """Creates a Circuit instance from a JSON-compatible dictionary."""
        # First validate the data format using the schema
        schema_validate_circuit(data)

        qubits = data["qubits"]
        version = data.get("version", "1.0")

        circuit = cls(qubits, version)
        for op in data["operations"]:
            circuit.add_operation(op["gate"], op["targets"])

        return circuit

    def __str__(self) -> str:
        """
        Returns a string representation.
        Note: Big-endian display order is implied by operation storage.
        """
        lines = [f"Circuit(qubits={self.qubits}, version={self.version})"]
        for i, op in enumerate(self.operations):
            lines.append(f"  {i}: {op['gate']} targets={op['targets']}")
        return "\n".join(lines)
