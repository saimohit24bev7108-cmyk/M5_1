/**
 * M5 Integration Master
 * Wires state-store, service-adapter, navigation, and interaction-core
 * into all four screens. Initializes on DOMContentLoaded.
 *
 * Screen-specific bindings:
 *   - Overview: perturbation button, CTA links
 *   - Workspace: gate palette, mode toggle, execute, inspector
 *   - Pipeline: phase progress, telemetry log
 *   - Result: data binding, rerun
 */
(function() {
  'use strict';

  const IC = window.M5Interaction;
  const store = window.M5Store;
  const adapter = window.M5Adapter;
  const nav = window.M5Nav;

  const GATE_DESC = {
    'I': 'Identity operator (no state change)',
    'X': 'Pauli-X bit-flip gate (π rotation about X)',
    'Y': 'Pauli-Y bit and phase flip',
    'Z': 'Pauli-Z phase-flip gate',
    'H': 'Hadamard basis superposition gate',
    'S': 'Phase gate (π/2 phase rotation)',
    'T': 'π/4 rotation gate (non-Clifford)',
    'CNOT': 'Controlled-NOT entangling operation'
  };

  const PIPELINE_PHASES = [
    { label: '1. Input circuit admitted', detail: 'QASM 3.0 parsed · AST generated' },
    { label: '2. Schema validated', detail: 'circuit.schema.json (Draft-07)' },
    { label: '3. Configuration validated', detail: 'Matrix backend engine assigned' },
    { label: '4. Limits verified', detail: '2/8 qubits · 1/4 concurrency lock' },
    { label: '5. Simulation admitted to local queue', detail: 'Priority: Standard · Worker node 01' },
    { label: '6. State evolution executed', detail: '2^2 = 4 statevector amplitudes calc' },
    { label: '7. Noise applied', detail: 'Depol gate p=0.010 · Readout p=0.020' },
    { label: '8. Finite-shot sampling', detail: '1000 shots · Seed: 42' },
    { label: '9. Derived analysis calculated', detail: 'Bloch vectors · Purity metric' },
    { label: '10. Finalize immutable result package', detail: 'SHA-256 checksum generation' }
  ];

  // ─── HELPERS ─────────────────────────────────────────────
  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return document.querySelectorAll(sel); }

  function announce(msg) {
    const el = $('#aria-status');
    if (el) { el.textContent = msg; setTimeout(() => { el.textContent = ''; }, 3000); }
  }

  function showToast(msg) {
    const toast = $('#statusToast');
    const msgEl = $('#toastMessage');
    if (!toast || !msgEl) return;
    msgEl.textContent = msg;
    toast.classList.remove('translate-y-20', 'opacity-0', 'pointer-events-none');
    toast.classList.add('translate-y-0', 'opacity-100');
    setTimeout(() => {
      toast.classList.add('translate-y-20', 'opacity-0', 'pointer-events-none');
      toast.classList.remove('translate-y-0', 'opacity-100');
    }, 2500);
  }

  // ─── OVERVIEW BINDINGS ───────────────────────────────────
  function initOverview() {
    // Perturbation toggle
    const btn = $('#perturb-btn');
    const v00 = $('#val-00');
    const v11 = $('#val-11');
    const bar00 = $('#bar-00');
    const bar11 = $('#bar-11');
    const fid = $('#fidelity-label');

    if (btn && v00 && v11 && fid) {
      let noisy = false;
      IC.bindTap(btn, () => {
        noisy = !noisy;
        if (noisy) {
          v00.textContent = '0.4912';
          v11.textContent = '0.4908';
          fid.textContent = 'Fidelity: 0.9820';
          if (bar00) bar00.style.width = '49.12%';
          if (bar11) bar11.style.width = '49.08%';
          btn.querySelector('span:last-child').textContent = 'Restore Coherence';
          btn.setAttribute('aria-pressed', 'true');
        } else {
          v00.textContent = '0.5000';
          v11.textContent = '0.5000';
          fid.textContent = 'Fidelity: 1.0000';
          if (bar00) bar00.style.width = '50.00%';
          if (bar11) bar11.style.width = '50.00%';
          btn.querySelector('span:last-child').textContent = 'Sample Perturbation';
          btn.setAttribute('aria-pressed', 'false');
        }
        announce(noisy ? 'Perturbation applied' : 'Coherence restored');
      });
    }

    // CTA links
    const wsLink = $('#btn-open-workspace');
    if (wsLink) {
      IC.bindTap(wsLink, (e) => {
        e.preventDefault();
        nav.navigateTo('workspace');
      });
    }
    const archLink = $('#btn-explore-arch');
    if (archLink) {
      IC.bindTap(archLink, (e) => {
        e.preventDefault();
        // Docs maps to overview per spec
        nav.navigateTo('overview');
      });
    }
  }

  // ─── WORKSPACE BINDINGS ──────────────────────────────────
  function initWorkspace() {
    // Gate palette
    $$('.gate-btn[data-gate]').forEach(btn => {
      const gate = btn.getAttribute('data-gate');
      IC.bindTap(btn, () => {
        const cur = store.getState().selectedGate;
        const newGate = cur === gate ? null : gate;
        store.setState({ selectedGate: newGate });
        updatePaletteVisuals();
        updateInspector(gate,
          gate === 'CNOT' ? '[0, 1]' : '[0]',
          GATE_DESC[gate]
        );
        announce(newGate ? `${gate} gate selected` : 'Gate deselected');
      });
      IC.makeKeyboardAccessible(btn, { label: `${gate} gate`, role: 'button' });
    });

    // Canvas operations (static circuit — inspect only, no placement)
    $$('[data-op]').forEach(el => {
      IC.bindTap(el, () => {
        const op = el.getAttribute('data-op');
        const qubit = el.getAttribute('data-qubit');
        const step = el.getAttribute('data-step');
        updateInspector(
          op === 'CNOT' ? 'CNOT (CX)' : op,
          qubit.includes(',') ? `[${qubit}]` : `[${qubit}]`,
          GATE_DESC[op]
        );
        // Update badge
        const badge = $('#inspector-badge');
        if (badge) badge.textContent = `OP #${step}`;
        announce(`Inspecting ${op} at step ${step}`);
      });
      IC.makeKeyboardAccessible(el, { label: `${el.getAttribute('data-op')} operation`, role: 'button' });
    });

    // Mode toggle
    const idealBtn = $('#mode-ideal');
    const noisyBtn = $('#mode-noisy');
    const budgetLabel = $('#noise-budget');

    function setMode(mode) {
      store.setState({ mode });
      if (mode === 'ideal') {
        idealBtn.className = 'flex items-center justify-center gap-1.5 py-2 rounded bg-paper-base text-ink-primary font-mono-md text-mono-md font-medium shadow-sm transition-all';
        idealBtn.setAttribute('aria-checked', 'true');
        idealBtn.setAttribute('aria-pressed', 'true');
        noisyBtn.className = 'flex items-center justify-center gap-1.5 py-2 rounded text-ink-muted font-mono-md text-mono-md hover:text-ink-primary transition-all';
        noisyBtn.setAttribute('aria-checked', 'false');
        noisyBtn.setAttribute('aria-pressed', 'false');
        if (budgetLabel) budgetLabel.textContent = 'FIDELITY: 100%';
      } else {
        noisyBtn.className = 'flex items-center justify-center gap-1.5 py-2 rounded bg-paper-base text-ink-primary font-mono-md text-mono-md font-medium shadow-sm transition-all';
        noisyBtn.setAttribute('aria-checked', 'true');
        noisyBtn.setAttribute('aria-pressed', 'true');
        idealBtn.className = 'flex items-center justify-center gap-1.5 py-2 rounded text-ink-muted font-mono-md text-mono-md hover:text-ink-primary transition-all';
        idealBtn.setAttribute('aria-checked', 'false');
        idealBtn.setAttribute('aria-pressed', 'false');
        if (budgetLabel) budgetLabel.textContent = 'DEPOLARIZING: p=0.012';
      }
      announce(`Simulation mode: ${mode}`);
    }

    if (idealBtn) IC.bindTap(idealBtn, () => setMode('ideal'));
    if (noisyBtn) IC.bindTap(noisyBtn, () => setMode('noisy'));

    // Restore mode from state
    setMode(store.getState().mode || 'ideal');

    // Configure & Run button
    const cfgBtn = $('#btn-configure-run');
    if (cfgBtn) {
      IC.bindAction(cfgBtn, async () => {
        await executeSimulation();
      });
    }

    // Execute button
    const execBtn = $('#btn-execute');
    if (execBtn) {
      IC.bindAction(execBtn, async () => {
        await executeSimulation();
      });
    }

    // Inert actions: Validate, New, Import, Export
    ['btn-validate', 'btn-import', 'btn-export'].forEach(id => {
      const el = $(`#${id}`);
      if (el) {
        IC.bindTap(el, () => {
          showToast(`${el.textContent.trim()} action is not available in fixture mode.`);
          announce(`${el.textContent.trim()} unavailable`);
        });
      }
    });

    // New button — resets session
    const newBtn = $('#btn-new');
    if (newBtn) {
      IC.bindTap(newBtn, () => {
        store.resetSession();
        showToast('Circuit reset to default Bell state.');
        announce('Circuit reset');
      });
    }
  }

  function updatePaletteVisuals() {
    const selected = store.getState().selectedGate;
    $$('.gate-btn[data-gate]').forEach(btn => {
      const gate = btn.getAttribute('data-gate');
      if (gate === selected) {
        btn.classList.add('ring-2', 'ring-terracotta-accent');
      } else {
        btn.classList.remove('ring-2', 'ring-terracotta-accent');
      }
    });
  }

  function updateInspector(gate, targets, desc) {
    const gateEl = $('#inspector-gate');
    const targetsEl = $('#inspector-targets');
    const descEl = $('#inspector-desc');
    if (gateEl) gateEl.textContent = gate;
    if (targetsEl) targetsEl.textContent = targets;
    if (descEl) descEl.textContent = desc || 'Standard quantum gate';
  }

  // ─── SIMULATION EXECUTION ───────────────────────────────
  async function executeSimulation() {
    const request = store.buildRequest();
    const reqId = request.request_id;
    const runId = request.run_id;

    // Navigate to pipeline
    nav.navigateTo('pipeline');

    // Update pipeline IDs
    const pReqId = $('#pipeline-req-id');
    const pRunId = $('#pipeline-run-id');
    if (pReqId) pReqId.textContent = reqId;
    if (pRunId) pRunId.textContent = runId;

    // Build pipeline phases
    buildPipelinePhases();
    updatePipelineLog(['Allocated quantum simulator core context.']);

    // Animate phases
    await animatePipeline(request);

    // Submit to adapter
    try {
      const response = await adapter.submit(request);

      if (!response) {
        // Stale response
        return;
      }

      if (response.status === 'error') {
        store.setState({ lastError: response.error, lastResponse: null });
        showToast(`Error: ${response.error.code}`);
        announce(`Simulation failed: ${response.error.message}`);
        completePipelineWithError(response.error);
        return;
      }

      // Replace fixture IDs with actual response IDs
      store.setState({
        lastResponse: response,
        lastError: null,
        request_id: response.request_id,
        run_id: response.run_id
      });

      // Complete pipeline
      completePipelineSuccess();

      // Populate result screen
      populateResult(response);

      // Auto-navigate to result after brief delay
      setTimeout(() => {
        nav.navigateTo('result');
        announce('Simulation completed. Viewing results.');
      }, 800);

    } catch (err) {
      store.setState({ lastError: { code: 'E_SERVICE_ERROR', message: err.message }, lastResponse: null });
      showToast('Simulation failed unexpectedly.');
      announce('Simulation failed unexpectedly');
      completePipelineWithError({ code: 'E_SERVICE_ERROR', message: err.message });
    }
  }

  // ─── PIPELINE UI ─────────────────────────────────────────
  function buildPipelinePhases() {
    const container = $('#pipeline-phases');
    if (!container) return;
    container.innerHTML = '';

    PIPELINE_PHASES.forEach((phase, i) => {
      const div = document.createElement('div');
      div.className = 'p-space-sm flex items-start justify-between gap-space-sm opacity-60';
      div.id = `phase-${i}`;
      div.innerHTML = `
        <div class="flex items-start gap-space-sm min-w-0">
          <div class="w-5 h-5 rounded-full bg-surface-container flex items-center justify-center shrink-0 mt-0.5" id="phase-icon-${i}">
            <span class="material-symbols-outlined text-[14px] text-ink-muted">hourglass_empty</span>
          </div>
          <div class="flex flex-col min-w-0">
            <span class="font-body-sm text-body-sm text-ink-muted font-medium truncate">${phase.label}</span>
            <span class="font-mono-md text-[11px] text-ink-muted">${phase.detail}</span>
          </div>
        </div>
        <div class="flex flex-col items-end shrink-0">
          <span class="font-mono-md text-[11px] text-ink-muted">--:--:--</span>
          <span class="font-label-badge text-[9px] uppercase tracking-wide text-ink-muted bg-surface-container px-1 rounded" id="phase-status-${i}">Waiting</span>
        </div>`;
      container.appendChild(div);
    });
  }

  async function animatePipeline(request) {
    const mode = request.mode;
    const totalPhases = mode === 'ideal' ? 9 : 10; // skip noise phase in ideal

    for (let i = 0; i < Math.min(6, totalPhases); i++) {
      await new Promise(r => setTimeout(r, 80));
      markPhaseComplete(i);
    }
    // Mark active phase
    const activeIdx = 6;
    markPhaseActive(activeIdx);
  }

  function markPhaseComplete(idx) {
    const phase = $(`#phase-${idx}`);
    const icon = $(`#phase-icon-${idx}`);
    const status = $(`#phase-status-${idx}`);
    if (!phase) return;
    phase.classList.remove('opacity-60');
    if (icon) icon.innerHTML = '<span class="material-symbols-outlined text-[14px] text-ink-primary font-bold">check</span>';
    if (icon) icon.className = 'w-5 h-5 rounded-full bg-surface-container-high flex items-center justify-center shrink-0 mt-0.5';
    if (status) { status.textContent = 'Done'; status.className = 'font-label-badge text-[9px] uppercase tracking-wide text-ink-secondary bg-surface-container px-1 rounded'; }
  }

  function markPhaseActive(idx) {
    const phase = $(`#phase-${idx}`);
    const icon = $(`#phase-icon-${idx}`);
    const status = $(`#phase-status-${idx}`);
    if (!phase) return;
    phase.classList.remove('opacity-60');
    phase.className = 'p-space-sm flex items-start justify-between gap-space-sm bg-surface-container-low transition-colors';
    if (icon) {
      icon.className = 'w-5 h-5 rounded-full bg-terracotta-accent flex items-center justify-center shrink-0 mt-0.5';
      icon.innerHTML = '<span class="relative flex h-2 w-2"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-paper-base opacity-75"></span><span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-paper-base"></span></span>';
    }
    if (status) {
      status.textContent = 'Active';
      status.className = 'font-label-badge text-[9px] uppercase tracking-wide text-paper-base bg-terracotta-accent px-1.5 py-0.5 rounded font-semibold';
    }
  }

  function completePipelineSuccess() {
    // Mark all phases complete
    for (let i = 0; i < PIPELINE_PHASES.length; i++) {
      markPhaseComplete(i);
    }
    const statusText = $('#pipeline-status-text');
    if (statusText) statusText.textContent = 'COMPLETED';
    const badge = $('#pipeline-status-badge');
    if (badge) {
      badge.innerHTML = '<span class="material-symbols-outlined text-[14px] text-ink-primary">check_circle</span><span class="font-mono-md text-mono-md text-ink-primary font-medium tracking-wide uppercase">COMPLETED</span>';
    }
  }

  function completePipelineWithError(error) {
    const statusText = $('#pipeline-status-text');
    if (statusText) statusText.textContent = 'FAILED';
    updatePipelineLog([`Error: ${error.code} — ${error.message}`]);
  }

  function updatePipelineLog(lines) {
    const log = $('#pipeline-log');
    if (!log) return;
    log.innerHTML = lines.map(line =>
      `<div class="flex items-start gap-2"><span class="text-ink-muted shrink-0 select-none">[--:--:--]</span><span class="text-surface-variant">${line}</span></div>`
    ).join('');
  }

  // ─── RESULT UI ───────────────────────────────────────────
  function populateResult(response) {
    if (!response || !response.result) return;
    const r = response.result;

    // IDs
    const runIdEl = $('#result-run-id');
    if (runIdEl) runIdEl.textContent = response.run_id;
    const pathEl = $('#result-path');
    if (pathEl) pathEl.textContent = `runs/${response.run_id}/`;

    // Seed
    const seedEl = $('#result-seed');
    if (seedEl) seedEl.textContent = `SEED: ${r.seed} (REPRODUCIBLE)`;

    // Mode
    const modeEl = $('#result-mode');
    if (modeEl) {
      modeEl.textContent = r.mode === 'noisy'
        ? 'Noisy · Depolarizing p=0.01 · Readout p=0.02'
        : 'Ideal · Pure Statevector';
    }

    // Shots
    const shotsEl = $('#result-shots');
    if (shotsEl) shotsEl.textContent = `${r.shots.toLocaleString()} Total`;
    const shotsBadge = $('#result-shots-badge');
    if (shotsBadge) shotsBadge.textContent = `N=${r.shots.toLocaleString()} SHOTS`;

    // Label
    const labelEl = $('#result-label');
    if (labelEl) labelEl.textContent = r.result_label || 'SIMULATION';

    // Probabilities
    renderProbabilities(r);

    // Histogram
    renderHistogram(r);
  }

  function renderProbabilities(r) {
    const container = $('#result-probabilities');
    if (!container || !r.probabilities) return;

    const numQubits = r.num_qubits;
    const numStates = Math.pow(2, numQubits);
    const states = [];
    for (let i = 0; i < numStates; i++) {
      const label = '|' + i.toString(2).padStart(numQubits, '0') + '⟩';
      const prob = r.probabilities[i] || 0;
      const countKey = i.toString(2).padStart(numQubits, '0');
      states.push({ label, prob, countKey });
    }

    let html = `<div class="flex items-center justify-between text-ink-muted font-mono-md text-[11px]">
      <span>STATE VECTOR |Ψ⟩</span>
      <span>Fixture Data</span></div><div class="flex flex-col gap-space-md">`;

    states.forEach(s => {
      const pct = (s.prob * 100).toFixed(1);
      const isLeakage = s.prob > 0 && s.prob < 0.1;
      html += `<div class="flex flex-col gap-1.5">
        <div class="flex items-baseline justify-between font-mono-md text-mono-md">
          <div class="flex items-center gap-2">
            <span class="font-semibold text-ink-primary">${s.label}</span>
            ${isLeakage ? '<span class="font-label-badge text-[9px] uppercase px-1.5 py-0.2 bg-error-container text-on-error-container rounded">Leakage</span>' : ''}
          </div>
          <span class="${isLeakage ? 'text-terracotta-accent' : 'text-ink-primary'} font-semibold">${s.prob.toFixed(4)}</span>
        </div>
        <div class="relative w-full h-3 bg-surface-container-highest rounded-full overflow-hidden">
          <div class="h-full ${isLeakage ? 'bg-terracotta-bright' : 'bg-ink-primary'} rounded-full transition-all duration-700" style="width: ${pct}%;"></div>
        </div>
      </div>`;
    });

    html += '</div>';
    container.innerHTML = html;
  }

  function renderHistogram(r) {
    const container = $('#result-histogram');
    if (!container || !r.counts) return;

    const numQubits = r.num_qubits;
    const totalShots = r.shots;
    const entries = [];
    const maxCount = Math.max(...Object.values(r.counts), 1);

    for (let i = 0; i < Math.pow(2, numQubits); i++) {
      const key = i.toString(2).padStart(numQubits, '0');
      const count = r.counts[key] || 0;
      entries.push({ label: `|${key}⟩`, count, key });
    }

    // Bar chart
    let html = `<div class="grid grid-cols-${entries.length} gap-2 items-end h-32 pt-space-md px-2 bg-surface-container-lowest rounded-lg">`;
    entries.forEach(e => {
      const heightPct = Math.max((e.count / maxCount) * 80, 2);
      const isNoise = e.count > 0 && e.count < totalShots * 0.05;
      html += `<div class="flex flex-col items-center gap-1.5 h-full justify-end">
        <span class="font-mono-md text-[10px] ${isNoise ? 'text-terracotta-bright' : 'text-ink-muted'}">${e.count}</span>
        <div class="w-full max-w-[42px] ${isNoise ? 'bg-secondary-container' : 'bg-ink-primary'} rounded-t-sm transition-all duration-500" style="height: ${heightPct}%;"></div>
        <span class="font-mono-md text-[11px] font-semibold text-ink-primary">${e.label}</span>
      </div>`;
    });
    html += '</div>';

    // Count grid
    html += `<div class="grid grid-cols-2 gap-space-sm pt-space-xs">`;
    entries.forEach(e => {
      const pct = ((e.count / totalShots) * 100).toFixed(1);
      const isNoise = e.count > 0 && e.count < totalShots * 0.05;
      html += `<div class="p-space-sm bg-surface-container-low rounded flex items-center justify-between">
        <span class="font-mono-md text-mono-md text-ink-primary font-medium">${e.label} ${isNoise ? 'Noise' : 'Basis'}</span>
        <div class="text-right">
          <span class="font-mono-md text-mono-md font-semibold ${isNoise ? 'text-terracotta-bright' : 'text-ink-primary'}">${e.count}</span>
          <span class="font-mono-md text-[11px] text-ink-muted ml-1">(${pct}%)</span>
        </div>
      </div>`;
    });
    html += '</div>';

    container.innerHTML = html;
  }

  // ─── RESULT BINDINGS ─────────────────────────────────────
  function initResult() {
    // ReRun button
    const rerunBtn = $('#btnReRun');
    if (rerunBtn) {
      IC.bindAction(rerunBtn, async () => {
        await executeSimulation();
      });
    }

    // Restore last result from state
    const state = store.getState();
    if (state.lastResponse) {
      populateResult(state.lastResponse);
    }
  }

  // ─── INIT ────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    // Initialize navigation
    nav.init();

    // Initialize all screens
    initOverview();
    initWorkspace();
    initResult();

    // Restore screen from state
    const savedScreen = store.getState().currentScreen;
    if (savedScreen && savedScreen !== 'overview') {
      nav.navigateTo(savedScreen);
    }

    // Subscribe to state changes for slots display
    store.subscribe((state) => {
      const slotsEl = $('#header-slots');
      if (slotsEl) {
        const active = adapter.activeCount();
        slotsEl.textContent = `SLOTS: ${active}/4`;
      }
    });

    console.log('[M5 Integration] Initialized successfully.');
  });
})();
