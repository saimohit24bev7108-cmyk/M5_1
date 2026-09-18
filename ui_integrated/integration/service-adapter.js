/**
 * M5 Service Adapter
 * Fixture-based adapter matching the M5 service request/response contract.
 * - Generates unique request_id/run_id per submission
 * - Tracks active run IDs for duplicate detection
 * - Returns fixture responses with correct IDs filled in
 * - Never labelled as live backend result
 */
class ServiceAdapter {
  constructor() {
    this._activeRunIds = new Set();
    this._pendingRequest = null; // for stale-response protection
  }

  /**
   * Submit a simulation request.
   * @param {Object} request - M5 service request shape
   * @returns {Promise<Object>} - M5 service response shape
   */
  async submit(request) {
    const requestId = request.request_id;
    const runId = request.run_id;

    // Duplicate detection
    if (this._activeRunIds.has(runId)) {
      return this._buildError(requestId, runId, window.M5Fixtures.errors.E_DUPLICATE_REQUEST);
    }

    // Concurrency limit (max 4 slots)
    if (this._activeRunIds.size >= 4) {
      return this._buildError(requestId, runId, window.M5Fixtures.errors.E_SIMULATION_LIMIT);
    }

    // Basic validation
    if (!request.circuit || !request.mode || !request.shots) {
      return this._buildError(requestId, runId, window.M5Fixtures.errors.E_VALIDATION_ERROR);
    }

    // Mark active
    this._activeRunIds.add(runId);
    this._pendingRequest = requestId;

    try {
      // Simulate processing delay (deterministic)
      await new Promise(resolve => setTimeout(resolve, 600));

      // Stale-response protection: ignore if a newer request superseded this one
      if (this._pendingRequest !== requestId) {
        return null; // stale
      }

      // Select fixture based on mode
      const fixtures = window.M5Fixtures;
      const fixtureData = request.mode === 'noisy'
        ? fixtures.bell_state_noisy
        : fixtures.bell_state_ideal;

      // Build response with actual request IDs
      const response = {
        status: 'completed',
        request_id: requestId,
        run_id: runId,
        result: {
          ...fixtureData.result,
          shots: request.shots,
          seed: request.seed,
          mode: request.mode
        }
      };

      return response;
    } finally {
      this._activeRunIds.delete(runId);
    }
  }

  _buildError(requestId, runId, errorTemplate) {
    return {
      status: 'error',
      request_id: requestId,
      run_id: runId,
      error: { ...errorTemplate }
    };
  }

  /** Cancel any pending request (for stale-response protection). */
  cancelPending() {
    this._pendingRequest = null;
  }

  /** Get count of active jobs. */
  activeCount() {
    return this._activeRunIds.size;
  }
}

window.M5Adapter = window.M5Adapter || new ServiceAdapter();
