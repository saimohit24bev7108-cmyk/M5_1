/**
 * M5 Navigation
 * Hash-based SPA routing. Shows/hides screen sections by data-screen attribute.
 * Updates bottom nav active states using existing ZIP CSS classes.
 *
 * Route mapping:
 *   #overview   → overview screen
 *   #workspace  → circuit workspace screen
 *   #pipeline   → simulation pipeline screen (runs tab)
 *   #result     → result package screen (runs tab)
 *   #analysis   → result screen (analysis tab, same view)
 *   #docs       → overview screen (docs tab, editorial content)
 *
 * Consistent semantic destinations per spec:
 *   "Overview"/"Overview"   → #overview
 *   "Workspace"/"Circuit"   → #workspace
 *   "Runs"/"Manifest"       → #result (default runs view)
 *   "Analysis"              → #result
 *   "Docs"                  → #overview
 */
const Navigation = (() => {
  const ROUTE_TO_SCREEN = {
    'overview': 'overview',
    'workspace': 'workspace',
    'pipeline': 'pipeline',
    'result': 'result',
    'runs': 'result',
    'analysis': 'result',
    'docs': 'overview'
  };

  const NAV_PATH_TO_ROUTE = {
    'overview': 'overview',
    'workspace': 'workspace',
    'circuit': 'workspace',
    'runs': 'result',
    'manifest': 'result',
    'analysis': 'result',
    'docs': 'overview'
  };

  let _initialized = false;

  function init() {
    if (_initialized) return;
    _initialized = true;

    window.addEventListener('hashchange', () => {
      _applyRoute();
    });

    // Bind nav links
    document.querySelectorAll('nav a[data-path]').forEach(link => {
      const path = link.getAttribute('data-path');
      const route = NAV_PATH_TO_ROUTE[path] || path;

      window.M5Interaction.bindTap(link, (e) => {
        e.preventDefault();
        navigateTo(route);
      });

      // Accessibility
      const dest = path.charAt(0).toUpperCase() + path.slice(1);
      link.setAttribute('aria-label', `Navigate to ${dest}`);
    });

    // Apply initial route
    _applyRoute();
  }

  function navigateTo(route) {
    window.location.hash = route;
    // hashchange listener will call _applyRoute()
  }

  function _applyRoute() {
    const hash = window.location.hash.replace('#', '') || 'overview';
    const screenId = ROUTE_TO_SCREEN[hash] || 'overview';

    // Update store
    if (window.M5Store) {
      window.M5Store.setState({ currentScreen: screenId });
    }

    // Show/hide screens
    document.querySelectorAll('[data-screen]').forEach(section => {
      if (section.getAttribute('data-screen') === screenId) {
        section.style.display = '';
        section.removeAttribute('aria-hidden');
      } else {
        section.style.display = 'none';
        section.setAttribute('aria-hidden', 'true');
      }
    });

    // Update nav active states
    const navLinks = document.querySelectorAll('nav a[data-path]');
    navLinks.forEach(link => {
      const linkPath = link.getAttribute('data-path');
      const linkRoute = NAV_PATH_TO_ROUTE[linkPath] || linkPath;
      const isActive = linkRoute === screenId ||
        (hash === 'pipeline' && linkPath === 'runs');

      if (isActive) {
        link.classList.add('text-ink-primary', 'font-medium');
        link.classList.remove('text-ink-muted');
        link.setAttribute('aria-current', 'page');
      } else {
        link.classList.remove('text-ink-primary', 'font-medium');
        link.classList.add('text-ink-muted');
        link.removeAttribute('aria-current');
      }
    });

    // Scroll to top on navigation
    window.scrollTo(0, 0);
  }

  function getCurrentRoute() {
    return window.location.hash.replace('#', '') || 'overview';
  }

  return { init, navigateTo, getCurrentRoute };
})();

window.M5Nav = Navigation;
