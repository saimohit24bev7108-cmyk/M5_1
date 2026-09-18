import pytest
from src.m5_simulator.circuit import Circuit
from src.m5_simulator.gates import get_gate, CNOT_ID, ConfigRejectedError

def test_valid_one_qubit_circuit():
    c = Circuit(qubits=1)
    c.add_operation("H", [0])
    c.add_operation("X", [0])
    c.validate()
    assert len(c.operations) == 2

def test_valid_bell_circuit():
    c = Circuit(qubits=2)
    c.add_operation("H", [0])
    c.add_operation("CNOT", [0, 1])
    c.validate()
    assert len(c.operations) == 2
    assert c.operations[0]["gate"] == "H"
    assert c.operations[1]["gate"] == "CNOT"

def test_all_supported_single_qubit_gates():
    gates = ["I", "X", "Y", "Z", "H", "S", "T"]
    c = Circuit(qubits=1)
    for g in gates:
        # Use separate circuits to avoid too many ops in one, though not required
        temp_c = Circuit(qubits=1)
        temp_c.add_operation(g, [0])
        temp_c.validate()
        assert get_gate(g) is not CNOT_ID

def test_valid_cnot():
    c = Circuit(qubits=2)
    c.add_operation("CNOT", [0, 1])
    c.validate()
    assert c.operations[0]["gate"] == "CNOT"

def test_rejection_zero_qubits():
    with pytest.raises(ValueError, match="between 1 and 8"):
        Circuit(qubits=0)

def test_rejection_too_many_qubits():
    with pytest.raises(ValueError, match="between 1 and 8"):
        Circuit(qubits=9)

def test_rejection_invalid_qubit_index():
    c = Circuit(qubits=2)
    with pytest.raises(IndexError):
        c.add_operation("X", [2])

def test_rejection_single_qubit_gate_wrong_targets():
    c = Circuit(qubits=2)
    # Too many
    with pytest.raises(ValueError, match="requires exactly 1 target"):
        c.add_operation("H", [0, 1])
    # Too few
    with pytest.raises(ValueError, match="requires exactly 1 target"):
        c.add_operation("H", [])

def test_rejection_cnot_duplicate_targets():
    c = Circuit(qubits=2)
    with pytest.raises(ValueError, match="targets must be distinct"):
        c.add_operation("CNOT", [0, 0])

def test_rejection_unsupported_gate():
    c = Circuit(qubits=1)
    with pytest.raises(ConfigRejectedError, match="E_CONFIG_REJECTED"):
        c.add_operation("UNKNOWN", [0])

def test_preservation_of_operation_order():
    c = Circuit(qubits=1)
    c.add_operation("X", [0])
    c.add_operation("H", [0])
    c.add_operation("Z", [0])
    assert c.operations[0]["gate"] == "X"
    assert c.operations[1]["gate"] == "H"
    assert c.operations[2]["gate"] == "Z"

def test_circuit_export_import():
    c = Circuit(qubits=2)
    c.add_operation("H", [0])
    c.add_operation("CNOT", [0, 1])

    data = c.to_dict()
    assert data["qubits"] == 2
    assert len(data["operations"]) == 2

    c_new = Circuit.from_dict(data)
    assert c_new.qubits == 2
    assert c_new.operations == c.operations

def test_rejection_malformed_circuit_data():
    # Missing qubits
    with pytest.raises(Exception):
        Circuit.from_dict({"version": "1.0", "operations": []})
    # Invalid qubit count in data
    with pytest.raises(Exception):
        Circuit.from_dict({"version": "1.0", "qubits": 10, "operations": []})

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
