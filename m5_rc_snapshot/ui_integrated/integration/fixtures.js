export const FIXTURES = {
  'bell_state_ideal': {
    request: {
      "request_id": "req_bell_ideal",
      "run_id": "run_bell_ideal",
      "circuit": {
        "schema_version": "1.0",
        "num_qubits": 2,
        "operations": [
          { "gate": "H", "targets": [0] },
          { "gate": "CNOT", "targets": [0, 1] }
        ]
      },
      "mode": "ideal",
      "noise": {},
      "shots": 1000,
      "seed": 42
    },
    response: {
      "status": "completed",
      "request_id": "req_bell_ideal",
      "run_id": "run_bell_ideal",
      "result": {
        "status": "completed",
        "result_label": "SIMULATION",
        "num_qubits": 2,
        "shots": 1000,
        "seed": 42,
        "mode": "ideal",
        "probabilities": [0.5, 0.0, 0.0, 0.5],
        "counts": {
          "00": 503,
          "11": 497
        }
      }
    }
  },
  'bell_state_noisy': {
    request: {
      "request_id": "req_bell_noisy",
      "run_id": "run_bell_noisy",
      "circuit": {
        "schema_version": "1.0",
        "num_qubits": 2,
        "operations": [
          { "gate": "H", "targets": [0] },
          { "gate": "CNOT", "targets": [0, 1] }
        ]
      },
      "mode": "noisy",
      "noise": { "depolarizing": 0.01 },
      "shots": 1000,
      "seed": 42
    },
    response: {
      "status": "completed",
      "request_id": "req_bell_noisy",
      "run_id": "run_bell_noisy",
      "result": {
        "status": "completed",
        "result_label": "SIMULATION",
        "num_qubits": 2,
        "shots": 1000,
        "seed": 42,
        "mode": "noisy",
        "probabilities": [0.4912, 0.0044, 0.0044, 0.4908],
        "counts": {
          "00": 491,
          "01": 4,
          "10": 5,
          "11": 491
        }
      }
    }
  },
  'error_limit': {
    response: {
      "status": "error",
      "request_id": "req_limit",
      "run_id": "run_limit",
      "error": {
        "code": "E_SIMULATION_LIMIT",
        "message": "Maximum active simulation jobs reached. Try again after an active job completes."
      }
    }
  },
  'error_duplicate': {
    response: {
      "status": "error",
      "request_id": "req_dup",
      "run_id": "run_dup",
      "error": {
        "code": "E_DUPLICATE_REQUEST",
        "message": "A job with run_id 'run_dup' is already active."
      }
    }
  }
};
