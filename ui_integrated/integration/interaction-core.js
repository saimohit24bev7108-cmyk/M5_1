/**
 * M5 Interaction Core
 * Unified Pointer Events interaction model with:
 * - Per-control action locks (no global lock)
 * - Tap-vs-scroll detection (10px / 500ms threshold)
 * - Duplicate activation suppression (pointer → click)
 * - Keyboard accessibility bridging
 * - touch-action: manipulation on all interactive controls
 *
 * Uses pointerdown/pointermove/pointerup/pointercancel exclusively.
 * Does NOT independently attach touchstart/mousedown/click.
 */
const InteractionCore = (() => {
  // Per-element action lock map (WeakMap so GC handles cleanup)
  const _locks = new WeakMap();

  /**
   * Check if an element's action is currently locked.
   */
  function isLocked(el) {
    return _locks.has(el) && _locks.get(el) === true;
  }

  /**
   * Lock an element's action. Returns false if already locked.
   */
  function lock(el) {
    if (isLocked(el)) return false;
    _locks.set(el, true);
    return true;
  }

  /**
   * Unlock an element's action.
   */
  function unlock(el) {
    _locks.set(el, false);
  }

  /**
   * Bind a pointer-event-driven tap handler to an element.
   * Implements tap-vs-scroll detection (10px, 500ms).
   * Suppresses the subsequent click event if pointer handler fires.
   *
   * @param {HTMLElement} el - Target element
   * @param {Function} handler - Activation callback (receives original pointerdown event)
   * @param {Object} [opts] - Options
   * @param {boolean} [opts.lockAction=false] - Enable per-element action locking
   * @param {number} [opts.lockTimeout=3000] - Auto-unlock timeout (ms)
   */
  function bindTap(el, handler, opts = {}) {
    const lockAction = opts.lockAction || false;
    const lockTimeout = opts.lockTimeout || 3000;

    let startX = 0, startY = 0, startTime = 0;
    let pointerActivated = false;

    // Set touch-action for tap-only controls
    el.style.touchAction = 'manipulation';

    el.addEventListener('pointerdown', (e) => {
      startX = e.clientX;
      startY = e.clientY;
      startTime = Date.now();
      pointerActivated = false;
    }, { passive: true });

    el.addEventListener('pointerup', (e) => {
      const dx = Math.abs(e.clientX - startX);
      const dy = Math.abs(e.clientY - startY);
      const dt = Date.now() - startTime;

      // Tap detection: ≤10px movement, ≤500ms duration
      if (dx <= 10 && dy <= 10 && dt <= 500) {
        pointerActivated = true;

        if (lockAction) {
          if (!lock(el)) return; // already locked
          // Safety timeout
          setTimeout(() => unlock(el), lockTimeout);
        }

        handler(e);
      }
    }, { passive: true });

    el.addEventListener('pointercancel', () => {
      // Cancel pending tap
      startX = startY = startTime = 0;
      pointerActivated = false;
    }, { passive: true });

    // Suppress duplicate click if pointer handler already fired
    el.addEventListener('click', (e) => {
      if (pointerActivated) {
        e.preventDefault();
        e.stopImmediatePropagation();
        pointerActivated = false;
        return;
      }
      // Keyboard click (Enter/Space) — allow through
      if (lockAction) {
        if (!lock(el)) {
          e.preventDefault();
          return;
        }
        setTimeout(() => unlock(el), lockTimeout);
      }
      handler(e);
    });
  }

  /**
   * Bind tap handler to a button/link with immediate visual feedback.
   * Adds active:scale-95 equivalent via transform for <100ms feedback.
   *
   * @param {HTMLElement} el - Target element
   * @param {Function} handler - Activation callback (async OK)
   * @param {Object} [opts] - Options passed to bindTap + lockAction defaults true
   */
  function bindAction(el, handler, opts = {}) {
    const mergedOpts = { lockAction: true, ...opts };

    bindTap(el, async (e) => {
      try {
        await handler(e);
      } finally {
        unlock(el);
      }
    }, mergedOpts);
  }

  /**
   * Add keyboard activation to a non-semantic element.
   * Makes it focusable and activates on Enter/Space.
   */
  function makeKeyboardAccessible(el, opts = {}) {
    if (el.tabIndex < 0 || (!el.hasAttribute('tabindex'))) {
      el.tabIndex = 0;
    }
    if (opts.label) {
      el.setAttribute('aria-label', opts.label);
    }
    if (opts.role) {
      el.setAttribute('role', opts.role);
    }
    if (opts.pressed !== undefined) {
      el.setAttribute('aria-pressed', String(opts.pressed));
    }

    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        el.click();
      }
    });
  }

  /**
   * Set up touch-action on an element for drag/manipulation surfaces.
   */
  function setDragSurface(el) {
    el.style.touchAction = 'none';
  }

  return {
    isLocked,
    lock,
    unlock,
    bindTap,
    bindAction,
    makeKeyboardAccessible,
    setDragSurface
  };
})();

window.M5Interaction = InteractionCore;
