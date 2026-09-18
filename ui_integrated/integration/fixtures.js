/**
 * M5 Deterministic Fixtures
 * Matches the exact M5 service request/response contract.
 * Fixture IDs are filled dynamically by the service adapter.
 * Includes all 7 error codes defined in the M5 service.
 */
const FIXTURES = {
  bell_state_ideal: {
    status: 'completed',
    result: {
      status: 'completed',
      result_label: 'SIMULATION',
      num_qubits: 2,
      shots: 1000,
      seed: 42,
      mode: 'ideal',
      probabilities: [0.5, 0.0, 0.0, 0.5],
      counts: { '00': 503, '11': 497 }
    }
  },

  bell_state_noisy: {
    status: 'completed',
    result: {
      status: 'completed',
      result_label: 'SIMULATION',
      num_qubits: 2,
      shots: 1000,
      seed: 42,
      mode: 'noisy',
      probabilities: [0.4850, 0.0150, 0.0140, 0.4860],
      counts: { '00': 489, '01': 14, '10': 15, '11': 482 }
    }
  },

  errors: {
    E_VALIDATION_ERROR: {
      code: 'E_VALIDATION_ERROR',
      message: 'Request validation failed. Check circuit and configuration fields.'
    },
    E_SIMULATION_LIMIT: {
      code: 'E_SIMULATION_LIMIT',
      message: 'Maximum active simulation jobs reached. Try again after an active job completes.'
    },
    E_DUPLICATE_REQUEST: {
      code: 'E_DUPLICATE_REQUEST',
      message: 'A job with this run_id is already active.'
    },
    E_MALFORMED_INPUT: {
      code: 'E_MALFORMED_INPUT',
      message: 'Request must be a JSON-compatible dict.'
    },
    E_CONFIG_REJECTED: {
      code: 'E_CONFIG_REJECTED',
      message: 'Circuit configuration rejected by the backend.'
    },
    E_EXECUTION_ERROR: {
      code: 'E_EXECUTION_ERROR',
      message: 'Simulation execution error occurred during statevector evolution.'
    },
    E_SERVICE_ERROR: {
      code: 'E_SERVICE_ERROR',
      message: 'An unexpected service error occurred.'
    }
  }
};

window.M5Fixtures = FIXTURES;
