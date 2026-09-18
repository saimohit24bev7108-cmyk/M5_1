import { FIXTURES } from './fixtures.js';

export class ServiceAdapter {
  async submit(request) {
    console.log('[ServiceAdapter] Submitting request:', request);

    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 800));

    // Deterministic Fixture Matching
    // Match by circuit operations and mode
    const isBellState = this._isBellState(request.circuit);
    
    if (isBellState && request.mode === 'ideal') {
      return FIXTURES.bell_state_ideal.response;
    }
    if (isBellState && request.mode === 'noisy') {
      return FIXTURES.bell_state_noisy.response;
    }

    // Fallback to Bell State Ideal if no match (for demo purposes)
    return FIXTURES.bell_state_ideal.response;
  }

  _isBellState(circuit) {
    if (!circuit || !circuit.operations) return false;
    const ops = circuit.operations;
    if (ops.length !== 2) return false;
    return ops[0].gate === 'H' && ops[0].targets[0] === 0 &&
           ops[1].gate === 'CNOT' && ops[1].targets[0] === 0 && ops[1].targets[1] === 1;
  }
}
