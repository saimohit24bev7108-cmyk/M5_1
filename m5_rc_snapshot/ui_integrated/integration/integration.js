import { ServiceAdapter } from './service-adapter.js';
import { StateStore } from './state-store.js';
import { Navigation } from './navigation.js';

const store = new StateStore();
const adapter = new ServiceAdapter();
const nav = new Navigation(store);

window.app = { store, adapter, nav };

export default { store, adapter, nav };

// Initialize UI bindings
document.addEventListener('DOMContentLoaded', () => {
  console.log('[Integration] Initializing M5 UI Integration...');
  
  // Bind bottom navigation
  const navLinks = document.querySelectorAll('nav a');
  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const path = link.getAttribute('data-path');
      nav.navigateTo(path);
    });
  });

  // Bind navigation state to UI
  window.addEventListener('app-navigate', (e) => {
    const path = e.detail.path;
    navLinks.forEach(link => {
      if (link.getAttribute('data-path') === path) {
        link.classList.add('text-ink-primary', 'font-medium');
        link.classList.remove('text-ink-muted');
        link.setAttribute('aria-current', 'page');
      } else {
        link.classList.remove('text-ink-primary', 'font-medium');
        link.classList.add('text-ink-muted');
        link.removeAttribute('aria-current');
      }
    });
    
    // Redirect to actual file for this simple integration
    const screenMap = {
      'overview': 'm5_simulator_overview/code.html',
      'workspace': 'm5_circuit_workspace/code.html',
      'runs': 'm5_result_package/code.html',
      'analysis': 'm5_result_package/code.html', // Fallback
      'docs': 'm5_simulator_overview/code.html' // Fallback
    };
    
    if (screenMap[path]) {
      window.location.href = screenMap[path];
    }
  });
});
