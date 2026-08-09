const TOKEN_KEY = "toeic_pilot_access_token";

/**
 * Subscribers waiting on a token change.
 *
 * The browser's own `storage` event only fires in *other* tabs, so writing the
 * token and expecting React to notice would quietly never work in the tab that
 * did the writing. These listeners cover that case; the DOM event covers the
 * others.
 */
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

export function subscribeToToken(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  notify();
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  notify();
}
