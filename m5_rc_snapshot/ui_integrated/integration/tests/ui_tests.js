/**
 * M5 UI Integration Tests
 * 
 * Verifies the connection between the visual UI and the integration layer.
 */

async function testUI(page) {
  const screens = [
    'm5_simulator_overview/code.html',
    'm5_circuit_workspace/code.html',
    'm5_simulation_pipeline/code.html',
    'm5_result_package/code.html'
  ];

  for (const screen of screens) {
    await page.goto(`file://ui_integrated/${screen}`);
    console.log(`Verified ${screen} loads correctly.`);
  }

  // Test Service Connection
  await page.goto(`file://ui_integrated/m5_circuit_workspace/code.html`);
  const response = await page.evaluate(async () => {
    const { adapter } = window.app;
    const req = {
      circuit: { operations: [{ gate: 'H', targets: [0] }, { gate: 'CNOT', targets: [0, 1] }] },
      mode: 'ideal',
      shots: 1000,
      seed: 42
    };
    return await adapter.submit(req);
  });

  if (response.status === 'completed') {
    console.log('Service connection verified: Valid response received.');
  } else {
    throw new Error('Service connection failed.');
  }
}
