export class StateStore {
  constructor() {
    this.state = {
      currentCircuit: {
        num_qubits: 2,
        operations: [
          { gate: 'H', targets: [0] },
          { gate: 'CNOT', targets: [0, 1] }
        ]
      },
      simulationMode: 'ideal',
      shots: 1000,
      seed: 42,
      lastResponse: null,
      activeJobId: null,
      currentScreen: 'overview'
    };
    this.listeners = [];
  }

  setState(newState) {
    this.state = { ...this.state, ...newState };
    this.listeners.forEach(l => l(this.state));
  }

  getState() {
    return this.state;
  }

  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }
}
