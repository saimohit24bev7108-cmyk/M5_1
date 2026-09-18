/**
 * M5 UI State Store
 * Persists session state in sessionStorage under key 'm5_ui_session_v1'.
 * Generates request/run IDs matching the M5 architecture convention:
 *   req_<YYYYMMDD>_<5-digit counter>
 *   run_<6-digit counter>
 */
const SESSION_KEY = 'm5_ui_session_v1';

function getDateStamp() {
  const d = new Date();
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

function defaultState() {
  return {
    request_id: null,
    run_id: null,
    fixture_counter: 0,
    circuit: {
      schema_version: '1.0',
      num_qubits: 2,
      operations: [
        { gate: 'H', targets: [0] },
        { gate: 'CNOT', targets: [0, 1] }
      ]
    },
    shots: 1000,
    seed: 42,
    mode: 'ideal',
    noise: {},
    selectedGate: null,
    lastResponse: null,
    lastError: null,
    currentScreen: 'overview'
  };
}

class StateStore {
  constructor() {
    this._listeners = [];
    this._state = this._load();
  }

  _load() {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        // Merge with defaults to fill any missing keys
        return { ...defaultState(), ...parsed };
      }
    } catch (e) {
      // Corrupted storage — reset
    }
    return defaultState();
  }

  _save() {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(this._state));
    } catch (e) {
      // Storage full or unavailable — silent
    }
  }

  getState() {
    return { ...this._state };
  }

  setState(partial) {
    this._state = { ...this._state, ...partial };
    this._save();
    this._notify();
  }

  /** Generate a new unique request_id and run_id pair. */
  generateIds() {
    const counter = (this._state.fixture_counter || 0) + 1;
    const dateStamp = getDateStamp();
    const reqId = `req_${dateStamp}_${String(counter).padStart(5, '0')}`;
    const runId = `run_${String(counter).padStart(6, '0')}`;
    this.setState({
      fixture_counter: counter,
      request_id: reqId,
      run_id: runId
    });
    return { request_id: reqId, run_id: runId };
  }

  /** Build a service request from current state. */
  buildRequest() {
    const ids = this.generateIds();
    const s = this._state;
    return {
      request_id: ids.request_id,
      run_id: ids.run_id,
      circuit: { ...s.circuit },
      mode: s.mode,
      noise: s.mode === 'noisy' ? (s.noise || {}) : {},
      shots: s.shots,
      seed: s.seed
    };
  }

  /** Reset session (new circuit action). */
  resetSession() {
    const counter = this._state.fixture_counter; // preserve counter
    this._state = { ...defaultState(), fixture_counter: counter };
    this._save();
    this._notify();
  }

  subscribe(listener) {
    this._listeners.push(listener);
    return () => {
      this._listeners = this._listeners.filter(l => l !== listener);
    };
  }

  _notify() {
    const snapshot = this.getState();
    this._listeners.forEach(fn => {
      try { fn(snapshot); } catch (e) { /* listener error */ }
    });
  }
}

// Singleton
window.M5Store = window.M5Store || new StateStore();
