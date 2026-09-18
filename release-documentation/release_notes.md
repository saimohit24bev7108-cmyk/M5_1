# M5 Simulator Release Candidate Documentation

## Purpose
The M5 Simulator is a deterministic, local quantum circuit simulator designed for high-fidelity, reproducible state evolution and observation statistics.

## Architecture
- **Backend**: Pure Python matrix-based statevector evolution.
- **Service**: In-process JSON-compatible simulation service.
- **UI**: Standalone HTML/CSS/JS interface integrated with the local service via a fixture adapter.
- **Concurrency**: Dedicated thread worker pool for simulation jobs.

## Technical Specifications
### Supported Gates
- `I` (Identity)
- `X` (Pauli-X)
- `Y` (Pauli-Y)
- `Z` (Pauli-Z)
- `H` (Hadamard)
- `S` (Phase)
- `T` (pi/4 rotation)
- `CNOT` (Controlled-NOT)

### Noise Behavior
- Deterministic noise injection using Kraus operators.
- Supported: Depolarizing noise.
- Unsupported noise models are rejected via `E_CONFIG_REJECTED`.

### Service Contract
#### Request Format
```json
{
  "request_id": "string",
  "run_id": "string",
  "circuit": {
    "schema_version": "1.0",
    "num_qubits": integer,
    "operations": [ { "gate": "string", "targets": [integer] } ]
  },
  "mode": "ideal" | "noisy",
  "noise": {},
  "shots": integer,
  "seed": integer
}
```

#### Success Response
```json
{
  "status": "completed",
  "request_id": "string",
  "run_id": "string",
  "result": {
    "status": "completed",
    "result_label": "SIMULATION",
    "num_qubits": integer,
    "shots": integer,
    "seed": integer,
    "mode": "string",
    "probabilities": [float],
    "counts": { "state": integer }
  }
}
```

#### Error Response
```json
{
  "status": "error",
  "request_id": "string",
  "run_id": "string",
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

## Constraints & Limits
- **Register Width**: Maximum 8 Qubits (Enforced).
- **Concurrency**: Maximum 4 concurrent simulation jobs (Enforced).
- **Network**: No external network, API keys, cloud services, or hardware access.
- **Determinism**: Byte-identical reproducibility given identical seed and instructions.

## UI Scope & Integration
- **Screens**: Overview, Circuit Workspace, Simulation Pipeline, Result Package.
- **Visuals**: Preserves original Stitch UI exactly.
- **Fonts**: Newsreader (Display), Inter (Body), JetBrains Mono (Technical).
- **Mode**: Deterministic fixture mode used for local demonstration.
- **Limitations**: Download Package and Analysis tools are inert in the current release.

## Verification Evidence
- **Backend Tests**: 374 passed (TESTED)
- **UI Integration**: Passed (TESTED)
- **Visual Regression**: Passed at 390x844 and 430x932 (TESTED)
- **Assets**: Local vendoring verified (TESTED)

## Local Run Instructions
1. Navigate to `ui_integrated/`.
2. Open `m5_simulator_overview/code.html` in a modern web browser.
3. Interaction follows the documented navigation flow.

## Known Risks & Limitations
- **UI Analysis**: The Analysis screen is currently a placeholder.
- **Result Downloads**: The Download Package button is inert.
- **Browser Compatibility**: Verified on Chromium-based browsers.

## Evidence State Summary
- Backend Logic: TESTED
- Service Contract: TESTED
- UI Visuals: TESTED
- Integration: TESTED
- Approval: NOT INDEPENDENTLY APPROVED
