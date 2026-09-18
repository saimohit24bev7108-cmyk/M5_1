export class Navigation {
  constructor(store) {
    this.store = store;
  }

  navigateTo(path) {
    console.log(`[Navigation] Navigating to: ${path}`);
    this.store.setState({ currentScreen: path });
    
    // In a real app, this would handle window.location or a router.
    // For this integrated local version, we can just update the UI.
    window.dispatchEvent(new CustomEvent('app-navigate', { detail: { path } }));
  }
}
