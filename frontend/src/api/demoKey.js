const DEMO_KEY_STORAGE = 'kroma_demo_key';

function isStorageAvailable() {
  try {
    return typeof window !== 'undefined' && typeof window.sessionStorage !== 'undefined' && window.sessionStorage !== null;
  } catch (e) {
    return false;
  }
}

/**
 * Retrieves the current demo key from sessionStorage.
 * @returns {string} The stored demo key or empty string.
 */
export function getDemoKey() {
  if (!isStorageAvailable()) {
    return '';
  }
  try {
    return sessionStorage.getItem(DEMO_KEY_STORAGE) || '';
  } catch (e) {
    return '';
  }
}

/**
 * Sets or removes the demo key in sessionStorage.
 * @param {string} value - The demo key string or a falsy value to remove it.
 */
export function setDemoKey(value) {
  if (!isStorageAvailable()) {
    return;
  }
  try {
    if (value) {
      sessionStorage.setItem(DEMO_KEY_STORAGE, value);
    } else {
      sessionStorage.removeItem(DEMO_KEY_STORAGE);
    }
  } catch (e) {
    // no-op on failure
  }
}

/**
 * Checks if a demo key exists in sessionStorage.
 * @returns {boolean} True if a demo key exists, false otherwise.
 */
export function hasDemoKey() {
  return Boolean(getDemoKey());
}
