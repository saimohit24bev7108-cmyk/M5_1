const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function run() {
  const browser = await chromium.launch({
    args: ['--allow-file-access-from-files']
  });

  const uiTestsCode = fs.readFileSync('ui_integrated/integration/tests/ui_tests.js', 'utf8');
  const visualRegressionCode = fs.readFileSync('ui_integrated/integration/tests/visual_regression.js', 'utf8');
  
  eval(uiTestsCode);
  eval(visualRegressionCode);

  console.log('--- Running UI Integration Tests ---');
  const contextUI = await browser.newContext();
  const pageUI = await contextUI.newPage();
  
  pageUI.on('pageerror', err => {
    console.error(`[Page Error] ${err.message}`);
  });

  try {
    const originalGoto = pageUI.goto.bind(pageUI);
    pageUI.goto = async (url) => {
      if (url.startsWith('file://ui_integrated/')) {
        const relativePath = url.replace('file://ui_integrated/', '');
        const absolutePath = `file://${path.resolve('ui_integrated', relativePath)}`;
        return originalGoto(absolutePath);
      }
      return originalGoto(url);
    };

    const screens = [
      'm5_simulator_scientific_overview/code.html',
      'm5_circuit_workspace_precision_lab/code.html',
      'm5_simulation_pipeline/code.html',
      'm5_result_package/code.html'
    ];

    for (const screen of screens) {
      await pageUI.goto(`file://ui_integrated/${screen}`);
      console.log(`Verified ${screen} loads correctly.`);
    }

    await pageUI.goto(`file://ui_integrated/m5_circuit_workspace_precision_lab/code.html`);
    
    await pageUI.waitForFunction(() => window.app !== undefined, { timeout: 5000 });

    const response = await pageUI.evaluate(async () => {
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
    console.log('UI Integration Tests: PASSED');
  } catch (e) {
    console.error('UI Integration Tests: FAILED');
    console.error(e);
  } finally {
    await contextUI.close();
  }

  console.log('\n--- Running Visual Regression Tests ---');
  const viewports = [
    { width: 390, height: 844 },
    { width: 430, height: 932 }
  ];

  const screens = [
    'm5_simulator_scientific_overview/code.html',
    'm5_circuit_workspace_precision_lab/code.html',
    'm5_result_package/code.html'
  ];

  try {
    for (const vp of viewports) {
      const contextVR = await browser.newContext({ 
        viewport: vp,
        args: ['--allow-file-access-from-files'] // Also needed here
      });
      const pageVR = await contextVR.newPage();
      
      for (const screen of screens) {
        const baselinePath = path.resolve('__stitch_temp__/stitch_m5_quantum_circuit_simulator', screen);
        const integratedPath = path.resolve('ui_integrated', screen);
        
        await runVisualRegression(pageVR, baselinePath, integratedPath);
      }
      await contextVR.close();
    }
    console.log('Visual Regression Tests: PASSED');
  } catch (e) {
    console.error('Visual Regression Tests: FAILED');
    console.error(e);
  }

  await browser.close();
}

run().catch(console.error);
